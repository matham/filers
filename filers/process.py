'''Video Processing
=====================

Provides a class that manipulates files en-masse using FFmpeg. It can
compress/uncompress/merge/concatenate or perform other tasks on video files.

In order to use this module, the ffmpeg binaries need to be installed in the
parent directory of this module, or in $(FFMPEG_ROOT)/bin.

Keyboard Keys
-------------

`space`:
    Toggles the current pause state.
`enter`:
    Starts processing.
`escape`:
    Stop the processing.
'''

import sys
import json
from os import makedirs
from os.path import join, exists, expanduser, abspath, isdir, isfile, dirname,\
    split, splitext, getsize, sep
import logging
from threading import Thread
import time
from functools import partial
import traceback
import subprocess as sp
import tempfile
import re
from re import match, escape, sub
from time import sleep
from collections import defaultdict

from kivy.clock import Clock
from kivy.compat import clock
from kivy.factory import Factory
from kivy.uix.behaviors.knspace import KNSpaceBehavior
from kivy.uix.gridlayout import GridLayout
from kivy.uix.popup import Popup
from kivy.logger import Logger
from kivy.event import EventDispatcher
from kivy.properties import (NumericProperty, ReferenceListProperty,
    ObjectProperty, ListProperty, StringProperty, BooleanProperty,
    DictProperty, AliasProperty, OptionProperty, ConfigParserProperty)

from cplcom import config_name
from filers.tools import (str_to_float, pretty_space, pretty_time, KivyQueue,
                          to_bool, ConfigProperty, byteify)
from filers import root_data_path

__all__ = ('VideoConverter', )


def exit_converter():
    c = VideoConverterController.converter_singleton
    if c:
        try:
            c.stop(terminate=True)
        except:
            pass

        try:
            c.save_config()
        except Exception as e:
            Logger.error('Converter: {}'.format(e))
            Logger.exception(e)


class VideoConverterController(EventDispatcher):

    settings_path = ConfigParserProperty(
        join(root_data_path, 'converter.json'), 'Filers',
        'converter_settings_path', config_name)

    conversion_group_settings = ListProperty([])

    conversion_group_widgets = []

    converter_singleton = None

    converter_view = ObjectProperty(None)

    container = ObjectProperty(None)

    res_container = ObjectProperty(None)

    settings_display = None

    current_group_i = None

    files = []

    processed = 0

    processing = False

    def __init__(self, **kwargs):
        super(VideoConverterController, self).__init__(**kwargs)
        VideoConverterController.converter_singleton = self
        self.settings_display = Factory.ConverterSettings(controller=self)
        self.load_config(self.settings_path)
        self.conversion_group_settings = []
        self.conversion_group_widgets = []

    @staticmethod
    def get_window_title():
        c = VideoConverterController.converter_singleton
        if not c or not c.files or len(c.files) == c.processed:
            return ''

        s = ' - Converter'
        if not c.processed:
            s += ' ({})'.format(len(c.files))
        else:
            s += ' ({}/{})'.format(len(c.processed, c.files))

        if not c.processing:
            s += ' PAUSED'
        return s

    def log_error(self, msg=None, e=None, exc_info=None, level='error'):
        q = self.converter_view.error_output.queue
        l = getattr(Logger, level)
        val = msg

        if msg:
            if e:
                val = '{}: {}'.format(msg, repr(e))
                l(val)
            else:
                l(msg)

        if exc_info is not None:
            Logger.error(e, exc_info=exc_info)

        if val:
            q.add_item(val)

    def load_config(self, filename):
        if not isfile(filename):
            return
        filename = abspath(filename)

        for c in self.conversion_group_widgets[:]:
            self.delete_group(c)

        try:
            with open(filename) as fh:
                global_opt, convert_opt = json.load(fh)
            global_opt, convert_opt = byteify(global_opt), byteify(convert_opt)

            for k, v in global_opt.items():
                setattr(self, k, v)
            for d in convert_opt:
                self.add_group(settings=d, show=False)
        except Exception as e:
            self.log_error(e=e, exc_info=sys.exc_info(), msg='Loading config')
        else:
            if filename:
                self.settings_path = filename

    def save_config(self, filename=None):
        filename = filename or self.settings_path
        if not filename:
            return

        try:
            with open(filename, 'w') as fh:
                json.dump(
                    (self.get_config_dict(), self.conversion_group_settings),
                    fh, sort_keys=True, indent=4, separators=(',', ': '))
        except Exception as e:
            self.log_error(e=e, exc_info=sys.exc_info(), msg='Loading config')
        else:
            if filename:
                self.settings_path = filename

    def ui_config(self, load, path, selection, filename):
        fname = abspath(join(path, filename))
        if load:
            self.load_config(fname)
        else:
            self.save_config(fname)

    def get_config_dict(self):
        attrs = []
        return {k: getattr(self, k) for k in attrs}

    def add_group(self, settings={}, show=True):
        item = ConversionGroup(controller=self)
        settings = self.settings_display.get_settings(settings)
        self.conversion_group_widgets.append(item)
        self.conversion_group_settings.append(settings)
        self.container.add_widget(item)

        if show:
            self.show_settings(item)

    def delete_group(self, item):
        self.settings_display.dismiss()
        i = self.conversion_group_widgets.index(item)
        del self.conversion_group_settings[i]
        del self.conversion_group_widgets[i]
        self.container.remove_widget(item)

    def show_settings(self, item):
        self.settings_display.item = item
        self.settings_display.open()

    def stop(self, terminate=False):
        pass

    def update_item_settings(self, item, src):
        pass


