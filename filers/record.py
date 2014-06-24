'''Provides a class that plays and records videos from webcams using
ffpyplayer.

Keyboard keys
--------------

`space`:
    Starts and stops recording video to an output file.
`enter`:
    Starts playing the input cam.
`escape`:
    Stops the video from playing, and turns off the recorder if recording.
'''

__all__ = ('Recorder', )

import os
import logging
from threading import Thread
import psutil
import time
from fractions import Fraction
import traceback
from functools import partial
from kivy.weakmethod import WeakMethod
from kivy.utils import get_hex_from_color
from kivy.clock import Clock
from kivy.compat import PY2
from kivy.uix.boxlayout import BoxLayout
from kivy.properties import (NumericProperty, ReferenceListProperty,
    ObjectProperty, ListProperty, StringProperty, BooleanProperty,
    DictProperty, AliasProperty, OptionProperty, ConfigParserProperty)
from filers.tools import (str_to_float, pretty_space, pretty_time, KivyQueue,
                          ConfigProperty)
from filers import config_name
from ffpyplayer.player import MediaPlayer
from ffpyplayer.pic import get_image_size
from ffpyplayer.tools import list_dshow_devices
from ffpyplayer.writer import MediaWriter


unicode_type = unicode if PY2 else str
'''
Unicode type used to convert anything into unicode.
'''


ConfigProperty = partial(ConfigProperty, section='Recorder',
                         config_name=config_name)
'''
A partially initialized :py:class:`~kivy.properties.ConfigParserProperty`.
The section name is `'Recorder'` and the Config class name is
:attr:`~filers.config_name`.
'''


