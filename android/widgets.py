"""Reusable widgets and small UI helpers."""
from kivy.graphics import Color, Ellipse, Line, Rectangle, RoundedRectangle
from kivy.metrics import dp
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget
from kivy.clock import Clock

import core
import strings as S
from theme import (BLACK, BLUE, GREEN, HAS_LOGO, LOGO, WHITE, left_text)


def make_input(hint, text="", password=False, filt=None):
    return TextInput(text=text, hint_text=hint, multiline=False, password=password,
                     size_hint_y=None, height=dp(44), write_tab=False,
                     input_type="text", keyboard_suggestions=False,
                     use_bubble=True, use_handles=True, input_filter=filt,
                     padding=[dp(10), dp(12), dp(10), dp(8)])


class Overlay(FloatLayout):
    """Full-screen green layer that sits on top of the app and blocks taps."""

    def __init__(self, **kw):
        super().__init__(**kw)
        with self.canvas.before:
            Color(*GREEN)
            self._bg = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._upd, size=self._upd)

    def _upd(self, *_):
        self._bg.pos = self.pos
        self._bg.size = self.size

    def on_touch_down(self, touch):
        if super().on_touch_down(touch):
            return True
        return self.collide_point(*touch.pos)


class Splash(FloatLayout):
    """v8 Welcome / splash: near-black with green/blue light streaks, logo, wordmark, spinner."""

    def __init__(self, **kw):
        super().__init__(**kw)
        with self.canvas.before:
            Color(0.04, 0.05, 0.06, 1)
            self._bg = Rectangle(pos=self.pos, size=self.size)
            # green glow top-left
            Color(0.02, 0.55, 0.18, 0.35)
            self._glow = Ellipse(pos=(-dp(80), self.height * 0.55 if self.height else 400),
                                 size=(dp(320), dp(320)))
            # diagonal green streaks (left)
            Color(0.05, 0.7, 0.25, 0.18)
            self._g1 = Line(points=[], width=dp(3))
            self._g2 = Line(points=[], width=dp(2))
            # blue streaks (right / bottom)
            Color(0.1, 0.25, 0.9, 0.16)
            self._b1 = Line(points=[], width=dp(2.5))
            self._b2 = Line(points=[], width=dp(2))
        self.bind(pos=self._upd_splash, size=self._upd_splash)

        col = BoxLayout(orientation="vertical", size_hint=(0.88, 0.78),
                        pos_hint={"center_x": 0.5, "center_y": 0.52}, spacing=dp(8))
        if HAS_LOGO:
            col.add_widget(Image(source=LOGO, size_hint=(None, None),
                                 size=(dp(96), dp(96)),
                                 pos_hint={"center_x": 0.5}))
        col.add_widget(Label(text="[b]dSOS[/b]", markup=True, font_size="42sp",
                             color=WHITE, size_hint_y=None, height=dp(52),
                             halign="center"))
        col.add_widget(Label(text="1 dSOS = 1 slice = 0.001 ETH",
                             font_size="15sp", color=(0.75, 0.9, 0.8, 1),
                             size_hint_y=None, height=dp(28), halign="center"))
        col.add_widget(Label(text="Decentralized. Trustless.\nYours.",
                             markup=True, font_size="18sp", color=WHITE,
                             size_hint_y=None, height=dp(52),
                             halign="center", valign="middle"))
        self._spin_lbl = Label(text="Connecting...", font_size="14sp",
                               color=(0.55, 0.7, 1, 1), size_hint_y=None, height=dp(28))
        col.add_widget(self._spin_lbl)
        from theme import APP_VERSION, APP_BUILD, APP_COMMIT
        col.add_widget(Label(
            text=f"{APP_VERSION} · build {APP_BUILD} · {APP_COMMIT}",
            font_size="12sp", color=(0.45, 0.5, 0.55, 1),
            size_hint_y=None, height=dp(22)))
        self.add_widget(col)
        self._angle = 0
        Clock.schedule_interval(self._tick_spin, 0.05)

    def _upd_splash(self, *_):
        self._bg.pos = self.pos
        self._bg.size = self.size
        h, w = self.height or 1, self.width or 1
        self._glow.pos = (-dp(60), h * 0.55)
        self._glow.size = (dp(300), dp(300))
        # green diagonals left
        self._g1.points = [0, h * 0.85, w * 0.35, h * 0.55]
        self._g2.points = [0, h * 0.65, w * 0.28, h * 0.40]
        # blue diagonals right/bottom
        self._b1.points = [w * 0.55, h * 0.25, w, h * 0.05]
        self._b2.points = [w * 0.40, 0, w, h * 0.30]

    def _tick_spin(self, dt):
        self._angle = (self._angle + 12) % 360
        # simple text pulse instead of a real spinner widget
        dots = "." * (1 + (self._angle // 90) % 3)
        self._spin_lbl.text = "Connecting" + dots
        return True

    def on_touch_down(self, touch):
        return True  # block everything while splash is up


class Panel(BoxLayout):
    """White rounded card."""

    def __init__(self, bg=WHITE, **kw):
        kw.setdefault("padding", dp(14))
        super().__init__(**kw)
        with self.canvas.before:
            Color(*bg)
            self._r = RoundedRectangle(radius=[dp(18)])
        self.bind(pos=self._upd, size=self._upd)

    def _upd(self, *_):
        self._r.pos = self.pos
        self._r.size = self.size


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
        self.bind(pos=self._upd, size=self._upd)

    def _upd(self, *_):
        self._r.pos = self.pos
        self._r.size = self.size


class Ring(Widget):
    """Donut chart: parts = [(fraction, color), ...], fractions add up to <= 1."""

    def __init__(self, **kw):
        super().__init__(**kw)
        self.parts = []
        self.bind(pos=self.redraw, size=self.redraw)

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
        self.bind(pos=self._upd, size=self._upd)

    def _upd(self, *_):
        d = min(self.width, self.height) - dp(6)
        self._e.size = (d, d)
        self._e.pos = (self.center_x - d / 2, self.center_y - d / 2)


class Choice(Button):
    """Rounded button that can be 'selected' (chips, big buttons)."""

    def __init__(self, base=WHITE, sel=BLUE, fg=BLACK, sel_fg=WHITE, **kw):
        super().__init__(background_normal="", background_down="",
                         background_color=(0, 0, 0, 0), color=fg, **kw)
        self.base, self.sel, self.fg, self.sel_fg = base, sel, fg, sel_fg
        self._on = False
        self._en = True
        with self.canvas.before:
            self._c = Color(*base)
            self._r = RoundedRectangle(radius=[dp(16)])
        self.bind(pos=self._upd, size=self._upd)
        self._paint()

    def _upd(self, *_):
        self._r.pos = self.pos
        self._r.size = self.size

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


class TypeCard(Button):
    """Offer type tile with a blue border when selected."""

    def __init__(self, code, title, sub, color_hex, **kw):
        super().__init__(background_normal="", background_down="",
                         background_color=(0, 0, 0, 0), markup=True, halign="left",
                         valign="middle", color=BLACK, padding_x=dp(14),
                         text=(f"[color={color_hex}][b]{code}[/b][/color]   [b]{title}[/b]\n"
                               f"[size=12sp]{sub}[/size]"), **kw)
        self.bind(size=lambda i, s: setattr(i, "text_size", (s[0] - dp(28), s[1])))
        with self.canvas.before:
            Color(*WHITE)
            self._r = RoundedRectangle(radius=[dp(16)])
        with self.canvas.after:
            self._bc = Color(0, 0, 0, 0)
            self._ln = Line(rounded_rectangle=(0, 0, 1, 1, dp(16)), width=dp(2))
        self.bind(pos=self._upd, size=self._upd)

    def _upd(self, *_):
        self._r.pos = self.pos
        self._r.size = self.size
        self._ln.rounded_rectangle = (self.x, self.y, self.width, self.height, dp(16))

    def set_selected(self, on):
        self._bc.rgba = BLUE if on else (0, 0, 0, 0)


class DashedBox(BoxLayout):
    """Transparent box with a dashed black border."""

    def __init__(self, **kw):
        super().__init__(**kw)
        with self.canvas.after:
            Color(*BLACK)
            self._ln = Line(rounded_rectangle=(0, 0, 1, 1, dp(16)), width=dp(1.4),
                            dash_length=dp(5), dash_offset=dp(4))
        self.bind(pos=self._upd, size=self._upd)

    def _upd(self, *_):
        self._ln.rounded_rectangle = (self.x, self.y, self.width, self.height, dp(16))


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
        self.bind(pos=self._upd, size=self._upd)

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
        self.bind(pos=self.redraw, size=self.redraw)
        self.redraw()

    def redraw(self, *_):
        self.canvas.clear()
        x, y = self.pos
        w, h = self.size
        with self.canvas:
            Color(*(BLUE if self.active else WHITE))
            RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(6)])
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
        self.bind(pos=self.redraw, size=self.redraw)
        self.redraw()

    def redraw(self, *_):
        self.canvas.clear()
        x, y = self.pos
        w, h = self.size
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
        self.bind(pos=self._upd, size=self._upd)

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
        self.bind(pos=self.update_line, size=self.update_line)

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
            # non-zero initial size so the first draw never sees a zero outline
            self._ln = Line(rounded_rectangle=(0, 0, max(self.width, dp(1)), max(self.height, dp(1)), dp(18)),
                            width=dp(2))
        self.bind(pos=self._upd_border, size=self._upd_border)

    def _upd_border(self, *_):
        w = max(float(self.width or 0), 1.0)
        h = max(float(self.height or 0), 1.0)
        self._ln.rounded_rectangle = (self.x, self.y, w, h, dp(18))

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
                self._ln = Line(rounded_rectangle=(0, 0, 1, 1, dp(12)), width=dp(2))
            else:
                self._ln = None
        self.bind(pos=self._upd, size=self._upd)

    def _upd(self, *_):
        self._r.pos = self.pos
        self._r.size = self.size
        if self._ln is not None:
            w = max(float(self.width or 0), 1.0)
            h = max(float(self.height or 0), 1.0)
            self._ln.rounded_rectangle = (self.x, self.y, w, h, dp(12))


class ProgressBar(Widget):
    """Thin rounded bar: frac = share of the window still left (0..1)."""

    def __init__(self, frac=0.0, color=GREEN, **kw):
        kw.setdefault("size_hint_y", None)
        kw.setdefault("height", dp(8))
        super().__init__(**kw)
        self.frac = max(0.0, min(1.0, frac))
        self.color = color
        self.bind(pos=self.redraw, size=self.redraw)
        self.redraw()

    def redraw(self, *_):
        self.canvas.clear()
        with self.canvas:
            Color(0.9, 0.91, 0.91, 1)
            RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(4)])
            if self.frac > 0:
                Color(*self.color)
                RoundedRectangle(pos=self.pos, size=(max(self.width * self.frac, dp(8)), self.height),
                                 radius=[dp(4)])
