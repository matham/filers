
# TDOD: filter config values for errors.

__all__ = ('MainFrame', 'FilersApp', 'run_filers')

import kivy
import sys
import os
from os.path import dirname, join
import six
from functools import partial

from kivy.config import Config
try:
    Config.set('kivy', 'exit_on_escape', 0)
    kivy.require('1.8.1')
    from kivy.base import EventLoop
    EventLoop.ensure_window()
    from kivy.clock import Clock
    Clock.max_iteration = 20
except:
    if 'SPHINX_DOC_INCLUDE' not in os.environ:
        raise
from kivy.core.window import Window
from kivy.app import App
from kivy.properties import ObjectProperty, ListProperty, StringProperty
from kivy.lang import Builder
from kivy.compat import PY2
from kivy.modules import inspector
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.behaviors import FocusBehavior
from kivy.config import ConfigParser
import logging
from kivy.logger import Logger, FileHandler as kivy_handler
logging.root = Logger
from __init__ import __version__ as filers_version

import ffpyplayer
from ffpyplayer.tools import set_log_callback
logging.info('VideoFFPy: Using ffpyplayer {}'.format(ffpyplayer.version))

from filers.record import Recorder
from filers.process import Processor
from filers.file_tools import FileTools
from filers.misc_widgets import PopupBrowser
from filers import config_name
from filers.tools import to_bool, ConfigProperty

unicode_type = unicode if PY2 else str
'''
Unicode type used to convert anything into unicode.
'''

ConfigProperty = partial(ConfigProperty, section='Filers',
                         config_name=config_name)
'''
A partially initialized :py:class:`~kivy.properties.ConfigParserProperty`.
The section name is `'Filers'` and the Config class name is
:attr:`~filers.config_name`.
'''


class MainFrame(FocusBehavior, BoxLayout):
    ''' Root widget that is returned by the :attr:`FilersApp.build` method.
    This contains all the gui widgets.
    '''

    def keyboard_on_key_down(self, window, keycode, text, modifiers):
        if super(MainFrame, self).keyboard_on_key_down(window, keycode, text,
                                                       modifiers):
            return True
        return self.panel.active_wgt.on_keyboard_down(window, keycode, text,
                                                      modifiers)

    def keyboard_on_key_up(self, window, keycode):
        if super(MainFrame, self).keyboard_on_key_up(window, keycode):
            return True
        return self.panel.active_wgt.on_keyboard_up(window, keycode)


