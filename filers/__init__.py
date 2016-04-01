'''
Application that can record and process video using FFmpeg. It can also
manipulate files ensuring that they are not lost in the process.
'''

import sys
from os.path import dirname, join

__all__ = ('FilerException', 'config_name')

__version__ = '0.2-dev'

root_install_path = dirname(__file__)
if hasattr(sys, '_MEIPASS'):
    root_install_path = sys._MEIPASS

root_data_path = join(dirname(__file__), 'data')
if hasattr(sys, '_MEIPASS'):
    root_data_path = sys._MEIPASS

config_name = "Filers"


class FilerException(Exception):
    ''' Filers exception class.
    '''
    pass
