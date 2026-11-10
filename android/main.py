import json
import os
import threading

from kivy.animation import Animation
from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, Ellipse, Line, Rectangle, RoundedRectangle
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget
from kivy.utils import escape_markup

import core
import tx
import util

HERE = os.path.dirname(os.path.abspath(__file__))
LOGO = os.path.join(HERE, "logo.png")
HAS_LOGO = os.path.exists(LOGO)

GREEN = (4 / 255, 168 / 255, 53 / 255, 1)   # same green as the logo background
BLUE = (0, 0.2, 1, 1)
BLACK = (0.04, 0.04, 0.04, 1)
WHITE = (1, 1, 1, 1)
RED = (0.69, 0, 0.13, 1)
GRAY = (0.78, 0.8, 0.8, 1)
LIGHT = (0.94, 0.95, 0.95, 1)
Window.clearcolor = GREEN
Window.softinput_mode = "below_target"   # keep the focused field visible above the keyboard

SPLASH_SECONDS = 1.8
DSOS_ADDR = "0x7Bd7c427b3c69e2a09603573ac875987c61ECAB8"
ETHERSCAN_WRITE = "https://etherscan.io/address/" + DSOS_ADDR + "#writeContract"
DAPP_URL = "https://taru8899.github.io/SOS69069dSOS/dsos-dapp-v29.html"
WINDOWS = {"1 day": 7200, "2 days": 14400, "7 days": 50400}


def short(addr):
    a = (addr or "").strip()
    return f"{a[:6]}...{a[-4:]}" if len(a) > 12 else a


def left_text(left):
    return "expired" if left <= 0 else f"{core.dur(left)} left"


def set_visible(w, show):
    """Show/hide a widget without removing it (keeps text fields stable)."""
    if not hasattr(w, "_h"):
        w._h = w.height
    w.height = w._h if show else 0
    w.opacity = 1 if show else 0
    w.disabled = not show


def make_input(hint, text="", password=False, filt=None):
    return TextInput(text=text, hint_text=hint, multiline=False, password=password,
                     size_hint_y=None, height=dp(44), write_tab=False,
                     input_type="text", keyboard_suggestions=False,
                     use_bubble=True, use_handles=True, input_filter=filt,
                     padding=[dp(10), dp(12), dp(10), dp(8)])


