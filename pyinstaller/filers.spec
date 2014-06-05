# -*- mode: python -*-
from kivy.tools.packaging.pyinstaller_hooks import install_hooks
install_hooks(globals())

import os
import filers
import ffpyplayer
from os.path import join, dirname
from os import environ
from kivy.garden import filebrowser

base_dir = dirname(dirname(filers.__file__))

a = Analysis([join(base_dir, 'pyinstaller', 'main.py')],
             excludes=['ffpyplayer'])

for d in a.datas:
    if 'pyconfig' in d[0]:
        a.datas.remove(d)
        break

a.datas += [x for x in Tree(dirname(ffpyplayer.__file__), prefix='ffpyplayer/')
             if not x[0].endswith('.pyc')]
a.datas += [x for x in Tree(join(base_dir, 'filers'), prefix='filers/')
            if not x[0].endswith('.pyc') and not x[0].endswith('.ini')]
a.datas += [x for x in Tree(join(base_dir, 'filers', 'media'),
                            prefix='media/')]
a.datas += [x for x in Tree(join(base_dir, 'doc', 'source'),
                            prefix='filers/doc/source')
            if x[0].endswith('_kivy.rst')]
a.datas += [x for x in Tree(dirname(filebrowser.__file__),
                            prefix='libs/garden/garden.filebrowser/')
             if not x[0].endswith('.pyc')]

ffmpeg_root = environ.get('FFMPEG_ROOT')
if ffmpeg_root and os.path.exists(join(ffmpeg_root, 'bin')):
    a.datas += Tree(join(ffmpeg_root, 'bin'))
sdl_root = environ.get('SDL_ROOT')
if sdl_root and os.path.exists(join(sdl_root, 'bin')):
    a.datas += Tree(join(sdl_root, 'bin'))
    bin_path = join(sdl_root, 'bin')

pyz = PYZ(a.pure)
exe = EXE(pyz, [],
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          name=join('dist', 'Filers.exe'),
          debug=False,
          strip=None,
          upx=False,
          console=True,
          icon=join(base_dir, join(base_dir, 'filers', 'media', 'Dancing_rats_clean.ico')))
