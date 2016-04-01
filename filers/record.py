'''Provides a class that plays and records videos.

Keyboard keys
--------------

`space`:
    Starts and stops recording video to an output file.
`enter`:
    Starts playing the input cam.
`escape`:
    Stops the video from playing, and turns off the recorder if recording.
'''

from os.path import isfile, join, dirname, abspath, exists, expanduser
from os.path import isdir
import logging
from threading import Thread, RLock
import psutil
import time
from fractions import Fraction
import traceback
from time import sleep
from functools import partial
from collections import namedtuple, defaultdict
import re
import sys
from math import ceil
import json
try:
    from Queue import Queue
except ImportError:
    from queue import Queue

import ffpyplayer
from ffpyplayer.player import MediaPlayer
from ffpyplayer.pic import get_image_size, Image, SWScale
from ffpyplayer.tools import list_dshow_devices, set_log_callback
from ffpyplayer.tools import get_supported_pixfmts, get_format_codec
from ffpyplayer.writer import MediaWriter

from pybarst.core.server import BarstServer
from pybarst.rtv import RTVChannel
from pyflycap2.interface import GUI, Camera, CameraContext

from kivy.clock import Clock
from kivy.compat import clock
from kivy.uix.behaviors.knspace import KNSpaceBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.screenmanager import ScreenManager
from kivy.uix.popup import Popup
from kivy.properties import (
    NumericProperty, ReferenceListProperty,
    ObjectProperty, ListProperty, StringProperty, BooleanProperty,
    DictProperty, AliasProperty, OptionProperty, ConfigParserProperty)
from kivy.event import EventDispatcher
from kivy.logger import Logger

from filers import config_name, root_data_path, root_install_path
from filers.tools import (str_to_float, pretty_space, pretty_time, KivyQueue,
                          ConfigProperty, to_bool)
from filers .misc_widgets import EventFocusBehavior


__all__ = ('Recorder', )

set_log_callback(logger=Logger, default_only=True)
logging.info('Filers: Using ffpyplayer {}'.format(ffpyplayer.__version__))

VideoMetadata = namedtuple('VideoMetadata', ['fmt', 'w', 'h', 'rate'])


def eat_first(f, val, *largs, **kwargs):
    f(*largs, **kwargs)


def byteify(val):
    if isinstance(val, dict):
        return {byteify(key): byteify(value)
                for key, value in val.iteritems()}
    elif isinstance(val, list):
        return [byteify(element) for element in val]
    elif isinstance(val, unicode):
        return val.encode('utf-8')
    else:
        return val


def exit_players():
    for player in Players.players:
        try:
            player.stop_all(join=True)
        except:
            pass
    p = Players.players_singleton
    if p:
        try:
            p.save_config()
        except Exception as e:
            Logger.error('Players: {}'.format(e))
            Logger.exception(e)


class Players(EventDispatcher):

    settings_path = ConfigParserProperty(
        join(root_data_path, 'recorder.json'), 'Filers',
        'settings_path', config_name)

    cam_grid_rows = NumericProperty(2)

    source_names = {}

    source_cls = {}

    settings_display = None

    container = ObjectProperty(None)

    players = []

    display_update = None

    players_singleton = None

    players_view = ObjectProperty(None)

    def __init__(self, **kwargs):
        super(Players, self).__init__(**kwargs)
        Players.players_singleton = self
        self.source_names = {
            'RTV': RTVPlayer, 'FFmpeg': FFmpegPlayer, 'PTGray': PTGrayPlayer}
        self.source_cls = {v: k for (k, v) in self.source_names.items()}
        self.settings_display = PlayerSettings(players=self)
        self.load_config(self.settings_path)

    @staticmethod
    def get_window_title():
        n = len(Players.players)
        if not n:
            return ''

        c = sum([0 if p.play_state == 'none' else 1 for p in Players.players])
        if c == n:
            return ' - Recorder ({})'.format(n)
        return ' - Recorder ({}/{})'.format(c, n)

    def log_error(self, msg=None, e=None, exc_info=None, level='error'):
        q = self.players_view.error_output.queue
        l = getattr(Logger, level)
        val = msg

        if msg:
            if e:
                val = '{}: {}'.format(msg, repr(e))
                l(val)
            else:
                l(msg)

        if exc_info is not None:
            Logger.error(e, exc_info=exc_info)

        if val:
            q.append(val)

    def load_config(self, filename):
        if not isfile(filename):
            return
        filename = abspath(filename)

        for player in Players.players[:]:
            self.delete_player(player)

        try:
            with open(filename) as fh:
                global_opt, players_opt = json.load(fh)
            global_opt, players_opt = byteify(global_opt), byteify(players_opt)

            for k, v in global_opt.items():
                setattr(self, k, v)
            for d in players_opt:
                self.add_player(settings=d, show=False,
                                cls=d.get('cls', 'FFmpeg'))
        except Exception as e:
            self.log_error(e=e, exc_info=sys.exc_info(), msg='Loading config')
        else:
            if filename:
                self.settings_path = filename

    def save_config(self, filename=None):
        filename = filename or self.settings_path
        if not filename:
            return

        p = self.settings_display and self.settings_display.player
        if p:
            p.read_widget_record_settings()
            p.read_widget_play_settings()

        for p in Players.players:
            p.read_viewer_settings()

        global_opt = self.get_config_dict()
        players_opt = []
        for p in Players.players:
            d = p.get_config_dict()
            players_opt.append(d)

        try:
            with open(filename, 'w') as fh:
                json.dump((global_opt, players_opt), fh, sort_keys=True,
                          indent=4, separators=(',', ': '))
        except Exception as e:
            self.log_error(e=e, exc_info=sys.exc_info(), msg='Loading config')
        else:
            if filename:
                self.settings_path = filename

    def ui_config(self, load, path, selection, filename):
        fname = abspath(join(path, filename))
        if load:
            self.load_config(fname)
        else:
            self.save_config(fname)

    def get_config_dict(self):
        attrs = ['cam_grid_rows']
        return {k: getattr(self, k) for k in attrs}

    def display_update_callback(self, *largs):
        for player in Players.players:
            player.player_view.update_cycle()

    def add_player(self, settings={}, show=True, cls='FFmpeg'):
        player = self.source_names[cls](players=self, **settings)
        Players.players.append(player)
        display = PlayerView(player=player, players=self)
        player.player_view = display
        player.display_widget = display.knspace.display.ids.display.__self__
        self.container.add_widget(display)
        player.write_viewer_settings()

        if self.display_update is None:
            self.display_update = Clock.schedule_interval(
                self.display_update_callback, .1)

        if show:
            self.show_settings(player)

    def replace_player_cls(self, player, new_cls):
        if isinstance(player, self.source_names[new_cls]):
            return

        player.stop_all()
        player.display_widget = None
        try:
            Players.players.remove(player)
        except ValueError:
            pass
        new_player = self.source_names[new_cls](players=self)
        view = new_player.player_view = player.player_view
        view.player = new_player
        Players.players.append(new_player)
        new_player.read_viewer_settings()

        if self.settings_display.parent is not None:
            new_player.display_widget = \
                self.settings_display.knspace.display.ids.display.__self__
            self.settings_display.player = new_player
            new_player.write_widget_settings()
        else:
            print "this shouldn't happen"
            new_player.display_widget = \
                player.player_view.knspace.display.ids.display.__self__
        self.settings_display.knspace.source_type.current = new_cls

    def show_settings(self, player):
        self.settings_display.player = player
        player.write_widget_settings()
        player.display_widget = \
            self.settings_display.knspace.display.ids.display.__self__
        self.settings_display.open()

    def hide_settings(self, player):
        player.read_widget_play_settings()
        player.read_widget_record_settings()
        player.stop()
        self.settings_display.dismiss()
        self.settings_display.player = None
        player.display_widget = \
            player.player_view.knspace.display.ids.display.__self__

    def delete_player(self, player):
        self.settings_display.dismiss()
        player.stop_all()
        self.settings_display.player = None
        try:
            Players.players.remove(player)
        except ValueError:
            pass
        for w in self.container.children:
            if w.player == player:
                self.container.remove_widget(w)
                break
        if not Players.players:
            Clock.unschedule(self.display_update)