class ConversionGroup(KNSpaceBehavior, GridLayout):

    controller = ObjectProperty(None, rebind=True)

    in_ex_file = StringProperty('')

    out_ex_file = StringProperty('')


class ConverterSettings(KNSpaceBehavior, Popup):

    controller = ObjectProperty(None, rebind=True)

    item = ObjectProperty(None, allownone=True)

    def get_settings(self, settings={}):
        s = {}
        s.update(settings)
        return s

    def set_settings(self, settings={}):
        pass


class VideoConverter(KNSpaceBehavior, GridLayout):

    def __init__(self, **kwargs):
        super(VideoConverter, self).__init__(**kwargs)

        def init(*largs):
            self.controller = VideoConverterController(
                converter_view=self, container=self.ids.container,
                res_container=self.ids.res_container)
        Clock.schedule_once(init, 0)

    controller = ObjectProperty(None, rebind=True)


"""

unicode_type = unicode if PY2 else str
'''
Unicode type used to convert anything into unicode.
'''


ConfigProperty = partial(ConfigProperty, section='Processor',
                         config_name=config_name)
'''
A partially initialized :py:class:`~kivy.properties.ConfigParserProperty`.
The section name is `'Processor'` and the Config class name is
:attr:`~filers.config_name`.
'''


class Processor(GridLayout):
    '''
    See module description.
    '''

    queue = None
    ''' The :class:`~filers.tools.KivyQueue` with which we communicate with the
    kivy event loop. The work thread sends updates to Kivy with this queue.
    Following is the list of queue keys that can be sent, along with their
    possible values.

        `clean`: None
            Sent when the threads starts.
        `count`: int
            Sent periodically while pre-reading the input files describing
            the files read so far. It's a 5-tuple of: # output files,
            # input files, # of walked directories, total size of the input
            files, and a dictionary where the keys are ignored files, or
            extensions types (e.g. .txt) and their values are the number of
            times they were ignored.
        `count_done`: int
            Identical to `count`, except it's sent when the count is done.
        `failure`: str
            Sent when something went wrong and the threads ends. The
            value is a string with the reason for the failure. Upon failure,
            the controller should call stop and set itself in stopped mode.
        `file_cmd`: str
            Sent for every file before it is processed. It's a string
            containing the full command with which FFmpeg will be called.
        `file_stat`: 11-tuple
            Sent after each file that has been processed (e.g. moved)
            containing status information. It's a 11-tuple of: the total size
            of output files processed, the estimated total size of all the
            output files, the total size of input files processed, the total
            size of all the input files (can change dynamically as files are
            skipped), the total number of input files processed, the count of
            all the input files, the total number of output files processed,
            the count of all the output files, the estimated bps at which
            things are done, the total time elapsed, the estimated time left.
        `skipped`: str
            Sent when the file is skipped due to error. The
            string describes the files involved and the reason.
        `done`: None
            Sent when the thread has completed it's work.
    '''

    thread = None
    ''' The thread that runs our secondary thread. All disk R/W and processing
    is done from that thread. See :attr:`process_thread`. Defaults to None.
    '''

    ffmpeg_path = ''
    ''' The full path to the FFmpeg executable. To find it, it looks in the
    same path that :py:mod:`ffpyplayer` looks for the binaries
    (`FFMPEG_ROOT` in os.environ as well as the parent directory of this file).
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
    pause = False
    ''' When set to True, it signals the thread to pause. Setting to False will
    un-pause. Defaults to False.
    '''
    report = ''
    ''' A text report of the files to be processed and ignored. This is
    generated before any processing occurs. Defaults to `''`.
    '''
    error_list = []
    ''' A list of text items, each item representing a file that failed to be
    processed. It is updated dynamically. Defaults to `[]`.
    '''
    success_list = []
    ''' A list of text items, each item representing a file that was
    successfully processed. It is updated dynamically. Defaults to `[]`.
    '''

    input_split_pat = re.compile('''((?:[^,"']|"[^"]*"|'[^']*')+)''')
    ''' The compiled pattern we use to break apart the list of input files to
    process. Defaults to the compiled value of `', *'`.
    '''

    input = ConfigProperty(u'', 'input', unicode_type)
    ''' The list of input files and folders to be processed. It is
    a comma (plus optional spaces) separated list. File or directory names
    that contain a space, should be quoted with `"`. Triple clicking on this
    field will launch a file browser.
    Defaults to `u''`.
    '''
    simple_filt = ConfigProperty(True, 'simple_filt', to_bool)
    ''' Whether the filter we use to filter the input files with
    uses the simple common format (where * - match anything, ? match any single
    char), if True. If False, it's a python regex string. Defaults to True.
    '''
    input_filter = ConfigProperty(u'*.avi', 'input_filter', unicode_type)
    ''' The filter to use to filter the input files. See
    :attr:`simple_filt`. Defaults to `'*.avi'`.
    '''
    group_filt = ConfigProperty(u'', 'group_filt', unicode_type)
    ''' The matching string parts to remove to get the output
    filename. If :attr:`simple_filt` is True, it uses `*` to match any group
    of chars, and `?` to match a single char. If :attr:`simple_filt` is
    False, it uses a python regex for the matching. This really only
    makes sense with a regex. This is mostly useful when merging
    files.

    For example, say we have two files called `Video file1.avi`,
    and `Video file2.avi`, and we wish to merge them into a new file
    called `Video file.avi`. Then :attr:`group_filt` will be
    `'(?<=file).+(?=\.avi)'`. This uses positive and negative lookahead
    assertions to match the number, which then gets removed in
    processing. Defaults to `''`.

    If multiple input files match the same output filename, those files
    will be merged using the :attr:`merge_type` mode.
    '''
    input_start = ConfigProperty(0., 'input_start', float)
    ''' The time in seconds to seek into the video. If specified,
    the output video file will not have the first :attr:`input_start` seconds
    of the original file. Defaults to `0`.
    '''
    input_end = ConfigProperty(0., 'input_end', float)
    ''' The duration of the output video file. If specified,
    the output video file will start at :attr:`input_start` (or zero if not
    specified) seconds and only copy the following :attr:`input_end` seconds.
    If zero, it'll not cut anything. Defaults to `0`.
    '''
    merge_type = ConfigProperty(u'none', 'merge_type', unicode_type)
    ''' If multiple input files match the same output filename as
    specified with :attr:`group_filt`, those files will be merged using the
    mode specified here. Possible modes are `none`, `overlay`, or
    `concatenate`. Defaults to `none`.

        `none`
            If multiple input files are specified for a single output
            file, an error is raised.
        `overlay`
            The output video files will be overlaid, side by side, on
            a single output video file. A maximum of 4 input files is
            supported for any single output file.
        `concatenate`
            The files will be concatenated, one after another in series.
    '''
    out_overwrite = ConfigProperty(False, 'out_overwrite', to_bool)
    ''' Whether a output file will overwrite an already
    existing filename with that name. If False, the file will be
    considered a error and skipped. Defaults to False.
    '''
    out_audio = ConfigProperty(False, 'out_audio', to_bool)
    ''' Whether the audio should be included in the output file. If False, the
    output file will only have video, not audio, Defaults to False.
    '''
    out_codec = ConfigProperty(u'h264', 'out_codec', unicode_type)
    ''' The codec of the output file. This determines whether the output will
    be compressed or uncompressed. Can be one of `raw`, `h264`. Defaults to
    `h264`.

        `raw`
            The output file will be uncompressed.
        `h264`
            The output file will be compressed with h264.
    '''
    crf = ConfigProperty(u'18', 'crf', unicode_type)
    ''' How much the output file should be compressed, when :attr:`out_codec`
    is `h264`. The valid numbers are between `18 - 28`. A larger
    number means higher compression, and typically slower. A lower
    number means less compression and better quality, but a larger
    output file. Defaults to 18.
    '''
    compress_speed = ConfigProperty(u'veryfast', 'compress_speed',
                                    unicode_type)
    ''' Similar to :attr:`crf`, but less effective. The faster
    the compression, the lower the output quality. In practice,
    `veryfast` seems to work well. Can be one of `ultrafast`,
    `superfast`, `veryfast`, `faster`, `fast`, `medium`, `slow`,
    `slower`, `veryslow`. Defaults to `veryfast`.
    '''
    num_threads = ConfigProperty(u'auto', 'num_threads', unicode_type)
    ''' The number of threads FFmpeg should use. Valid values are
    `0`, or `auto`, in which case FFmpeg selects the optimum number. Or
    any integer. The integer should probably not be larger than the
    number of cores on the machine.
    '''
    out_append = ConfigProperty(u'', 'out_append', unicode_type)
    ''' A string that gets appended to the output filename. See
    :attr:`output`. Defaults to `''`.
    '''
    add_command = ConfigProperty(u'', 'add_command', unicode_type)
    ''' An additional string that could be used to add any
    commands to the FFmpeg command line. Defaults to `''`.
    '''
    output = ConfigProperty(u'', 'output', unicode_type)
    ''' The output directory where the output files are saved. For
    input files specified directly, they are placed directly in this
    directory. For input directories, for all the files and subfiles,
    their root directory specified is replaced with this directory, so
    that the output will have the same tree structure as the input.

    Each output filename will be a directory, followed by the input
    filename without the extension, with all matches to :attr:`group_filt`
    deleted. Followed by the :attr:`out_append` string and finally followed
    by the extension, which is `.avi` if :attr:`out_codec` is `raw`,
    otherwise it's '.mp4'. Defaults to `''`.
    '''
    pre_process = ConfigProperty(u'', 'pre_process', unicode_type)
    '''
    When specified, we run the command given in :attr:`pre_process`, where
    the first instance of `{}` in :attr:`pre_process` is replaced by the
    source filename (the first, if there's more than one source file for this
    output file). This command is run from an internally created second
    process. Example commands is::

        ffprobe {}

    which will run ffprobe on the input file. The output of this command will
    be used with :attr:`pre_process_pat`.
    '''
    pre_process_pat = ConfigProperty(u'', 'pre_process_pat', unicode_type)
    '''
    When :attr:`pre_process` is provided, we use this pattern to process the
    output of that command. For the first step, we use the
    :attr:`pre_process_pat` python regex to match the output of
    :attr:`pre_process`. If the output doesn't match the pattern, that file is
    skipped.

    If the output matches, in the next step, we call the python format method
    on the final ffmpeg command that will be executed, where the arguments to
    the format method is the groups of the match object generated from the
    regex match. That formatted string is then used as the executed string.
    '''

    pause_on_skip = ConfigProperty(5, 'pause_on_skip', int)
    '''
    If :attr:`pause_on_skip` files have been skipped, we'll pause. If -1, we
    don't pause.
    '''

    _last_update = 0.
    ''' The last time we received a file_stat queue packet or we updated the
    title. '''
    _last_time = 0.
    ''' The estimated remaining time from the last time that we received a
    file_stat key in the :attr:`queue`. '''
    remaining_time = StringProperty('')
    ''' The estimated remaining time to finish processing. '''
    percent_done = NumericProperty(0.)
    ''' The estimated percent files done, estimated from the input/output
    file sizes. '''
    count_status = StringProperty('')
    ''' A string of the current counting status when the files are enumerated.
    '''
    proc_status = StringProperty('')
    ''' A string of the current processing status when the files are processed.
    '''
    ignored_list = StringProperty('')
    ''' A string of the input files ignored. '''
    rate = StringProperty('')
    ''' The current byte rate at which files are being processed. '''
    cmd = StringProperty('')
    ''' The most recent command line executed. '''
    done_reason = StringProperty('')
    ''' The reason why processing stopped. Can be an error, or if it finished
    successfully.
    '''
    skip_count = NumericProperty(0)
    ''' The total number of input files skipped. '''
    error_log = StringProperty('')
    ''' A string of all the errors encountered so far. '''
    ext_running = BooleanProperty(False)
    ''' Whether the processing is currently running (even when paused). '''
    paused = BooleanProperty(False)
    ''' Whether the processing is currently paused. '''

    go_wgt = ObjectProperty(None)
    ''' The button widget that starts processing. '''
    pause_wgt = ObjectProperty(None)
    ''' The button widget that pauses processing. '''

    def get_status(self):
        skipped = ('Skipped {:d}, '.format(self.skip_count)
                   if self.skip_count else '')
        prefix = running = ''
        rate = self.rate
        done_reason = self.done_reason
        if rate:
            prefix = ' - '
        if done_reason:
            dc = ('[color=00FF00]' if done_reason == 'Done!'
                  else '[color=FF0000]')
            running = '{}{}{}[/color]'.format(prefix, dc, self.done_reason)
        elif self.paused:
            running = '{}[color=F7FF00]paused[/color]'.format(prefix)
        elif self.ext_running:
            running = '{}[color=00FF00]running[/color]'.format(prefix)
        s = '{}\n{}\n{}{}{}'.format(self.count_status, self.proc_status,
                                    skipped, self.rate, running)
        return s
    status = AliasProperty(get_status, None, bind=('skip_count', 'done_reason',
            'count_status', 'proc_status', 'rate', 'ext_running', 'paused'))
    ''' A pretty string describing the current status.
    '''

    def get_title(self):
        if self.ext_running:
            paused = self.paused
            if not paused:
                self.remaining_time = pretty_time(max(0, self._last_time -
                (time.clock() - self._last_update)))
                return ' Processing - {}'.format(self.remaining_time)
            self._last_update = time.clock()
            return ' Processing - {}, Paused'.format(self.remaining_time)
        else:
            return ''
        return ' Processing - {}'.format('') if self.ext_running else ''
    window_title = AliasProperty(get_title, None)
    ''' The window title when this widget has focus.
    '''

    def __init__(self, **kwargs):
        super(Processor, self).__init__(**kwargs)
        self.queue = KivyQueue(Clock.create_trigger(self.read_queue))
        self._last_update = time.clock()

        if 'FFMPEG_ROOT' in os.environ and\
        exists(join(os.environ['FFMPEG_ROOT'], 'bin')):
            base_path = abspath(join(os.environ['FFMPEG_ROOT'], 'bin'))
        else:
            base_path = abspath(dirname(dirname(__file__)))
        ffmpeg_path = join(base_path, 'ffmpeg')
        if exists(ffmpeg_path + '.exe') and isfile(ffmpeg_path + '.exe'):
            ffmpeg_path += '.exe'
        elif not (exists(ffmpeg_path) and isfile(ffmpeg_path)):
            ffmpeg_path = ''
        if not ffmpeg_path:
            logging.exception('Processor: Cannot find ffmpeg binary.')
        self.ffmpeg_path = ffmpeg_path

    def __del__(self):
        self.stop()

    def read_queue(self, *largs):
        '''
        The method that is called by the Kivy thread when it's notified by the
        internal thread of updates. It reads the :attr:`queue` and process any
        waiting updates.
        '''
        queue = self.queue
        while 1:
            try:
                key, val = queue.get()
            except KivyQueue.Empty:
                return
            if key == 'failure':
                self.done_reason = val
                self.go_wgt.state = 'normal'
            elif key == 'clean':
                self.count_status = ''
                self.remaining_time = ''
                self.percent_done = 0.
                self.ignored_list = ''
                self.rate = ''
                self.cmd = ''
                self.done_reason = ''
                self.error_log = ''
                self.skip_count = 0
            elif key.startswith('count'):
                c_out, count_in, dir_count, size, ignored = val
                count_done = ''
                if key == 'count_done':
                    count_done = ' [color=00FF00]DONE![/color]'
                ig = ''
                if ignored:
                    ig = ('(ignored [color=FF00C4]{:d}[/color]) '
                          .format(sum(ignored.values())))
                bg = '[color=00FF00]'
                by = '[color=F7FF00]'
                a = '[/color]'
                self.count_status = ('Counting: {}{:d}{} files &bl;{}{}{}&br;,'
                ' {}{:d}{} directories {}--> {}{:d}{} files.{}'.format(bg,
                count_in, a, by, pretty_space(size), a, by, dir_count, a, ig,
                by, c_out, a, count_done))
                self.ignored_list = '\n'.join(['{}:\t\t{:d}'.format(k, v)
                .expandtabs() for k, v in dict(ignored).iteritems()])
            elif key == 'file_cmd':
                self.cmd = val
            elif key == 'done':
                self.done_reason = 'Done!'
                self.go_wgt.state = 'normal'
            elif key == 'file_stat':
                self._last_time = val[-1]
                self._last_update = time.clock()
                self.remaining_time = pretty_time(val[-1])
                self.percent_done = val[2] / float(val[3])
                bg = '[color=00FF00]'
                by = '[color=F7FF00]'
                a = '[/color]'
                self.proc_status = ('Processing: {}{:d}{} files &bl;{}{}{}&br;'
                ' --> {}{:d}{} &bl;{}{}{} / {}{}{}&br; '.format(by, val[4], a,
                by, pretty_space(val[2]), a, bg, val[6], a, bg,
                pretty_space(val[0]), a, bg, pretty_space(val[1]), a))
                self.rate = ('[color=CDFF00]{}, {} sec[/color]'.
                             format(pretty_space(val[-3], is_rate=True),
                                    pretty_time(val[-2])))
            elif key == 'skipped':
                self.error_log += '\n\n{}'.format(val)
                self.skip_count += 1
                if self.skip_count == self.pause_on_skip:
                    self.pause_wgt.state = 'down'

    def on_keyboard_down(self, keyboard, keycode, text, modifiers):
        ''' Method called by the Kivy thread when a key in the keyboard is
        pressed.
        '''
        if keycode[1] == 'spacebar':
            self.pause_wgt.state = ('down' if self.pause_wgt.state ==
                                    'normal' else 'normal')
        elif keycode[1] == 'enter':
            self.go_wgt.state = 'down'
        elif keycode[1] == 'escape':
            self.go_wgt.state = 'normal'
        else:
            return False
        return True

    def on_keyboard_up(self, keyboard, keycode):
        ''' Method called by the Kivy thread when a key in the keyboard is
        released.
        '''
        return False

    def save_report(self):
        ''' Saves a report of what was processed up to now. See
        :attr:`report`, :attr:`error_list`.
        The report includes the list of files to be processed, and once
        processing started, also the list of files that failed.

        If :attr:`output` is a directory, the
        file will be saved there, otherwise it's saved to the users main
        directory. The report filename starts with ffmpeg_process_report and
        ends with .txt.
        '''
        odir = self.output
        if not isdir(odir):
            odir = dirname(odir)
        if (not odir) or not isdir(odir):
            odir = expanduser('~')
        odir = abspath(odir)
        (fd, _) = tempfile.mkstemp(suffix='.txt',\
        prefix='ffmpeg_process_report_', dir=odir)
        try:
            f = os.fdopen(fd, 'wb')
        except:
            (fd, _) = tempfile.mkstemp(suffix='.txt',
            prefix='ffmpeg_process_report_', dir=expanduser('~'))
            try:
                f = os.fdopen(fd, 'wb')
            except:
                return
        f.write(self.report)
        f.write('Success list:\n')
        for s in self.success_list:
            f.write(s)
            f.write('\n')
        f.write('Error list:\n')
        for err in self.error_list:
            f.write(err)
            f.write('\n')
        f.close()

    def start(self):
        ''' Starts the the processing.

        This launches the second thread that does the disk I/O and starts
        processing the files according to the settings. If it is already
        running, it does nothing.

        :return:

            True, if it successfully started, False otherwise.
        '''
        if self.running and self.thread and self.thread.is_alive():
            return
        self.stop()
        self.running = True
        try:
            self.thread = Thread(target=self.process_thread, name='Processor')
            self.thread.start()
        except:
            logging.error('Processor: Thread failed:\n' +
                          traceback.format_exc())
            self.stop()
            return False
        return True

    def toggle_pause(self):
        ''' Changes whether the thread is paused or running to the opposite
        of its current state.
        '''
        self.pause = not self.pause
        return self.pause

    def stop(self):
        ''' Asks the processing thread started with :meth:`start` to end.
        This will cause processing to stop.
        '''
        self.finish = True
        while self.running and self.thread and self.thread.is_alive():
            time.sleep(0.05)
        self.running = False
        self.thread = None
        self.finish = False

    def enumerate_files(self):
        ''' Returns an iterator that walks all the input files and directories
        to return the files to be processed according to the current
        configuration.

        It walks all the input files and directories, and for every input file
        generates a corresponding output file using the specified output.
        Multiple input files can be assigned to a single output file, in which
        case they are merged according to :attr:`merge_type`.

        :returns:

            A 5-tuple of: a dictionary where keys are output files and
            values is a list of 2-tuples where each 2-tuple is a input file and
            it size. The number of files processed, the number of directories
            processed, the total size of the files processed, and a dictionary
            of ignored files (see `count` in :attr:`queue`). On the final
            iteration, it returns a sorted list of 2-tuples of the output files
            dictionary items.

        :raises FilerException:

            When the the config is inavlid an exception is raised.
        '''
        files_out = defaultdict(list)
        odir = self.output
        if not isdir(odir):
            raise FilerException('{} is not an output directory.'.\
                                 format(self.output))
        odir = abspath(odir)
        ext_out = '.mp4' if self.out_codec == 'h264' else '.avi'
        filt_in = self.input_filter
        filt_group = self.group_filt
        if self.simple_filt:
            filt_in = sub(escape('\\?'), '.', sub(escape('\\*'), '.*',
                                                  escape(filt_in)))
            filt_group = sub(escape('\\?'), '.', sub(escape('\\*'), '.*',
                                                     escape(filt_group)))
        try:
            filt_in = re.compile(filt_in)
            filt_group = re.compile(filt_group)
        except:
            raise FilerException('invalid filtering pattern')
        apnd = self.out_append

        ignored = defaultdict(int)
        src_list = [f.strip(''', '"''') for f in
                    self.input_split_pat.split(self.input)]
        src_list = [abspath(f) for f in src_list if f]

        count = 0
        dir_count = 0
        size = 0
        for f in src_list:
            if isfile(f) and match(filt_in, f):
                sz = getsize(f)
                files_out[join(odir, sub(filt_group, '',\
                splitext(split(f)[1])[0]) + apnd + ext_out)].append((f, sz))
                count += 1
                size += sz
                yield files_out, count, dir_count, size, ignored
            elif isdir(f):
                dir_count -= 1
                for root, _, files in os.walk(f):
                    dir_count += 1
                    if not files:
                        continue
                    root = abspath(root)
                    sdir = root.replace(f, '').strip(sep)
                    for filename in files:
                        filepath = join(root, filename)
                        if isfile(filepath) and match(filt_in, filepath):
                            sz = getsize(filepath)
                            files_out[join(odir, sdir, sub(filt_group, '',\
                            splitext(filename)[0]) + apnd + ext_out)].\
                            append((filepath, sz))
                            count += 1
                            size += sz
                        else:
                            fname, ext = splitext(filename)
                            ignored[ext if ext else fname] += 1
                        yield files_out, count, dir_count, size, ignored
            else:
                fname, ext = splitext(f)
                ignored[ext if ext else fname] += 1
                yield files_out, count, dir_count, size, ignored
        yield sorted(files_out.items(), key=lambda x: x[0]), count, dir_count,\
        size, ignored

    def gen_cmd(self, files):
        '''
        Takes a list of input / output files and returns the full FFmpeg
        command for each output file.

        :Parameters:

            `files`: list
                The list of tuples of all the input / output files.
                It is the list of files returned in the first element in the
                tuple by :attr:`enumerate_files`.

        :return:

            A list of tuples. Each 5-tuple is the full FFmpeg command line
            (string), the total size of the input files for that output
            file, the number of input files, the first input file for this
            output file, and the output file name.
        '''
        merge_type = self.merge_type

        audio = self.out_audio
        s = self.input_start
        e = self.input_end
        seeking = ''
        if s:
            seeking = ' -ss {:.3f}'.format(s)
        if e:
            seeking = '{} -t {:.3f}'.format(seeking, e)
        opts = ' {}'.format(self.add_command) if self.add_command else ''
        if self.out_codec == 'h264':
            opts += ' -vcodec libx264 -preset {} -crf {}'.\
            format(self.compress_speed, self.crf)
        elif self.out_codec == 'raw':
            opts += ' -vcodec rawvideo'
        if not audio:
            opts += ' -an'
        opts += ' -y' if self.out_overwrite else ' -n'
        opts = '{} -threads {}'.format(opts, self.num_threads if
                                       self.num_threads != 'auto' else '0')

        res = []
        for dst, src_list in files:
            src = sorted([f[0] for f in src_list])
            inames = ' -i "{}"'.format('" -i "'.join(src))

            merge_cmd = ''
            if merge_type == 'overlay' and len(src) > 1:
                merge_cmd = ' -filter_complex '
                if len(src) == 2:
                    merge_cmd = ' -filter_complex "[0:0]pad=iw*2:ih[a];'\
                    '[a][1:0]overlay=w" -shortest'
                elif len(src) == 3:
                    merge_cmd = ' -filter_complex "[0:0]pad=iw*2:ih*2[a];'\
                    '[a][1:0]overlay=w[b];[b][2:0]overlay=0:h" -shortest'
                elif len(src) == 4:
                    merge_cmd = ' -filter_complex "[0:0]pad=iw*2:ih*2[a];'\
                    '[a][1:0]overlay=w[b];[b][2:0]overlay=0:h[c];[c][3:0]'\
                    'overlay=w:h" -shortest'
            elif merge_type == 'concatenate' and len(src) > 1:
                if audio:
                    base_str = ('[{}:0] [{}:1] ' * len(src)).format(\
                    *[int(i / 2) for i in range(2 * len(src))])
                    merge_cmd = ' -filter_complex \'{} concat=n={:d}:v=1:a=1 '\
                    '[v] [a]\' -map \'[v]\' -map \'[a]\''.\
                    format(base_str, len(src))
                else:
                    base_str = ('[{}:0] ' * len(src)).format(*range(len(src)))
                    merge_cmd = ' -filter_complex \'{} concat=n={:d}:v=1 '\
                    '[v]\' -map \'[v]\''.format(base_str, len(src))
            res.append(('"{}"{}{}{}{} "{}"'.format(self.ffmpeg_path, inames,
            seeking, merge_cmd, opts, dst), sum([f[1] for f in src_list]),
            len(src), src[0], dst))
        return res

    def process_thread(self):
        ''' The thread that processes the input / output files. It communicates
        with the outside world using :attr:`queue`.

        Upon exit, it sets :attr:`running` to False.
        '''
        queue = self.queue
        put = queue.put
        clock = time.clock
        merge_type = self.merge_type
        put('clean', None)
        pre = self.pre_process
        pre_pat = self.pre_process_pat
        try:
            pre_pat = re.compile(pre_pat)
        except Exception, e:
            put('failure', e.message)
            self.running = False
            return

        itr = self.enumerate_files()
        try:
            s = time.clock()
            while True:
                if self.finish:
                    raise FilerException('Processing terminated by user.')
                files, count, dir_count, size, ignored = itr.next()
                e = time.clock()
                if e - s > 0.3:
                    s = e
                    put('count', (len(files), count, dir_count, size, ignored))
        except StopIteration:
            pass
        except FilerException, e:
            put('failure', e.message)
            self.running = False
            return
        self.error_list = []
        self.success_list = []
        file_str = '\n'.join(['{} <-- {}'.format(k, ','.join([vv[0] for vv in\
            v])) for k, v in files])
        ignored_str = '\n'.join(['{}:{:d}'.format(k, v) for k, v in
                                 dict(ignored).iteritems()])
        self.report = 'File list:\n{}\nIgnored list:\n{}\n'.format(file_str,
                                                                   ignored_str)
        put('count_done', (len(files), count, dir_count, size, ignored))
        for k, v in files:
            if len(v) > 1 and merge_type == 'none':
                put('failure', 'More than one input file was provided for a '\
                    'single output file, and merge was not specified.')
                self.running = False
                return
            if len(v) > 1 and pre:
                put('failure', 'More than one input file was provided for a '\
                'single output file, and pre-processing was not specified.')
                self.running = False
                return
            elif len(v) > 4 and merge_type == 'overlay':
                put('failure', 'More than 4 input files was provided for a '\
                    'single output file - not currently supported for overlay.'
                    )
                self.running = False
                return

        error_list = self.error_list
        success_list = self.success_list
        out_size_done = 0
        out_size_total = 0
        in_size_done = 0
        in_size_total = size
        in_count_done = 0
        in_count_total = count
        out_count_done = 0
        out_count_total = len(files)
        bps = 0.
        time_total = 0.
        elapsed = 0.0000001
        ts = clock()
        t_left = 0
        for cmd, fsize, fcount, src, dst in self.gen_cmd(files):
            try:
                if self.finish or self.pause:
                    elapsed = clock() - ts
                    while self.pause and not self.finish:
                        sleep(.1)
                    if self.finish:
                        put('failure', 'Processing terminated by user.')
                        self.running = False
                        return
                    ts = clock()
                d = dirname(dst)
                if not exists(d):
                    try:
                        makedirs(d)
                    except Exception as e:
                        pass
                if pre:
                    info = sp.STARTUPINFO()
                    info.dwFlags = sp.STARTF_USESHOWWINDOW
                    info.wShowWindow = sp.SW_HIDE
                    sprocess = sp.Popen(pre.format(src), stdout=sp.PIPE,
                        stderr=sp.PIPE, stdin=sp.PIPE, startupinfo=info)
                    sprocess.stdin.close()
                    stdoutdata, stderrdata = sprocess.communicate()
                    if sprocess.wait():
                        raise FilerException('Pre process error: \n{}\n{}'.\
                                             format(stdoutdata, stderrdata))
                    m = match(pre_pat, stdoutdata)
                    if not m:
                        raise FilerException('Match not found in pre'
                        '-processing output')
                    cmd = cmd.format(*m.groups())
                put('file_cmd', cmd)

                info = sp.STARTUPINFO()
                info.dwFlags = sp.STARTF_USESHOWWINDOW
                info.wShowWindow = sp.SW_HIDE
                sprocess = sp.Popen(cmd, stdout=sp.PIPE, stderr=sp.PIPE,
                                    stdin=sp.PIPE, startupinfo=info)
                sprocess.stdin.close()
                stdoutdata, stderrdata = sprocess.communicate()
                if sprocess.wait():
                    raise FilerException('Process error: \n{}\n{}'.\
                                         format(stdoutdata, stderrdata))
                out_size_done += getsize(dst)
                in_size_done += fsize
                in_count_done += fcount
                out_count_done += 1
                time_total = clock() - ts + elapsed
                bps = in_size_done / time_total
                out_size_total = int(in_size_total / float(in_size_done) *
                                     out_size_done)
                t_left = (in_size_total - in_size_done) / bps
                put('file_stat', (out_size_done, out_size_total, in_size_done,
                                  in_size_total, in_count_done, in_count_total,
                                  out_count_done, out_count_total, bps,
                                  time_total, t_left))
                success_list.append('{}\n{}'.format(cmd, stderrdata))
            except Exception as e:
                in_size_total -= fsize
                msg = '{}\n{}'.format(cmd, e.message)
                error_list.append(msg)
                put('skipped', msg)
        put('done', None)

        self.running = False
"""
