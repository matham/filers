'''Filers
===========

Application that can record and process video.
'''

import sys
from os.path import dirname, join

__all__ = ('FilerException', )

__version__ = '0.2-dev'

root_install_path = dirname(__file__)
'''The root directory where filers is installed, including when compiled
as an exe.
'''
if hasattr(sys, '_MEIPASS'):
    root_install_path = sys._MEIPASS

root_data_path = join(dirname(__file__), 'data')
'''The directory for filers' data, including when compiled as an exe.
'''
if hasattr(sys, '_MEIPASS'):
    root_data_path = sys._MEIPASS


class FilerException(Exception):
    ''' Filers exception class.
    '''
    pass
