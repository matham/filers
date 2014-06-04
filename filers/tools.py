''' A module that provides common tools.
'''

__all__ = ('KivyQueue', 'pretty_time', 'pretty_space', 'str_to_float',
           'hashfile', 'to_bool', 'ConfigProperty')

try:
    import Queue as queue
    from Queue import Queue
except:
    import queue
    from queue import Queue
from kivy.properties import ConfigParserProperty


class KivyQueue(Queue):
    '''
    A Multithread safe class that calls a callback whenever an item is added
    to the queue. Instead of having to poll or wait, you could wait to get
    notified of additions.

    >>> def callabck():
    ...     print('Added')
    >>> q = KivyQueue(notify_func=callabck)
    >>> q.put('test', 55)
    Added
    >>> q.get()
    ('test', 55)

    :param notify_func: The function to call when adding to the queue
    '''

    Empty = queue.Empty

    notify_func = None

    def __init__(self, notify_func, **kwargs):
        Queue.__init__(self, **kwargs)
        self.notify_func = notify_func

    def put(self, key, val):
        '''
        Adds a (key, value) tuple to the queue and calls the callback function.
        '''
        Queue.put(self, (key, val), False)
        self.notify_func()

    def get(self):
        '''
        Returns the next items in the queue, if non-empty, otherwise a
        :py:attr:`Queue.Empty` exception is raised.
        '''
        return Queue.get(self, False)


def pretty_time(seconds):
    '''
    Returns a nice representation of a time value.

    >>> pretty_time(36574)
    '10:9:34.0'

    :param seconds: The number, in seconds, to convert to a string.
    '''
    seconds = int(seconds * 10)
    s, ms = divmod(seconds, 10)
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    if h:
        return '{0:d}:{1:d}:{2:d}.{3:d}'.format(h, m, s, ms)
    elif m:
        return '{0:d}:{1:d}.{2:d}'.format(m, s, ms)
    else:
        return '{0:d}.{1:d}'.format(s, ms)


def pretty_space(space, is_rate=False):
    '''
    Returns a nice string representation of a number representing either size,
    e.g. 10 MB, or rate, e.g. 10 MB/s.

    >>> pretty_space(10003045065)
    '9.32 GB'
    >>> tools.pretty_space(10003045065, is_rate=True)
    '9.32 GB/s'

    :param space: The number to convert.
    :param is_rate:
        Whether the number represents size or rate. Defaults to False.
    '''
    t = '/s' if is_rate else ''
    for x in ['bytes', 'KB', 'MB', 'GB']:
        if space < 1024.0:
            return "%3.2f %s%s" % (space, x, t)
        space /= 1024.0
    return "%3.2f %s%s" % (space, 'TB', t)


def str_to_float(strnum, minval=0, maxval=2 ** 31 - 1, err_max=True,
                 val_type=float, err_val=None):
    '''
    Returns a integer or float given a string possibly containing a number.

    >>> str_to_float('9.578')
    9.578
    >>> str_to_float('9.a578', err_max=False)
    0

    :param strnum: The string containing the number.
    :param minval: The minimum value that can be returned. Defaults to 0.
    :param maxval: The maximum value that can be returned. Defaults to 2**31-1.
    :param err_max:
        Whether to return the maximum or minimum upon error. If
        True, the maximum is returned, otherwise the minimum. Defaults to True.
    :param val_type:
        The type to return. Can be float or int. Defaults to float.
    :param err_val:
        The value to return upon error. If None, either the max or
        min value is used. Otherwise this is used. Defaults to None.
    '''
    try:
        val = val_type(strnum)
    except:
        if strnum == 'True':
            return max(min(1, maxval), minval)
        elif strnum == 'False':
            return max(min(0, maxval), minval)
        val = err_val if err_val is not None else\
        (maxval if err_max else minval)
    if val < minval or val > maxval:
        val = err_val if err_val is not None else\
        (maxval if err_max else minval)
    return val


def hashfile(filename, hasher, blocksize=65536):
    '''
    Returns a hash of the file.

    >>> from hashlib import sha256
    >>> hashfile('filepath', sha256())
    '6Zxvdsfk327*'

    :param filename: The filename of the file to hash.
    :param hasher: A hasher instance to use for computing the hash.
    :param blocksize:
        Splits the file up into blocksizes and reads them piecemeal. Defaults
        to 65536.
    '''
    with open(filename, 'rb') as f:
        buf = f.read(blocksize)
        while len(buf) > 0:
            hasher.update(buf)
            buf = f.read(blocksize)
    return hasher.digest()


def to_bool(val):
    '''
    Takes anything and converts it to a bool type.
    '''
    if val == 'False':
        return False
    return not not val


def ConfigProperty(val, name, val_type, section, config_name):
    '''
    Returns the correct partialy-initialized
    :py:class:`~kivy.properties.ConfigParserProperty` class accoridng to the
    input parameters.

    :Parameters:

        `val`: anything
            The default and error value to use for this property instance.
        `name`: str
            The config key to use for this property instance.
        `val_type`: callable
            The val_type callable to use for this property instance.
        `section`: str
            The config section to use for this property instance.
        `config_name`: str
            The config object name to use for this property instance.

    :returns:

        A :py:class:`~kivy.properties.ConfigParserProperty` instance.
    '''
    return ConfigParserProperty(val, section, name, config_name,
                                 val_type=val_type, errorvalue=val)
