"""Reusable widgets and small UI helpers."""
from kivy.graphics import Color, Ellipse, Line, Rectangle, RoundedRectangle
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget

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


class Splash(Overlay):
    """Logo on green, shown on top of the app for a moment."""

    def __init__(self, **kw):
        super().__init__(**kw)
        if HAS_LOGO:
            self.add_widget(Image(source=LOGO, size_hint=(0.6, 0.6),
                                  pos_hint={"center_x": 0.5, "center_y": 0.5}))
        else:
            self.add_widget(Label(text=S.SPLASH_FALLBACK, markup=True, font_size="48sp",
                                  color=WHITE, pos_hint={"center_x": 0.5, "center_y": 0.5}))


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

    def __init__(self, **kw):
        kw.setdefault("size_hint_y", None)
        kw.setdefault("height", dp(1))
        super().__init__(**kw)
        with self.canvas:
            Color(0.9, 0.91, 0.91, 1)
            self._r = Rectangle()
        self.bind(pos=self._upd, size=self._upd)

    def _upd(self, *_):
        self._r.pos = self.pos
        self._r.size = self.size
