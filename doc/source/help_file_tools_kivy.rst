.. _help_file_tools_kivy:

File Tools Help
===============

:doc:`help_kivy.rst`

Tools to manipulate video files en-masse using patterns. It can
move/copy/verify/delete files based on a list of input files and patterns
determining how the output files should look.

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

`preview mode button`:
    When in preview mode, operations on the files are simulated but are not
    actually performed. That is when clicking start, the log will show
    what operations would be performed, but no operation is actually performed.
    Also, it'll pause after each new input file is simulated.

`Save report button`:
    The save report button, saves a report of which files were processed up
    till now. The report includes the list of files to be processed, and once
    processing started, also the list of files that failed.

    If `output` is a directory, the report will be saved there, otherwise it's
    saved to the users main directory. The report filename starts with
    ffmpeg_process_report and ends with .txt.

Configuration and Options
--------------------------

    :doc:`help_config_file_tools_kivy.rst`