class FilersApp(App):
    ''' The filer app class. '''

    version = filers_version
    ''' Filers version. '''
    rec_wgt = ObjectProperty(None)
    ''' The :class:`~filers.record.Recorder` widget instance. '''
    proc_wgt = ObjectProperty(None)
    ''' The :class:`~filers.process.Processor` widget instance. '''
    files_wgt = ObjectProperty(None)
    ''' The :class:`~filers.file_tools.FileTools` widget instance. '''

    filebrowser = ObjectProperty(None)
    ''' The :class:`~filers.misc_widget.PopupBrowser` instance. '''

    last_src_path = ConfigProperty(u'', 'last_src_path', unicode_type)
    '''  The last path that file browser opened while trying to save a file.
    Defaults to user's documents directory if not provided. '''
    last_tgt_path = ConfigProperty(u'', 'last_tgt_path', unicode_type)
    '''  The last path that file browser opened while trying to read a file.
    Defaults to user's documents directory if not provided. '''
    display_color = ConfigProperty(True, 'display_color', to_bool)
    ''' Whether the recorder should output images in color or black & white.
    If `True`, it outputs color. Defaults to `True`. '''

    filers_log = ListProperty([])
    ''' A list of the most recent output log lines. '''
    help_source = StringProperty('')
    ''' The path to the root rst file that contains the user help for Filers.
    If it's a compiled exe, we look for `./doc/source/help_kivy.rst`,
    otherwise, we look for `../doc/source/help_kivy.rst`
    '''

    def build(self):
        self.filebrowser = PopupBrowser()
        root = os.path.abspath(dirname(__file__))
        Builder.load_file(join(root, 'record.kv'))
        Builder.load_file(join(root, 'process.kv'))
        Builder.load_file(join(root, 'file_tools.kv'))
        frame = MainFrame()
        #inspector.create_inspector(Window, frame)
        return frame

    def on_start(self):

        if getattr(sys, 'frozen', False):
            app_path = dirname(sys.executable)
            self.help_source = join(dirname(__file__), 'doc', 'source',
                                    'help_kivy.rst')
        else:
            app_path = dirname(__file__)
            self.help_source = join(dirname(dirname(__file__)), 'doc',
                                    'source', 'help_kivy.rst')

        self.config_filers = ConfigParser(name=config_name)
        ini = self.config_filers
        config_path = os.path.join(app_path, 'filers.ini')
        if not os.path.exists(config_path):
            with open(config_path, 'w'):
                pass
        ini.read(config_path)
        if not self.last_src_path:
            self.last_src_path = os.path.expanduser('~/')
        if not self.last_tgt_path:
            self.last_tgt_path = os.path.expanduser('~/')

        self.set_tittle()
        self.rec_wgt.filers_start()
        Clock.schedule_interval(self.set_tittle, 1)

    def set_tittle(self, *largs):
        ''' Sets the title of the window using the currently running
        tab. This is called at 1Hz. '''
        Window.set_title('Filers v' + self.version + ', CPL lab.' +\
        self.rec_wgt.window_title + self.proc_wgt.window_title +\
        self.files_wgt.window_title)

    def assign_path(self, text, path, selection, fileselect=False,
                    quote=False):
        ''' Takes a list of selected files and returns it as a string with
        possibly quoted filenames.

        :Parameters:

            `text`: kivy Label
                A object whose `text` parameter will be set with the resulting
                string.
            `path`: str
                The root path in which the filenames in `selection` are
                contained.
            `selection`: list
                A list of filenames currently selected.
            `fileselect`: bool
                Whether we would convert all the selected files into a
                their directories, e.g. if only directories should be selected.
                Defaults to False.
            `quote`: bool
                Whether filenames with spaces in them should be quoted with
                `"`. Defaults to False.
        '''
        abspath = os.path.abspath
        join = os.path.join
        files = [abspath(join(path, f)) for f in selection]
        for i in range(len(files)):
            if (not fileselect) and not os.path.isdir(files[i]):
                files[i] = dirname(files[i])
        if quote:
            for i in range(len(files)):
                if ' ' in files[i] or ',' in files[i]:
                    files[i] = '"{}"'.format(files[i])
        text.text = ', '.join(files)


def run_filers():
    '''
    Runs the filers application.
    '''

    def request_close(*largs, **kwargs):
        if kwargs.get('source', None) == 'keyboard':
            return True
    Window.bind(on_request_close=request_close)

    logger_func = {'quiet': logging.critical, 'panic': logging.critical,
                   'fatal': logging.critical, 'error': logging.error,
                   'warning': logging.warning, 'info': logging.info,
                   'verbose': logging.debug, 'debug': logging.debug}

    def _log_callback(message, level):
        message = message.strip()
        if message:
            logger_func[level]('ffpyplayer: {}'.format(message))

    set_log_callback(_log_callback)
    logging.root.setLevel(logging.INFO)

    a = FilersApp()
    kivy_writer = kivy_handler._write_message

    def new_write(self, record):
        ''' Writes the log line to the log list. It removes to ensure the log
        list only contains 100 items.
        '''
        try:
            msg = ('[%-18s] ' % record.levelname) + record.msg.\
            decode('utf-8').replace('\x00', '')
        except:
            msg = 'Cannot display log line.'
        a.filers_log.append(msg)
        del a.filers_log[:max(0, len(a.filers_log) - 100)]
        kivy_writer(self, record)
    kivy_handler._write_message = new_write

    err = None
    try:
        a.run()
    except:
        err = sys.exc_info()
    finally:
        set_log_callback(None)
    if a.rec_wgt:
        a.rec_wgt.stop()
    if a.proc_wgt:
        a.proc_wgt.stop()
    if a.files_wgt:
        a.files_wgt.stop()
    if err:
        six.reraise(*err)


if __name__ == '__main__':
    run_filers()
