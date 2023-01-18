# Monitor Arlo Security Cameras, Download Video and Get Notifications

This tool connects to Arlo cameras and displays their images. It allows you to update
a camera image with a snapshot or a live video stream. It also downloads all
video from the Arlo cloud. Low battery and motion detection notifications are
displayed on the computer.

## Camera Images

The GUI looks like this for a two-camera Arlo installation:

![GUI](/images/gui.png)

Left-clicking on a camera image updates it with a snapshot; right-clicking displays
a live video stream. The video stream ends when either the left or the right
mouse button is clicked.

## Downloads

All videos in the cloud from up to 30 days old will be downloaded to the local
`Videos/Arlo` directory.

## Notifications

Notifications are sent when a camera's battery is low or when motion is detected
by any of the cameras. The motion detection notification initially looks like
this:

![Notification 1](/images/notification1.png)

The initial notification alerts tlert notifies you the time and camera where the motion was
detected. After video for that motion event becomes available in the cloud,
the alert is updated to look like this:

![Notification 2](/images/notification2.png)

The updated notification includes a link to the video, which can be played or
downloaded. It will also automatically be downloaded to the `Videos/Arlo` directory.

The notifications above were seen on Kubuntu. They look slightly different on other
systems. On Windows, the second notification does not contain web links. Instead it
lists the filename of the video.

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

This code needs Python 3.7 or later. It relies on the package
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
