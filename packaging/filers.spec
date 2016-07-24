# -*- mode: python -*-
from kivy.tools.packaging.pyinstaller_hooks import get_deps_minimal, hookspath, runtime_hooks
from pyflycap2 import dep_bins
from ffpyplayer import dep_bins as ffbins
from pybarst import dep_bins as pybarst_bins
from kivy.deps import sdl2, glew
from PyInstaller.utils.hooks import collect_submodules, collect_data_files
block_cipher = None

d = get_deps_minimal(video=None, audio=None)
hiddenimports = d['hiddenimports']
excludes = d['excludes']
excludes += ['numpy']
hiddenimports += collect_submodules('ffpyplayer') + collect_submodules('pybarst') \
    + collect_submodules('pyflycap2')
datas = collect_data_files('cplcom') + collect_data_files('filers')

a = Analysis(['../filers/main.py'],
             hookspath=hookspath(),
             datas=datas,
             runtime_hooks=runtime_hooks(),
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             hiddenimports=hiddenimports,
             excludes=excludes)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          exclude_binaries=True,
          name='filers',
          debug=False,
          strip=False,
          upx=True,
          console=True )
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               *[Tree(p) for p in (sdl2.dep_bins + glew.dep_bins + dep_bins +
                 ffbins + pybarst_bins + ['../filers/filers'])],
               strip=False,
               upx=True,
               name='filers')