class Player(EventDispatcher):

    players = ObjectProperty(None)

    cls = StringProperty('')

    player_view = None

    err_trigger = None

    play_thread = None

    play_state = StringProperty('none')
    '''Can be one of none, starting, playing, stopping.
    '''

    play_lock = None

    play_callback = None
    '''Shared between the event that sets the state to stop and the event that
    sets the state to playing.
    '''

    record_thread = None

    record_state = StringProperty('none')
    '''Can be one of none, starting, recording, stopping.
    '''

    record_lock = None

    record_callback = None
    '''Shared between the event that sets the state to stop and the event that
    sets the state to recording.
    '''

    record_directory = StringProperty(expanduser('~'))

    record_fname = StringProperty('video{}.avi')

    record_fname_count = StringProperty('0')

    config_active = BooleanProperty(False)

    display_trigger = None

    display_widget = None

    last_image = None

    image_queue = None

    use_real_time = False

    metadata_play = ObjectProperty(None)

    metadata_play_used = ObjectProperty(None)

    metadata_record = ObjectProperty(None)

    real_rate = 0

    frames_played = 0

    frames_recorded = 0

    frames_skipped = 0

    size_recorded = 0

    ts_play = 0

    ts_record = 0

    preview_stats = StringProperty('')

    player_summery = StringProperty('')

    record_stats = StringProperty('')

    def __init__(self, **kwargs):
        self.metadata_play = VideoMetadata(
            *kwargs.pop('metadata_play', ('', 0, 0, 0)))
        self.metadata_play_used = VideoMetadata(
            *kwargs.pop('metadata_play_used', ('', 0, 0, 0)))
        self.metadata_record = VideoMetadata(
            *kwargs.pop('metadata_record', ('', 0, 0, 0)))
        self.cls = self.__class__.__name__[:-6]
        super(Player, self).__init__(**kwargs)
        self.play_lock = RLock()
        self.record_lock = RLock()
        self.display_trigger = Clock.create_trigger(self.display_frame, 0)

    def err_callback(self, *largs, **kwargs):
        self.stop()
        self.player_view.knspace.play.state = 'normal'
        settings = self.players.settings_display
        if settings.player == self:
            settings.knspace.play.state = 'normal'
        self.players.log_error(**kwargs)

    def get_config_dict(self):
        attrs = [
            'record_directory', 'record_fname', 'record_fname_count',
            'metadata_play', 'metadata_play_used', 'metadata_record', 'cls']
        return {k: getattr(self, k) for k in attrs}

    def write_widget_settings(self):
        kn = self.players.settings_display.knspace
        name = self.players.source_cls[self.__class__]
        kn.source_type.current = name
        kn.popup.ids[name].state = 'down'
        kn.record_pix_fmt.text, kn.record_w.text, \
            kn.record_h.text, kn.record_rate.text = \
            ((str(x) if x else '') for x in self.metadata_record)

    def read_widget_play_settings(self):
        pass

    def read_widget_record_settings(self):
        kn = self.players.settings_display.knspace
        fmt, w, h, rate = kn.record_pix_fmt.text, kn.record_w.text, \
            kn.record_h.text, kn.record_rate.text
        self.metadata_record = VideoMetadata(
            fmt, int(w) if w else 0, int(h) if h else 0,
            float(rate) if rate else 0.)

    def write_viewer_settings(self):
        kn = self.player_view.knspace
        kn.path_dir.text = self.record_directory
        t = kn.path_fname.orig_text = kn.path_fname.text = self.record_fname
        n = kn.path_count.text = self.record_fname_count
        kn.path_fname.text = kn.path_fname.fmt_text = t.replace('{}', n)

    def read_viewer_settings(self):
        kn = self.player_view.knspace
        self.record_directory = kn.path_dir.text
        self.record_fname = kn.path_fname.orig_text
        self.record_fname_count = kn.path_count.text

    def display_frame(self, *largs):
        widget = self.display_widget
        img = self.last_image
        if widget is not None and img is not None:
            widget.update_img(img[0])

    def compute_recording_opts(self, ifmt=None, iw=None, ih=None, irate=None):
        play_used = self.metadata_play_used
        ifmt = ifmt or play_used.fmt
        iw = iw or play_used.w
        ih = ih or play_used.h
        irate = irate or play_used.rate
        ofmt, ow, oh, orate = self.metadata_record
        ifmt = ifmt or 'yuv420p'
        iw = iw or 640
        ih = ih or 480
        irate = irate or 30.
        ofmt = ofmt or ifmt
        ow = ow or iw
        oh = oh or ih
        orate = orate or irate
        return (ifmt, iw, ih, irate), (ofmt, ow, oh, orate)

    def compute_preview_stats(self):
        self.read_widget_play_settings()
        self.read_widget_record_settings()
        kn = self.players.settings_display.knspace
        drive = kn.record_drive.text
        if not drive:
            drive = 'C'
        if len(drive) == 1:
            drive += ':\\'

        (ifmt, iw, ih, irate), (ofmt, ow, oh, orate) = \
            self.compute_recording_opts()

        ibps = sum(get_image_size(ifmt, iw, ih)) * irate
        obps = sum(get_image_size(ofmt, ow, oh)) * orate

        _, _, free, _ = psutil.disk_usage(drive)
        text = 'Play: {}. Record: {}. 1 Min={}, Free {}'.format(
            pretty_space(ibps, is_rate=True), pretty_space(obps, is_rate=True),
            pretty_space(obps * 60), pretty_time(free / float(obps)))
        self.preview_stats = text

    def save_screenshot(self, path, selection, filename):
        fname = join(abspath(path), filename)
        try:
            if self.last_image is None:
                raise ValueError('No image acquired')

            img, _ = self.last_image
            fmt = img.get_pixel_format()
            w, h = img.get_size()

            codec = get_format_codec(fname)
            ofmt = get_supported_pixfmts(codec, fmt)[0]
            if ofmt != fmt:
                sws = SWScale(w, h, fmt, ofmt=ofmt)
                img = sws.scale(img)
                fmt = ofmt

            out_opts = {'pix_fmt_in': fmt, 'width_in': w, 'height_in': h,
                        'frame_rate': (30, 1)}
            writer = MediaWriter(fname, [out_opts])
            writer.write_frame(img=img, pts=0, stream=0)
            writer.close()
        except Exception as e:
            self.players.log_error(
                e=e, exc_info=sys.exc_info(),
                msg='Screenshot: Could not save {}'.format(fname))

    def play(self):
        '''Called from main thread only, starts playing and sets play state to
        `starting`. Only called when :attr:`play_state` is `none`.
        '''
        if self.play_state != 'none':
            Logger.warn(
                '%s: Asked to play while {}'.format(self.play_state), self)
            return
        if self.players.settings_display.player is self:
            self.read_widget_play_settings()
        self.play_state = 'starting'
        thread = self.play_thread = Thread(
            target=self.play_thread_run, name='Play thread')
        thread.start()

    def record(self):
        '''Called from main thread only, starts recording and sets record state
        to `starting`. Only called when :attr:`record_state` is `none`.
        '''
        if self.record_state != 'none':
            Logger.warn(
                '%s: Asked to record while {}'.format(self.record_state), self)
            return
        if self.players.settings_display.player is self:
            self.read_widget_record_settings()
        self.read_viewer_settings()
        self.record_state = 'starting'
        self.read_viewer_settings()
        self.image_queue = Queue()
        filename = join(
            self.record_directory,
            self.record_fname.replace('{}', self.record_fname_count))
        thread = self.record_thread = Thread(
            target=self.record_thread_run, name='Record thread',
            args=(filename, ))
        thread.start()

    def stop_recording(self, *largs):
        if self.record_state == 'none':
            return

        with self.record_lock:
            if self.record_state == 'stopping':
                return

            if self.record_callback is not None:
                self.record_callback.cancel()
                self.record_callback = None
            self.image_queue.put_nowait('eof')
            self.image_queue = None
            self.record_state = 'stopping'

        self.player_view.knspace.record.state = 'normal'
        path_count = self.player_view.knspace.path_count
        if path_count.text:
            path_count.text = str(int(path_count.text) + 1)

    def stop(self, *largs):
        self.stop_recording()
        if self.play_state == 'none':
            return

        with self.play_lock:
            if self.play_state == 'stopping':
                return

            if self.play_callback is not None:
                self.play_callback.cancel()
                self.play_callback = None
            self.play_state = 'stopping'
        self.player_view.knspace.play.state = 'normal'
        if self.players.settings_display.player is self:
            self.players.settings_display.knspace.play.state = 'normal'

    def stop_all(self, join=False):
        self.stop()
        if join:
            if self.record_thread:
                self.record_thread.join()
            if self.play_thread:
                self.play_thread.join()

    def change_status(self, thread='play', start=True, e=None):
        '''Called from the play or record secondary thread to change the
        play/record state to playing/recording or none.
        '''
        if start:
            with getattr(self, thread + '_lock'):
                state = getattr(self, thread + '_state')
                if state not in ('starting', 'stopping'):
                    Logger.warn(
                        '%s: Asked to continue {}ing while {}'.
                        format(thread, state), self)
                    return
                if state == 'stopping':
                    return

                ev = Clock.schedule_once(
                    partial(self._complete_start, thread), 0)
                setattr(self, thread + '_callback', ev)
            while getattr(self, thread + '_state') == 'starting':
                sleep(.01)
        else:
            if e and getattr(self, thread + '_state') == thread + 'ing':
                src = '{}er'.format(thread.capitalize())
                Clock.schedule_once(partial(
                    self.err_callback, msg='%s: %s' % (self, src),
                    exc_info=sys.exc_info(), e=e), 0)
            self._request_stop(thread)
            while getattr(self, thread + '_state') != 'stopping':
                sleep(.01)
            Clock.schedule_once(partial(self._complete_stop, thread), 0)

    def update_metadata(self, fmt=None, w=None, h=None, rate=None):
        ifmt, iw, ih, irate = self.metadata_play_used
        if fmt is not None:
            ifmt = fmt
        if w is not None:
            iw = w
        if h is not None:
            ih = h
        if rate is not None:
            irate = rate
        self.metadata_play_used = VideoMetadata(ifmt, iw, ih, irate)

    def _request_stop(self, thread):
        with getattr(self, thread + '_lock'):
            callback = getattr(self, thread + '_callback')
            if callback is not None:
                callback.cancel()

            if getattr(self, thread + '_state') != 'stopping':
                if thread == 'play':
                    ev = Clock.schedule_once(self.stop, 0)
                else:
                    ev = Clock.schedule_once(self.stop_recording, 0)
                setattr(self, thread + '_callback', ev)
            else:
                setattr(self, thread + '_callback', None)

    def _complete_start(self, thread, *largs):
        with getattr(self, thread + '_lock'):
            if getattr(self, thread + '_state') == 'starting':
                setattr(self, thread + '_state', thread + 'ing')

    def _complete_stop(self, thread, *largs):
        if thread == 'play':
            self.play_thread = None
        else:
            self.record_thread = None
        setattr(self, thread + '_state', 'none')

    def play_thread_run(self):
        pass

    def record_thread_run(self, filename):
        queue = self.image_queue
        recorder = None
        irate = None
        t0 = None
        self.size_recorded = self.frames_skipped = self.frames_recorded = 0
        while self.record_state != 'stopping':
            item = queue.get()
            if item == 'eof':
                break
            img, t = item

            if img == 'rate':
                assert recorder is None
                irate = t
                continue

            if recorder is None:
                self.ts_record = clock()
                t0 = t
                iw, ih = img.get_size()
                ipix_fmt = img.get_pixel_format()

                _, (opix_fmt, ow, oh, orate) = self.compute_recording_opts(
                    ipix_fmt, iw, ih, irate)

                orate = Fraction(orate)
                if orate >= 1.:
                    orate = Fraction(orate.denominator, orate.numerator)
                    orate = orate.limit_denominator(2 ** 30 - 1)
                    orate = (orate.denominator, orate.numerator)
                else:
                    orate = orate.limit_denominator(2 ** 30 - 1)
                    orate = (orate.numerator, orate.denominator)

                stream = {
                    'pix_fmt_in': ipix_fmt, 'pix_fmt_out': opix_fmt,
                    'width_in': iw, 'height_in': ih, 'width_out': ow,
                    'height_out': oh, 'codec': 'rawvideo', 'frame_rate': orate}

                try:
                    recorder = MediaWriter(filename, [stream])
                except Exception as e:
                    self.change_status('record', False, e)
                    return
                self.change_status('record', True)

            try:
                self.size_recorded = recorder.write_frame(img, t - t0)
                self.frames_recorded += 1
            except Exception as e:
                self.frames_skipped += 1
                Logger.warn('{}: Recorder error writing frame: {}'
                            .format(self, e))

        self.change_status('record', False)


