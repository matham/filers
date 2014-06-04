
__all__ = ('PopupBrowser', 'CountDownTimer', 'BufferImage')


from kivy.properties import NumericProperty, ReferenceListProperty, ObjectProperty,\
ListProperty, StringProperty, BooleanProperty, DictProperty, AliasProperty,\
OptionProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scatter import Scatter
from kivy.uix.popup import Popup
from kivy.graphics.texture import Texture
from kivy.graphics import Rectangle, BindTexture
from kivy.graphics.transformation import Matrix
from kivy.graphics.fbo import Fbo
from kivy.uix.behaviors import DragBehavior
try:
    from kivy.garden.filebrowser import FileBrowser
except:
    import os
    if 'SPHINX_DOC_INCLUDE' not in os.environ:
        raise
from kivy.clock import Clock
import time


class PopupBrowser(DragBehavior, Popup):
    ''' A popup that contains the :class:`FileBrowser` class. It allows
    selection of files and folders.
    '''

    callback = ObjectProperty(None, allownone=True)
    ''' A function that gets called, if not `None`, when a file is selected
    through the `on_success` and `on_submit` events of :class:`FileBrowser`.
    :attr:`callback` will be reset to `None` when the FileBrowser popup is
    dismissed. The parameters passed to the function is `path`, the current
    path for the browser, and `selection`, the list of currently selected
    files. Defaults to None.
    '''


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


class BufferImage(Scatter):
    ''' Class that displays an image and allows its manipulation using touch.
    It receives an ffpyplayer :py:class:`~ffpyplayer.pic.Image` object.
    '''

    iw = NumericProperty(0.)
    ''' The width of the input image. Defaults to zero.
    '''
    ih = NumericProperty(0.)
    ''' The height of the input image. Defaults to zero.
    '''
    last_w = 0
    ''' The width of the screen region available to display the image. Can be
    used to determine if the screen size changed and we need to output a
    different sized image. This gets set internally by :math:`update_img`.
    Defaults to zero.
    '''
    last_h = 0
    ''' The width of the screen region available to display the image. This
    gets set internally by :math:`update_img`. Defaults to zero.
    '''
    fmt = ''
    ''' The input format of the last image passed in. E.g. rgb24, yuv420p, etc.
    '''

    img = None
    ''' Holds the last input :py:class:`~ffpyplayer.pic.Image`.
    '''
    img_texture = None
    ''' The texture into which the images are blitted if not yuv420p.
    Defaults to None.
    '''
    kivy_fmt = ''
    ''' The last kivy color format type of the image. Defaults to `''`. '''
    _tex_y = None
    ''' The y texture into which the y plane of the images are blitted when
    yuv420p. Defaults to None.
    '''
    _tex_u = None
    ''' The u texture into which the u plane of the images are blitted when
    yuv420p. Defaults to None.
    '''
    _tex_v = None
    ''' The v texture into which the v plane of the images are blitted when
    yuv420p. Defaults to None.
    '''
    _fbo = None
    ''' The Fbo used when blitting yuv420p images. '''

    YUV_RGB_FS = b'''
    $HEADER$
    uniform sampler2D tex_y;
    uniform sampler2D tex_u;
    uniform sampler2D tex_v;

    void main(void) {
        float y = texture2D(tex_y, tex_coord0).r;
        float u = texture2D(tex_u, tex_coord0).r - 0.5;
        float v = texture2D(tex_v, tex_coord0).r - 0.5;
        float r = y + 1.402 * v;
        float g = y - 0.344 * u - 0.714 * v;
        float b = y + 1.772 * u;
        gl_FragColor = vec4(r, g, b, 1.0);
    }
    '''
    ''' The shader code used blitting yuv420p images.
    '''

    def update_img(self, img):
        ''' Updates the screen with a new image.
        '''
        if img is None:
            return
        update = False
        img_w, img_h = img.get_size()
        img_fmt = img.get_pixel_format()

        w, h = self.parent.size
        if (not w) or not h:
            self.img = img
            return

        if self.iw != img_w or self.ih != img_h:
            update = True

        if self.fmt != img_fmt:
            self.fmt = img_fmt
            self.kivy_ofmt = {'yuv420p': 'yuv420p', 'rgba': 'rgba',
                              'rgb24': 'rgb', 'gray': 'luminance'}[img_fmt]
            update = True

        if update or w != self.last_w or h != self.last_h:
            scalew, scaleh = w / float(img_w), h / float(img_h)
            scale = min(min(scalew, scaleh), 1)
            self.transform = Matrix()
            self.apply_transform(Matrix().scale(scale, scale, 1),
                                 post_multiply=True)
            self.iw, self.ih = img_w, img_h
            self.last_h = h
            self.last_w = w

        self.img = img
        kivy_ofmt = self.kivy_ofmt

        if update:
            self.canvas.remove_group(str(self) + 'image_display')
            if kivy_ofmt == 'yuv420p':
                w2 = int(img_w / 2)
                h2 = int(img_h / 2)
                self._tex_y = Texture.create(size=(img_w, img_h),
                                             colorfmt='luminance')
                self._tex_u = Texture.create(size=(w2, h2),
                                             colorfmt='luminance')
                self._tex_v = Texture.create(size=(w2, h2),
                                             colorfmt='luminance')
                with self.canvas:
                    self._fbo = fbo = Fbo(size=(img_w, img_h),
                                          group=str(self) + 'image_display')
                with fbo:
                    BindTexture(texture=self._tex_u, index=1)
                    BindTexture(texture=self._tex_v, index=2)
                    Rectangle(size=fbo.size, texture=self._tex_y)
                fbo.shader.fs = BufferImage.YUV_RGB_FS
                fbo['tex_y'] = 0
                fbo['tex_u'] = 1
                fbo['tex_v'] = 2
                tex = self.img_texture = fbo.texture
                fbo.add_reload_observer(self.reload_buffer)
            else:
                tex = self.img_texture = Texture.create(size=(img_w, img_h),
                                                        colorfmt=kivy_ofmt)
                tex.add_reload_observer(self.reload_buffer)

            tex.flip_vertical()
            with self.canvas:
                Rectangle(texture=tex, pos=(0, 0), size=(img_w, img_h),
                          group=str(self) + 'image_display')

        if kivy_ofmt == 'yuv420p':
            dy, du, dv, _ = img.to_memoryview()
            self._tex_y.blit_buffer(dy, colorfmt='luminance')
            self._tex_u.blit_buffer(du, colorfmt='luminance')
            self._tex_v.blit_buffer(dv, colorfmt='luminance')
            self._fbo.ask_update()
            self._fbo.draw()
        else:
            self.img_texture.blit_buffer(img.to_memoryview()[0],
                                         colorfmt=kivy_ofmt)
            self.canvas.ask_update()

    def reload_buffer(self, *args):
        ''' Reloads the last displayed image. It is called whenever the
        screen size changes or the last image need to be recalculated.
        '''
        self.update_img(self.img)
