"""Reusable widgets and small UI helpers."""
from kivy.app import App
from kivy.clock import Clock
from kivy.graphics import Color, Ellipse, Line, Quad, Rectangle, RoundedRectangle, Triangle
from kivy.metrics import dp
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget

import core
import strings as S
import util
from theme import (BLACK, BLUE, BUILD, GREEN, HAS_LOGO, HAS_START, LOGO, RED, START, WHITE,
                   WORDMARK, HAS_WORDMARK, left_text)


def rad(w, h, r):
    """Corner radius that always fits the box (a radius bigger than half the box breaks drawing)."""
    return max(0.0, min(float(r), float(w) / 2.0, float(h) / 2.0))


def settle(w, fn):
    """Redraw on every pos/size change and once more after layout has finished: some Android
    layout passes move a widget without the redraw seeing the final position."""
    w.bind(pos=fn, size=fn)
    trig = Clock.create_trigger(fn, 0)
    w.bind(pos=trig, size=trig, parent=trig)
    trig()


def set_rr(line, x, y, w, h, r):
    """Set a rounded-rectangle outline only when the box has a real size."""
    if w >= 2 and h >= 2:
        line.rounded_rectangle = (x, y, w, h, rad(w, h, r))


def make_input(hint, text="", password=False, filt=None):
    ti = TextInput(text=text, hint_text=hint, multiline=False, password=password,
                   size_hint_y=None, height=dp(48), write_tab=False,
                   input_type="text", keyboard_suggestions=False,
                   use_bubble=True, use_handles=True, input_filter=filt,
                   background_normal="", background_active="", background_disabled_normal="",
                   background_color=(0, 0, 0, 0), foreground_color=BLACK,
                   hint_text_color=(0.45, 0.47, 0.47, 1), cursor_color=BLUE,
                   selection_color=(0, 0.2, 1, 0.3),
                   padding=[dp(14), dp(14), dp(14), dp(8)])
    # the white background must be the FIRST thing drawn: added after the TextInput's own
    # graphics it is painted over the text and the text looks invisible.
    bg = RoundedRectangle()
    ti.canvas.before.insert(0, bg)
    ti.canvas.before.insert(0, Color(*WHITE))
    ti.foreground_color = BLACK

    def fit(*_):
        bg.pos, bg.size = ti.pos, ti.size
        bg.radius = [rad(ti.width, ti.height, dp(14))]
    settle(ti, fit)
    return ti


class Overlay(FloatLayout):
    """Full-screen green layer that sits on top of the app and blocks taps."""

    def __init__(self, **kw):
        kw.setdefault("size_hint", (1, 1))
        kw.setdefault("pos_hint", {"x": 0, "y": 0})   # a FloatLayout child without pos_hint keeps its absolute pos
        super().__init__(**kw)
        with self.canvas.before:
            Color(*GREEN)
            self._bg = Rectangle(pos=self.pos, size=self.size)
        settle(self, self._upd)

    def _upd(self, *_):
        self._bg.pos = self.pos
        self._bg.size = self.size

    def on_touch_down(self, touch):
        if super().on_touch_down(touch):
            return True
        return self.collide_point(*touch.pos)


class Panel(BoxLayout):
    """White rounded card."""

    def __init__(self, bg=WHITE, **kw):
        kw.setdefault("padding", dp(14))
        super().__init__(**kw)
        with self.canvas.before:
            Color(*bg)
            self._r = RoundedRectangle(radius=[dp(18)])
        settle(self, self._upd)

    def _upd(self, *_):
        self._r.pos = self.pos
        self._r.size = self.size
        self._r.radius = [rad(self.width, self.height, dp(18))]


class Card(Panel):
    def __init__(self, text, bg=WHITE, fg=BLACK, **kw):
        super().__init__(bg=bg, size_hint_y=None, **kw)
        self.lbl = Label(text=text, markup=True, color=fg, halign="left",
                         valign="top", size_hint_y=None)
        self.lbl.bind(width=lambda i, w: setattr(i, "text_size", (w, None)))
        self.lbl.bind(texture_size=self._fit)
        self.add_widget(self.lbl)

    def _fit(self, inst, ts):
        inst.height = ts[1]
        self.height = ts[1] + dp(28)


class Pill(Label):
    """Small rounded label, e.g. the 'Ethereum' chip."""

    def __init__(self, bg=BLACK, **kw):
        super().__init__(**kw)
        with self.canvas.before:
            Color(*bg)
            self._r = RoundedRectangle(radius=[dp(16)])
        settle(self, self._upd)

    def _upd(self, *_):
        self._r.pos = self.pos
        self._r.size = self.size
        self._r.radius = [rad(self.width, self.height, dp(16))]