class FFmpegPlayer(Player):

    play_filename = StringProperty('')

    file_fmt = StringProperty('dshow')
    '''Can be empty or a format e.g. `dshow`. '''

    icodec = StringProperty('')

    dshow_true_filename = StringProperty('')

    dshow_opt = StringProperty('')

    dshow_names = {}

    dshow_opts = {}

    dshow_opt_pat = re.compile(
        '([0-9]+)X([0-9]+) (.+), ([0-9\\.]+)(?: - ([0-9\\.]+))? fps')

    def __init__(self, **kw):
        play_filename = kw.get('play_filename')
        file_fmt = kw.get('file_fmt')
        dshow_true_filename = kw.get('dshow_true_filename')
        dshow_opt = kw.get('dshow_opt')

        if (file_fmt == 'dshow' and play_filename and dshow_true_filename and
                dshow_opt):
            self.dshow_names = {play_filename: dshow_true_filename}
            self.dshow_opts = {play_filename:
                               {dshow_opt: self.parse_dshow_opt(dshow_opt)}}
        super(FFmpegPlayer, self).__init__(**kw)

    def refresh_dshow(self, cams_wid, opts_wid):
        counts = defaultdict(int)
        video, _, names = list_dshow_devices()
        video2 = {}
        names2 = {}

        # rename to have pretty unique names
        for true_name, name in names.items():
            if true_name not in video:
                continue

            count = counts[name]
            name2 = '{}-{}'.format(name, count) if count else name
            counts[name] = count + 1

            # filter and clean cam opts
            names2[name2] = true_name
            opts = video2[name2] = {}

            for fmt, _, (w, h), (rmin, rmax) in video[true_name]:
                if not fmt:
                    continue
                if rmin != rmax:
                    key = '{}X{} {}, {} - {} fps'.format(w, h, fmt, rmin, rmax)
                else:
                    key = '{}X{} {}, {} fps'.format(w, h, fmt, rmin)
                if key not in opts:
                    opts[key] = (fmt, (w, h), (rmin, rmax))

        self.dshow_opts = video2
        self.dshow_names = names2

        values = sorted(names2.keys())
        # save old vals
        old_name = self.play_filename
        old_opt = self.dshow_opt
        # reset
        cams_wid.text = ''
        cams_wid.values = values
        cams_wid.text = values[0]

        if old_name in names2:
            cams_wid.text = old_name
            if old_opt in video2[old_name]:
                opts_wid.text = old_opt

    def update_dshow_opt(self, cams_widget, opts_widget):
        vals = opts_widget.values = sorted(
            self.dshow_opts.get(cams_widget.text, []),
            key=self.get_opt_image_size)
        if vals:
            opt = self.dshow_opt
            opts_widget.text = opt if opt in vals else vals[0]
        else:
            opts_widget.text = ''

    def parse_dshow_opt(self, opt):
        m = re.match(self.dshow_opt_pat, opt)
        if m is None:
            raise ValueError('{} not a valid option'.format(opt))

        w, h, fmt, rmin, rmax = m.groups()
        if rmax is None:
            rmax = rmin

        w, h, rmin, rmax = int(w), int(h), float(rmin), float(rmax)
        return fmt, (w, h), (rmin, rmax)

    def get_opt_image_size(self, opt):
        fmt, (w, h), _ = self.parse_dshow_opt(opt)
        return w * h, sum(get_image_size(fmt, w, h))

    def get_config_dict(self):
        config = super(FFmpegPlayer, self).get_config_dict()
        attrs = ['play_filename', 'file_fmt', 'icodec', 'dshow_true_filename',
                 'dshow_opt']
        for k in attrs:
            config[k] = getattr(self, k)
        return config

    def read_widget_play_settings(self):
        super(FFmpegPlayer, self).read_widget_play_settings()
        kn = self.players.settings_display.knspace
        fmt, w, h = kn.play_pix_fmt.text, kn.play_w.text, \
            kn.play_h.text
        self.metadata_play = VideoMetadata(
            fmt, int(w) if w else 0, int(h) if h else 0, 0.)
        self.icodec = kn.play_codec.text
        self.file_fmt = kn.play_file_fmt.text
        self.dshow_opt = kn.dshow_opts.text
        if self.play_filename != kn.filename.text:
            self.play_filename = kn.filename.text
            self.dshow_true_filename = self.dshow_names.get(
                    self.play_filename, self.play_filename)

    def write_widget_settings(self):
        super(FFmpegPlayer, self).write_widget_settings()
        kn = self.players.settings_display.knspace

        kn.dshow_cams.values = sorted(self.dshow_names.keys())
        if self.file_fmt == 'dshow':
            kn.webcam_fmt.state = 'down'
            kn.dshow_cams.text = self.play_filename
            self.update_dshow_opt(kn.dshow_cams, kn.dshow_opts)
        else:
            kn.other_fmt.state = 'down'
            kn.dshow_cams.values = []
            kn.dshow_cams.text = ''
            kn.filename.text = self.play_filename

        kn.play_codec.text = self.icodec
        kn.play_file_fmt.text = self.file_fmt
        fmt, w, h, _ = self.metadata_play
        kn.play_pix_fmt.text, kn.play_w.text, \
            kn.play_h.text = fmt, (str(w) if w else ''), \
            (str(h) if h else '')

    def player_callback(self, mode, value):
        if mode == 'display_sub':
            return
        if mode.endswith('error'):
            Clock.schedule_once(partial(
                self.err_callback, msg='Player: {}, {}'.format(mode, value)),
                                0)
        self._request_stop('play')

    def play_thread_run(self):
        self.frames_played = 0
        self.ts_play = self.real_rate = 0.
        ff_opts = {'sync': 'video', 'an': True, 'sn': True, 'paused': True}
        ifmt, icodec = self.file_fmt, self.icodec
        if ifmt:
            ff_opts['f'] = ifmt
        if icodec:
            ff_opts['vcodec'] = icodec
        ipix_fmt, iw, ih, _ = self.metadata_play
        ff_opts['x'] = iw
        ff_opts['y'] = ih

        lib_opts = {}
        if ifmt == 'dshow':
            rate = self.metadata_record.rate
            if self.dshow_opt:
                fmt, size, (rmin, rmax) = self.parse_dshow_opt(self.dshow_opt)
                lib_opts['pixel_format'] = fmt
                lib_opts['video_size'] = '{}x{}'.format(*size)
                if rate:
                    rate = min(max(rate, rmin), rmax)
                    lib_opts['framerate'] = '{}'.format(rate)
            elif rate:
                lib_opts['framerate'] = '{}'.format(rate)

        fname = self.play_filename
        if ifmt == 'dshow':
            fname = 'video={}'.format(self.dshow_true_filename)

        try:
            ffplayer = MediaPlayer(
                fname, callback=self.player_callback, ff_opts=ff_opts,
                lib_opts=lib_opts)
        except Exception as e:
            self.change_status('play', False, e)
            return

        src_fmt = ''
        s = clock()
        while self.play_state == 'starting' and clock() - s < 30.:
            src_fmt = ffplayer.get_metadata().get('src_pix_fmt')
            if src_fmt:
                break
            time.sleep(0.01)
        if not src_fmt:
            try:
                raise ValueError("Player failed, couldn't get pixel type")
            except Exception as e:
                self.change_status('play', False, e)
                return

        if ipix_fmt:
            src_fmt = ipix_fmt
        fmt = {'gray': 'gray', 'rgb24': 'rgb24', 'bgr24': 'rgb24',
               'rgba': 'rgba', 'bgra': 'rgba'}.get(src_fmt, 'yuv420p')
        ffplayer.set_output_pix_fmt(fmt)

        ffplayer.toggle_pause()
        logging.info('Player: input, output formats are: {}, {}'
                     .format(src_fmt, fmt))

        img = None
        s = clock()
        while self.play_state == 'starting' and clock() - s < 30.:
            img, val = ffplayer.get_frame()
            if val == 'eof':
                try:
                    raise ValueError("Player failed, reached eof")
                except Exception as e:
                    self.change_status('play', False, e)
                    return

            if img:
                ivl_start = clock()
                break
            time.sleep(0.01)

        rate = ffplayer.get_metadata().get('frame_rate')
        if rate == (0, 0):
            try:
                raise ValueError("Player failed, couldn't read frame rate")
            except Exception as e:
                self.change_status('play', False, e)
                return

        if not img:
            try:
                raise ValueError("Player failed, couldn't read frame")
            except Exception as e:
                self.change_status('play', False, e)
                return

        rate = rate[0] / float(rate[1])
        w, h = img[0].get_size()
        fmt = img[0].get_pixel_format()
        last_queue = self.image_queue
        put = None
        trigger = self.display_trigger
        use_rt = self.use_real_time

        Clock.schedule_once(
            partial(eat_first, self.update_metadata, rate=rate, w=w, h=h,
                    fmt=fmt), 0)
        self.change_status('play', True)
        self.last_image = img[0], ivl_start if use_rt else img[1]
        if last_queue is not None:
            put = last_queue.put
            put(('rate', rate))
            put((img[0], ivl_start if use_rt else img[1]))
        trigger()

        tdiff = 1 / (rate * 2.)
        self.ts_play = ivl_start
        count = 1
        self.frames_played = 1

        try:
            while self.play_state != 'stopping':
                img, val = ffplayer.get_frame()
                ivl_end = clock()
                if ivl_end - ivl_start >= 1.:
                    self.real_rate = count / (ivl_end - ivl_start)
                    count = 0
                    ivl_start = ivl_end

                if val == 'eof' or val == 'paused':
                    raise ValueError("Player {} got {}".format(self, val))

                if not img:
                    time.sleep(min(val, tdiff) if val else tdiff)
                    continue

                count += 1
                self.frames_played += 1

                if last_queue is not self.image_queue:
                    last_queue = self.image_queue
                    if last_queue is not None:
                        put = last_queue.put
                        put(('rate', rate))
                    else:
                        put = None

                if put is not None:
                    put((img[0], ivl_end if use_rt else img[1]))

                self.last_image = img[0], ivl_end if use_rt else img[1]
                trigger()
        except Exception as e:
            self.change_status('play', False, e)
            return
        self.change_status('play', False)


