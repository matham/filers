.. _help_process_kivy:

Processor Help
===============

:doc:`help_kivy.rst`

Tools to manipulate video files en-masse using FFmpeg. It can
compress/uncompress/merge/concatenate or perform other tasks on video files.

Keyboard Keys
-------------

The following keyboard keys are used by this tab:

`space`:
    Toggles the current pause state. When paused, no files will be processed.
    Similar to pressing the pause button.
`enter`:
    Starts processing. When starting processing, we first enumerate the input
    files, once that's done, we processes all the input files one by one.
`escape`:
    Stop the processing. Stops the processing after the currently processed
    file finishes.

`Save report button`:
    The save report button, saves a report of which files were processed up
    till now. The report includes the list of files to be processed, and once
    processing started, also the list of files that failed.

    If `output` is a directory, the report will be saved there, otherwise it's
    saved to the users main directory. The report filename starts with
    ffmpeg_process_report and ends with .txt.

Configuration and Options
--------------------------

    :doc:`help_config_process_kivy.rst`
