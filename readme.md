Filers
=======


See http://matham.github.io/filers/index.html for docs.

Installation
-------------

This a project for acquiring and, manipulating video files, as well as
organizing and re-ordering files en-masse.

To run, you do ``python main.py``.

Filers requires the following projects:

* python
* kivy
* kivy garden - FileBrowser
* ffpyplyaer
* psutil
* six


Packaging
-------------
To package Filers as an exe with pyinstaller, from Filers root directory
execute:

    python path_to_pyinstaller/pyinstaller.py pyinstaller/filers.spec

and that will generate a dist directory containing the `Filers.exe`.
