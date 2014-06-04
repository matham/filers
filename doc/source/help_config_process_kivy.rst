Process
=======

:doc:`help_process_kivy.rst`, :doc:`help_kivy.rst`

Merge Mode
----------

Config key: merge_type

If multiple input files match the same output filename as
specified with `group_filt`, those files will be merged using the
mode specified here. Possible modes are `none`, `overlay`, or
`concatenate`. Defaults to `none`.

    `none`
        If multiple input files are specified for a single output
        file, an error is raised.
    `overlay`
        The output video files will be overlaid, side by side, on
        a single output video file. A maximum of 4 input files is
        supported for any single output file.
    `concatenate`
        The files will be concatenated, one after another in series.

Append
------

Config key: out_append

A string that gets appended to the output filename. See
`output`. Defaults to `''`.

Output
------

Config key: output

The output directory where the output files are saved. For
input files specified directly, they are placed directly in this
directory. For input directories, for all the files and subfiles,
their root directory specified is replaced with this directory, so
that the output will have the same tree structure as the input.

Each output filename will be a directory, followed by the input
filename without the extension, with all matches to `group_filt`
deleted. Followed by the `out_append` string and finally followed
by the extension, which is `.avi` if `out_codec` is `raw`,
otherwise it's '.mp4'. Defaults to `''`.

Threads
-------

Config key: num_threads

The number of threads FFmpeg should use. Valid values are
`0`, or `auto`, in which case FFmpeg selects the optimum number. Or
any integer. The integer should probably not be larger than the
number of cores on the machine.

Pre Process Pattern
-------------------

Config key: pre_process_pat

When `pre_process` is provided, we use this pattern to process the
output of that command. For the first step, we use the
`pre_process_pat` python regex to match the output of
`pre_process`. If the output doesn't match the pattern, that file is
skipped.

If the output matches, in the next step, we call the python format method
on the final ffmpeg command that will be executed, where the arguments to
the format method is the groups of the match object generated from the
regex match. That formatted string is then used as the executed string.

Input Delay
-----------

Config key: input_start

The time in seconds to seek into the video. If specified,
the output video file will not have the first `input_start` seconds
of the original file. Defaults to `0`.

Input Cutoff
------------

Config key: input_end

The duration of the output video file. If specified,
the output video file will start at `input_start` (or zero if not
specified) seconds and only copy the following `input_end` seconds.
If zero, it'll not cut anything. Defaults to `0`.

Grouping Filter
---------------

Config key: group_filt

The matching string parts to remove to get the output
filename. If `simple_filt` is True, it uses `*` to match any group
of chars, and `?` to match a single char. If `simple_filt` is
False, it uses a python regex for the matching. This really only
makes sense with a regex. This is mostly useful when merging
files.

For example, say we have two files called `Video file1.avi`,
and `Video file2.avi`, and we wish to merge them into a new file
called `Video file.avi`. Then `group_filt` will be
`'(?<=file).+(?=\.avi)'`. This uses positive and negative lookahead
assertions to match the number, which then gets removed in
processing. Defaults to `''`.

If multiple input files match the same output filename, those files
will be merged using the `merge_type` mode.

Keep Audio
----------

Config key: out_audio

Whether the audio should be included in the output file. If False, the
output file will only have video, not audio, Defaults to False.

Input Files Filter
------------------

Config key: input_filter

The filter to use to filter the input files. See
`simple_filt`. Defaults to `'*.avi'`.

Speed
-----

Config key: compress_speed

Similar to `crf`, but less effective. The faster
the compression, the lower the output quality. In practice,
`veryfast` seems to work well. Can be one of `ultrafast`,
`superfast`, `veryfast`, `faster`, `fast`, `medium`, `slow`,
`slower`, `veryslow`. Defaults to `veryfast`.

Crf
---

Config key: crf

How much the output file should be compressed, when `out_codec`
is `h264`. The valid numbers are between `18 - 28`. A larger
number means higher compression, and typically slower. A lower
number means less compression and better quality, but a larger
output file. Defaults to 18.

Pre Processing
--------------

Config key: pre_process

When specified, we run the command given in `pre_process`, where
the first instance of `{}` in `pre_process` is replaced by the
source filename (the first, if there's more than one source file for this
output file). This command is run from an internally created second
process. Example commands is::

    ffprobe {}

which will run ffprobe on the input file. The output of this command will
be used with `pre_process_pat`.

Input Files
-----------

Config key: input

The list of input files and folders to be processed. It is
a comma (plus optional spaces) separated list. File or directory names
that contain a space, should be quoted with `"`. Triple clicking on this
field will launch a file browser.
Defaults to `u''`.

Additional Commands
-------------------

Config key: add_command

An additional string that could be used to add any
commands to the FFmpeg command line. Defaults to `''`.

Simple / Regex Filtering
------------------------

Config key: simple_filt

Whether the filter we use to filter the input files with
uses the simple common format (where * - match anything, ? match any single
char), if True. If False, it's a python regex string. Defaults to True.

Output Type
-----------

Config key: out_codec

The codec of the output file. This determines whether the output will
be compressed or uncompressed. Can be one of `raw`, `h264`. Defaults to
`h264`.

    `raw`
        The output file will be uncompressed.
    `h264`
        The output file will be compressed with h264.

Overwrite
---------

Config key: out_overwrite

Whether a output file will overwrite an already
existing filename with that name. If False, the file will be
considered a error and skipped. Defaults to False.

