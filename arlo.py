#!/usr/bin/env python3

import datetime, io, math, os, pickle, queue, sys, threading, tkinter
from tkinter import simpledialog
from dataclasses import dataclass
from urllib.parse import urljoin
from urllib.request import pathname2url

import cv2 # install with "pip install opencv-python"; on Ubuntu install with "sudo apt install -y python3-opencv"
from PIL import Image, ImageTk # install with "pip install Pillow"; on Ubuntu install with "sudo apt install -y python3-pil python3-pil.imagetk"

import pyaarlo # install with "pip install git+https://github.com/twrecked/pyaarlo"

from pyaarlo.constant import (TFA_SMS_TYPE, TFA_EMAIL_TYPE,
                              LAST_IMAGE_DATA_KEY, MOTION_DETECTED_KEY)

#
# pyaarlo saves session in BASE_DIRECTORY.
#
if sys.platform == 'win32':
    BASE_DIRECTORY = os.path.expanduser('~/AppData/Local/Pyaarlo')
else:
    BASE_DIRECTORY = os.path.expanduser('~/.cache/pyaarlo')

if 'win' in sys.platform:
    VIDEO_FILENAME_FORMAT = '${Y}-${m}-${d} ${t} ${N}' # avoid ':' in filenames
else:
    VIDEO_FILENAME_FORMAT = '${Y}-${m}-${d} ${T} ${N}' # ':' is just fine

# After motion detection videos for this event are located. Html to play and
# download these videos are written to in VIDEO_DIRECTORY. They will be cleaned
# up after HTML_EXPIRATION seconds.
VIDEO_DIRECTORY = os.path.expanduser('~/Videos/Arlo')
HTML_EXPIRATION = 3 * 24 * 3600  # 3 days in seconds

if not os.path.exists(VIDEO_DIRECTORY):
    os.makedirs(VIDEO_DIRECTORY)

#
# Platform-specific Notifications.
#
@dataclass
class Notification:
    id               : object
    notification     : str
    notification_body: str

if sys.platform == "linux":
    import dbus # install with "pip3 install dbus-python"; on Ubuntu install with "sudo apt install -y python3-dbus"

    notify_itm = "org.freedesktop.Notifications"
    notify_if  = dbus.Interface(dbus.SessionBus().
                                get_object(notify_itm,
                                           f"/{notify_itm.replace('.', '/')}"),
                                notify_itm)

    def notify(notification:str, notification_body:str) -> Notification:
        return Notification(notify_if.Notify(os.path.split(sys.argv[0])[1], 0,
                                             "", notification,
                                             notification_body, [],
                                             {"urgency": 1}, 0),
                            notification, notification_body)

    def update_notification(notification: Notification) -> None:
        notify_if.Notify(os.path.split(sys.argv[0])[1],
                         notification.id, "", notification.notification,
                         notification.notification_body, [],
                         {"urgency": 1}, 0)

    notification_supports_html = True

elif sys.platform == "win32":
    import win10toast # install with "pip install win10toast"

    toaster = win10toast.ToastNotifier()

    def notify(notification:str, notification_body:str) -> Notification:
        while toaster.notification_active():
            time.sleep(1.0)
        toaster.show_toast(notification, notification_body,
                           duration=60, threaded=True)
        return Notification(None, notification, notification_body)

    def update_notification(notification: Notification) -> None:
        while toaster.notification_active():
            time.sleep(1.0)
        toaster.show_toast(notification.notification,
                           notification.notification_body,
                           duration=60, threaded=True)

    notification_supports_html = False

else:

    def notify(notification:str, notification_body:str) -> Notification:
        print()
        print(notification)
        print('=' * len(notification))
        print(notification_body)
        print()
        return Notification(None, notification, notification_body)

    def update_notification(notification: Notification) -> None:
        print()
        print(notification.notification)
        print('=' * len(notification.notification))
        print(notification.notification_body)
        print()

    notification_supports_html = False