class PillBtn(ButtonBehavior, Pill):
    """The 'Ethereum' chip as a tap target: green status dot, thin white border and a 3x3 grid
    icon so that it looks like something to press."""

    def __init__(self, **kw):
        kw.setdefault("padding", [dp(24), 0, dp(26), 0])
        super().__init__(**kw)
        with self.canvas.after:
            Color(*GREEN)
            self._dot = Ellipse()
            Color(1, 1, 1, 0.85)
            self._ln = Line(rounded_rectangle=(0, 0, 40, 40, dp(16)), width=dp(1.1))
            self._grid = [Rectangle() for _ in range(9)]
        settle(self, self._upd_dot)

    def _upd_dot(self, *_):
        d = dp(9)
        self._dot.size = (d, d)
        self._dot.pos = (self.x + dp(12), self.center_y - d / 2)
        set_rr(self._ln, self.x, self.y, self.width, self.height, dp(16))
        c = dp(3)
        gap = dp(2.5)
        x0 = self.right - dp(14) - (3 * c + 2 * gap)
        y0 = self.center_y - (3 * c + 2 * gap) / 2
        for k, r in enumerate(self._grid):
            r.size = (c, c)
            r.pos = (x0 + (k % 3) * (c + gap), y0 + (k // 3) * (c + gap))


class Ring(Widget):
    """Donut chart: parts = [(fraction, color), ...], fractions add up to <= 1."""

    def __init__(self, **kw):
        super().__init__(**kw)
        self.parts = []
        settle(self, self.redraw)

    def set_parts(self, parts):
        self.parts = parts
        self.redraw()

    def redraw(self, *_):
        self.canvas.clear()
        w = dp(13)
        r = min(self.width, self.height) / 2 - w
        if r <= 0:
            return
        cx, cy = self.center
        with self.canvas:
            Color(0.93, 0.94, 0.94, 1)
            Line(circle=(cx, cy, r), width=w)
            start = 0.0
            for frac, col in self.parts:
                if frac <= 0:
                    continue
                end = min(1.0, start + frac)
                Color(*col)
                Line(circle=(cx, cy, r, start * 360, end * 360), width=w, cap="none")
                start = end


class NavBtn(Button):
    """Flat bottom-bar tab."""

    def __init__(self, **kw):
        super().__init__(background_normal="", background_down="",
                         background_color=(0, 0, 0, 0), font_size="14sp", **kw)


class RoundBtn(Button):
    """Round button (blue by default)."""

    def __init__(self, bg=BLUE, **kw):
        super().__init__(background_normal="", background_down="",
                         background_color=(0, 0, 0, 0), **kw)
        with self.canvas.before:
            Color(*bg)
            self._e = Ellipse()
        settle(self, self._upd)

    def _upd(self, *_):
        d = min(self.width, self.height) - dp(6)
        self._e.size = (d, d)
        self._e.pos = (self.center_x - d / 2, self.center_y - d / 2)


class Choice(Button):
    """Rounded button that can be 'selected' (chips, big buttons)."""

    def __init__(self, base=WHITE, sel=BLUE, fg=BLACK, sel_fg=WHITE, **kw):
        kw.setdefault("valign", "middle")
        super().__init__(background_normal="", background_down="",
                         background_color=(0, 0, 0, 0), color=fg,
                         disabled_color=(0.35, 0.4, 0.4, 1), **kw)
        self.bind(size=lambda i, sz: setattr(i, "text_size", (sz[0], sz[1]) if i.halign == "left" else (None, sz[1])))
        self.base, self.sel, self.fg, self.sel_fg = base, sel, fg, sel_fg
        self._on = False
        self._en = True
        with self.canvas.before:
            self._c = Color(*base)
            self._r = RoundedRectangle(radius=[dp(16)])
        settle(self, self._upd)
        self._paint()

    def _upd(self, *_):
        self._r.pos = self.pos
        self._r.size = self.size
        self._r.radius = [rad(self.width, self.height, dp(16))]

    def _paint(self):
        c = self.sel if self._on else self.base
        self._c.rgba = (c[0], c[1], c[2], 1 if self._en else 0.45)
        self.color = self.sel_fg if self._on else self.fg

    def set_selected(self, on):
        self._on = on
        self._paint()

    def set_enabled(self, en):
        self._en = en
        self.disabled = not en
        self._paint()


class DashedBox(BoxLayout):
    """Transparent box with a dashed black border."""

    def __init__(self, **kw):
        super().__init__(**kw)
        with self.canvas.after:
            Color(*BLACK)
            self._ln = Line(rounded_rectangle=(0, 0, 40, 40, dp(16)), width=dp(1.4),
                            dash_length=dp(5), dash_offset=dp(4))
        settle(self, self._upd)

    def _upd(self, *_):
        set_rr(self._ln, self.x, self.y, self.width, self.height, dp(16))


def label(text, **kw):
    kw.setdefault("color", BLACK)
    kw.setdefault("halign", "left")
    kw.setdefault("valign", "middle")
    lab = Label(text=text, markup=True, **kw)
    lab.bind(size=lambda i, s: setattr(i, "text_size", s))
    return lab


def offer_card(o):
    colors = {"redeemable": "00a82d", "expiring": "0b0b0b", "expired": "b00021"}
    return Card(S.OFFER_CARD.format(
        kind=o["kind"], count=o["count"], id=o["id"],
        pin=S.OFFER_PIN_TAG if o["kind"] == "G" else "",
        color=colors.get(o["status"], "0b0b0b"),
        status=S.STATUS.get(o["status"], o["status"]),
        eth=core.eth(o["count"] * core.UNIT), left=left_text(o["left"]),
        sendable=S.YES if o["sendable"] else S.NO, sweepable_at=o["sweepable_at"]))


def title_row(text, link_text=None, on_link=None):
    row = BoxLayout(size_hint_y=None, height=dp(34))
    row.add_widget(label(f"[b]{text}[/b]", font_size="18sp"))
    if link_text:
        btn = NavBtn(text=f"[u]{link_text}[/u]", markup=True, color=BLACK,
                     size_hint_x=None, width=dp(90))
        btn.bind(on_release=lambda *_: on_link())
        row.add_widget(btn)
    return row


class Divider(Widget):
    """Thin horizontal line between rows."""

    def __init__(self, color=(0.9, 0.91, 0.91, 1), **kw):
        kw.setdefault("size_hint_y", None)
        kw.setdefault("height", dp(1))
        super().__init__(**kw)
        with self.canvas:
            Color(*color)
            self._r = Rectangle()
        settle(self, self._upd)

    def _upd(self, *_):
        self._r.pos = self.pos
        self._r.size = self.size


class Check(Widget):
    """Tick box. `active` is True when ticked; on_change(active) is called on every tap."""

    def __init__(self, on_change=None, **kw):
        kw.setdefault("size_hint", (None, None))
        kw.setdefault("size", (dp(34), dp(34)))
        super().__init__(**kw)
        self.active = False
        self.on_change = on_change
        settle(self, self.redraw)
        self.redraw()

    def redraw(self, *_):
        self.canvas.clear()
        x, y = self.pos
        w, h = self.size
        with self.canvas:
            Color(*(BLUE if self.active else WHITE))
            RoundedRectangle(pos=self.pos, size=self.size, radius=[rad(self.width, self.height, dp(6))])
            if self.active:
                Color(*WHITE)
                Line(points=[x + w * .22, y + h * .52, x + w * .42, y + h * .30,
                             x + w * .78, y + h * .72], width=dp(2.6))

    def toggle(self):
        self.active = not self.active
        self.redraw()
        if self.on_change:
            self.on_change(self.active)

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self.toggle()
            return True
        return super().on_touch_down(touch)


class LockIcon(Widget):
    """Blue padlock on a light-blue rounded square."""

    def __init__(self, **kw):
        kw.setdefault("size_hint", (None, None))
        kw.setdefault("size", (dp(54), dp(60)))
        super().__init__(**kw)
        settle(self, self.redraw)
        self.redraw()

    def redraw(self, *_):
        self.canvas.clear()
        x, y = self.pos
        w, h = self.size
        if w < 20 or h < 20:
            return
        with self.canvas:
            Color(0.87, 0.9, 1, 1)
            RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(16)])
            Color(*BLUE)
            Line(rounded_rectangle=(x + w * .34, y + h * .42, w * .32, h * .28, dp(8)),
                 width=dp(2.4))
            RoundedRectangle(pos=(x + w * .26, y + h * .24), size=(w * .48, h * .30),
                             radius=[dp(5)])


