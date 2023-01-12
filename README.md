# Monitor Arlo Security Cameras, download Videos and get Notifications

This tool connects to Arlo cameras and shows their images. It allows to update
a camera image with a snapshot or a live video stream. It also downloads all
videos from the Arlo cloud. Notifications for low battery and motion detection
are shown on the computer.

## Camera Images

The GUI looks like this for an Arlo installation with two cameras:

![GUI](/images/gui.png)

A left-click on a camera images updates it with a snapshot; a right-click shows
a live video stream. The video stream stops when either the left or the right
mouse button is clicked.

## Downloads

All videos in the cloud from up to 30 days ago are downloaded to local
directory `Videos/Arlo`.

## Notifications

Notifications are sent when a camera battery is low or when motion is detected
by any of the cameras. The motion detection notification looks initially like
this:

![Notification 1](/images/notification1.png)

The initial notification alerts to the time and camera where the motion was
detected. After a video for that motion event becomes available in the cloud,
the notification is updated to look like this:

![Notification 2](/images/notification2.png)

The updated notification contains a link to the video; it can be played or
downloaded. It will also automatically be downloaded to directory `Videos/Arlo`.

The above notifications were seen on Kubuntu. They look slightly different on other
systems. On Windows, the second notification does not include web links. It
lists the file name of the video instead.

## Usage

Several command-line parameters are supported. The user name and password can
be given there and the method for two-factor authorization can be selected.

```
usage: arlo.py [-h] [--username USERNAME] [--password PASSWORD] [--tfa TFA]

options:
  -h, --help            show this help message and exit
  --username USERNAME, -u USERNAME
                        Arlo username (usually e-mail address).
  --password PASSWORD, -p PASSWORD
                        Arlo password.
  --tfa TFA, -t TFA     Method for two-factor-authorization, either e-mail or text message, supported values 'EMAIL' and 'SMS'; default 'EMAIL'.
```
All these parameters are optional. A GUI dialog opens when they are not given.

## Dependencies

This code needs Python 3.7 or later. It relies on package
[pyaarlo](https://github.com/twrecked/pyaarlo) to communicate with the
Arlo cloud.

On Ubuntu Linux, all dependencies can be met with:

```
sudo apt install -y python3-opencv python3-tk python3-pil python3-pil.imagetk python3-dbus
pip3 install git+https://github.com/twrecked/pyaarlo
```

On other platforms `pip` installs the packages:

```
pip install opencv-python Pillow
pip install git+https://github.com/twrecked/pyaarlo
```

On Windows package `win10toast` is used to send notifications. It can be
installed with

```
pip install win10toast
```

On Linux notifications are sent to the dbus.