# ---------------------------------------------------------------- widgets
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
            self.add_widget(Label(text="[b]dSOS[/b]", markup=True, font_size="48sp",
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


class BalanceCard(Panel):
    def __init__(self, d, **kw):
        super().__init__(size_hint_y=None, height=dp(176), **kw)
        total = max(d["balance"], 1)
        self.ring = Ring(size_hint=(None, 1), width=dp(112))
        rest = max(0, d["balance"] - d["sendable"] - d["expiring"] - d["expired"])
        self.ring.set_parts([
            (d["sendable"] / total, BLUE),
            (d["expiring"] / total, BLACK),
            (d["expired"] / total, RED),
            (rest / total, GRAY),
        ])
        lbl = Label(
            text=(f"dSOS balance\n"
                  f"[size=44sp][b]{d['balance']:,}[/b][/size] dSOS\n"
                  f"= {core.eth(d['value_wei'])} ETH redeemable\n\n"
                  f"[color=0033ff][b]Sendable {d['sendable']:,}[/b][/color]   "
                  f"[b]Expiring <1d {d['expiring']:,}[/b]\n"
                  f"[color=b00021][b]Expired, unswept {d['expired']:,}[/b][/color]"),
            markup=True, color=BLACK, halign="left", valign="top")
        lbl.bind(size=lambda i, s: setattr(i, "text_size", s))
        self.add_widget(lbl)
        self.add_widget(self.ring)


# ---------------------------------------------------------------- create offer
class CreateScreen(Overlay):
    """Create offer page. Builds the transaction data; it does not send anything."""

    def __init__(self, app, **kw):
        super().__init__(**kw)
        self.app = app
        self.kind = "B"
        self.slices = 5
        self.window = "2 days"
        self.holder_mode = "me"

        col = BoxLayout(orientation="vertical")

        # header
        head = BoxLayout(size_hint_y=None, height=dp(72), padding=[dp(14), dp(10)], spacing=dp(14))
        back = RoundBtn(text="<", font_size="26sp", bold=True, bg=WHITE, color=BLACK,
                        size_hint=(None, 1), width=dp(56))
        back.bind(on_release=lambda *_: app.close_top())
        head.add_widget(back)
        head.add_widget(label("[b]Create offer[/b]", font_size="24sp"))
        col.add_widget(head)

        # scrolling form
        sv = ScrollView()
        form = BoxLayout(orientation="vertical", spacing=dp(10), size_hint_y=None,
                         padding=[dp(14), 0, dp(14), dp(14)])
        form.bind(minimum_height=form.setter("height"))

        form.add_widget(label("[b]Type[/b]", size_hint_y=None, height=dp(26)))
        grid = GridLayout(cols=2, spacing=dp(10), size_hint_y=None, height=dp(2 * 64 + 10))
        self.type_cards = {}
        for code, title, sub, hx in (("B", "Basic", "Sendable", "0033ff"),
                                     ("T", "Type T", "Sendable", "0b0b0b"),
                                     ("P", "Type P", "Sendable", "00a82d"),
                                     ("G", "Gated", "PIN - not sendable", "0b0b0b")):
            c = TypeCard(code, title, sub, hx)
            c.bind(on_release=lambda _w, k=code: self.pick_kind(k))
            self.type_cards[code] = c
            grid.add_widget(c)
        form.add_widget(grid)

        # slices
        sl = Panel(orientation="vertical", size_hint_y=None, height=dp(196), spacing=dp(6))
        top = BoxLayout(size_hint_y=None, height=dp(24))
        top.add_widget(label("Slices (dSOS)"))
        top.add_widget(label("0.001 ETH each", halign="right"))
        sl.add_widget(top)
        mid = BoxLayout(size_hint_y=None, height=dp(84))
        minus = RoundBtn(text="-", font_size="34sp", bg=BLACK, color=WHITE,
                         size_hint=(None, 1), width=dp(72))
        minus.bind(on_release=lambda *_: self.set_slices(self.slices - 1))
        plus = RoundBtn(text="+", font_size="30sp", bg=BLACK, color=WHITE,
                        size_hint=(None, 1), width=dp(72))
        plus.bind(on_release=lambda *_: self.set_slices(self.slices + 1))
        self.num = Label(text="", markup=True, color=BLACK, halign="center", valign="middle")
        self.num.bind(size=lambda i, s: setattr(i, "text_size", s))
        mid.add_widget(minus)
        mid.add_widget(self.num)
        mid.add_widget(plus)
        sl.add_widget(mid)
        chips = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        self.slice_chips = {}
        for n in (1, 5, 10, 50):
            ch = Choice(base=LIGHT, text=str(n))
            ch.bind(on_release=lambda _w, v=n: self.set_slices(v))
            self.slice_chips[n] = ch
            chips.add_widget(ch)
        sl.add_widget(chips)
        form.add_widget(sl)

        # redeem window
        form.add_widget(label("[b]Redeem window[/b]", size_hint_y=None, height=dp(26)))
        wrow = BoxLayout(size_hint_y=None, height=dp(52), spacing=dp(8))
        self.win_chips = {}
        for key in ("1 day", "2 days", "7 days", "Custom"):
            ch = Choice(text=key)
            ch.bind(on_release=lambda _w, k=key: self.pick_window(k))
            self.win_chips[key] = ch
            wrow.add_widget(ch)
        form.add_widget(wrow)
        self.custom_in = make_input("Window in blocks (7200 = about 1 day)", filt="int")
        form.add_widget(self.custom_in)
        self.custom_in.bind(text=lambda *_: self.refresh())
        self.win_note = label("", size_hint_y=None, height=dp(60), valign="top", font_size="13sp")
        form.add_widget(self.win_note)

        # holder
        form.add_widget(label("[b]Holder[/b]", size_hint_y=None, height=dp(26)))
        hold = Panel(orientation="vertical", size_hint_y=None, height=dp(150), spacing=dp(6))
        self.holder_btn = Button(text="", markup=True, halign="left", valign="middle",
                                 background_normal="", background_down="",
                                 background_color=(0, 0, 0, 0), color=BLACK,
                                 size_hint_y=None, height=dp(52))
        self.holder_btn.bind(size=lambda i, s: setattr(i, "text_size", (s[0], s[1])))
        self.holder_btn.bind(on_release=lambda *_: self.toggle_holder())
        hold.add_widget(self.holder_btn)
        self.other_row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(6))
        self.other_in = make_input("Holder address 0x...")
        self.other_in.bind(text=lambda *_: self.refresh())
        pb = Button(text="Paste", size_hint=(None, 1), width=dp(72), background_normal="",
                    background_color=BLUE, color=WHITE, bold=True)
        pb.bind(on_release=lambda *_: self.paste_other())
        self.other_row.add_widget(self.other_in)
        self.other_row.add_widget(pb)
        hold.add_widget(self.other_row)
        self.hold_panel = hold
        form.add_widget(hold)

        # ledger
        dash = DashedBox(size_hint_y=None, height=dp(56), padding=[dp(16), 0])
        dash.add_widget(label("Ledger record - optional signature"))
        dash.add_widget(label("Skipped", halign="right", size_hint_x=None, width=dp(70)))
        form.add_widget(dash)

        sv.add_widget(form)
        col.add_widget(sv)

        # footer
        foot = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(124),
                         padding=[dp(14), dp(12)], spacing=dp(8))
        with foot.canvas.before:
            Color(*BLACK)
            fbg = Rectangle()
        foot.bind(pos=lambda i, p: setattr(fbg, "pos", p),
                  size=lambda i, s: setattr(fbg, "size", s))
        self.btn = Choice(base=BLUE, sel=BLUE, fg=WHITE, sel_fg=WHITE, bold=True,
                          font_size="18sp", size_hint_y=None, height=dp(58))
        self.btn.bind(on_release=lambda *_: self.on_create())
        foot.add_widget(self.btn)
        self.note = Label(text="", color=(0.8, 0.82, 0.82, 1), font_size="13sp",
                          halign="center", valign="middle")
        self.note.bind(size=lambda i, s: setattr(i, "text_size", s))
        foot.add_widget(self.note)
        col.add_widget(foot)

        self.add_widget(col)
        self.refresh()

    # ---- state
    def pick_kind(self, k):
        self.kind = k
        self.refresh()

    def set_slices(self, n):
        self.slices = max(1, min(100000, n))
        self.refresh()

    def pick_window(self, k):
        self.window = k
        self.refresh()

    def toggle_holder(self):
        self.holder_mode = "other" if self.holder_mode == "me" else "me"
        self.refresh()

    def paste_other(self):
        t = util.paste_text()
        if t:
            self.other_in.text = t
        else:
            self.note.text = "Clipboard is empty or not readable."

    def blocks(self):
        if self.window == "Custom":
            t = self.custom_in.text.strip()
            return int(t) if t.isdigit() else 0
        return WINDOWS[self.window]

    def holder_addr(self):
        if self.holder_mode == "me":
            return self.app.addr.text.strip()
        return self.other_in.text.strip()

    def problem(self):
        if self.kind == "G":
            return "Gated offers need a PIN. Coming in the next step."
        if self.blocks() < 1:
            return "Enter the window in blocks."
        if not tx.valid_address(self.holder_addr()):
            if self.holder_mode == "me":
                return "Enter your address on the Wallet tab first."
            return "Holder needs a valid 0x address."
        return ""

    def refresh(self):
        eth = core.eth(self.slices * core.UNIT)
        self.num.text = f"[size=54sp][b]{self.slices}[/b][/size]\n= {eth} ETH"
        for code, c in self.type_cards.items():
            c.set_selected(code == self.kind)
        for n, c in self.slice_chips.items():
            c.set_selected(n == self.slices)
        for k, c in self.win_chips.items():
            c.set_selected(k == self.window)
        set_visible(self.custom_in, self.window == "Custom")

        b = self.blocks()
        data = self.app.data
        txt = f"{b:,} blocks"
        if data:
            txt += f" - expires near block {data['block'] + b:,}"
        txt += (". Windows over 7,200 blocks stay sendable from your wallet." if b > core.WINDOW
                else ". Windows of 7,200 blocks or less are NOT sendable from a wallet.")
        self.win_note.text = txt

        me = self.holder_mode == "me"
        mine = self.app.addr.text.strip()
        self.holder_btn.text = (f"[b]Myself[/b]\n{short(mine) or 'enter address on Wallet tab'}"
                                if me else "[b]Another address[/b]\ntap to use my own address")
        set_visible(self.other_row, not me)
        self.hold_panel.height = dp(84) if me else dp(150)

        p = self.problem()
        self.btn.text = f"Create offer \u00b7 {eth} ETH"
        self.btn.set_enabled(not p)
        self.note.text = p or "Offers not redeemed before expiry can be swept into the shared pool."

    def on_create(self):
        if self.problem():
            return
        try:
            t = tx.create_offer_tx(self.kind, self.holder_addr(), self.slices, self.blocks())
        except Exception as e:  # noqa: BLE001
            self.note.text = str(e)
            return
        summary = (f"[b]Create {self.kind} offer[/b]\n"
                   f"{self.slices} dSOS = {t['value_eth']} ETH\n"
                   f"Window {self.blocks():,} blocks\n"
                   f"Holder {short(self.holder_addr())}")
        self.app.open_overlay(TxScreen(self.app, t, summary))