# Write HTML to play and download given video, return url and file name.
def write_video_html(video: pyaarlo.media.ArloVideo) -> str:
    video_file_name = video._arlo.ml._downloader._output_name(video)
    base_file_name  = os.path.split(video_file_name)[1][:-4]
    video_url  = video.video_url
    html_path = video_file_name[:-4] + '.html'
    if notification_supports_html:
        with open(html_path, 'wt') as f:
            print(f'''<html>
<title>{base_file_name}</title>
<h2>{base_file_name}</h2>
<video controls width="1024">
<source src="{video_url}" type="video/mp4">
</video>
<br><br><br>
Download video <a href="{video_url}" download="{base_file_name}.mp4">
{base_file_name}</a>.
</html>''', file=f)
        file_url = urljoin('file:', pathname2url(html_path))
    else:
        file_url = None
    return file_url, base_file_name

# Delete all expired .html files in VIDEO_DIRECTORY.
def expire_video_htmls() -> None:
    if not notification_supports_html:
        return
    now = datetime.datetime.now().timestamp()
    for filename in os.listdir(VIDEO_DIRECTORY):
        if not filename.endswith('.html'):
            continue
        full_path = os.path.join(VIDEO_DIRECTORY, filename)
        if now - os.path.getmtime(full_path) > HTML_EXPIRATION:
            try:
                os.remove(full_path)
            except:
                pass

#
# GUI Dialog for Arlo Credentials.
#
class ArloCredentials:

    def __init__(self, username, password, tfa: str):
        if username is None:
            username = self.username_from_session()
        self.result = (None, None, None)
        self.win = tkinter.Tk()
        self.win.title('Arlo Credentials')
        uname_label = tkinter.Label(self.win, text='Arlo Username: ')
        uname_label.grid(column=0, row=0, sticky=tkinter.W)
        pwd_label = tkinter.Label(self.win, text='Arlo Password: ')
        pwd_label.grid(column=0, row=1, sticky=tkinter.W)
        tfa_label = tkinter.Label(self.win, text='Second Factor: ')
        tfa_label.grid(column=0, row=2, sticky=tkinter.W)
        self.uname_entry = tkinter.Entry(self.win)
        self.uname_entry.grid(column=1, row=0, pady=2)
        self.uname_entry.focus_set()
        self.pwd_entry = tkinter.Entry(self.win, show='*')
        self.pwd_entry.grid(column=1, row=1, pady=2)
        if username is not None:
            self.uname_entry.insert(0, username)
            self.pwd_entry.focus_set()
        if password is not None:
            self.pwd_entry.insert(0, password)
        self.uname_entry.bind('<Return>', lambda x:self.pwd_entry.focus_set())
        self.pwd_entry.bind('<Return>', lambda x:self.ok())
        self.tfa = tkinter.IntVar()
        self.tfa.set(2 if tfa == TFA_SMS_TYPE else 1)
        tfa_frame = tkinter.Frame(self.win)
        tfa_frame.grid(column=1, row=2, pady=2)
        email = tkinter.Radiobutton(tfa_frame, text="E-Mail",
                                    variable=self.tfa, value=1)
        email.grid(column=0, row=0)
        sms = tkinter.Radiobutton(tfa_frame, text="SMS (Text)",
                                  variable=self.tfa, value=2)
        sms.grid(column=1, row=0)
        ok_button = tkinter.Button(self.win, text='OK', command=self.ok)
        ok_button.grid(column=0, row=3, columnspan=2, pady=5)
        self.win.mainloop()

    def ok(self):
        self.result = self.uname_entry.get().strip(), \
                      self.pwd_entry.get().strip(), \
                      TFA_SMS_TYPE if self.tfa.get() == 2 else TFA_EMAIL_TYPE
        self.win.destroy()

    @property
    def credentials(self):
        return self.result

    # Try to find username in saved session; return username or None.
    def username_from_session(self):
        session = os.path.join(BASE_DIRECTORY, 'session.pickle')
        if os.path.exists(session):
            with open(session, 'rb') as f:
                config = pickle.load(f)
            if config.get('version') == '2':
                for key in config:
                    if key != 'version':
                        return key
        return None