class Dot(Label):
    """Round numbered marker used in the step list."""

    def __init__(self, bg=BLUE, **kw):
        kw.setdefault("size_hint", (None, None))
        kw.setdefault("size", (dp(40), dp(40)))
        kw.setdefault("bold", True)
        super().__init__(**kw)
        with self.canvas.before:
            self._c = Color(*bg)
            self._e = Ellipse()
        settle(self, self._upd)

    def _upd(self, *_):
        self._e.pos = self.pos
        self._e.size = self.size


class Steps(BoxLayout):
    """Vertical list of equal rows with a line running through the dots."""

    def __init__(self, **kw):
        kw.setdefault("orientation", "vertical")
        super().__init__(**kw)
        with self.canvas.before:
            Color(0.78, 0.8, 0.8, 1)
            self._ln = Line(points=[0, 0, 0, 0], width=dp(3))
        settle(self, self.update_line)

    def update_line(self, *_):
        n = max(len(self.children), 1)
        row = self.height / n
        x = self.x + dp(25)
        self._ln.points = [x, self.top - row / 2, x, self.y + row / 2]


class Tappable(ButtonBehavior, Panel):
    """White card that can be tapped (on_release) and shows a blue border when selected."""

    def __init__(self, **kw):
        super().__init__(**kw)
        with self.canvas.after:
            self._bc = Color(0, 0, 0, 0)
            self._ln = Line(rounded_rectangle=(0, 0, 40, 40, dp(18)), width=dp(2))
        settle(self, self._upd_border)

    def _upd_border(self, *_):
        set_rr(self._ln, self.x, self.y, self.width, self.height, dp(18))

    def set_selected(self, on):
        self._bc.rgba = BLUE if on else (0, 0, 0, 0)


