'''Filers App
===============

The main app.
'''

from os.path import dirname, join, abspath, isdir
from functools import partial
from cplcom.app import CPLComApp, run_app as run_cpl_app

from kivy.core.window import Window
from kivy.lang import Builder
from kivy import resources
from kivy.clock import Clock
from cplcom.config import populate_dump_config

from filers import __version__
from filers.record import exit_players, Players
# from filers.process import exit_converter, VideoConverterController
import filers.misc_widgets
# from filers.file_tools import FileTools

__all__ = ('FilersApp', 'run_app')


class FilersApp(CPLComApp):
    ''' The filer app class. '''

    @classmethod
    def get_config_classes(cls):
        d = super(FilersApp, cls).get_config_classes()
        d.update(Players.get_config_classes())
        return d

    def __init__(self, **kwargs):
        super(FilersApp, self).__init__(**kwargs)
        settings = populate_dump_config(
            self.ensure_config_file(self.json_config_path), {'app': FilersApp})

        for k, v in settings['app'].items():
            setattr(self, k, v)

    def build(self):
        Builder.load_file(join(dirname(__file__), 'record.kv'))
        # Builder.load_file(join(dirname(__file__), 'process.kv'))
        # Builder.load_file(join(dirname(__file__), 'file_tools.kv'))
        return super(FilersApp, self).build()

    def on_start(self):
        self.set_tittle()
        Clock.schedule_interval(self.set_tittle, 1)

    def set_tittle(self, *largs):
        ''' Sets the title of the window using the currently running
        tab. This is called at 1Hz. '''
        return
        Window.set_title('Filers v{}, CPL lab.{}{}'.format(
            __version__, Players.get_window_title(),
            VideoConverterController.get_window_title()))

    def check_close(self):
        if Players.is_playing():
            self._close_message = 'Cannot close while media is still playing.'
            return False
        return True

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
        text.text = ', '.join(sorted(set(files)))


def _cleanup():
    exit_players()
    # exit_converter()

run_app = partial(run_cpl_app, FilersApp, _cleanup)
'''The function that starts the GUI and the entry point for
the main script.
'''

if __name__ == '__main__':
    run_app()
