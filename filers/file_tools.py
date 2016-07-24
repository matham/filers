'''File tools
===============

Provides a class that manipulates files en-masse using patterns. It can
move/copy/verify/delete files based on a list of input files and patterns
determining how the output files should look.

Keyboard Keys
--------------

`space`:
    Toggles the current pause state.
`enter`:
    Starts processing.
`escape`:
    Stop the processing.
'''

__all__ = ('FileTools', )

import os
from os import makedirs, remove, chmod
from os.path import join, exists, expanduser, abspath, isdir, isfile, dirname,\
split, splitext, getsize, sep
import stat
import logging
from threading import Thread
import time
import traceback
import tempfile
from functools import partial
import re
from re import match, escape, sub
from hashlib import sha256
import shutil
from collections import defaultdict
from kivy.compat import PY2
from kivy.clock import Clock
from kivy.uix.boxlayout import BoxLayout
from kivy.properties import (NumericProperty, ReferenceListProperty,
    ObjectProperty, ListProperty, StringProperty, BooleanProperty,
    DictProperty, AliasProperty, OptionProperty, ConfigParserProperty)
from filers.tools import (pretty_space, pretty_time, KivyQueue, to_bool,
                          hashfile, ConfigProperty)

from filers import FilerException, config_name
from time import sleep


unicode_type = unicode if PY2 else str
'''
Unicode type used to convert anything into unicode.
'''


ConfigProperty = partial(ConfigProperty, section='File_tools',
                         config_name=config_name)
'''
A partially initialized :py:class:`~kivy.properties.ConfigParserProperty`.
The section name is `'File_tools'` and the Config class name is
:attr:`~filers.config_name`.
'''