class Badge(Label):
    """Rounded square with the offer type letter (B, T, P, G)."""
    STYLE = {"B": (BLUE, WHITE), "T": (BLACK, WHITE), "P": (GREEN, WHITE), "G": (WHITE, BLACK)}

    def __init__(self, kind, **kw):
        kw.setdefault("size_hint", (None, None))
        kw.setdefault("size", (dp(48), dp(48)))
        bg, fg = self.STYLE.get(kind, (BLACK, WHITE))
        super().__init__(text=kind, color=fg, bold=True, font_size="20sp", **kw)
        with self.canvas.before:
            Color(*bg)
            self._r = RoundedRectangle(radius=[dp(12)])
            if kind == "G":
                Color(*BLACK)
                self._ln = Line(rounded_rectangle=(0, 0, 40, 40, dp(12)), width=dp(2))
            else:
                self._ln = None
        settle(self, self._upd)

    def _upd(self, *_):
        self._r.pos = self.pos
        self._r.size = self.size
        self._r.radius = [rad(self.width, self.height, dp(12))]
        if self._ln is not None:
            set_rr(self._ln, self.x, self.y, self.width, self.height, dp(12))


class ThinBar(Widget):
    """Thin rounded bar: frac = share of the window still left (0..1)."""

    def __init__(self, frac=0.0, color=GREEN, **kw):
        kw.setdefault("size_hint_y", None)
        kw.setdefault("height", dp(8))
        super().__init__(**kw)
        self.frac = max(0.0, min(1.0, frac))
        self.color = color
        settle(self, self.redraw)
        self.redraw()

    def redraw(self, *_):
        self.canvas.clear()
        if self.width < 2 or self.height < 2:
            return
        r = rad(self.width, self.height, dp(4))
        with self.canvas:
            Color(0.9, 0.91, 0.91, 1)
            RoundedRectangle(pos=self.pos, size=self.size, radius=[r])
            if self.frac > 0:
                Color(*self.color)
                w = min(self.width, max(self.width * self.frac, dp(8)))
                RoundedRectangle(pos=self.pos, size=(w, self.height),
                                 radius=[rad(w, self.height, dp(4))])


# ---------------------------------------------------------------- shell widgets
class PullScroll(ScrollView):
    """ScrollView that calls `on_pull()` when the person pulls down past the top.

    The pull is measured by touch: the touch must start while the list is at the top, travel
    down by PULL_DP and still be at the top when the finger lifts."""
    PULL_DP = 110

    def __init__(self, on_pull=None, **kw):
        super().__init__(**kw)
        self.on_pull = on_pull
        self._pt = None

    def on_touch_down(self, touch):
        self._pt = touch if (self.collide_point(*touch.pos) and self.scroll_y >= 0.999) else None
        return super().on_touch_down(touch)

    def on_touch_up(self, touch):
        pt, self._pt = self._pt, None
        res = super().on_touch_up(touch)
        if pt is touch and (touch.oy - touch.y) > dp(self.PULL_DP) and self.scroll_y >= 0.98:
            self.pulled()
        return res

    def pulled(self):
        if self.on_pull:
            self.on_pull()
            return
        app = App.get_running_app()
        if app is not None and hasattr(app, "reload"):
            app.reload()


