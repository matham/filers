filers Config
=============

:FFMpeg:

`cls`: 
 (internal) The string associated with the player source used.
 
 It is one of ``FFMpeg``, ``RTV``, or ``PTGray`` indicating the camera
 being used.
 
`dshow_opt`: 
 The camera options associated with :attr:`dshow_true_filename` when
 dshow is used.
 
`dshow_true_filename`: 
 The real and complete filename of the direct show (webcam) device.
     
 
`file_fmt`: dshow
 The format used to play the video. Can be empty or a format e.g.
 ``dshow`` for webcams.
 
`icodec`: 
 The codec used to open the video stream with.
     
 
`metadata_play`: None
 (internal) Describes the video metadata of the video player.
     
 
`metadata_play_used`: None
 (internal) Describes the video metadata of the video player that is
 actually used by the player.
 
`metadata_record`: None
 (internal) Describes the video metadata of the video recorder.
     
 
`play_filename`: 
 The filename of the media being played. Can be e.g. a url etc.
     
 
`record_directory`: E:\msys64\home\Matthew Einhorn
 The directory into which videos should be saved.
     
 
`record_fname`: video{}.avi
 The filename to be used to record the next video.
 
 If ``{}`` is present in the filename, it'll be replaced with the value of
 :attr:`record_fname_count` which auto increments after every video, when
 used.
 
`record_fname_count`: 0
 A counter that auto increments by one after every recorded video.
 
 Used to give unique filenames for each video file.
 

:PTGray:

`cam_config_opts`: {}
 The configuration options used to configure the camera after opening.
     
 
`cls`: 
 (internal) The string associated with the player source used.
 
 It is one of ``FFMpeg``, ``RTV``, or ``PTGray`` indicating the camera
 being used.
 
`ip`: 
 The ip address of the camera to open. Either :attr:`ip` or
 :attr:`serial` must be provided.
 
`metadata_play`: None
 (internal) Describes the video metadata of the video player.
     
 
`metadata_play_used`: None
 (internal) Describes the video metadata of the video player that is
 actually used by the player.
 
`metadata_record`: None
 (internal) Describes the video metadata of the video recorder.
     
 
`record_directory`: E:\msys64\home\Matthew Einhorn
 The directory into which videos should be saved.
     
 
`record_fname`: video{}.avi
 The filename to be used to record the next video.
 
 If ``{}`` is present in the filename, it'll be replaced with the value of
 :attr:`record_fname_count` which auto increments after every video, when
 used.
 
`record_fname_count`: 0
 A counter that auto increments by one after every recorded video.
 
 Used to give unique filenames for each video file.
 
`serial`: 0
 The serial number of the camera to open. Either :attr:`ip` or
 :attr:`serial` must be provided.
 

:RTV:

`cls`: 
 (internal) The string associated with the player source used.
 
 It is one of ``FFMpeg``, ``RTV``, or ``PTGray`` indicating the camera
 being used.
 
`metadata_play`: None
 (internal) Describes the video metadata of the video player.
     
 
`metadata_play_used`: None
 (internal) Describes the video metadata of the video player that is
 actually used by the player.
 
`metadata_record`: None
 (internal) Describes the video metadata of the video recorder.
     
 
`pipe_name`: filers_rtv
 The internal name used to communicate with Barst. When running remotely,
 the name is used to discover Barst.
 
`port`: 0
 The RTV port on the card to use.
     
 
`record_directory`: E:\msys64\home\Matthew Einhorn
 The directory into which videos should be saved.
     
 
`record_fname`: video{}.avi
 The filename to be used to record the next video.
 
 If ``{}`` is present in the filename, it'll be replaced with the value of
 :attr:`record_fname_count` which auto increments after every video, when
 used.
 
`record_fname_count`: 0
 A counter that auto increments by one after every recorded video.
 
 Used to give unique filenames for each video file.
 
`remote_computer_name`: 
 The name of the computer running Barst, if it's a remote computer.
 Otherwise it's the empty string.
 
`video_fmt`: full_NTSC
 The video format of the video being played.
 
 It can be one of the keys in::
 
     {'full_NTSC': (640, 480), 'full_PAL': (768, 576),
     'CIF_NTSC': (320, 240), 'CIF_PAL': (384, 288),
     'QCIF_NTSC': (160, 120), 'QCIF_PAL': (192, 144)}
 

:app:

`inspect`: False
 Enables GUI inspection. If True, it is activated by hitting ctrl-e in
 the GUI.
 

:recorder:

`cam_grid_rows`: 2
 The number of rows into which to split the video recorders when there's
 more than one recorder open.
 