class RTVPlayer(Player):

    video_fmts = {
        'full_NTSC': (640, 480), 'full_PAL': (768, 576),
        'CIF_NTSC': (320, 240), 'CIF_PAL': (384, 288),
        'QCIF_NTSC': (160, 120),  'QCIF_PAL': (192, 144)
    }

    remote_computer_name = StringProperty('')

    pipe_name = StringProperty('filers_rtv')

    port = NumericProperty(0)

    video_fmt = StringProperty('full_NTSC')

    channel = None

    def __init__(self, **kwargs):
        super(RTVPlayer, self).__init__(**kwargs)
        self.metadata_play = self.metadata_play_used = \
            VideoMetadata('gray', 0, 0, 0)

    def get_config_dict(self):
        config = super(RTVPlayer, self).get_config_dict()
        attrs = ['remote_computer_name', 'pipe_name', 'port', 'video_fmt']
        for k in attrs:
            config[k] = getattr(self, k)
        return config

    def read_widget_play_settings(self):
        super(RTVPlayer, self).read_widget_play_settings()
        kn = self.players.settings_display.knspace
        pix_fmt = kn.rtv_pix_fmt.text
        video_fmt = kn.rtv_vid_fmt.text.split(' ')[0]
        w, h = self.video_fmts[video_fmt]
        self.metadata_play_used = self.metadata_play = VideoMetadata(
            pix_fmt, w, h, 29.97)
        self.video_fmt = video_fmt
        self.img_fmt = pix_fmt
        port = kn.rtv_port.text
        self.port = int(port) if port else 0
        self.pipe_name = kn.rtv_pipe_name.text
        self.remote_computer_name = kn.rtv_remote_name.text

    def write_widget_settings(self):
        super(RTVPlayer, self).write_widget_settings()
        kn = self.players.settings_display.knspace
        kn.rtv_pix_fmt.text = self.metadata_play.fmt
        w, h = self.video_fmts[self.video_fmt]
        kn.rtv_vid_fmt.text = '{} ({}, {})'.format(self.video_fmt, w, h)

        kn.rtv_port.text = str(self.port)
        kn.rtv_pipe_name.text = self.pipe_name
        kn.rtv_remote_name.text = self.remote_computer_name

    def stop(self, *largs):
        super(RTVPlayer, self).stop(*largs)
        chan = self.channel
        if chan is not None:
            try:
                chan.set_state(False)
            except:
                pass

    def play_thread_run(self):
        self.frames_played = 0
        self.ts_play = self.real_rate = 0.
        files = (
            r'C:\Program Files\Barst\Barst.exe',
            r'C:\Program Files\Barst\Barst64.exe',
            r'C:\Program Files (x86)\Barst\Barst.exe',
            join(root_install_path, 'Barst.exe'))
        barst_bin = None
        for f in files:
            f = abspath(f)
            if isfile(f):
                barst_bin = f
                break

        local = not self.remote_computer_name
        name = self.remote_computer_name if not local else '.'
        pipe_name = self.pipe_name
        full_name = r'\\{}\pipe\{}'.format(name, pipe_name)

        try:
            server = BarstServer(barst_path=barst_bin, pipe_name=full_name)
            server.open_server()
            img_fmt = self.metadata_play.fmt
            w, h = self.video_fmts[self.video_fmt]
            chan = RTVChannel(
                chan=self.port, server=server, video_fmt=self.video_fmt,
                frame_fmt=img_fmt, luma_filt=img_fmt == 'gray', lossless=True)
            chan.open_channel()
            try:
                chan.close_channel_server()
            except:
                pass
            chan.open_channel()
            chan.set_state(True)

            last_queue = None
            put = None
            started = False
            trigger = self.display_trigger
            use_rt = self.use_real_time
            count = 0

            while self.play_state != 'stopping':
                ts, buf = chan.read()
                if not started:
                    self.ts_play = ivl_start = clock()
                    self.change_status('play', True)
                    started = True

                ivl_end = clock()
                if ivl_end - ivl_start >= 1.:
                    self.real_rate = count / (ivl_end - ivl_start)
                    count = 0
                    ivl_start = ivl_end

                count += 1
                self.frames_played += 1

                if last_queue is not self.image_queue:
                    last_queue = self.image_queue
                    if last_queue is not None:
                        put = last_queue.put
                        put(('rate', 29.97))
                    else:
                        put = None

                img = Image(plane_buffers=[buf], pix_fmt=img_fmt, size=(w, h))
                if put is not None:
                    put((img, ivl_end if use_rt else ts))

                self.last_image = img, ivl_end if use_rt else ts
                trigger()
        except Exception as e:
            self.change_status('play', False, e)
            try:
                chan.close_channel_server()
            except:
                pass
            return

        try:
            chan.close_channel_server()
        except:
            pass
        self.change_status('play', False)


