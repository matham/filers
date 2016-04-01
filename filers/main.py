'''
TODO: keyboard selection and manipulation.
'''

import kivy
import sys
from os.path import dirname, join, exists, abspath, isdir
import six

from kivy.config import Config
try:
    Config.set('kivy', 'exit_on_escape', 0)
    kivy.require('1.9.1')
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
from kivy.factory import Factory
from kivy.modules import inspector
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.behaviors import FocusBehavior
from kivy.config import ConfigParser
import kivy.garden.filebrowser
import logging
from filers import __version__
from filers import config_name, root_data_path, root_install_path

from filers.record import exit_players, Players
import filers.misc_widgets
# from filers.process import Processor
# from filers.file_tools import FileTools

__all__ = ('MainFrame', 'FilersApp', 'run_filers')


class MainFrame(FocusBehavior, BoxLayout):
    ''' Root widget that is returned by the :attr:`FilersApp.build` method.
    This contains all the gui widgets.
    '''

    pass


class FilersApp(App):
    ''' The filer app class. '''

    filebrowser = ObjectProperty(None)
    ''' The :class:`PopupBrowser` instance. '''

    def build(self):
        self.filebrowser = Factory.get('PopupBrowser')()
        root = abspath(dirname(__file__))
        Builder.load_file(join(root_install_path, 'record.kv'))
        # Builder.load_file(join(root, 'process.kv'))
        # Builder.load_file(join(root, 'file_tools.kv'))
        frame = MainFrame()
        # inspector.create_inspector(Window, frame)
        return frame

    def on_start(self):
        self.config_filers = ConfigParser(name=config_name)
        ini = self.config_filers
        config_path = join(root_data_path, 'filers.ini')
        if not exists(config_path):
            with open(config_path, 'w'):
                pass
        ini.read(config_path)

        self.set_tittle()
        Clock.schedule_interval(self.set_tittle, 1)

    def set_tittle(self, *largs):
        ''' Sets the title of the window using the currently running
        tab. This is called at 1Hz. '''
        Window.set_title('Filers v{}, CPL lab.{}'.format(
            __version__, Players.get_window_title()))

    def assign_path(
            self, text, path, selection, filename, fileselect=False,
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
            `filename`: str
                The text in the filename filed in the browser.
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
        files = [abspath(join(path, f)) for f in selection]
        for i in range(len(files)):
            if (not fileselect) and not isdir(files[i]):
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
    logging.root.setLevel(logging.INFO)

    a = FilersApp()
    err = None
    try:
        a.run()
    except:
        err = sys.exc_info()
    exit_players()
    if err is not None:
        six.reraise(*err)


if __name__ == '__main__':
    run_filers()