class Tap(ButtonBehavior, BoxLayout):
    """Any layout that can be tapped."""


class LogoBtn(ButtonBehavior, Image):
    """The logo in the header: tap = back to the Wallet page."""


class Caret(ButtonBehavior, Widget):
    """Down-arrow chip under the logo (large tap area). `open` flips the arrow up."""

    def __init__(self, **kw):
        kw.setdefault("size_hint", (None, None))
        kw.setdefault("size", (dp(56), dp(34)))
        super().__init__(**kw)
        self.open = False
        settle(self, self.redraw)

    def set_open(self, on):
        self.open = on
        self.redraw()

    def redraw(self, *_):
        self.canvas.clear()
        if self.width < 8 or self.height < 8:
            return
        cx, cy = self.center
        a = dp(7)
        w, h = min(self.width, dp(48)), min(self.height, dp(28))
        with self.canvas:
            Color(0, 0, 0, 0.18)
            RoundedRectangle(pos=(cx - w / 2, cy - h / 2), size=(w, h), radius=[rad(w, h, dp(14))])
            Color(*WHITE)
            if self.open:
                Triangle(points=[cx - a, cy - a / 2, cx + a, cy - a / 2, cx, cy + a / 2])
            else:
                Triangle(points=[cx - a, cy + a / 2, cx + a, cy + a / 2, cx, cy - a / 2])


class ErrorBanner(BoxLayout):
    """Red strip with the error text, a Copy button (full text) and a Close button."""

    def __init__(self, short_text, full_text, on_close, **kw):
        kw.setdefault("size_hint", (1, None))
        kw.setdefault("height", dp(108))
        kw.setdefault("padding", [dp(12), dp(8)])
        kw.setdefault("spacing", dp(8))
        super().__init__(**kw)
        self.full = full_text
        with self.canvas.before:
            Color(*RED)
            self._bg = Rectangle()
        settle(self, self._upd)
        lab = Label(text=short_text, color=WHITE, font_size="13sp", halign="left",
                    valign="middle", shorten=True, shorten_from="right", max_lines=5)
        lab.bind(size=lambda i, s: setattr(i, "text_size", s))
        self.add_widget(lab)
        col = BoxLayout(orientation="vertical", size_hint_x=None, width=dp(84), spacing=dp(6))
        cp = Choice(base=WHITE, text=S.BTN_COPY, bold=True, font_size="13sp")
        cp.bind(on_release=lambda *_: util.copy_text(self.full))
        cl = Choice(base=BLACK, fg=WHITE, text=S.BTN_CLOSE, bold=True, font_size="13sp")
        cl.bind(on_release=lambda *_: on_close(self))
        col.add_widget(cp)
        col.add_widget(cl)
        self.add_widget(col)

    def _upd(self, *_):
        self._bg.pos = self.pos
        self._bg.size = self.size


class Tile(ButtonBehavior, BoxLayout):
    """Round launcher tile: coloured circle with a glyph, caption below."""

    def __init__(self, glyph, caption, color, enabled=True, **kw):
        kw.setdefault("orientation", "vertical")
        kw.setdefault("spacing", dp(6))
        super().__init__(**kw)
        col = tuple(color[:3]) + ((1,) if enabled else (0.35,))
        self.disc = Label(text=glyph, bold=True, font_size="26sp", color=WHITE,
                          size_hint=(1, None), height=dp(68))
        with self.disc.canvas.before:
            Color(*col)
            self._e = Ellipse()
        settle(self.disc, self._upd)
        self.add_widget(self.disc)
        cap = Label(text=caption, color=BLACK if enabled else (0.5, 0.52, 0.52, 1),
                    font_size="12sp", halign="center", valign="top")
        cap.bind(size=lambda i, s: setattr(i, "text_size", s))
        self.add_widget(cap)

    def _upd(self, *_):
        d = max(2.0, min(self.disc.width, self.disc.height) - dp(4))
        self._e.size = (d, d)
        self._e.pos = (self.disc.center_x - d / 2, self.disc.center_y - d / 2)