class TxScreen(Overlay):
    """Shows the ready-to-send transaction with copy buttons."""

    def __init__(self, app, t, summary, **kw):
        super().__init__(**kw)
        self.app = app
        col = BoxLayout(orientation="vertical")
        head = BoxLayout(size_hint_y=None, height=dp(72), padding=[dp(14), dp(10)], spacing=dp(14))
        back = RoundBtn(text="<", font_size="26sp", bold=True, bg=WHITE, color=BLACK,
                        size_hint=(None, 1), width=dp(56))
        back.bind(on_release=lambda *_: app.close_top())
        head.add_widget(back)
        head.add_widget(label("[b]Transaction ready[/b]", font_size="24sp"))
        col.add_widget(head)

        self.status = label("", size_hint_y=None, height=dp(22), font_size="13sp",
                            padding=(dp(14), 0))
        col.add_widget(self.status)

        sv = ScrollView()
        box = BoxLayout(orientation="vertical", spacing=dp(10), size_hint_y=None,
                        padding=[dp(14), 0, dp(14), dp(20)])
        box.bind(minimum_height=box.setter("height"))

        box.add_widget(Card(summary))
        box.add_widget(Card(
            "This app cannot sign or send yet. Send the transaction from a wallet or "
            "website that can call contracts (see the buttons below). Check every value first, "
            "and test with 1 slice.", bg=BLACK, fg=WHITE))

        p = t["params"]
        data = t["data"]
        box.add_widget(self.copy_row("To (dSOS contract)", DSOS_ADDR, short(DSOS_ADDR)))
        box.add_widget(self.copy_row("Value (ETH)", t["value_eth"], f"{t['value_eth']} ETH"))
        box.add_widget(self.copy_row("Data (hex)", data, f"{data[:22]}...{data[-8:]}"))
        box.add_widget(label("[b]Etherscan Write Contract: createOffer[/b]",
                             size_hint_y=None, height=dp(30)))
        box.add_widget(self.copy_row("payable amount (ETH)", t["value_eth"], t["value_eth"]))
        box.add_widget(self.copy_row("kind (uint8)", p["kind"], p["kind"]))
        box.add_widget(self.copy_row("to (address)", p["to"], short(p["to"])))
        box.add_widget(self.copy_row("delayBlocks", p["delayBlocks"], p["delayBlocks"]))
        box.add_widget(self.copy_row("payloadHash", p["payloadHash"], short(p["payloadHash"])))
        box.add_widget(self.copy_row("signature (bytes)", "0x", "0x"))
        box.add_widget(Card("metadata (string): leave it empty."))

        b1 = Choice(base=BLUE, fg=WHITE, text="Open Etherscan Write Contract",
                    size_hint_y=None, height=dp(52), bold=True)
        b1.bind(on_release=lambda *_: self.open(ETHERSCAN_WRITE))
        b2 = Choice(base=BLACK, fg=WHITE, text="Open dApp in browser",
                    size_hint_y=None, height=dp(52), bold=True)
        b2.bind(on_release=lambda *_: self.open(DAPP_URL))
        box.add_widget(b1)
        box.add_widget(b2)
        box.add_widget(Card(
            "Offers not redeemed before expiry can be swept into the shared pool, "
            "and that ETH is gone for good."))

        sv.add_widget(box)
        col.add_widget(sv)
        self.add_widget(col)

    def copy_row(self, title, value, shown):
        row = Panel(size_hint_y=None, height=dp(68), spacing=dp(8))
        row.add_widget(label(f"[size=12sp]{escape_markup(title)}[/size]\n[b]{escape_markup(shown)}[/b]"))
        btn = Button(text="Copy", size_hint=(None, None), size=(dp(72), dp(40)),
                     pos_hint={"center_y": 0.5}, background_normal="",
                     background_color=BLUE, color=WHITE, bold=True)
        btn.bind(on_release=lambda *_: self.copy(title, value))
        row.add_widget(btn)
        return row

    def copy(self, title, value):
        ok = util.copy_text(value)
        self.status.text = f"Copied: {title}" if ok else "Copy failed on this phone."

    def open(self, url):
        if not util.open_url(url):
            self.status.text = "Could not open the browser."