#
# An instance of class Camera represents an Arlo camera.
#
class Camera:

    VIDEO_UPDATE_INTERVAL   =     25  # try updating video frame every 25 msecs
    BATTERY_UPDATE_INTERVAL = 900000  # update battery level every 15 minutes
    VIDEO_STREAM_FORMAT     =  'arlo' # request rtsps stream
    LOW_BATTERY_THRESHOLD   =     15  # warn when battery level drops below this
    MEDIA_UPDATE_INTERVAL   =  90000  # check every 90 seconds for motion video

    def __init__(self, camera, frame, image_size):
        self.camera = camera
        self.frame = frame
        self.image_size = image_size
        self.name = camera.name
        self.model = camera.model_id
        self.frame.configure(text=self.name, labelanchor='n')
        # self.label has camera image.
        self.label = tkinter.Label(self.frame)
        self.label.grid(column=0, row=0, sticky=tkinter.W)
        # self.status_line is shown below camera image.
        self.low_battery_warned = False
        self.addl_status_text = ''
        self.status_line = tkinter.Label(self.frame)
        self.status_line.grid(column=0, row=1, sticky=tkinter.W)
        self.snapshot_requested = False
        # Load camera image.
        self.lastImageData(self.camera, LAST_IMAGE_DATA_KEY,
                           self.camera.last_image_from_cache)
        self.updateBatteryLevel()
        # Members for live video stream.
        self.live_stream = 'off' # values: 'on', 'off', 'init', 'error'
        self.thread = None
        self.video_frame_queue = queue.SimpleQueue()
        # Motion detection.
        self.motion_notices = []
        camera.add_attr_callback(MOTION_DETECTED_KEY, self.motionDetected)
        # Snapshot callback.
        camera.add_attr_callback(LAST_IMAGE_DATA_KEY, self.lastImageData)
        # Left and right mouse buttons callback.
        self.label.bind("<Button-1>", self.buttonPressed)
        self.label.bind("<Button-3>", self.buttonPressed)

    # Update battery level; called every 15 minutes.
    def updateBatteryLevel(self):
        self.battery_level = self.camera.battery_level
        self.updateStatus(self.addl_status_text)
        if self.battery_level < self.LOW_BATTERY_THRESHOLD and \
           not self.low_battery_warned:
            notify("Arlo camera battery is low.", f"Camera {self.name} "
                   f"has only {self.battery_level}% battery left.")
            self.low_battery_warned = True
        self.status_line.after(self.BATTERY_UPDATE_INTERVAL,
                               self.updateBatteryLevel)

    # Update status line.
    def updateStatus(self, addl = ''):
        self.addl_status_text = addl
        status_text = f"Camera model {self.model}, battery level "\
                      f"{self.battery_level}%{addl}"
        self.status_line.configure(text=status_text)

    # Turn live stream off so streamThread shuts down.
    def shutdown(self):
        if self.live_stream != 'off':
            self.stopStream()

    # Resize image to fit within self.image_size; maintain aspect ratio.
    def resize(self, image):
        factor = min(self.image_size[0] / image.width,
                     self.image_size[1] / image.height)
        return image.resize((int(image.width * factor),
                             int(image.height * factor)))

    # Update still image; called on LAST_IMAGE_DATA_KEY event.
    def lastImageData(self, device, attr, value):
        with io.BytesIO(value) as file:
            image = Image.open(file)
            image.load()
        self.image = ImageTk.PhotoImage(image=self.resize(image))
        self.label.configure(image=self.image)
        if self.snapshot_requested:
            self.snapshot_requested = False
            self.updateStatus()

    # Called on motionDetected event. Sends notification to session.
    def motionDetected(self, device, attr, value):
        if value:
            now = datetime.datetime.now()
            time_string = now.strftime('%m-%d %H:%M:%S')
            notification = notify("Motion detected.", "Motion detected on "
                                  f"{time_string} at {self.name}.")
            self.motion_notices.append((now, notification))
            self.frame.after(self.MEDIA_UPDATE_INTERVAL,
                             self.findMotionVideos)

    # This function is called after a motion was detected. It waits for the
    # video that shows that motion and extends the notification with a link to
    # this video.
    def findMotionVideos(self):
        self.camera._arlo.ml.update()
        self.camera.update_media(wait=True)
        videos = self.camera.last_n_videos(25)
        now = datetime.datetime.now().timestamp()
        for video in videos:
            video_time = video.created_at / 1000
            new_motion_notices = []
            for time, notification in self.motion_notices:
                if abs(time.timestamp() - video_time) < 5.0:
                    file_url, file_name = write_video_html(video)
                    if notification_supports_html:
                        notification.notification_body += \
                            f'<br><a href="{file_url}">Play</a> or <a href='\
                            f'"{video.video_url}" download="{file_name}.mp4">'\
                             'download</a> video.'
                    else:
                        notification.notification_body += '\r\nVideo '\
                            f"'{file_name}' is available for this motion event."
                    update_notification(notification)
                elif now - time.timestamp() < 3600: # give up after an hour
                    new_motion_notices.append((time, notification))
            self.motion_notices = new_motion_notices
            if not self.motion_notices:
                break
        if self.motion_notices: # update videos and try again
            self.frame.after(self.MEDIA_UPDATE_INTERVAL, self.findMotionVideos)

    # This function is called when the left or right mouse button is pressed in
    # an image. The left mouse button updates the image with a snapshot; the
    # right one starts a video stream. Either button stops a video stream.
    def buttonPressed(self, e):
        if self.live_stream != 'off': # either mouse button stops video stream
            self.stopStream()
            self.updateStatus()
        elif e.num == 1: # left mouse button takes snapshot
            self.snapshot_requested = True
            self.updateStatus("   snapshot requested")
            self.camera.request_snapshot()
        elif e.num == 3: # right mouse button starts video stream
            if self.live_stream == 'off':
                url = self.camera.start_stream(self.VIDEO_STREAM_FORMAT)
                if isinstance(url, str) and url.startswith('rtsps://'):
                    self.live_stream = 'init'
                    self.thread = threading.Thread(target=self.streamThread,
                                                   args=[url])
                    self.thread.start()
                    self.label.after(self.VIDEO_UPDATE_INTERVAL,
                                     self.updateVideoFrame)
                    self.updateStatus("   waiting for video stream")

    # Helper function for video streaming. Runs in a thread that receives
    # the video stream and appends video frames to the frame queue.
    def streamThread(self, url):
        cap = cv2.VideoCapture(url)
        while cap.isOpened():
            retval, video_frame = cap.read()
            if not retval or self.live_stream == 'off':
                break
            video_frame = video_frame[:,:,::-1] # color mode BGR -> RGB
            image = self.resize(Image.fromarray(video_frame))
            self.video_frame_queue.put(image)
        if self.live_stream != 'off':
            self.live_stream = 'error'
        cap.release()

    # Stop video stream and wait for thread to exit.
    def stopStream(self):
        assert self.live_stream != 'off'
        self.live_stream = 'off'
        self.camera.stop_stream()
        self.thread.join()
        self.thread = None

    # Helper function for video streaming. This function is called every
    # VIDEO_UPDATE_INTERVAL msecs; it checks the frame queue for frames
    # and displays the most recent one.
    def updateVideoFrame(self):
        if not self.video_frame_queue.empty():
            if self.live_stream == 'init':
                self.updateStatus("   video stream")
                self.live_stream = 'on'
            while not self.video_frame_queue.empty():
                video_frame = self.video_frame_queue.get()
            self.image = ImageTk.PhotoImage(image=video_frame)
            self.label.configure(image=self.image)
        if self.live_stream == 'error':
            self.stopStream()
            self.updateStatus()
        elif self.live_stream != 'off':
            self.label.after(self.VIDEO_UPDATE_INTERVAL, self.updateVideoFrame)

