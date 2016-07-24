'''Widgets
==========

Various widgets used in Filers.
'''

import time
from functools import partial

from kivy.properties import (
    NumericProperty, ReferenceListProperty, ObjectProperty,
    ListProperty, StringProperty, BooleanProperty, DictProperty, AliasProperty,
    OptionProperty)
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.spinner import Spinner
from kivy.core.window import Keyboard
from kivy.uix.checkbox import CheckBox
from kivy.clock import Clock

__all__ = ('SilentCheckBox', 'CountDownTimer', 'ColoredSpinner')

keycodes_nums = {v: k for k, v in Keyboard.keycodes.items()}


class CountDownTimer(BoxLayout):
    ''' Widget that displays a countdown timer.
    '''

    counter = NumericProperty(0)
    ''' The current value of the counter, whether counting down, or paused.
    Defaults to zero.
    '''
    counting = BooleanProperty(False)
    ''' True when the timer is counting down, False when it's paused or
    stopped. Read only. Defaults to False.
    '''
    blink_color = ListProperty([0, 0, 0, .5])
    ''' The background color of the timer. When the timer counts out, it is
    changed to generate a blinking effect.
    '''
    _start_time = 0
    ''' The system time when last countdown started.
    '''
    _start_count = 0
    ''' The initial counter value when countdown starts. :attr:`counter` is
    updated continuously as time runs down. This keeps the original value so
    that float errors don't add up and we can simply subtract current time
    from start time to get counter value.
    '''
    _blinking = False
    ''' Whether background is blinking. If True, the background blinks at
    0.33Hz.
    '''

    def count_start(self):
        ''' Starts the counter to count down from the current value of
        :attr:`counter`. When the counter reaches zero, the background will
        blink.

        :return:

            `'normal'` if the counter failed, `'down'` if it started the
            countdown.
        '''
        self.counting = True
        if not self.counter:
            self.counting = False
            return 'normal'
        self._start_count = self.counter
        self._start_time = time.clock()
        self._blinking = False
        Clock.schedule_interval(self.refresh, 1 / 10.)
        return 'down'

    def count_end(self):
        ''' Stops the countdown. If the background was blinking, it'll stop.
        '''
        self.counting = False
        self.blink_color = [0, 0, 0, .5]
        Clock.unschedule(self.refresh)

    def refresh(self, *largs):
        ''' Method that gets called at 0.1Hz during the countdown and at 0.33Hz
        when the countdown reached zero and the background blinks. It updates
        the background color and :attr:`counter`.
        '''
        if self._blinking:
            c = self.blink_color
            if c == [0, 1, 0, 1]:
                self.blink_color = [1, 0, 1, 1]
            else:
                self.blink_color = [0, 1, 0, 1]
            return
        diff = time.clock() - self._start_time
        if diff > self._start_count:
            Clock.unschedule(self.refresh)
            Clock.schedule_interval(self.refresh, 1 / 3.)
            self.counter = 0.0000001
            self._blinking = True
            self.refresh()
        else:
            self.counter = self._start_count - diff


class SilentCheckBox(CheckBox):

    def on_touch_down(self, touch):
        pass

    def on_touch_move(self, touch):
        pass

    def on_touch_up(self, touch):
        pass


def get_spinner_opt(spinner, cls, **kwargs):
    kwargs['background_normal'] = spinner.background_normal
    kwargs['background_color'] = spinner.background_color
    return cls(**kwargs)


class ColoredSpinner(Spinner):

    def __init__(self, **kwargs):
        self.option_cls = partial(get_spinner_opt, self, self.option_cls)
        super(ColoredSpinner, self).__init__(**kwargs)
