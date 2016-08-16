.. _install-filers:

*************
Installation
*************

Dependencies
-------------

    * Python 2.7, 3.3+
    * `CPLCom <https://matham.github.io/cplcom/installation.html>`_
    * `FFPyPlayer <https://matham.github.io/ffpyplayer/installation.html>`_
    * `PyFlyCap2 <https://matham.github.io/pyflycap2/installation.html>`_
    * `PyBarst <https://matham.github.io/pybarst/installation.html>`_
    * `Kivy nightly <http://kivy.org/docs/installation/installation-windows.html>`_
    * psutil, six (``pip install psutil six``)

Filers
-------
After installing the dependencies Filers can be installed using::

    pip install https://github.com/matham/filers/archive/master.zip

*************
Packaging
*************

To package Filers as an exe on windows, pyinstaller
(`pip install --upgrade pyinstaller`) is required. Then, from Filers root
directory execute:

    python -m PyInstaller packaging/filers.spec

and that will generate a dist directory containing the `Filers.exe`.
