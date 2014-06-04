Record
======

:ref:`help_record`, :ref:`help`

Direct Show Camera Options
--------------------------

Config key: idshow_opt

The current direct show options for the
current direct show selected camera. Defaults to `''`.

Output Directory
----------------

Config key: odir

The directory where the output file will be saved. Defaults to `''`.
This is just the directory name, not the actual file name.

Output Pixel Format
-------------------

Config key: opix_fmt

The pixel format of the frames of the output video. E.g.
rgb24, yuv420p etc. Defaults to `'yuv420p'`. If empty, it will use
`ipix_fmt`. If it's not the same as `ipix_fmt` the frame will
first be converted to `opix_fmt`.

Input Height
------------

Config key: iheight

The height of a frame of the input video. Defaults to zero.
This sets the input frame size. If the value is inavlid, the cam may
fail to open.

Output Rate
-----------

Config key: orate

The rate of the output video. If zero, will use `irate`.
Defaults to `0.`. This should be as close to the true fps of the input
camera, otherwise frames may be discarded or added to pad the video.

Input Codec
-----------

Config key: icodec

The codec of the input video, e.g. rawvideo, mjpeg. Defaults to `''`.
This should match the format in which the camera is providing the video.

Input Pixel Format
------------------

Config key: ipix_fmt

The pixel format of the frames of the input video. E.g.
rgb24, yuv420p etc. Defaults to `''`. If the camera doesn't support this
format, opening the camera may fail.

Output Codec
------------

Config key: ocodec

The codec of the output video, e.g. rawvideo, mjpeg. Defaults
to `'rawvideo'`. If empty, will use `icodec`. This controls the content
of the output video, e.g. whether it's raw, compressed etc.

Update Interval
---------------

Config key: space_update_intvl

The rate at which we update the RAM / disk space / CPU usage
information. Defaults to 1 (1 Hz).

Input Rate
----------

Config key: irate

The rate of the input video. It may not be accurate. Defaults to `''`.
This sets the rate at which the webcam should sample the camera. The actual
rate may be less than this.

Output Height
-------------

Config key: oheight

The height of a frame of the output video. Defaults to zero.
If zero, it uses `iheight`. When none-zero, the output frame will be scaled
to this size.

Output Extension
----------------

Config key: oext

The extension to be appended to the output video file. See
`ofilename`. Defaults to `'.avi'`. Should only not be empty if
`ofilename` doesn't already have an extension.

Output Increment
----------------

Config key: oincrement

An integer. Can be used when using the same filename
for multiple output videos, then, this value will simply be
incremented resulting in unique names. See `ofilename`. Defaults to zero.

Everytime a recording video is stopped recording, this value automatically
increments.

Direct Show Camera Name
-----------------------

Config key: idshow_dev

When playing using direct show, the direct show device
name. Defaults to `''`. This is typically used with USB webcams.

Output Format
-------------

Config key: ofmt

The format of the output video, e.g. avi, mp4, etc. Defaults
to `''avi`. If empty, will use `ifmt`. This just control the container of
the output video, not the actual content.

Output Filename
---------------

Config key: ofilename

The filename of the output video to be saved. The full
filename of the output video is `odir` followed by `ofilename`,
followed by `oext`. However, if `ofilename` contains a `{}`, `{}`
is first replaced with the contents of `oincrement`. Defaults to `''`.

Output Width
------------

Config key: owidth

The width of a frame of the output video. Defaults to zero. If
zero, it uses `iwidth`. When none-zero, the output frame will be scaled
to this size.

Input Width
-----------

Config key: iwidth

The width of a frame of the input video. Defaults to zero.
This sets the input frame size. If the value is inavlid, the cam may
fail to open.

Input Filename
--------------

Config key: ifilename

The filename of the input video. Can be a ip cam address,
or a direct show cam name, etc. Defaults to `''`.

Input Format
------------

Config key: ifmt

The format of the input video, e.g. dshow, avi, etc. Defaults to `''`.
    

