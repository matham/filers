'''Recorder
===========

Module for playing and recording Filers video.
'''

from os.path import isfile, join, dirname, abspath, exists
from os.path import isdir
import psutil
import json

from ffpyplayer.pic import get_image_size

from kivy.clock import Clock
from kivy.compat import clock
from kivy.uix.behaviors.knspace import KNSpaceBehavior, knspace
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.screenmanager import ScreenManager
from kivy.uix.popup import Popup
from kivy.properties import (
    NumericProperty, ReferenceListProperty,
    ObjectProperty, ListProperty, StringProperty, BooleanProperty,
    DictProperty, AliasProperty, OptionProperty, ConfigParserProperty)
from kivy.event import EventDispatcher
from kivy import resources

from cplcom import config_name
from cplcom.graphics import EventFocusBehavior
from cplcom.config import populate_dump_config
from cplcom.player import FFmpegPlayer, RTVPlayer, PTGrayPlayer, \
    VideoMetadata, CameraContext
from cplcom.app import app_error
from filers import root_data_path, root_install_path
from filers.tools import (str_to_float, pretty_space, pretty_time, KivyQueue,
                          ConfigProperty, to_bool, byteify)


__all__ = ('Players', 'FilersPlayer', 'FFmpegFilersPlayer', 'RTVFilersPlayer',
           'PTGrayFilersPlayer', 'exit_players', 'PlayerRoot', 'PlayerView',
           'PlayerSettings')


def exit_players():
    '''Closes all running players and saves the last config.
    '''
    for player in Players.players:
        try:
            player.stop_all(join=True)
        except:
            pass
    p = Players.players_singleton
    if p:
        p.save_config()


class Players(EventDispatcher):
    '''Singleton that controls all the players.
    '''

    __settings_attrs__ = ('cam_grid_rows', )

    settings_path = ConfigParserProperty(
        join(root_data_path, 'recorder.json'), 'Filers',
        'settings_path', config_name)

    cam_grid_rows = NumericProperty(2)
    '''The number of rows into which to split the video recorders when there's
    more than one recorder open.
    '''

    source_names = {}

    source_cls = {}

    settings_display = None

    container = ObjectProperty(None)

    players = []

    display_update = None

    players_singleton = None

    players_view = ObjectProperty(None)

    ptgray_disabled = CameraContext is None

    @staticmethod
    def is_playing():
        return any((p.play_state != 'none' or p.record_state != 'none'
                    for p in Players.players))

    @classmethod
    def get_config_classes(cls):
        return {'recorder': Players, 'FFMpeg': FFmpegFilersPlayer,
                'RTV': RTVFilersPlayer, 'PTGray': PTGrayFilersPlayer}

    def __init__(self, **kwargs):
        super(Players, self).__init__(**kwargs)
        Players.players_singleton = self
        self.source_names = {
            'RTV': RTVFilersPlayer, 'FFmpeg': FFmpegFilersPlayer,
            'PTGray': PTGrayFilersPlayer}
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

    @app_error
    def load_config(self, filename):
        filename = resources.resource_find(filename)
        if not filename or not isfile(filename):
            return

        for player in Players.players[:]:
            self.delete_player(player)

        with open(filename) as fh:
            opts = byteify(json.load(fh))

        for k, v in opts.pop('recorder', {}).items():
            setattr(self, k, v)
        for _, d in sorted(opts.items(), key=lambda x: x[0]):
            self.add_player(settings=d, show=False,
                            cls=d.pop('cls', 'FFmpeg'))
        self.settings_path = filename

    @app_error
    def save_config(self, filename=None):
        filename = filename or self.settings_path
        if not filename:
            return
        filename = knspace.app.ensure_config_file(filename)

        p = self.settings_display and self.settings_display.player
        if p:
            p.read_widget_record_settings()
            p.read_widget_play_settings()

        for p in Players.players:
            p.read_viewer_settings()

        d = {'recorder': self}
        for i, p in enumerate(Players.players):
            d['player{}'.format(i)] = p

        populate_dump_config(filename, d, from_file=False)
        self.settings_path = filename

    def ui_config(self, load, path, selection, filename):
        fname = abspath(join(path, filename))
        if load:
            self.load_config(fname)
        else:
            self.save_config(fname)

    def display_update_callback(self, *largs):
        for player in Players.players:
            player.player_view.update_cycle()

    @app_error
    def add_player(self, settings={}, show=True, cls='FFmpeg'):
        player = self.source_names[cls](players=self, **settings)
        Players.players.append(player)
        display = PlayerView(player=player, players=self)
        player.player_view = display
        player.display_widget = display.knspace.display.__self__
        self.container.add_widget(display)
        player.write_viewer_settings()

        if self.display_update is None:
            self.display_update = Clock.schedule_interval(
                self.display_update_callback, .1)

        if show:
            self.show_settings(player)

    @app_error
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
                self.settings_display.knspace.display.__self__
            self.settings_display.player = new_player
            new_player.write_widget_settings()
        else:
            new_player.display_widget = \
                player.player_view.knspace.display.__self__
        self.settings_display.knspace.source_type.current = new_cls

    def show_settings(self, player):
        self.settings_display.player = player
        player.write_widget_settings()
        player.display_widget = \
            self.settings_display.knspace.display.__self__
        self.settings_display.open()

    def hide_settings(self, player):
        player.read_widget_play_settings()
        player.read_widget_record_settings()
        player.stop()
        self.settings_display.dismiss()
        self.settings_display.player = None
        player.display_widget = \
            player.player_view.knspace.display.__self__

    @app_error
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