# ---------------------------------------------------------------- app
def offer_card(o):
    colors = {"redeemable": "00a82d", "expiring": "0b0b0b", "expired": "b00021"}
    col = colors.get(o["status"], "0b0b0b")
    return Card(
        f"[b]{o['kind']}[/b]  {o['count']:,} dSOS  #{o['id']}"
        f"{'  PIN' if o['kind'] == 'G' else ''}   "
        f"[color={col}][b]{o['status'].capitalize()}[/b][/color]\n"
        f"{core.eth(o['count'] * core.UNIT)} ETH - {left_text(o['left'])}\n"
        f"Sendable: {'yes' if o['sendable'] else 'no'}   Sweepable at block {o['sweepable_at']:,}")


def title_row(text, link_text=None, on_link=None):
    row = BoxLayout(size_hint_y=None, height=dp(34))
    row.add_widget(label(f"[b]{text}[/b]", font_size="18sp"))
    if link_text:
        btn = NavBtn(text=f"[u]{link_text}[/u]", markup=True, color=BLACK,
                     size_hint_x=None, width=dp(90))
        btn.bind(on_release=lambda *_: on_link())
        row.add_widget(btn)
    return row


class DsosApp(App):
    def build(self):
        self.title = "dSOS"
        if HAS_LOGO:
            self.icon = LOGO
        self.cfg_path = os.path.join(self.user_data_dir, "cfg.json")
        cfg = {}
        try:
            with open(self.cfg_path) as f:
                cfg = json.load(f)
        except Exception:  # noqa: BLE001
            pass

        self.data = None
        self.err = None
        self.page = "wallet"
        self.overlays = []

        # ---- top: header + status line + wallet inputs + scrolling page
        top = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(6))
        head = BoxLayout(size_hint_y=None, height=dp(56), spacing=dp(10))
        if HAS_LOGO:
            head.add_widget(Image(source=LOGO, size_hint=(None, 1), width=dp(52)))
        self.sub = label("[b]Main wallet[/b]\n" + (short(cfg.get("addr", "")) or "enter address"))
        head.add_widget(self.sub)
        head.add_widget(Pill(text="Ethereum", color=WHITE, bold=True,
                             size_hint=(None, None), size=(dp(104), dp(34)),
                             pos_hint={"center_y": 0.5}))
        top.add_widget(head)

        self.msg = Label(text="", size_hint_y=None, height=dp(20), color=BLACK, font_size="13sp")
        top.add_widget(self.msg)

        # wallet inputs: created once and only hidden/shown, never re-parented
        self.addr = make_input("Wallet address 0x...", cfg.get("addr", ""))
        self.key = make_input("Etherscan API key (optional)", cfg.get("key", ""), password=True)
        self.inputs = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(148),
                                spacing=dp(6))
        self.inputs.add_widget(self._with_paste(self.addr))
        self.inputs.add_widget(self._with_paste(self.key))
        load_btn = Button(text="Load", size_hint_y=None, height=dp(48),
                          background_normal="", background_color=BLUE, color=WHITE, bold=True)
        load_btn.bind(on_release=self.load)
        self.inputs.add_widget(load_btn)
        top.add_widget(self.inputs)

        self.sv = ScrollView()
        self.box = BoxLayout(orientation="vertical", spacing=dp(10), size_hint_y=None)
        self.box.bind(minimum_height=self.box.setter("height"))
        self.sv.add_widget(self.box)
        top.add_widget(self.sv)

        # ---- bottom bar
        nav = BoxLayout(size_hint_y=None, height=dp(66))
        with nav.canvas.before:
            Color(*BLACK)
            nav_bg = Rectangle()
        nav.bind(pos=lambda i, p: setattr(nav_bg, "pos", p),
                 size=lambda i, s: setattr(nav_bg, "size", s))
        self.nav_btns = {}
        for name, lab in (("wallet", "Wallet"), ("offers", "Offers")):
            nav.add_widget(self._tab(name, lab))
        plus = RoundBtn(text="+", font_size="34sp", color=WHITE, bold=True, size_hint_x=0.9)
        plus.bind(on_release=lambda *_: self.open_overlay(CreateScreen(self)))
        nav.add_widget(plus)
        for name, lab in (("stake", "Stake"), ("credits", "Credits")):
            nav.add_widget(self._tab(name, lab))

        main = BoxLayout(orientation="vertical")
        main.add_widget(top)
        main.add_widget(nav)

        # ---- splash on top of everything at start
        root = FloatLayout()
        root.add_widget(main)
        self.splash = Splash()
        root.add_widget(self.splash)
        self.render()
        self._mark_tabs()
        return root

    def _with_paste(self, field):
        row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(6))
        row.add_widget(field)
        pb = Button(text="Paste", size_hint=(None, 1), width=dp(72), background_normal="",
                    background_color=BLUE, color=WHITE, bold=True)
        pb.bind(on_release=lambda *_: self.paste_into(field))
        row.add_widget(pb)
        return row

    def paste_into(self, field):
        t = util.paste_text()
        if t:
            field.text = t
            self.msg.text = "Pasted from clipboard"
        else:
            self.msg.text = "Clipboard is empty or not readable"

    def _tab(self, name, text):
        b = NavBtn(text=text)
        b.bind(on_release=lambda *_: self.set_page(name))
        self.nav_btns[name] = b
        return b

    def _mark_tabs(self):
        for name, b in self.nav_btns.items():
            on = name == self.page
            b.color = WHITE if on else (0.6, 0.62, 0.62, 1)
            b.bold = on

    def set_page(self, name):
        self.page = name
        self._mark_tabs()
        self.render()
        self.sv.scroll_y = 1

    # ---- overlays (Create offer, Transaction ready)
    def open_overlay(self, w):
        self.overlays.append(w)
        self.root.add_widget(w)

    def close_top(self):
        if self.overlays:
            self.root.remove_widget(self.overlays.pop())

    def on_back(self, window, key, *args):
        if key == 27 and self.overlays:   # Android back button
            self.close_top()
            return True
        return False

    def on_start(self):
        Window.bind(on_keyboard=self.on_back)
        Clock.schedule_once(self.hide_splash, SPLASH_SECONDS)

    def hide_splash(self, *_):
        anim = Animation(opacity=0, duration=0.4)
        anim.bind(on_complete=lambda *a: self.root.remove_widget(self.splash))
        anim.start(self.splash)
        if self.addr.text.strip():
            self.load()  # auto-load the saved wallet

    # ---------------------------------------------------------- data
    def save_cfg(self):
        try:
            os.makedirs(self.user_data_dir, exist_ok=True)
            with open(self.cfg_path, "w") as f:
                json.dump({"addr": self.addr.text.strip(), "key": self.key.text.strip()}, f)
        except Exception:  # noqa: BLE001
            pass

    def load(self, *_):
        self.save_cfg()
        self.msg.text = "Loading..."
        threading.Thread(target=self._work, args=(self.addr.text, self.key.text),
                         daemon=True).start()

    def _work(self, addr, key):
        try:
            d = core.Chain(key).load(addr)
            Clock.schedule_once(lambda dt: self.show(d))
        except Exception as e:  # noqa: BLE001
            m = str(e)
            Clock.schedule_once(lambda dt: self.fail(m))

    def fail(self, m):
        self.msg.text = ""
        self.err = m
        self.render()

    def show(self, d):
        self.data = d
        self.err = None
        self.msg.text = f"Block {d['block']:,} via {d['source']}"
        self.sub.text = f"[b]Main wallet[/b]\n{short(d['address'])}"
        self.render()

    # ---------------------------------------------------------- pages
    def render(self):
        b = self.box
        b.clear_widgets()
        p = self.page
        d = self.data
        set_visible(self.inputs, p == "wallet")
        if self.err:
            b.add_widget(Card("[b]Error[/b]\n" + escape_markup(self.err)))
        if d is None:
            if p == "wallet":
                if not self.err:
                    b.add_widget(Card("Enter your wallet address above and tap Load."))
            else:
                b.add_widget(Card("No data yet. Open the Wallet tab, enter your address and tap Load."))
            return
        getattr(self, "page_" + p)(b, d)

    def page_wallet(self, b, d):
        b.add_widget(BalanceCard(d))
        if d["next_expiry"]:
            left = d["next_expiry"] - d["block"]
            b.add_widget(Card(
                f"[b]Next expiry in ~{core.dur(left)}[/b]\n"
                f"Redeem before block {d['next_expiry']:,}",
                bg=BLACK, fg=WHITE))
        b.add_widget(title_row("Active offers", "See all", lambda: self.set_page("offers")))
        if not d["offers"]:
            b.add_widget(Card("No active offers."))
        for o in d["offers"][:2]:
            b.add_widget(offer_card(o))
        b.add_widget(Card(
            f"Shared pool\n[b]{core.eth(d['pool_wei'])} ETH[/b] - {d['supply']:,} dSOS active"))

    def page_offers(self, b, d):
        b.add_widget(title_row(f"Offers ({len(d['offers'])})"))
        if not d["offers"]:
            b.add_widget(Card("No active offers."))
        for o in d["offers"]:
            b.add_widget(offer_card(o))
        b.add_widget(Card(
            "[b]How to read this[/b]\n"
            "Sendable = not a G offer and more than 7,200 blocks (about 1 day) left.\n"
            "Expired offers still count in your balance until someone sweeps them."))

    def page_stake(self, b, d):
        b.add_widget(Card(
            f"[size=22sp][b]{'Staked' if d['staked'] else 'Not staked'}[/b][/size]\n"
            f"{'You can redeem credits now.' if d['can_redeem'] else 'Credits cannot be redeemed yet.'}\n\n"
            f"Cheapest gate offer right now:\n[b]{core.eth(d['stake_need_wei'])} ETH[/b] "
            f"(type G, delay 1 block)"))
        b.add_widget(Card(
            "[b]How staking works[/b]\n"
            "1. Create a G offer with delay 1 and a value above the gate requirement.\n"
            "2. Let it expire and sweep it. The ETH stays in the pool for good.\n"
            "3. You are staked forever, then wait 14,400 blocks (about 2 days) "
            "before your first credit redemption.\n\n"
            "Redeeming any part of a gate offer removes its gate flag, so you do not get staked."))

    def page_credits(self, b, d):
        b.add_widget(Card(
            f"Credits held\n[size=44sp][b]{d['credits']:,}[/b][/size]\n"
            f"+ {d['formable']:,} formable from SOS trust records\n"
            f"Worth up to [b]{core.eth((d['credits'] + d['formable']) * core.UNIT)} ETH[/b]"))
        b.add_widget(Card(
            f"[b]SOS ledger[/b]\n"
            f"Push {d['push']:,}   Trust {d['trust']:,}\n"
            f"Effective {d['effective']:,}"))
        b.add_widget(Card(
            "1 credit = 0.001 ETH. Credits come 1:1 from trust records, "
            "need a staked wallet, and cannot be transferred.",
            bg=BLACK, fg=WHITE))
        if not d["staked"]:
            b.add_widget(Card("This wallet is not staked, so it cannot form or redeem credits."))


if __name__ == "__main__":
    DsosApp().run()
