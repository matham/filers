File_Tools
==========

:ref:`help_file_tools`, :ref:`help`

Simple / Regex Filtering
------------------------

Config key: simple_filt

Whether the filter we use to filter the input files with
uses the simple common format (where * - match anything, ? match any single
char), if True. If False, it's a python regex string. Defaults to True.

`True`:

    When true, we filter the input files using **\*** and **?**. For
    example `\*.avi` will match all the avi files and `*.txt` all the .txt
    files. The **?** symbol can be used to match any single character, for
    example, ``video??.avi`` will match files named ``videoab.avi``,
    ``video12.avi`` etc.

    Also, the ``output`` variable is then assumed to be the path to a
    directory into which all the input files will be copied. For example,
    given the following directory structure::

        C:\videos\day1\file1 day1.avi
        C:\videos\day1\file2 day1.avi
        C:\videos\day1\file1 day2.avi
        C:\videos\day1\file2 day2.avi
        C:\videos\file10.avi
        C:\videos\file11.avi

    If the ``input`` variable is ``"C:\videos"``, the ``mode`` is
    ``copy``, and the ``output`` variable is ``"C:\other videos"`` then
    the whole directory structure in ``"videos"`` will be duplicated at
    ``"other videos"``. The resulting files will be as follows::

        C:\other videos\day1\file1 day1.avi
        C:\other videos\day1\file2 day1.avi
        C:\other videos\day1\file1 day2.avi
        C:\other videos\day1\file2 day2.avi
        C:\other videos\file10.avi
        C:\other videos\file11.avi

`False`:

    When ``false`` we filter the input files using a python regex. Only
    files that match the regex will be included. For example, if
    ``filter files`` is ``video[0-9]+\.(avi|mp4)`` then it will accept e.g.
    ``video2.avi``, ``video66.mp4``, but not ``video2.txt`` or
    ``video.avi``.

    Also, the ``output`` variable is now a string into which the groups
    of the input filename will be pasted using ``format``. For example, if
    ``filter files`` is
    ``".+(treatment([0-9]+)Day([0-9]+)Video(:?[0-9]+).+)"`` then there are
    3 groups captured by the regex. The three groups are then passed as
    arguments to format called on the ``output`` string. Basically,
    the following operation is done on the contents of ``output``;
    ``output.format(*re.match(re.compile(filter_files), filename).groups())``,
    where ``filename`` is each input file and ``filter_files`` is the
    contents of ``"filter files"``.

    For example, if ``"filter files"`` is
    ``".+(treatment([0-9]+)Day([0-9]+)Video(:?[0-9]+).+)"``, ``"output"``
    is ``"C:\sorted\Treatment{1}\Day{2}\{0}``, and ``input`` is
    ``C:\videos"`` and we have the following file structure::

        C:\videos\treatment1Day1Video1.avi
        C:\videos\treatment1Day1Video3.avi
        C:\videos\treatment1Day2Video1.avi
        C:\videos\treatment2Day4Video1.avi
        C:\videos\treatment2Day4Video2.avi
        C:\videos\treatment2Day5Video2.avi

    Then, for each input file above we match the full filename to
    ``".+(treatment([0-9]+)Day([0-9]+)Video(:?[0-9]+).+)"`` which extracts
    3 groups: the filename not including the folder name, the treatment
    number, and the day number. These, when passed to format on the
    contents of ``output`` will create a sorted directory containing a
    folder for each treatment, which in turns contains a folder for each
    day. Finally, each subfolder will contain the videos matching its
    parent folders. The output files will now be::

        C:\sorted\Treatment1\Day1\treatment1Day1Video1.avi
        C:\sorted\Treatment1\Day1\treatment1Day1Video3.avi
        C:\sorted\Treatment1\Day2\treatment1Day2Video1.avi
        C:\sorted\Treatment2\Day4\treatment2Day4Video1.avi
        C:\sorted\Treatment2\Day4\treatment2Day4Video2.avi
        C:\sorted\Treatment2\Day5\treatment2Day5Video2.avi