#
# Main GUI class.
#
class ArloWindow:

    UPDATE_MEDIA_LIBRARY = 900000 # update media library every 15 minutes

    def __init__(self, **args):

        # By default use GUI to ask user 6-digit TFA code.
        if 'tfa_source' not in args:
            args['tfa_source'] = TFAgetCode()

        # Store configuration under ~/.cache/pyaarlo.
        if 'storage_dir' not in args:
            args['storage_dir'] = BASE_DIRECTORY

        # Download media to local directory.
        if 'save_media_to' not in args:
            args['save_media_to'] = os.path.join(VIDEO_DIRECTORY,
                                                 VIDEO_FILENAME_FORMAT)

        # Delete html for expired videos.
        expire_video_htmls()

        print('Connecting to Arlo cloud...')
        self.arlo = pyaarlo.PyArlo(**args)
        if self.arlo.is_connected:
            print('Connected.')

            self.window = tkinter.Tk()
            self.window.title("Arlo Camera Viewer")

            # Menu bar.
            self.menubar = tkinter.Menu(self.window)

            # File menu
            self.filemenu = tkinter.Menu(self.menubar, tearoff=0)
            self.filemenu.add_command(label="Exit", command=self.window.destroy)
            self.menubar.add_cascade(label="File", menu=self.filemenu)

            # Add menu bar.
            self.window.config(menu=self.menubar)

            # Compute number of rows and columns for window of camera images.
            no_columns = int(math.ceil(math.sqrt(len(self.arlo.cameras))))
            no_rows    = int(math.ceil(len(self.arlo.cameras) / no_columns))

            # These sizes are upper limits since we also maintain aspect ratios.
            width  = int(0.85 * self.window.winfo_screenwidth() / no_columns)
            height = int(0.85 * self.window.winfo_screenheight() / no_rows)
            image_size = (width, height)

            # Add a LabelFrame to window for each camera.
            camera_list = []
            for i, camera in enumerate(self.arlo.cameras):
                frame = tkinter.LabelFrame(self.window)
                camera_list.append(Camera(camera, frame, image_size))
                frame.grid(column=i%no_columns, row=i//no_columns,
                           padx=5, pady=5)

            # We do not re-scale images properly on resize event; disable.
            self.window.resizable(False, False)

            # Periodically update media library.
            self.window.after(2 * self.UPDATE_MEDIA_LIBRARY,
                              self.updateMediaLibrary)

            # Enter main loop.
            self.window.mainloop()

            # Exit video streams for clean shutdown.
            for camera in camera_list:
                camera.shutdown()
        else:
            print(f"Connection failed; {self.arlo.last_error}.")

    # Update media library; called periodically to learn about new videos
    # and download them, e.g. after motion detection.
    def updateMediaLibrary(self):
        self.arlo.ml.update()
        for camera in self.arlo.cameras:
            camera.update_media(wait=False)
        self.window.after(self.UPDATE_MEDIA_LIBRARY, self.updateMediaLibrary)