class FilersPlayer(object):

    player_view = None

    display_widget = None

    preview_stats = StringProperty('')

    def write_widget_settings(self):
        kn = self.players.settings_display.knspace
        name = self.cls
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

    @app_error
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

    def play(self):
        if self.players.settings_display.player is self:
            self.read_widget_play_settings()
        super(FilersPlayer, self).play()

    def record(self):
        if self.players.settings_display.player is self:
            self.read_widget_record_settings()
        self.read_viewer_settings()
        super(FilersPlayer, self).record()

    def stop_recording(self, *largs):
        if super(FilersPlayer, self).stop_recording(*largs):
            self.player_view.knspace.record.state = 'normal'
            path_count = self.player_view.knspace.path_count
            if path_count.text:
                path_count.text = str(int(path_count.text) + 1)
            return True
        return False

    def stop(self, *largs):
        if super(FilersPlayer, self).stop(*largs):
            self.player_view.knspace.play.state = 'normal'
            if self.players.settings_display.player == self:
                self.players.settings_display.knspace.play.state = 'normal'
            return True
        return False


class FFmpegFilersPlayer(FilersPlayer, FFmpegPlayer):
    '''Wrapper for ffmapeg based player.
    '''

    def refresh_dshow(self, cams_wid, opts_wid):
        super(FFmpegFilersPlayer, self).refresh_dshow()
        video2 = self.dshow_opts
        names2 = self.dshow_names

        values = sorted(names2.keys())
        # save old vals
        old_name = self.play_filename
        old_opt = self.dshow_opt
        # reset
        cams_wid.text = ''
        cams_wid.values = values
        if values:
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

    def read_widget_play_settings(self):
        super(FFmpegFilersPlayer, self).read_widget_play_settings()
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
        super(FFmpegFilersPlayer, self).write_widget_settings()
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


class RTVFilersPlayer(FilersPlayer, RTVPlayer):
    '''Wrapper for RTV based player.
    '''

    def read_widget_play_settings(self):
        super(RTVFilersPlayer, self).read_widget_play_settings()
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
        super(RTVFilersPlayer, self).write_widget_settings()
        kn = self.players.settings_display.knspace
        kn.rtv_pix_fmt.text = self.metadata_play.fmt
        w, h = self.video_fmts[self.video_fmt]
        kn.rtv_vid_fmt.text = '{} ({}, {})'.format(self.video_fmt, w, h)

        kn.rtv_port.text = str(self.port)
        kn.rtv_pipe_name.text = self.pipe_name
        kn.rtv_remote_name.text = self.remote_computer_name


class PTGrayFilersPlayer(FilersPlayer, PTGrayPlayer):
    '''Wrapper for Point Gray based player.
    '''

    def finish_ask_config(self, item, *largs, **kwargs):
        super(PTGrayFilersPlayer, self).finish_ask_config(
            item, *largs, **kwargs)
        serial = self.players.settings_display.knspace.pt_serial
        ip = self.players.settings_display.knspace.pt_ip
        if 'serial' in kwargs:
            serial.text = str(kwargs['serial'])
            ip.text = kwargs['ip']
        if 'serials' in kwargs:
            serial.values = map(str, kwargs['serials'])
            ip.values = kwargs['ips']

    def read_widget_play_settings(self):
        super(PTGrayFilersPlayer, self).read_widget_play_settings()
        kn = self.players.settings_display.knspace
        s = kn.pt_serial.text
        self.serial = int(s) if s else 0
        self.ip = kn.pt_ip.text

    def write_widget_settings(self):
        super(PTGrayFilersPlayer, self).write_widget_settings()
        kn = self.players.settings_display.knspace
        kn.pt_serial.text = str(self.serial)
        kn.pt_ip.text = self.ip


class PlayerRoot(KNSpaceBehavior, BoxLayout):

    players = ObjectProperty(None, rebind=True)

    def __init__(self, **kwargs):
        super(PlayerRoot, self).__init__(**kwargs)

        def init(*largs):
            p = self.players = Players(container=self.ids.container,
                                       players_view=self)
            self.knspace.recorder_n_rows.text = str(
                min(max(p.cam_grid_rows, 1), 10))
        Clock.schedule_once(init, 0)


class PlayerView(KNSpaceBehavior, EventFocusBehavior, BoxLayout):

    player = ObjectProperty(None, rebind=True)

    players = ObjectProperty(None, rebind=True)

    disk_used_percent = NumericProperty(0)

    elapsed_recording = StringProperty('0.0')

    disk_stat = StringProperty('')

    def on_key_press(self, key):
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