class Recorder(BoxLayout):
    ''' See module description.
    '''

    queue = None
    '''
    A :class:`~filers.tools.KivyQueue` instance to which the work thread will
    send updates and with which we communicate with the kivy event loop.
    Following is the list of string keys that can be sent, along with their
    possible values:

        `fps`: float
            The estimated fps of the input video playing. This is sent about
            once per second.
        `image`: :py:class:`~ffpyplayer.pic.Image`
            Sent for every frame read by the player from the input
            file / webcam. It's a :py:class:`~ffpyplayer.pic.Image` containing
            the frame data.
        `record_stats`: 2-tuple
            Sent after every frame written to disk by the recorder
            received from the player. It's a 2-tuple; the time elapsed since
            we started recording the video to disk (not playing), and the total
            size in bytes of the file recorded to disk so far.
        `skip_count`: int
            Sent whenever a frame sent to the recorder by the player
            is not written to disk because of e.g. a bad time stamp. The value
            is the total number of frames skipped so far. When a new file
            starts, a value of zero is sent.
        `failure`: str
            Sent when something went wrong and the threads ends. The
            value is a string with the reason for the failure. Upon failure,
            the controller should call stop and set itself in stopped mode.
        `done`: None
            None, sent when the thread has completed it's work.
    '''
    thread = None
    ''' The thread that runs our secondary thread. All disk R/W and processing
    is done from that thread. See :attr:`process_thread`. Defaults to None.
    '''
    stat_path = ''
    ''' The path to use to find the available disk space. This gets updated to
    the disk path of the output directory when it is changed. Defaults to
    `''`. If not valid, it uses the local drive.
    '''

    ff_player = None
    ''' The :py:class:`~ffpyplayer.player.MediaPlayer` object that
    controls the input file / webcam when running. Defaults to None.
    '''

    ff_recorder = None
    ''' The :py:class:`~ffpyplayer.writer.MediaWriter` object that controls the
    output file when recording. Defaults to None.
    '''

    running = False
    ''' Whether the thread is running. It is set to True before launching the
    thread, and the thread resets it to False before exiting. Defaults to
    False. See :attr:`process_thread`.
    '''

    finish = False
    ''' When set to True, it signals the thread to terminate. Defaults to
    False.
    '''

    skipped_frames = 0
    ''' The number of frames that was skipped by the recorder while writing
    the file to disk. Defaults to `0`.
    '''

    cam_list = {}
    ''' A dictionary of the the available direct show cameras and their
    options. The keys are the list of direct show cameras. Their values are
    a string representation of their options.
    '''

    isize = (0, 0)
    ''' After a new input video has started playing, this holds the true frame
    size of the video (width, height).
    '''

    real_ifmt = ''
    ''' After a new input video has started playing, this holds the true frame
    format of the video (e.g. rgb24, yuv420p).
    '''

    current_ofilename = StringProperty('')
    ''' The complete output filename, including path and everything. '''
    free_space = NumericProperty(0)
    ''' The total free space in bytes on the output disk. '''
    total_space = NumericProperty(1)
    ''' The total space in bytes on the output disk. '''
    cpu_percent = NumericProperty(0)
    ''' The current CPU percent usage. '''
    free_ram = NumericProperty(0)
    ''' The current amount of RAM free. '''
    total_ram = NumericProperty(1)
    ''' The total amount of RAM in the system. '''
    ifps = NumericProperty(0.)
    ''' The expected input frames rate. '''
    ibps = NumericProperty(0.)
    ''' The expected input byte rate given the rate and image type / size. '''
    ofps = NumericProperty(0.)
    ''' The expected output frames rate. '''
    obps = NumericProperty(0.)
    ''' The expected output byte rate given the rate and image type / size. '''
    oelapsed = NumericProperty(0.)
    ''' The total amount of time elapsed since start of recording. '''
    ofilesize = NumericProperty(0.)
    ''' The total output filesize in bytes. '''
    skip_count = NumericProperty(0.)
    ''' The total number of input frames that were skipped when writing. '''
    frame_count = NumericProperty(0)
    ''' The number of input frames received. '''
    record_count = NumericProperty(0)
    ''' The total number of frames received while recording. '''

    ombps_pretty = AliasProperty(lambda s: pretty_space(s.obps, is_rate=True),
                                 None, bind=('obps',))
    ''' A string version of :attr:`obps`. '''
    imbps_pretty = AliasProperty(lambda s: pretty_space(s.ibps, is_rate=True),
                                 None, bind=('ibps',))
    ''' A string version of :attr:`ibps`. '''
    oelapsed_pretty = AliasProperty(lambda s: pretty_time(s.oelapsed), None,
                                    bind=('oelapsed',))
    ''' A string version of :attr:`oelapsed`. '''
    osize_pretty = AliasProperty(lambda s: pretty_space(s.ofilesize), None,
                                 bind=('ofilesize',))
    ''' A string version of :attr:`ofilesize`. '''

    def record_stats(self):
        res = '[color=#FF3399]{}[/color]\n'.format(self.current_ofilename)
        skip_c = 'FF0000' if self.skip_count else 'FFFF00'
        res += 'Skipped: [color=#{}]{:.0f}[/color]\n'.format(skip_c,
                                                             self.skip_count)
        if (not self.obps) or (self.free_space / float(self.obps) > 300 and
                               self.free_space > 5368709120):
            free_c = '00FF00'
        else:
            free_c = 'FF0000'
        res += 'Free: [color=#{}]{}[/color]\n'.format(free_c,
               pretty_space(self.free_space))
        if self.obps:
            res += 'Time remaining: [color=#{}]{}[/color]'.format(free_c,
                   pretty_time(self.free_space / float(self.obps)))
        return res
    stats_pretty = AliasProperty(record_stats, None, bind=('current_ofilename',
    'osize_pretty', 'oelapsed_pretty', 'ombps_pretty', 'skip_count',
    'free_space', 'obps'))
    ''' Colored system stats. '''

    def short_input_stats(self):
        fps_color = '#FFFFFF'
        if self.ifps < self.irate and self.irate:
            ratio = self.ifps / self.irate
            fps_color = get_hex_from_color((1, ratio, ratio))
        s = '[color=#00FFFF]'
        e = '[/color]'
        return ('[color={0}]FPS: {1:.2f}[/color], MBps: {4}{2}{5}, Count: '
                '{4}{3:d}{5}'.format(fps_color, self.ifps, self.imbps_pretty,
                                     self.frame_count, s, e))
    stats_input_pretty = AliasProperty(short_input_stats, None, bind=('ifps',\
    'imbps_pretty', 'irate', 'frame_count'))
    ''' Colored input stats. '''

    def short_output_stats(self):
        if (not self.obps) or (self.free_space / float(self.obps) > 300 and
                               self.free_space > 5368709120):
            s = '[color=#00FF00]'
        else:
            s = '[color=#FF0000]'
        e = '[/color]'

        return ('Rate: {4}{0}{5}, Size: {4}{1}{5}, Elapsed: {4}{2}{5}, Count: '
                '{4}{3}{5}'.format(self.ombps_pretty, self.osize_pretty,
                self.oelapsed_pretty, self.record_count, s, e))
    stats_output_pretty = AliasProperty(short_output_stats, None,
    bind=('ombps_pretty', 'osize_pretty', 'oelapsed_pretty', 'free_space'))
    ''' Colored output stats. '''

    recording = BooleanProperty(False)
    ''' True whenever the instance is recording a output file. '''

    def get_title(self):
        return (' Recording - {}'.format(self.current_ofilename)
                if self.recording else '')
    window_title = AliasProperty(get_title, None)
    ''' The title used by the window when the :class:`Recorder` is active. '''

    space_update_intvl = ConfigProperty(1., 'space_update_intvl', float)
    ''' The rate at which we update the RAM / disk space / CPU usage
    information. Defaults to 1 (1 Hz).
    '''
    irate = ConfigProperty(0., 'irate', float)
    ''' The rate of the input video. It may not be accurate. Defaults to `''`.
    This sets the rate at which the webcam should sample the camera. The actual
    rate may be less than this.
    '''
    iwidth = ConfigProperty(0, 'iwidth', int)
    ''' The width of a frame of the input video. Defaults to zero.
    This sets the input frame size. If the value is inavlid, the cam may
    fail to open.'''
    iheight = ConfigProperty(0, 'iheight', int)
    ''' The height of a frame of the input video. Defaults to zero.
    This sets the input frame size. If the value is inavlid, the cam may
    fail to open.'''
    icodec = ConfigProperty('', 'icodec', unicode_type)
    ''' The codec of the input video, e.g. rawvideo, mjpeg. Defaults to `''`.
    This should match the format in which the camera is providing the video.
    '''
    ipix_fmt = ConfigProperty('', 'ipix_fmt', unicode_type)
    ''' The pixel format of the frames of the input video. E.g.
    rgb24, yuv420p etc. Defaults to `''`. If the camera doesn't support this
    format, opening the camera may fail.
    '''
    idshow_dev = ConfigProperty('', 'idshow_dev', unicode_type)
    ''' When playing using direct show, the direct show device
    name. Defaults to `''`. This is typically used with USB webcams.
    '''
    idshow_opt = ConfigProperty('', 'idshow_opt', unicode_type)
    ''' The current direct show options for the
    current direct show selected camera. Defaults to `''`.
    '''
    ifilename = ConfigProperty('', 'ifilename', unicode_type)
    ''' The filename of the input video. Can be a ip cam address,
    or a direct show cam name, etc. Defaults to `''`.
    '''
    ifmt = ConfigProperty('', 'ifmt', unicode_type)
    ''' The format of the input video, e.g. dshow, avi, etc. Defaults to `''`.
    '''
    owidth = ConfigProperty(0, 'owidth', int)
    ''' The width of a frame of the output video. Defaults to zero. If
    zero, it uses `iwidth`. When none-zero, the output frame will be scaled
    to this size.
    '''
    oheight = ConfigProperty(0, 'oheight', int)
    ''' The height of a frame of the output video. Defaults to zero.
    If zero, it uses `iheight`. When none-zero, the output frame will be scaled
    to this size.
    '''
    ofmt = ConfigProperty('avi', 'ofmt', unicode_type)
    ''' The format of the output video, e.g. avi, mp4, etc. Defaults
    to `''avi`. If empty, will use `ifmt`. This just control the container of
    the output video, not the actual content.
    '''
    ocodec = ConfigProperty('rawvideo', 'ocodec', unicode_type)
    ''' The codec of the output video, e.g. rawvideo, mjpeg. Defaults
    to `'rawvideo'`. If empty, will use `icodec`. This controls the content
    of the output video, e.g. whether it's raw, compressed etc.
    '''
    opix_fmt = ConfigProperty('yuv420p', 'opix_fmt', unicode_type)
    ''' The pixel format of the frames of the output video. E.g.
    rgb24, yuv420p etc. Defaults to `'yuv420p'`. If empty, it will use
    `ipix_fmt`. If it's not the same as `ipix_fmt` the frame will
    first be converted to `opix_fmt`.
    '''
    odir = ConfigProperty('', 'odir', unicode_type)
    ''' The directory where the output file will be saved. Defaults to `''`.
    This is just the directory name, not the actual file name.
    '''
    ofilename = ConfigProperty('', 'ofilename', unicode_type)
    ''' The filename of the output video to be saved. The full
    filename of the output video is `odir` followed by `ofilename`,
    followed by `oext`. However, if `ofilename` contains a `{}`, `{}`
    is first replaced with the contents of `oincrement`. Defaults to `''`.
    '''
    oext = ConfigProperty('.avi', 'oext', unicode_type)
    ''' The extension to be appended to the output video file. See
    `ofilename`. Defaults to `'.avi'`. Should only not be empty if
    `ofilename` doesn't already have an extension.
    '''
    orate = ConfigProperty(0., 'orate', float)
    ''' The rate of the output video. If zero, will use `irate`.
    Defaults to `0.`. This should be as close to the true fps of the input
    camera, otherwise frames may be discarded or added to pad the video.
    '''
    oincrement = ConfigProperty(0, 'oincrement', int)
    ''' An integer. Can be used when using the same filename
    for multiple output videos, then, this value will simply be
    incremented resulting in unique names. See `ofilename`. Defaults to zero.

    Everytime a recording video is stopped recording, this value automatically
    increments.
    '''

    play_image_wgt = None
    ''' The :class:`filers.misc_widgets.BufferImage` instance that displays
    the images read.
    '''
    play_btn_wgt = None
    ''' The button widget that starts and stops playing.
    '''
    record_btn_wgt = None
    ''' The button widget that starts and stops recording.
    '''
    increment_wgt = ObjectProperty(None)
    ''' The TextInput widget that in which the user enters the current
    :attr:`oincrement` value.
    '''

    def __init__(self, **kwargs):
        super(Recorder, self).__init__(**kwargs)
        self.queue = KivyQueue(Clock.create_trigger(self.read_queue))
        self.stat_path = os.path.splitdrive(os.path.expanduser('~'))[0]

        def update_stat_path(instance, value):
            drive = os.path.splitdrive(value)[0]
            if drive:
                self.stat_path = drive
            else:
                self.stat_path = os.path.splitdrive(os.path.expanduser('~'))[0]

        def update_ifps(instance, value):
            self.ifps = value

        def update_ofps(*l):
            self.ofps = self.orate if self.orate else self.irate
        self.bind(odir=update_stat_path, irate=update_ifps, orate=update_ofps)
        self.bind(irate=update_ofps)

        def update_bps(*l):
            try:
                if self.ipix_fmt and self.iwidth and self.iheight:
                    rate = sum(get_image_size(self.ipix_fmt, self.iwidth,
                                              self.iheight)) * self.irate
                else:
                    rate = 0.
            except:
                rate = 0.
            self.ibps = rate

            rate = self.orate if self.orate else self.irate
            pix_fmt = self.opix_fmt if self.opix_fmt else self.ipix_fmt
            width = self.owidth if self.owidth else self.iwidth
            height = self.oheight if self.oheight else self.iheight
            try:
                if pix_fmt and width and height:
                    rate = sum(get_image_size(pix_fmt, width, height)) * rate
                else:
                    rate = 0.
            except:
                rate = 0.
            self.obps = rate
        self.bind(ipix_fmt=update_bps, iwidth=update_bps,
                  iheight=update_bps, irate=update_bps, orate=update_bps,
                  opix_fmt=update_bps, owidth=update_bps, oheight=update_bps)

        def update_filename(*l):
            try:
                fname = self.ofilename
                if fname.find('{}') != -1:
                    filename = fname.format(self.oincrement)
                else:
                    filename = fname
                if self.oext:
                    filename += self.oext
                filename = os.path.join(self.odir, filename)
            except:
                filename = ''
            self.current_ofilename = filename
        self.bind(ofilename=update_filename, oincrement=update_filename,
                  oext=update_filename, odir=update_filename)
        self.update_diskspace()

    def __del__(self):
        self.stop()

    def filers_start(self):
        '''
        Should be called after instance creation when the user is ready to
        start running this instance. Can only be called once.
        '''
        Clock.schedule_interval(self.update_diskspace, self.space_update_intvl)

    def update_diskspace(self, *largs):
        '''
        This method is scheduled to be run at a rate of
        :attr:`space_update_intvl` starting from after :meth:`start` is called.
        It updates the RAM and CPU usage.
        '''
        usage = psutil.disk_usage(self.stat_path)
        self.free_space, self.total_space = usage.free, usage.total
        self.cpu_percent = psutil.cpu_percent(interval=0) / 100.
        vm = psutil.virtual_memory()
        self.free_ram = vm.available
        self.total_ram = vm.total

    def get_estimated_size(self, duration, count, obps):
        '''
        Returns the estimated free time for recording on the recording disk,
        given the current recording settings.

        :returns:
            a string formatted to show the estimated remaining time. It's
            color coded to show if the remaining time is very little.
        '''
        duration = str_to_float(duration, val_type=float, err_val=0.)
        count = str_to_float(count, val_type=int, err_val=1)
        duration *= count
        s = obps * duration

        if ((not obps) or (self.free_space / float(obps) - duration > 300
                                and self.free_space - s > 5368709120)):
            free_c = '00FF00'
        else:
            free_c = 'FF0000'
        label = ('Size: [color=#{0}]{1}[/color], Time: '
                 '&bl;[color=#{0}]{2}[/color]&br;')
        return label.format(free_c, pretty_space(s), pretty_time(duration))

    def read_queue(self, *largs):
        '''
        The method that is called by the Kivy thread when it's notified by the
        internal thread of updates. It reads the :attr:`queue` and process any
        waiting updates.
        '''
        img = None
        while 1:
            try:
                key, val = self.queue.get()
            except KivyQueue.Empty:
                break
            if key == 'failure':
                self.play_btn_wgt.state = 'normal'
            if key == 'done':
                self.play_btn_wgt.state = 'normal'
            elif key == 'image':
                img = val
                self.frame_count += 1
                if self.recording:
                    self.record_count += 1
            elif key == 'record_stats':
                self.oelapsed = val[0]
                self.ofilesize = val[1]
            elif key == 'skip_count':
                self.skip_count = val
            elif key == 'fps':
                self.ifps = val
        if img is not None:
            self.play_image_wgt.update_img(img)

    def on_keyboard_down(self, keyboard, keycode, text, modifiers):
        '''
        Method called by the Kivy thread when a key in the keyboard is pressed.
        '''
        if keycode[1] == 'spacebar':
            self.record_btn_wgt.state = ('down' if self.record_btn_wgt.state ==
                                         'normal' else 'normal')
        elif keycode[1] == 'enter':
            self.play_btn_wgt.state = 'down'
        elif keycode[1] == 'escape':
            self.play_btn_wgt.state = 'normal'
        else:
            return False
        return True

    def on_keyboard_up(self, keyboard, keycode):
        '''
        Method called by the Kivy thread when a key in the keyboard is
        released.
        '''
        return False

    def get_cam_list(self, old_cam, old_opt):
        ''' Returns a list of available direct show webcams and the string
        options for the currently selected one. It also updates the currently
        selected camera and its options.

        :Parameters:

            `old_cam`: str
                The currently selected camera. If it is still valid,
                that will remain selected, otherwise it'd be changed with
                to the first available camera (or empty if none).
            `old_opt`: str
                The options for the currently selected camera. If
                it is still valid, that will remain selected, otherwise it'd be
                changed to the first available option (or empty if none).

        :returns:

            A 2-tuple. The first element is the list of available webcams.
            The second element, is the list of available options for the
            current webcam.
        '''
        res_cam = ''
        res_opts = []
        res_opt = ''

        cam_list = list_dshow_devices()[0]
        cams = {}
        for cam, opts in cam_list.iteritems():
            cams[cam] = {}
            for opt in opts:
                pix, codec, size, rate = opt
                str_opts = 'Pixel format: %s, Codec: %s, %dx%d, (%d, %d) fps'\
                % (pix, codec, size[0], size[1], rate[0], rate[1])
                cams[cam][str_opts] = opt
        self.cam_list = cams
        res_cams = sorted(cams.keys())
        if not cams:
            self.idshow_dev = res_cam
            self.idshow_opt = res_opt
            return res_cams, res_opts
        if old_cam in cams:
            res_cam = old_cam
        else:
            res_cam = res_cams[0]
        res_opts = sorted(cams[res_cam].keys())
        if old_opt in res_opts:
            res_opt = old_opt
        elif res_opts:
            res_opt = res_opts[0]
        self.idshow_dev = res_cam
        self.idshow_opt = res_opt
        return res_cams, res_opts

    def set_cam(self, cam, old_opt):
        ''' Returns a string representation of the options for a particular
        direct show camera. It also updates the currently selected option for
        the webcam and the input filename.

        :Parameters:

            `cam`: str
                The name of camera.
            `old_opt`: str
                The currently selected configuration for this
                camera. If invalid, it will be changed.

        :returns:

            A list of available options for this webcam..
        '''
        cam_list = self.cam_list
        if cam not in cam_list:
            self.idshow_opt = '<Invalid camera>'
            self.ifilename = ''
            self.idshow_dev = cam
            return []

        res_opts = sorted(cam_list[cam].keys())
        res_opt = old_opt
        if res_opt not in res_opts:
            if res_opts:
                res_opt = res_opts[0]
            else:
                res_opt = ''
        self.idshow_opt = res_opt
        self.ifilename = 'video=' + cam
        self.idshow_dev = cam
        return res_opts

    def set_cam_opts(self, cam, opts):
        ''' Sets the configuration parameters to use a particular webcam and
        option set. It populates e.g. :attr:`iwidth` etc.

        :Parameters:

            `cam`: str
                The name of camera.
            `opts`: str
                The selected configuration for this camera.
        '''
        cam_list = self.cam_list
        if cam not in cam_list:
            for key, val in (('ipix_fmt', ''), ('icodec', ''), ('iwidth', 0),
                ('iheight', 0), ('irate', 0.),
                ('idshow_opt', '<Invalid camera>'), ('ifilename', ''),
                ('idshow_dev', cam)):
                setattr(self, key, val)
            return
        cam_opts = cam_list[cam]
        if opts not in cam_opts:
            for key, val in (('ipix_fmt', ''), ('icodec', ''), ('iwidth', 0),
                ('iheight', 0), ('irate', 0.),
                ('idshow_opt', ''), ('idshow_dev', cam)):
                setattr(self, key, val)
            return
        pix_fmt, codec, size, (_, rate) = cam_opts[opts]
        for key, val in (('ipix_fmt', pix_fmt), ('icodec', codec),
            ('ifmt', 'dshow'), ('iwidth', size[0]), ('iheight', size[1]),
            ('irate', rate), ('idshow_opt', opts), ('idshow_dev', cam)):
            setattr(self, key, val)

    def _ff_callback(self, selector, value):
        ''' The callback used by :py:mod:`ffpylayer` to notify us of issues.
        '''
        if selector == 'quit' or selector == 'eof':
            if self.running:
                self.finish = True
                self.queue.put('failure', 'Internal ffpyplayer stopped '
                               'playing.')

    def play(self, color=True):
        ''' Starts to play the input video file / webcam.

        This launches the second thread that does the disk I/O and video input.
        If it is already running, it does nothing.

        :returns:

            True, if it successfully started, False otherwise.
        '''
        if self.running and self.thread and self.thread.is_alive():
            return True
        self.stop()
        irate = self.irate
        if not irate:
            logging.error(\
                'Recorder: Cannot play; input frame rate not provided.')
            return False

        ff_opts = {'sync': 'video', 'an': True, 'sn': True, 'paused': True}
        ipix_fmt, ifmt, icodec = self.ipix_fmt, self.ifmt, self.icodec
        if ipix_fmt:
            ff_opts['out_fmt'] = bytes(ipix_fmt)
        if ifmt:
            ff_opts['f'] = bytes(ifmt)
        if icodec:
            ff_opts['vcodec'] = bytes(icodec)

        lib_opts = {}
        if ifmt == 'dshow':
            if ipix_fmt:
                lib_opts['pixel_format'] = bytes(ipix_fmt)
            if irate:
                lib_opts['framerate'] = bytes(str(irate))
            iw, ih = self.iwidth, self.iheight
            if iw and ih:
                lib_opts['video_size'] = bytes('{}x{}'.format(iw, ih))
            #==================================================================
            # if c['ipix_fmt'] and c['iwidth'] and c['iheight']:
            #     lib_opts['rtbufsize'] = sum(get_image_size(c['ipix_fmt'],
            #         c['iwidth'], c['iheight']))
            #     lib_opts['rtbufsize'] *= c['irate'] if c['irate'] else 30
            #     lib_opts['rtbufsize'] = str(int(min(lib_opts['rtbufsize'],
            #                                         500 * 1024 ** 2)))
            #==================================================================
        try:
            ifilename = self.ifilename
            ffplayer = self.ff_player = MediaPlayer(ifilename,
                callback=WeakMethod(self._ff_callback), loglevel='warning',
                ff_opts=ff_opts, lib_opts=lib_opts)
        except:
            logging.error('Recorder: Player failed:\n' +
                          traceback.format_exc())
            self.stop()
            return False

        src_fmt = ''
        s = time.clock()
        while (not self.finish) and time.clock() - s < 30.:
            src_fmt = ffplayer.get_metadata().get('src_pix_fmt')
            if src_fmt:
                break
            time.sleep(0.005)
        if not src_fmt:
            logging.error("Recorder: Player failed, couldn't get source type.")
            self.stop()
            return False
        fmt = {'gray': 'gray', 'rgb24': 'rgb24', 'bgr24': 'rgb24',
               'rgba': 'rgba', 'bgra': 'rgba'}.get(src_fmt, 'yuv420p')
        if not color:
            fmt = 'gray'
        ffplayer.set_output_pix_fmt(fmt)
        ffplayer.toggle_pause()
        logging.info('Recorder: input, output formats are: {}, {}'
                     .format(src_fmt, fmt))

        img = None
        s = time.clock()
        while (not self.finish) and time.clock() - s < 10.:
            img, val = ffplayer.get_frame()
            if img or val == 'eof' or val == 'paused':
                break
            time.sleep(0.005)
        if not img:
            logging.error("Recorder: Player failed, couldn't fetch a image.")
            self.stop()
            return False
        img = img[0]
        self.isize = img.get_size()
        self.real_ifmt = img.get_pixel_format()
        self.running = True
        self.iwidth, self.iheight = self.isize
        self.ipix_fmt = self.real_ifmt
        try:
            self.thread = Thread(target=self.process_thread,
                                 name='ff play/record')
            self.thread.start()
        except:
            logging.error('Recorder: Thread failed:\n' +
                          traceback.format_exc())
            self.stop()
            return False
        return True

    def stop(self):
        ''' Asks the second thread started with :meth:`play` to end.
        This will also cause recording to stop, if a file was being recorded.
        '''
        self.record_end()
        self.finish = True
        while self.running and self.thread and self.thread.is_alive():
            time.sleep(0.1)
        self.ff_player = None
        self.running = False
        self.finish = False
        self.thread = None

    def record_start(self):
        ''' Starts to record the input video file / webcam to the
        pre-configured output file. If it is already running, it does nothing.

        :returns:

            True, if it successfully began, False otherwise.
        '''
        if not self.running:
            return False
        if (self.ff_recorder and self.running and self.thread and
            self.thread.is_alive()):
            return True
        self.record_end()
        self.skipped_frames = 0
        iw, ih = self.isize
        ipix_fmt = self.real_ifmt
        opix_fmt = self.opix_fmt
        ow, oh = self.owidth, self.oheight
        codec = self.ocodec
        rate = self.orate if self.orate else self.irate
        rate = Fraction(rate).limit_denominator(2 ** 31 - 1)
        rate = (rate.numerator, rate.denominator)
        stream = {'pix_fmt_in': ipix_fmt, 'pix_fmt_out': opix_fmt,
                  'width_in': iw, 'height_in': ih, 'width_out': ow,
                  'height_out': oh, 'codec': codec, 'frame_rate': rate}
        fmt = self.ofmt

        try:
            self.ff_recorder = MediaWriter(self.current_ofilename, [stream],
                                           fmt)
        except:
            logging.error('Recorder: Failed to start recording:\n' +
                          traceback.format_exc())
            self.record_end()
            return False
        return True

    def record_end(self):
        ''' Stops the recorder and closes the output file. It does not stop
        playing the input video.

        If :attr:`ofilename` contains a `{}` and a file was being recorded,
        :attr:`oincrement` will be incremented by one.
        '''
        if self.ff_recorder and self.ofilename.find('{}') != -1:
            self.oincrement = self.oincrement + 1
        self.ff_recorder = None

    def process_thread(self):
        ''' The thread that processes the input / output video files and
        webcams. It communicates with the outside world using :attr:`queue`.

        Upon exit, it sets :attr:`running` to False.
        '''
        queue = self.queue
        put = queue.put
        player = self.ff_player
        recorder = None
        t = 1 / (self.irate * 2.)
        t_start = 0.
        skip_count = 0
        invl_start = time.clock()
        frame_count = 0

        try:
            while not self.finish:
                img, val = player.get_frame()
                invl_end = time.clock()
                if invl_end - invl_start >= 1.:
                    put('fps', frame_count / (invl_end - invl_start))
                    frame_count = 0
                    invl_start = invl_end
                if val == 'eof' or val == 'paused':
                    break
                if not img:
                    time.sleep(min(val, t) if val else t)
                    continue
                frame_count += 1
                if recorder != self.ff_recorder:
                    t_start = img[1]
                    recorder = self.ff_recorder
                    skip_count = 0
                    put('skip_count', 0)
                put('image', img[0])
                if recorder:
                    pts = img[1] - t_start
                    try:
                        put('record_stats', (pts, recorder.write_frame(img[0],
                            pts, 0)))
                    except:
                        skip_count += 1
                        put('skip_count', skip_count)
                        logging.warning(\
                        'Recorder: Bad pts {0:f}, frame skipped'.format(pts))
        except:
            logging.error('Recorder: Play thread failed: ' +
                          traceback.format_exc())
        put('done', None)
        self.running = False