class PTGrayPlayer(Player):

    serial = NumericProperty(0)

    serials = []

    cam_config_opts = DictProperty({})

    config_thread = None

    config_queue = None

    config_active = ListProperty([])

    ffmpeg_pix_map = {
        'mono8': 'gray', 'yuv411': 'uyyvyy411', 'yuv422': 'uyvy422',
        'yuv444': 'yuv444p', 'rgb8': 'rgb8', 'mono16': 'gray16le',
        'rgb16': 'rgb565le', 's_mono16': 'gray16le', 's_rgb16': 'rgb565le',
        'bgr': 'bgr24', 'bgru': 'bgra', 'rgb': 'rgb24', 'rgbu': 'rgba',
        'bgr16': 'bgr565le', 'yuv422_jpeg': 'yuvj422p'}

    def __init__(self, **kwargs):
        super(PTGrayPlayer, self).__init__(**kwargs)
        self.start_config()

    def on_serial(self, *largs):
        self.ask_config('serial')

    def start_config(self, *largs):
        self.config_queue = Queue()
        thread = self.config_thread = Thread(
            target=self.config_thread_run, name='Config thread')
        thread.start()
        self.ask_config('serials')

    def stop_all(self, join=False):
        super(PTGrayPlayer, self).stop_all(join=join)
        self.ask_config('eof')
        if join and self.config_thread:
            self.config_thread.join()

    def ask_config(self, item):
        queue = self.config_queue
        if queue is not None:
            self.config_active.append(item)
            queue.put_nowait(item)

    def finish_ask_config(self, item, *largs, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)
        serial = self.players.settings_display.knspace.pt_serial
        if 'serial' in kwargs:
            serial.text = str(kwargs['serial'])
        if 'serials' in kwargs:
            serial.values = map(str, kwargs['serials'])

    def get_config_dict(self):
        config = super(PTGrayPlayer, self).get_config_dict()
        attrs = ['serial', 'cam_config_opts']
        for k in attrs:
            config[k] = getattr(self, k)
        return config

    def write_gige_opts(self, c, opts):
        c.set_gige_mode(opts['mode'])
        c.set_drop_mode(opts['drop'])
        c.set_gige_config(opts['offset_x'], opts['offset_y'], opts['width'],
                          opts['height'], opts['fmt'])
        c.set_gige_packet_config(opts['resend'], opts['resend_timeout'],
                                 opts['max_resend_packets'])
        c.set_gige_binning(opts['horizontal'], opts['vertical'])

    def read_gige_opts(self, c):
        opts = self.cam_config_opts
        opts['drop'] = c.get_drop_mode()
        opts.update(c.get_gige_config())
        opts['mode'] = c.get_gige_mode()
        opts.update(c.get_gige_packet_config())
        opts['horizontal'], opts['vertical'] = c.get_gige_binning()

    def config_thread_run(self):
        queue = self.config_queue
        cc = CameraContext()
        state = self.config_active

        while True:
            item = queue.get()
            try:
                if item == 'eof':
                    return

                serial = 0
                do_serial = False
                if item == 'serials':
                    cc.rescan_bus()
                    cams = cc.get_gige_cams()
                    old_serial = serial = self.serial
                    if serial not in cams:
                        serial = cams[0] if cams else 0

                    Clock.schedule_once(partial(self.finish_ask_config, item,
                                                serials=cams, serial=serial))

                    if serial:
                        c = Camera(serial=serial)
                        c.connect()
                        if old_serial == serial:
                            self.write_gige_opts(c, self.cam_config_opts)
                        self.read_gige_opts(c)
                        c.disconnect()
                        c = None
                elif item == 'serial':
                    do_serial = True
                elif item == 'gui':
                    gui = GUI()
                    gui.show_selection()
                    do_serial = True

                if do_serial:
                    serial = self.serial
                    if serial:
                        c = Camera(serial=serial)
                        c.connect()
                        self.read_gige_opts(c)
                        c.disconnect()
                        c = None

                if serial:
                    opts = self.cam_config_opts
                    if opts['fmt'] not in self.ffmpeg_pix_map:
                        raise Exception('Pixel format {} cannot be converted'.
                                        format(opts['fmt']))
                    metadata = VideoMetadata(
                        self.ffmpeg_pix_map[opts['fmt']], opts['width'],
                        opts['height'], 30.0)
                    Clock.schedule_once(partial(
                        self.finish_ask_config, item, metadata_play=metadata,
                        metadata_play_used=metadata))
            except Exception as e:
                Clock.schedule_once(partial(
                    self.err_callback,
                    msg='PTGray configuration: {}'.format(self),
                    exc_info=sys.exc_info(), e=e),
                    0)
            finally:
                state.remove(item)

    def read_widget_play_settings(self):
        super(PTGrayPlayer, self).read_widget_play_settings()
        kn = self.players.settings_display.knspace
        s = kn.pt_serial.text
        self.serial = int(s) if s else 0

    def write_widget_settings(self):
        super(PTGrayPlayer, self).write_widget_settings()
        kn = self.players.settings_display.knspace
        kn.pt_serial.text = str(self.serial)

    def play_thread_run(self):
        self.frames_played = 0
        self.ts_play = self.real_rate = 0.
        c = None
        ffmpeg_fmts = self.ffmpeg_pix_map

        try:
            c = Camera(serial=self.serial)
            c.connect()

            last_queue = None
            put = None
            started = False
            trigger = self.display_trigger
            use_rt = self.use_real_time
            count = 0
            rate = self.metadata_play_used.rate

            c.start_capture()
            while self.play_state != 'stopping':
                c.read_next_image()
                if not started:
                    self.ts_play = ivl_start = clock()
                    self.change_status('play', True)
                    started = True

                ivl_end = clock()
                if ivl_end - ivl_start >= 1.:
                    self.real_rate = count / (ivl_end - ivl_start)
                    count = 0
                    ivl_start = ivl_end

                count += 1
                self.frames_played += 1

                if last_queue is not self.image_queue:
                    last_queue = self.image_queue
                    if last_queue is not None:
                        put = last_queue.put
                        put(('rate', rate))
                    else:
                        put = None

                image = c.get_current_image()
                pix_fmt = image['pix_fmt']
                if pix_fmt not in ffmpeg_fmts:
                    raise Exception('Pixel format {} cannot be converted'.
                                    format(pix_fmt))
                ff_fmt = ffmpeg_fmts[pix_fmt]
                if ff_fmt == 'yuv444p':
                    buff = image['buffer']
                    img = Image(
                        plane_buffers=[buff[0::3], buff[1::3], buff[2::3]],
                        pix_fmt=ff_fmt, size=(image['cols'], image['rows']))
                else:
                    img = Image(
                        plane_buffers=[image['buffer']], pix_fmt=ff_fmt,
                        size=(image['cols'], image['rows']))
                if put is not None:
                    put((img, ivl_end))

                self.last_image = img, ivl_end
                trigger()
        except Exception as e:
            self.change_status('play', False, e)
            try:
                c.disconnect()
            except:
                pass
            return

        try:
            c.disconnect()
        except:
            pass
        self.change_status('play', False)