class FileTools(BoxLayout):
    '''
    See module description.
    '''

    queue = None
    ''' The :class:`~filers.tools.KivyQueue` with which we communicate with the
    kivy event loop. The work thread sends updates to the kivy thread with this
    queue which is read by :meth:`read_queue`.

        `clean`: None
            Sent when the threads starts.
        `count`: int
            Sent periodically while reading the input files describing
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
        `cmd`: 3-tuple
            Sent for every file as it is processed (e.g. moved) or when
            previewing in preview mode. It's a 3-tuple of the source file, the
            mode (e.g. verifying), and the destination filename.
        `pause`: None
            Sent when the controller should set itself in pause mode,
            because the thread is paused. In preview mode, this is sent after
            every cmd. Otherwise, it might be sent e.g. if too many files were
            skipped.
        `file_stat`: 8-tuple
            Sent after each file that has been processed (e.g. moved)
            containing status information. It's a 8-tuple of: the total size
            of files processed, the total size of all files , the total number
            of files processed, the count of all files, the mode (e.g. move),
            the estimated bps at which things are done, the total time elapsed,
            the estimated time left.
        `skipped`: str
            A string. Sent when the file is skipped due to error. The
            string describes the files involved and the reason.
        `done`: None
            Sent when the thread has completed it's work.
    '''

    thread = None
    ''' The thread that runs our secondary thread. All disk R/W is done from
    that thread. See :attr:`process_thread`. Defaults to None.
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
    a comma (plus optional space) separated list. File or directory names
    that contain a space, should be quoted with `"`. Triple clicking on this
    field will launch a file browser.
    Defaults to `u''`.
    '''
    simple_filt = ConfigProperty(True, 'simple_filt', to_bool)
    ''' Whether the filter we use to filter the input files with
    uses the simple common format (where * - match anything, ? match any single
    char), if True. If False, it's a python regex string. Defaults to True.

    `True`:

        When true, we filter the input files using **\\*** and **?**. For
        example `\*.avi` will match all the avi files and `*.txt` all the .txt
        files. The **?** symbol can be used to match any single character, for
        example, ``video??.avi`` will match files named ``videoab.avi``,
        ``video12.avi`` etc.

        Also, the ``output`` variable is then assumed to be the path to a
        directory into which all the input files will be copied. For example,
        given the following directory structure::

            C:\\videos\\day1\\file1 day1.avi
            C:\\videos\\day1\\file2 day1.avi
            C:\\videos\\day1\\file1 day2.avi
            C:\\videos\\day1\\file2 day2.avi
            C:\\videos\\file10.avi
            C:\\videos\\file11.avi

        If the ``input`` variable is ``"C:\\videos"``, the ``mode`` is
        ``copy``, and the ``output`` variable is ``"C:\\other videos"`` then
        the whole directory structure in ``"videos"`` will be duplicated at
        ``"other videos"``. The resulting files will be as follows::

            C:\\other videos\\day1\\file1 day1.avi
            C:\\other videos\\day1\\file2 day1.avi
            C:\\other videos\\day1\\file1 day2.avi
            C:\\other videos\\day1\\file2 day2.avi
            C:\\other videos\\file10.avi
            C:\\other videos\\file11.avi

    `False`:

        When ``false`` we filter the input files using a python regex. Only
        files that match the regex will be included. For example, if
        ``filter files`` is ``video[0-9]+\.(avi|mp4)`` then it will accept e.g.
        ``video2.avi``, ``video66.mp4``, but not ``video2.txt`` or
        ``video.avi``.

        Also, the ``output`` variable is now a string into which the groups
        of the input filename will be pasted using ``format``. For example, if
        ``filter files`` is
        ``".+(treatment([0-9]+)Day([0-9]+)Video(:?[0-9]+).+)"`` then there are
        3 groups captured by the regex. The three groups are then passed as
        arguments to format called on the ``output`` string. Basically,
        the following operation is done on the contents of ``output``;
        ``output.format(*re.match(re.compile(filter_files), filename).groups())``,
        where ``filename`` is each input file and ``filter_files`` is the
        contents of ``"filter files"``.

        For example, if ``"filter files"`` is
        ``".+(treatment([0-9]+)Day([0-9]+)Video(:?[0-9]+).+)"``, ``"output"``
        is ``"C:\\sorted\\Treatment{1}\\Day{2}\\{0}``, and ``input`` is
        ``C:\\videos"`` and we have the following file structure::

            C:\\videos\\treatment1Day1Video1.avi
            C:\\videos\\treatment1Day1Video3.avi
            C:\\videos\\treatment1Day2Video1.avi
            C:\\videos\\treatment2Day4Video1.avi
            C:\\videos\\treatment2Day4Video2.avi
            C:\\videos\\treatment2Day5Video2.avi

        Then, for each input file above we match the full filename to
        ``".+(treatment([0-9]+)Day([0-9]+)Video(:?[0-9]+).+)"`` which extracts
        3 groups: the filename not including the folder name, the treatment
        number, and the day number. These, when passed to format on the
        contents of ``output`` will create a sorted directory containing a
        folder for each treatment, which in turns contains a folder for each
        day. Finally, each subfolder will contain the videos matching its
        parent folders. The output files will now be::

            C:\\sorted\\Treatment1\\Day1\\treatment1Day1Video1.avi
            C:\\sorted\\Treatment1\\Day1\\treatment1Day1Video3.avi
            C:\\sorted\\Treatment1\\Day2\\treatment1Day2Video1.avi
            C:\\sorted\\Treatment2\\Day4\\treatment2Day4Video1.avi
            C:\\sorted\\Treatment2\\Day4\\treatment2Day4Video2.avi
            C:\\sorted\\Treatment2\\Day5\\treatment2Day5Video2.avi

    .. note::
        When False, as with all regex, special characters need to be escaped.
        For example, ``\\`` needs to be written as ``\\`` to be used as a
        backslash.
    '''
    input_filter = ConfigProperty(u'', 'input_filter', unicode_type)
    ''' The filter to use to filter out input files. See
    :attr:`simple_filt`. Defaults to `''`.
    '''
    mode = ConfigProperty(u'copy', 'mode', unicode_type)
    ''' How to process the files. Can be one of `copy`, `verify`,
    `move`, or `delete originals`. Defaults to `copy`.

        `copy`:
            Will copy the files from source to destination, possibly
            renaming or placing files in different places using the
            `output` pattern. The copied file will be verified after the
            copy with :attr:`verify_type`, an error will be generated for every
            file that does not verify.
        `move`:
            Similar to `copy`, except the original files will be deleted
            after the copy, provided it verified.
        `verify`:
            Will simply verify that the source files can be found
            at the destination, as specified with the :attr:`output` pattern,
            using :attr:`verify_type`. An error will be generated for every
            file that does not verify.
        `delete originals`:
            Similar to what verify does, but then deletes the files that
            verified.

    Whatever the `mode`, all the files generated from the `input` variable
    is compared to the corresponding filename generated from the `output` and
    `filter files` variables using the verification procedure specified with
    `verify type`. For example, when moving, the source files are copied
    from their source location to the target location. Then if the source and
    destination file are verified, the source file is deleted, otherwise,
    an error is logged for this file.

    In all instances, if the verification fails, no further processing is done
    on that file. So e.g. `delete originals` will only delete the source files
    if they verify.
    '''
    verify_type = ConfigProperty(u'size', 'verify_type', unicode_type)
    ''' The algorithm we use to verify that a source file also exists at the
    destination. Can be one of `filename`, `size`, `sha256`. Defaults to
    `size`.

        `filename`:
            simply checks that a file with the given input filename also
            exists at the destination. Whether `simple filter` is `True` or
            `False`, the files are compared without their extensions. For
            example, in this mode, if the input file is `"Video file22.avi"`
            and the output file is `"Video file22.mp4"`, even if their file
            sizes were different it would pass verification.
        `size`:
            checks that the source and destination file sizes are identical,
            ignoring their names. For example, in this mode, if the input file
            is `"Video file22.avi"` and the output file is
            `"New Video file104.mp4"`, as long as their size is the same, in
            bytes, it would pass verification.
        `sha256`:
            uses the sha256 algorithm to verify that the source and destination
            files are identical byte for byte. This ignores the filenames. The
            files would pass verification only if the files are identical.

            .. note::
                The sha256 algorithm is slow and and its speed decreases
                linearly with file size.
    '''
    ext = ConfigProperty(u'', 'ext', unicode_type)
    ''' When provided, and only if :attr:`simple_filt` is True, the output
    filename will have its extension replaced with :attr:`ext`. Defaults to
    `''`. The extension, if provided should include the period, `.`.
    '''
    on_error = ConfigProperty(u'pause', 'on_error', unicode_type)
    ''' What to do when a file that is processed results in an error
    e.g. if it doesn't verify. Can be one of `pause` or `skip`. Defaults to
    `pause`.

        `pause`:
            Skips the file, notifies of error, and then pauses the program.
        `skip`:
            Simply skips the files and notifies of the error.
    '''
    preview = ConfigProperty(True, 'preview', to_bool)
    ''' If True, instead of running the action for this mode,
    it will run through file by file, pausing after each file, showing
    what action would be taken. For example, if the :attr:`mode` is `'move'`,
    it'll show the source and target filenames for each file to be moved,
    pausing after each, while not actually moving. Defaults to `True`.
    '''
    output = ConfigProperty(u'', 'output', unicode_type)
    ''' If :attr:`simple_filt` is True, this is a directory into which the
    source files are e.g. copied. If :attr:`simple_filt` is False, then the
    regex is used to match the source file and then its groups are
    used as substitute in the :attr:`output` string using format. I.e. if
    :attr:`input` is an input file, `pat` is :attr:`input_filter`, then the
    output file name for this input file is::

        output.format(*re.match(re.compile(pat), input).groups())

    Defaults to `u''`.
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
    cmd_lines = []
    ''' A list of the most recent actions that were taken in string form.
    '''
    cmd = StringProperty('')
    ''' A ttring of all the items in :attr:`cmd_lines`. '''
    error_log = StringProperty('')
    ''' A string describing the files that failed in the action. '''
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
    done_reason = StringProperty('')
    ''' The reason why processing stopped. Can be an error, or if it finished
    successfully.
    '''
    skip_count = NumericProperty(0)
    ''' The total number of input files skipped. '''
    _mode_str = {'copy': 'Copying', 'verify': 'Verifying', 'move': 'Moving',
            'delete originals': 'Deleting originals'}
    ''' A dict which expands the current mode into a presentable description.
    '''

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

    ext_running = BooleanProperty(False)
    ''' Whether the processing is currently running (even when paused). '''
    paused = BooleanProperty(False)
    ''' Whether the processing is currently paused. '''

    go_wgt = ObjectProperty(None)
    ''' The button widget that starts processing. '''
    pause_wgt = ObjectProperty(None)
    ''' The button widget that pauses processing. '''

    def get_title(self):
        if self.ext_running:
            paused = self.paused
            if not paused:
                self.remaining_time = pretty_time(max(0, self._last_time -\
                (time.clock() - self._last_update)))
                return ' File tools - {}'.format(self.remaining_time)
            self._last_update = time.clock()
            return ' File tools - {}, Paused'.format(self.remaining_time)
        else:
            return ''
        return ' File tools - {}'.format('') if self.ext_running else ''
    window_title = AliasProperty(get_title, None)
    ''' The window title when this widget has focus.
    '''

    def __init__(self, **kwargs):
        super(FileTools, self).__init__(**kwargs)
        self.queue = KivyQueue(Clock.create_trigger(self.read_queue))
        self._last_update = time.clock()

    def __del__(self):
        self.stop()

    def read_queue(self, *largs):
        '''
        The method that is called by the Kivy thread when it's notified by the
        internal thread of updates. It reads the :attr:`queue` and process any
        waiting updates.
        '''
        while 1:
            try:
                key, val = self.queue.get()
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
                self.cmd_lines = []
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
                ' {}{:d}{} directories {}--> {}{:d}{} files.{}'.format(
                bg, count_in, a, by, pretty_space(size), a, by, dir_count, a,
                ig, by, c_out, a, count_done))
                self.ignored_list = ('\n'.join(['{}:\t\t{:d}'.format(k, v).
                    expandtabs() for k, v in dict(ignored).iteritems()]))
            elif key == 'cmd':
                src, mode, dst = val
                self.cmd_lines.append('[color=00FFFF]{}[/color]: {} '
                                      '[color=FF0000]-->[/color] {}'
                                      .format(self._mode_str[mode], src, dst))
                if len(self.cmd_lines) > 100:
                    del self.cmd_lines[0]
                self.cmd = '\n'.join(self.cmd_lines)
            elif key == 'pause':
                self.pause_wgt.state = 'down'
            elif key == 'done':
                self.done_reason = 'Done!'
                self.go_wgt.state = 'normal'
            elif key == 'file_stat':
                self._last_time = val[-1]
                self._last_update = time.clock()
                self.remaining_time = pretty_time(val[-1])
                self.percent_done = val[0] / float(val[1])
                bg = '[color=00FF00]'
                by = '[color=F7FF00]'
                a = '[/color]'
                self.proc_status = ('{}: {}{:d}{} files &bl;{}{}{}&br;'.
                format(self._mode_str[val[-4]], by, val[2], a, by,
                       pretty_space(val[0]), a))
                self.rate = ('[color=CDFF00]{}, {} sec[/color]'
                             .format(pretty_space(val[-3], is_rate=True),
                                     pretty_time(val[-2])))
            elif key == 'skipped':
                self.error_log += '\n\n{}'.format(val)
                self.skip_count += 1

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
        :attr:`report`, :attr:`error_list`, and :attr:`success_list`.
        The report includes the list of files to be processed, and once
        processing started, also the list of files that succeeded and failed.

        If `output` in the config of :class:`FileTools` is a directory, the
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
        (fd, _) = tempfile.mkstemp(suffix='.txt',
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
            return True
        self.stop()
        self.running = True
        try:
            self.thread = Thread(target=self.process_thread,
                                 name='File_tools')
            self.thread.start()
        except:
            logging.error('File tools: Thread failed:\n' +
                          traceback.format_exc())
            self.stop()
            return False
        return True

    def set_pause(self, pause):
        ''' Sets whether the thread is paused or running.

        :Parameters:

            `pause`: bool
                If True, the state will be set to pause, otherwise, to continue
                running. This only has an effect once processing started.
        '''
        self.pause = pause

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
        generates a corresponding output file using the specified pattern
        matching.

        :returns:

            A 5-tuple of: a dictionary where keys are output files and
            values is a 3-tuple of full filepath, filename, and file size. The
            number of files processed, the number of directories processed, the
            total size of the files processed, and a dictionary of ignored
            files (see `count` in :attr:`queue`). On the final iteration,
            it returns a sorted list of 2-tuples of the output files
            dictionary items.

        :raises FilerException:

            When the the config is inavlid an exception is raised.
        '''
        files_out = {}
        odir = self.output
        simple = self.simple_filt
        ext_new = self.ext
        if simple:
            if not isdir(odir):
                raise FilerException('{} is not an output directory.'.
                                     format(odir))
            odir = abspath(odir)
        filt_in = self.input_filter
        if simple:
            filt_in = sub(escape('\\?'), '.', sub(escape('\\*'), '.*',
                                                  escape(filt_in)))
        try:
            filt_in = re.compile(filt_in)
        except:
            raise FilerException('invalid filtering pattern')

        ignored = defaultdict(int)
        src_list = [f.strip(''', '"''') for f in
                    self.input_split_pat.split(self.input)]
        src_list = [abspath(f) for f in src_list if f]

        count = 0
        dir_count = 0
        size = 0
        for f in src_list:
            m = match(filt_in, f)
            if isfile(f) and m:
                sz = getsize(f)
                name, ext = splitext(split(f)[1])
                if simple:
                    if ext_new:
                        oname = name + ext_new
                    else:
                        oname = name + ext
                    oname = join(odir, oname)
                else:
                    oname = odir.format(*m.groups())
                files_out[(oname, split(oname)[1])] = (f, split(f)[1], sz)
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
                        m = match(filt_in, filepath)
                        if isfile(filepath) and m:
                            sz = getsize(filepath)
                            name, ext = splitext(filename)
                            if simple:
                                if ext_new:
                                    oname = name + ext_new
                                else:
                                    oname = name + ext
                                oname = join(odir, sdir, oname)
                            else:
                                oname = odir.format(*m.groups())
                            files_out[(oname, split(oname)[1])] = (filepath,\
                                split(filepath)[1], sz)
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
        yield sorted(files_out.items(), key=lambda x: x[1][0]), count,\
        dir_count, size, ignored

    def process_thread(self):
        ''' The thread that processes the input / output files. It communicates
        with the outside world using :attr:`queue`.

        Upon exit, it sets :attr:`running` to False.
        '''
        queue = self.queue
        put = queue.put
        clock = time.clock
        mode = self.mode
        verify_mode = self.verify_type
        on_error = self.on_error
        preview = self.preview
        put('clean', None)
        rm_flag = stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO

        def verify(dst, dst_name, src, src_name):
            ''' Verifies using the current mode whether the two files match.
            E.g. `dst` is the full file path, while `dst_name` is just the
            filename.
            '''
            if verify_mode == 'filename':
                return dst_name == src_name
            elif verify_mode == 'size':
                return getsize(dst) == getsize(src)
            elif verify_mode == 'sha256':
                return hashfile(src, sha256()) == hashfile(dst, sha256())
            else:
                return False

        itr = self.enumerate_files()
        try:
            s = time.clock()
            while True:
                if self.finish:
                    raise FilerException('File tools terminated by user.')
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
        file_str = '\n'.join(['{} <-- {}'.format(k[0], v[0]) for k, v in
                              files])
        ignored_str = '\n'.join(['{}:{:d}'.format(k, v) for k, v in
                                 dict(ignored).iteritems()])
        self.report =\
        'Mode: {}\nVerify: {}\nFile list:\n{}\nIgnored list:\n{}\n'.\
        format(mode, verify_mode, file_str, ignored_str)
        put('count_done', (len(files), count, dir_count, size, ignored))

        if preview:
            for (dst, dst_name), (src, src_name, fsize) in files:
                put('cmd', (src, mode, dst))
                self.set_pause(True)
                put('pause', None)
                if self.finish or self.pause:
                    while self.pause and not self.finish:
                        sleep(.1)
                    if self.finish:
                        put('failure', 'File tools terminated by user.')
                        self.running = False
                        return
            put('done', None)
            self.running = False
            return

        error_list = self.error_list
        success_list = self.success_list
        size_done = 0
        size_total = size
        count_done = 0
        count_total = len(files)
        bps = 0.
        time_total = 0.
        elapsed = 0.0000001
        ts = clock()
        t_left = 0
        copy = shutil.copy2
        for (dst, dst_name), (src, src_name, fsize) in files:
            try:
                if self.finish or self.pause:
                    elapsed = clock() - ts
                    while self.pause and not self.finish:
                        sleep(.1)
                    if self.finish:
                        put('failure', 'File tools terminated by user.')
                        self.running = False
                        return
                    ts = clock()
                put('cmd', (src, mode, dst))

                if src == dst:
                    raise FilerException('{}: source and target are identical.'
                                         .format(dst))
                dst_dir = dirname(dst)
                if mode in ('copy', 'move'):
                    if exists(dst):
                        raise FilerException('{}: already exists.'.format(dst))
                    if not exists(dst_dir):
                        try:
                            makedirs(dst_dir)
                        except:
                            pass
                    copy(src, dst)
                    if not verify(dst, dst_name, src, src_name):
                        raise FilerException('{}, {}: verification failed.'.\
                                             format(src, dst))
                    if mode == 'move':
                        try:
                            remove(src)
                        except IOError:
                            chmod(src, rm_flag)
                            remove(src)
                elif mode in ('delete originals', 'verify'):
                    if not verify(dst, dst_name, src, src_name):
                        raise FilerException('{}, {}: verification failed.'.\
                                             format(src, dst))
                    if mode == 'delete originals':
                        try:
                            remove(src)
                        except IOError:
                            chmod(src, rm_flag)
                            remove(src)

                size_done += fsize
                count_done += 1
                time_total = clock() - ts + elapsed
                bps = size_done / time_total
                t_left = (size_total - size_done) / bps
                put('file_stat', (size_done, size_total, count_done,
                                  count_total, mode, bps, time_total, t_left))
                success_list.append('{}: {} --> {}'.format(mode, src, dst))
            except Exception, e:
                size_total -= fsize
                msg = '{}: {} --> {}\nFailed: {}'.format(mode, src, dst,
                                                         str(e))
                error_list.append(msg)
                put('skipped', msg)
                if on_error == 'pause':
                    put('pause', None)
                    self.set_pause(True)
        put('done', None)

        self.running = False