.. note::
    When False, as with all regex, special characters need to be escaped.
    For example, ``\`` needs to be written as ``\`` to be used as a
    backslash.

Output Verification
-------------------

Config key: verify_type

The algorithm we use to verify that a source file also exists at the
destination. Can be one of `filename`, `size`, `sha256`. Defaults to
`size`.

    `filename`:
        simply checks that a file with the given input filename also
        exists at the destination. Whether `simple filter` is `True` or
        `False`, the files are compared without their extensions. For
        example, in this mode, if the input file is `"Video file22.avi"`
        and the output file is `"Video file22.mp4"`, even if their file
        sizes were different it would pass verification.
    `size`:
        checks that the source and destination file sizes are identical,
        ignoring their names. For example, in this mode, if the input file
        is `"Video file22.avi"` and the output file is
        `"New Video file104.mp4"`, as long as their size is the same, in
        bytes, it would pass verification.
    `sha256`:
        uses the sha256 algorithm to verify that the source and destination
        files are identical byte for byte. This ignores the filenames. The
        files would pass verification only if the files are identical.

        .. note::
            The sha256 algorithm is slow and and its speed decreases
            linearly with file size.

Input Files Filter
------------------

Config key: input_filter

The filter to use to filter out input files. See
`simple_filt`. Defaults to `''`.

Extension
---------

Config key: ext

When provided, and only if `simple_filt` is True, the output
filename will have its extension replaced with `ext`. Defaults to
`''`. The extension, if provided should include the period, `.`.

Error Handling
--------------

Config key: on_error

What to do when a file that is processed results in an error
e.g. if it doesn't verify. Can be one of `pause` or `skip`. Defaults to
`pause`.

    `pause`:
        Skips the file, notifies of error, and then pauses the program.
    `skip`:
        Simply skips the files and notifies of the error.

Process Mode
------------

Config key: mode

How to process the files. Can be one of `copy`, `verify`,
`move`, or `delete originals`. Defaults to `copy`.

    `copy`:
        Will copy the files from source to destination, possibly
        renaming or placing files in different places using the
        `output` pattern. The copied file will be verified after the
        copy with `verify_type`, an error will be generated for every
        file that does not verify.
    `move`:
        Similar to `copy`, except the original files will be deleted
        after the copy, provided it verified.
    `verify`:
        Will simply verify that the source files can be found
        at the destination, as specified with the `output` pattern,
        using `verify_type`. An error will be generated for every
        file that does not verify.
    `delete originals`:
        Similar to what verify does, but then deletes the files that
        verified.

Whatever the `mode`, all the files generated from the `input` variable
is compared to the corresponding filename generated from the `output` and
`filter files` variables using the verification procedure specified with
`verify type`. For example, when moving, the source files are copied
from their source location to the target location. Then if the source and
destination file are verified, the source file is deleted, otherwise,
an error is logged for this file.

In all instances, if the verification fails, no further processing is done
on that file. So e.g. `delete originals` will only delete the source files
if they verify.

Output
------

Config key: output

If `simple_filt` is True, this is a directory into which the
source files are e.g. copied. If `simple_filt` is False, then the
regex is used to match the source file and then its groups are
used as substitute in the `output` string using format. I.e. if
`input` is an input file, `pat` is `input_filter`, then the
output file name for this input file is::

    output.format(*re.match(re.compile(pat), input).groups())

Defaults to `u''`.

Input Files
-----------

Config key: input

The list of input files and folders to be processed. It is
a comma (plus optional space) separated list. File or directory names
that contain a space, should be quoted with `"`. Triple clicking on this
field will launch a file browser.
Defaults to `u''`.

Preview Mode
------------

Config key: preview

If True, instead of running the action for this mode,
it will run through file by file, pausing after each file, showing
what action would be taken. For example, if the `mode` is `'move'`,
it'll show the source and target filenames for each file to be moved,
pausing after each, while not actually moving. Defaults to `True`.