class Welcome(FloatLayout):
    """Start screen: the big start image (flat green with the logo) as background, and below the
    logo the wordmark, the rate line, the slogan, a blue spinner, 'Connecting...' and the version.
    Without the image: flat green with a small logo."""

    def __init__(self, **kw):
        kw.setdefault("size_hint", (1, 1))
        kw.setdefault("pos_hint", {"x": 0, "y": 0})
        super().__init__(**kw)
        self._angle = 0.0
        self._ev = None
        with self.canvas.before:
            Color(*GREEN)
            self._bg = Rectangle()
        if HAS_START:
            self.bgimg = Image(source=START, size_hint=(1, 1), pos_hint={"x": 0, "y": 0},
                               fit_mode="cover")
            self.add_widget(self.bgimg)
            self.logo = None
        else:
            self.bgimg = None
            self.logo = Image(source=LOGO, size_hint=(None, None)) if HAS_LOGO else None
            if self.logo is not None:
                self.add_widget(self.logo)
        if HAS_WORDMARK:
            self.word = Image(source=WORDMARK, size_hint=(None, None))
        else:
            self.word = Label(text="dSOS", bold=True, font_size="56sp", color=WHITE,
                              size_hint=(None, None))
        self.add_widget(self.word)
        self.tag1 = Label(text=S.WELCOME_RATE, color=WHITE, font_size="16sp",
                          size_hint=(1, None), height=dp(28))
        self.tag2 = Label(text=S.WELCOME_SLOGAN, color=WHITE, font_size="20sp", halign="center",
                          valign="middle", size_hint=(1, None), height=dp(64))
        self.tag2.bind(size=lambda i, s: setattr(i, "text_size", s))
        self.status = Label(text=S.WELCOME_CONNECTING, color=WHITE, font_size="17sp",
                            size_hint=(1, None), height=dp(28))
        self.ver = Label(text=BUILD, color=(1, 1, 1, 0.7), font_size="12sp",
                         size_hint=(1, None), height=dp(22))
        for w in (self.tag1, self.tag2, self.status, self.ver):
            self.add_widget(w)
        with self.canvas:
            Color(1, 1, 1, 0.25)
            self._ring = Line(circle=(0, 0, 10), width=dp(2.2))
            Color(0.1, 0.35, 1, 1)
            self._arc = Line(circle=(0, 0, 10, 0, 100), width=dp(2.2))
        settle(self, self.layout)
        self.layout()

    def layout(self, *_):
        x, y = self.pos
        w, h = self.size
        if w < 10 or h < 10:
            return
        self._bg.pos, self._bg.size = (x, y), (w, h)
        if self.logo is not None:                      # fallback only (no start image)
            lg = min(w * 0.4, h * 0.22)
            self.logo.size = (lg, lg)
            self.logo.pos = (x + w / 2 - lg / 2, y + 0.50 * h - lg / 2)
        ww = min(w * 0.62, dp(300))
        if HAS_WORDMARK:
            self.word.size = (ww, ww * 111.0 / 371.0)
        else:
            self.word.size = (ww, dp(70))
        self.word.pos = (x + w / 2 - ww / 2, y + 0.35 * h - self.word.height / 2)
        self.tag1.pos = (x, y + 0.28 * h - self.tag1.height / 2)
        self.tag2.pos = (x, y + 0.21 * h - self.tag2.height / 2)
        sr = dp(17)
        scx, scy = x + w / 2, y + 0.14 * h
        self._ring.circle = (scx, scy, sr)
        self._spin_c = (scx, scy, sr)
        self._draw_arc()
        self.status.pos = (x, y + 0.09 * h - self.status.height / 2)
        self.ver.pos = (x, y + 0.05 * h - self.ver.height / 2)

    def _draw_arc(self):
        cx, cy, r = getattr(self, "_spin_c", (0, 0, 10))
        self._arc.circle = (cx, cy, r, self._angle, self._angle + 100)

    def _tick(self, dt):
        self._angle = (self._angle + 300 * dt) % 360
        self._draw_arc()

    def start(self):
        if self._ev is None:
            self._ev = Clock.schedule_interval(self._tick, 1 / 30.0)

    def stop(self):
        if self._ev is not None:
            self._ev.cancel()
            self._ev = None

    def on_touch_down(self, touch):
        return self.collide_point(*touch.pos)


def page_head(app, title):
    """Back button + title row used by every overlay page."""
    head = BoxLayout(size_hint_y=None, height=dp(64), padding=[dp(14), dp(8)], spacing=dp(14))
    back = IconBtn(icon="back", bg=WHITE, color=BLACK,
                    size_hint=(None, 1), width=dp(52))
    back.bind(on_release=lambda *_: app.close_top())
    head.add_widget(back)
    head.add_widget(label(title, font_size="24sp"))
    return head