class PlayerRoot(KNSpaceBehavior, BoxLayout):

    players = ObjectProperty(None, rebind=True)

    def __init__(self, **kwargs):
        super(PlayerRoot, self).__init__(**kwargs)

        def init(*largs):
            p = self.players = Players(container=self.ids.container,
                                       players_view=self)
            self.knspace.n_rows.text = str(min(max(p.cam_grid_rows, 1), 10))
        Clock.schedule_once(init, 0)


class PlayerView(KNSpaceBehavior, EventFocusBehavior, BoxLayout):

    player = ObjectProperty(None, rebind=True)

    players = ObjectProperty(None, rebind=True)

    disk_used_percent = NumericProperty(0)

    elapsed_recording = StringProperty('0.0')

    disk_stat = StringProperty('')

    def on_keypress(self, key):
        if key == 'spacebar':
            self.knspace.record.trigger_action(0)
        elif key == 'escape':
            play = self.knspace.play
            if play.state == 'down':
                play.trigger_action(0)
        elif key == 'enter':
            play = self.knspace.play
            if play.state == 'normal':
                play.trigger_action(0)

    def handle_fname(self, fname, count, source='fname'):
        n = count.text
        if source == 'count':
            fname.text = fname.fmt_text = fname.orig_text.replace('{}', n)
        elif not fname.focus:
            fname.orig_text = fname.text
            fname.text = fname.fmt_text = fname.orig_text.replace('{}', n)
        else:
            fname.text = fname.orig_text

    def update_cycle(self):
        player = self.player
        p = player.record_directory
        p = 'C:\\' if not exists(p) else (p if isdir(p) else dirname(p))
        disk_usage = psutil.disk_usage(p)
        p = self.disk_used_percent = round(disk_usage.percent) / 100.

        if player.record_state == 'recording':
            elapsed = pretty_time(max(0, clock() - player.ts_record))
            size = pretty_space(player.size_recorded)
            skipped = player.frames_skipped
            self.elapsed_recording = ('{}s ({}) [color=#FF0000]{}[/color]'.
                                      format(elapsed, size, skipped))

        _, (ofmt, ow, oh, orate) = player.compute_recording_opts()
        obps = sum(get_image_size(ofmt, ow, oh)) * orate
        free = disk_usage.free
        space = pretty_space(free)
        t = pretty_time(free / obps)
        color = 'FF0000' if p >= .75 else '00FF00'
        self.disk_stat = '[color=#{}]{}s ({})[/color]'.format(color, t, space)


class PlayerSettings(KNSpaceBehavior, Popup):

    player = ObjectProperty(None, rebind=True, allownone=True)

    players = ObjectProperty(None, rebind=True)

    parent_obj = ObjectProperty(None, rebind=True, allownone=True)


class SizedScreenManager(ScreenManager):

    current_screen_obj = ObjectProperty(None, rebind=True)