# Helper class that redirects TFA query to GUI.
class TFAgetCode:

    def __init__(self):
        pass

    def start(self) -> bool:
        return True

    # Function to ask TFA code that user receives in text messsage or e-mail.
    def get(self) -> str:
        win = tkinter.Tk()
        win.withdraw()
        tfa_code = simpledialog.askstring('Security Code', 'Enter code',
                                          parent=win)
        while tfa_code is not None and \
              (len(tfa_code) != 6 or not tfa_code.isdigit()):
            tfa_code = simpledialog.askstring('Security Code',
                f"Invalid code '{TFA_code}'. Enter 6-digit verification code",
                                              parent=win)
        win.destroy()
        return tfa_code

    def stop(self) -> None:
        pass

if __name__ == '__main__':
    import argparse, logging

    def tfaCheck(arg: str) -> str:
        if arg.upper() in [TFA_EMAIL_TYPE, TFA_SMS_TYPE]:
            return arg.upper()
        raise argparse.ArgumentTypeError(f"'{arg}' is not a supported 2-factor-"
                                         "authorization method; supported: "
                                    f"'{TFA_EMAIL_TYPE}' and '{TFA_SMS_TYPE}'.")

    parser = argparse.ArgumentParser()
    parser.add_argument('--username', '-u',
                        help='Arlo username (usually e-mail address).')
    parser.add_argument('--password', '-p', help='Arlo password.')
    parser.add_argument('--tfa', '-t', type=tfaCheck, default=TFA_EMAIL_TYPE,
                        help="Method for two-factor-authorization, either "
                        "e-mail or text message, supported values "
                        f"'{TFA_EMAIL_TYPE}' and '{TFA_SMS_TYPE}'; "
                        f"default '{TFA_EMAIL_TYPE}'.")
    parser.add_argument('--debug', '-d', action="store_true",
                        help='Enable pyaarlo debug messages.')
    args = parser.parse_args()

    if args.username is None or args.password is None:
        # Missing user name or password; invoke GUI to ask credentials.
        args.username, args.password, args.tfa = \
            ArloCredentials(args.username, args.password, args.tfa).credentials

        if args.username is None:
            # ArloCredentials window closed w/o "ok" click.
            sys.exit(0)

    if args.debug:
        logging.basicConfig(level=logging.DEBUG,
                 format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        _LOGGER = logging.getLogger('pyaarlo')

    ArloWindow(username=args.username, password=args.password,
               verbose_debug=args.debug,
               tfa_type=args.tfa)