# ---------------------------------------------------------------- icons (drawn, no font needed)
class Icon(Widget):
    """Simple line icon drawn on a unit square. name: plus minus back chevron send recv lock
    wallet list credits clock user."""

    def __init__(self, name, color=WHITE, **kw):
        kw.setdefault("size_hint", (None, None))
        kw.setdefault("size", (dp(26), dp(26)))
        super().__init__(**kw)
        self.name = name
        self.color = color
        settle(self, self.redraw)

    def set_color(self, c):
        self.color = c
        self.redraw()

    def redraw(self, *_):
        self.canvas.clear()
        s = min(self.width, self.height)
        if s < 6:
            return
        ox, oy = self.center_x - s / 2, self.center_y - s / 2

        def P(*pts):
            return [v for i in range(0, len(pts), 2)
                    for v in (ox + pts[i] * s, oy + pts[i + 1] * s)]
        lw = max(dp(1.8), s * 0.085)
        n = self.name
        with self.canvas:
            Color(*self.color)
            if n in ("plus", "minus"):
                Line(points=P(0.2, 0.5, 0.8, 0.5), width=lw, cap="round")
                if n == "plus":
                    Line(points=P(0.5, 0.2, 0.5, 0.8), width=lw, cap="round")
            elif n == "back":
                Line(points=P(0.62, 0.2, 0.34, 0.5, 0.62, 0.8), width=lw, cap="round", joint="round")
            elif n == "chevron":
                Line(points=P(0.38, 0.2, 0.66, 0.5, 0.38, 0.8), width=lw, cap="round", joint="round")
            elif n == "send":
                Line(points=P(0.25, 0.25, 0.75, 0.75), width=lw, cap="round")
                Line(points=P(0.38, 0.75, 0.75, 0.75, 0.75, 0.38), width=lw, cap="round", joint="round")
            elif n == "recv":
                Line(points=P(0.75, 0.75, 0.25, 0.25), width=lw, cap="round")
                Line(points=P(0.25, 0.62, 0.25, 0.25, 0.62, 0.25), width=lw, cap="round", joint="round")
            elif n == "lock":
                Line(rounded_rectangle=(ox + 0.2 * s, oy + 0.14 * s, 0.6 * s, 0.44 * s, 0.08 * s),
                     width=lw)
                Line(circle=(ox + 0.5 * s, oy + 0.58 * s, 0.17 * s, -90, 90), width=lw)
            elif n == "wallet":
                Line(rounded_rectangle=(ox + 0.12 * s, oy + 0.22 * s, 0.76 * s, 0.52 * s, 0.1 * s),
                     width=lw)
                Line(points=P(0.62, 0.48, 0.78, 0.48), width=lw, cap="round")
            elif n == "list":
                for y in (0.3, 0.5, 0.7):
                    Line(points=P(0.4, y, 0.86, y), width=lw, cap="round")
                    Ellipse(pos=(ox + 0.16 * s, oy + (y - 0.05) * s), size=(0.1 * s, 0.1 * s))
            elif n == "credits":
                Line(circle=(ox + 0.5 * s, oy + 0.5 * s, 0.38 * s), width=lw)
                Line(points=P(0.6, 0.64, 0.42, 0.64, 0.42, 0.5, 0.58, 0.5, 0.58, 0.36, 0.4, 0.36),
                     width=lw * 0.8, joint="round")
            elif n == "clock":
                Line(circle=(ox + 0.5 * s, oy + 0.5 * s, 0.38 * s), width=lw)
                Line(points=P(0.5, 0.5, 0.5, 0.74), width=lw, cap="round")
                Line(points=P(0.5, 0.5, 0.67, 0.4), width=lw, cap="round")
            elif n == "user":
                Line(circle=(ox + 0.5 * s, oy + 0.64 * s, 0.14 * s), width=lw)
                Line(circle=(ox + 0.5 * s, oy + 0.18 * s, 0.3 * s, -90, 90), width=lw)


class IconBtn(ButtonBehavior, FloatLayout):
    """Round button with a drawn icon on it."""

    def __init__(self, icon, bg=BLUE, color=WHITE, icon_size=26, **kw):
        super().__init__(**kw)
        self._bg = bg
        with self.canvas.before:
            self._c = Color(*bg)
            self._e = Ellipse()
        self.icon = Icon(icon, color=color, size=(dp(icon_size), dp(icon_size)),
                         pos_hint={"center_x": 0.5, "center_y": 0.5})
        self.add_widget(self.icon)
        settle(self, self._upd)

    def _upd(self, *_):
        d = max(2.0, min(self.width, self.height) - dp(6))
        self._e.size = (d, d)
        self._e.pos = (self.center_x - d / 2, self.center_y - d / 2)


