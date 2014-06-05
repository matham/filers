'''
Application that can record and process video using FFmpeg. It can also
manipulate files ensuring that they are not lost in the process.
'''

__all__ = ('FilerException', 'config_name')

__version__ = '0.1'


config_name = 'Filers'
''' The name of the :py:class:`~kivy.config.ConfigParser` that configures
the classes. Defaults to `'Filers'`.
'''


class FilerException(Exception):
    ''' Filers exception class.
    '''
    pass
