"""Reusable widgets and small UI helpers."""
from kivy.graphics import Color, Ellipse, Line, Rectangle, RoundedRectangle
from kivy.metrics import dp
from kivy.clock import Clock
from kivy.uix.behaviors import ButtonBehavior
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
    """Animated dSOS welcome screen; remains a root-level overlay."""
    def __init__(self, **kw):
        super().__init__(**kw)
        # Override the inherited green field with the v8 near-black canvas.
        with self.canvas.before:
            Color(0.012, 0.018, 0.025, 1)
            self._dark_bg = Rectangle(pos=self.pos, size=self.size)
            Color(0.02, 0.55, 0.22, 0.24)
            self._glow = Ellipse(pos=(0, 0), size=(dp(260), dp(260)))
            Color(0.0, 0.35, 0.95, 0.48)
            self._streak_blue = Line(points=[0, 0, 1, 1], width=dp(2.2))
            Color(0.02, 0.75, 0.28, 0.65)
            self._streak_green = Line(points=[0, 0, 1, 1], width=dp(2.8))
        self.bind(pos=self._splash_canvas, size=self._splash_canvas)

        mark = Widget(size_hint=(None, None), size=(dp(104), dp(104)),
                      pos_hint={"center_x": 0.5, "center_y": 0.70})
        with mark.canvas.before:
            Color(1, 1, 1, 1)
            mark._circle = Ellipse(pos=mark.pos, size=mark.size)
        mark.bind(pos=lambda w, p: setattr(w._circle, "pos", p),
                  size=lambda w, z: setattr(w._circle, "size", z))
        self.add_widget(mark)
        self.add_widget(Label(text="69069", color=(0.02, 0.05, 0.03, 1), bold=True,
                              font_size="23sp", size_hint=(None, None), size=(dp(104), dp(104)),
                              pos_hint={"center_x": 0.5, "center_y": 0.70}))
        self.add_widget(Label(text="dSOS", color=WHITE, bold=True, font_size="42sp",
                              size_hint=(1, None), height=dp(58),
                              pos_hint={"center_x": 0.5, "center_y": 0.48}))
        self.add_widget(Label(text="1 dSOS  =  1 slice  =  0.001 ETH", color=(0.82, 0.9, 0.86, 1),
                              font_size="15sp", size_hint=(1, None), height=dp(30),
                              pos_hint={"center_x": 0.5, "center_y": 0.39}))
        self.add_widget(Label(text="Authority of One 69069 AIX", color=(0.35, 0.72, 1, 1),
                              font_size="14sp", size_hint=(1, None), height=dp(26),
                              pos_hint={"center_x": 0.5, "center_y": 0.34}))
        self.add_widget(Label(text="A Ledger of Presence · No Assets to hold · No Wallet to drain",
                              color=(0.62, 0.69, 0.72, 1), font_size="10sp",
                              size_hint=(0.94, None), height=dp(24),
                              pos_hint={"center_x": 0.5, "center_y": 0.29}))
        self.status_lbl = Label(text="Connecting to Ethereum…", color=(0.75, 0.82, 0.82, 1),
                                font_size="12sp", size_hint=(1, None), height=dp(24),
                                pos_hint={"center_x": 0.5, "center_y": 0.20})
        self.add_widget(self.status_lbl)
        self._spin_angle = 0
        self._spinner = Widget(size_hint=(None, None), size=(dp(36), dp(36)),
                               pos_hint={"center_x": 0.5, "center_y": 0.25})
        with self._spinner.canvas:
            Color(0.05, 0.48, 1, 1)
            self._spin_line = Line(circle=(0, 0, dp(14), 0, 270), width=dp(3))
        self._spinner.bind(pos=self._spin_draw, size=self._spin_draw)
        self.add_widget(self._spinner)
        try:
            from build_info import VERSION, BUILD, COMMIT
        except Exception:
            VERSION, BUILD, COMMIT = "0.2.0", "local", "unknown"
        self.add_widget(Label(text=f"v{VERSION}  ·  Build {BUILD}  ·  {COMMIT[:8]}",
                              color=(0.48, 0.55, 0.58, 1), font_size="10sp",
                              size_hint=(1, None), height=dp(20),
                              pos_hint={"center_x": 0.5, "y": 0.025}))
        self._spin_event = Clock.schedule_interval(self._spin, 1 / 30)

    def _splash_canvas(self, *_):
        self._dark_bg.pos, self._dark_bg.size = self.pos, self.size
        self._glow.size = (dp(300), dp(300))
        self._glow.pos = (self.center_x - dp(150), self.center_y - dp(30))
        self._streak_blue.points = [self.x - dp(30), self.y + self.height * .30,
                                    self.x + self.width + dp(30), self.y + self.height * .82]
        self._streak_green.points = [self.x - dp(20), self.y + self.height * .18,
                                     self.x + self.width + dp(20), self.y + self.height * .63]

    def _spin_draw(self, *_):
        self._spin_line.circle = (self._spinner.center_x, self._spinner.center_y,
                                  dp(14), self._spin_angle, self._spin_angle + 270)

    def _spin(self, dt):
        self._spin_angle = (self._spin_angle + 6) % 360
        self._spin_draw()
        return True

    def set_status(self, text):
        self.status_lbl.text = str(text)


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
        if not hasattr(self, "_r"):
            return
        self._r.pos = self.pos
        self._r.size = (max(self.width, 1), max(self.height, 1))


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
        kw.setdefault("size_hint", (None, None))
        kw.setdefault("size", (dp(100), dp(30)))
        super().__init__(**kw)
        with self.canvas.before:
            Color(*bg)
            self._r = RoundedRectangle(radius=[dp(16)])
        self.bind(pos=self._upd, size=self._upd)

    def _upd(self, *_):
        if not hasattr(self, "_r"):
            return
        self._r.pos = self.pos
        self._r.size = (max(self.width, 1), max(self.height, 1))


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
        d = max(min(self.width, self.height) - dp(6), 0)
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
            self._r = RoundedRectangle(pos=self.pos,
                                       size=(max(self.width, 1), max(self.height, 1)),
                                       radius=[dp(16)])
        self.bind(pos=self._upd, size=self._upd)
        self._paint()

    def _upd(self, *_):
        if not hasattr(self, "_r"):
            return
        self._r.pos = self.pos
        self._r.size = (max(self.width, 1), max(self.height, 1))

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
        kw.setdefault("size_hint_y", None)
        kw.setdefault("height", dp(88))
        super().__init__(**kw)
        with self.canvas.after:
            self._bc = Color(0, 0, 0, 0)
            self._ln = Line(rounded_rectangle=(self.x, self.y, max(self.width, 1), max(self.height, 1), dp(18)), width=dp(2))
        self.bind(pos=self._upd_border, size=self._upd_border)

    def _upd_border(self, *_):
        if not hasattr(self, "_ln"):
            return
        self._ln.rounded_rectangle = (self.x, self.y, max(self.width, 1), max(self.height, 1), dp(18))

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
        if not hasattr(self, "_r"):
            return
        self._r.pos = self.pos
        self._r.size = (max(self.width, 1), max(self.height, 1))
        if self._ln is not None:
            self._ln.rounded_rectangle = (self.x, self.y, max(self.width, 1), max(self.height, 1), dp(12))


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
        if self.width <= 0 or self.height <= 0:
            return
        with self.canvas:
            Color(0.9, 0.91, 0.91, 1)
            RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(4)])
            if self.frac > 0:
                Color(*self.color)
                RoundedRectangle(pos=self.pos, size=(max(self.width * self.frac, dp(8)), self.height),
                                 radius=[dp(4)])