class NavTab(ButtonBehavior, BoxLayout):
    """Bottom bar tab: drawn icon above a label."""

    def __init__(self, icon, text, **kw):
        super().__init__(orientation="vertical", padding=[0, dp(8), 0, dp(4)], spacing=dp(2), **kw)
        holder = FloatLayout(size_hint_y=None, height=dp(28))
        self.icon = Icon(icon, color=(0.6, 0.62, 0.62, 1), pos_hint={"center_x": 0.5, "center_y": 0.5})
        holder.add_widget(self.icon)
        self.add_widget(holder)
        self.lab = Label(text=text, font_size="12sp", color=(0.6, 0.62, 0.62, 1))
        self.add_widget(self.lab)

    def set_active(self, on):
        c = WHITE if on else (0.6, 0.62, 0.62, 1)
        self.icon.set_color(c)
        self.lab.color = c
        self.lab.bold = on


STATUS_PILL = {}   # filled lazily from page styles: status -> (bg, fg)


def status_pill(text, bg, fg):
    return Pill(text=text, bg=bg, color=fg, bold=True, font_size="13sp", size_hint=(None, None),
                size=(dp(108), dp(30)), pos_hint={"center_y": 0.5})


OFFER_STATUS_STYLE = {"redeemable": ((0.88, 0.97, 0.90, 1), (0.04, 0.48, 0.17, 1)),
                      "expiring": (BLACK, WHITE),
                      "expired": ((1, 0.9, 0.9, 1), RED)}


def offer_row(o, on_tap=None):
    """Compact offer row as in the mockup: badge, '5 dSOS · #482', second line, status pill."""
    bg, fg = OFFER_STATUS_STYLE.get(o["status"], OFFER_STATUS_STYLE["redeemable"])
    c = Tappable(padding=[dp(12), dp(10)], spacing=dp(12), size_hint_y=None, height=dp(78))
    if on_tap:
        c.bind(on_release=lambda *_: on_tap())
    c.add_widget(Badge(o["kind"], pos_hint={"center_y": 0.5}))
    mid = BoxLayout(orientation="vertical")
    mid.add_widget(label(S.OC_TITLE.format(
        count=o["count"], id=o["id"], pin=S.OFFER_PIN_TAG if o["kind"] == "G" else ""),
        font_size="16sp"))
    eth = core.eth(o["count"] * core.UNIT)
    sub = S.WROW_EXPIRED if o["left"] <= 0 else S.WROW_SUB.format(eth=eth, left=left_text(o["left"]))
    mid.add_widget(label(sub, font_size="13sp"))
    c.add_widget(mid)
    c.add_widget(status_pill(S.STATUS.get(o["status"], o["status"]), bg, fg))
    return c


class TypeCard(Tappable):
    """Offer type tile as in the mockup: badge, title, one-line subtitle, blue border if chosen."""

    def __init__(self, code, title, sub, color_hex, **kw):
        kw.setdefault("padding", [dp(12), dp(8)])
        kw.setdefault("spacing", dp(12))
        super().__init__(**kw)
        self.add_widget(Badge(code, size=(dp(44), dp(44)), pos_hint={"center_y": 0.5}))
        mid = BoxLayout(orientation="vertical")
        mid.add_widget(label(f"[b]{title}[/b]", font_size="16sp"))
        mid.add_widget(label(sub, font_size="13sp"))
        self.add_widget(mid)


class IconRow(ButtonBehavior, BoxLayout):
    """Row: blue round icon, two-line text (set `.text`), chevron. Tap = on_release."""

    def __init__(self, icon, **kw):
        kw.setdefault("spacing", dp(12))
        super().__init__(**kw)
        self.add_widget(IconBtn(icon=icon, bg=BLUE, color=WHITE, icon_size=22,
                                size_hint=(None, 1), width=dp(52)))
        self.lab = label("", font_size="16sp")
        self.add_widget(self.lab)
        self.add_widget(Icon("chevron", color=BLACK, size=(dp(22), dp(22)),
                             pos_hint={"center_y": 0.5}))

    @property
    def text(self):
        return self.lab.text

    @text.setter
    def text(self, v):
        self.lab.text = v
