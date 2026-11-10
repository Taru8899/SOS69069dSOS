import json
import os
import threading

from kivy.animation import Animation
from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, Line, Rectangle, RoundedRectangle
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget
from kivy.utils import escape_markup

import core

HERE = os.path.dirname(os.path.abspath(__file__))
LOGO = os.path.join(HERE, "logo.png")
HAS_LOGO = os.path.exists(LOGO)

GREEN = (4 / 255, 168 / 255, 53 / 255, 1)   # same green as the logo background
BLUE = (0, 0.2, 1, 1)
BLACK = (0.04, 0.04, 0.04, 1)
WHITE = (1, 1, 1, 1)
RED = (0.69, 0, 0.13, 1)
GRAY = (0.78, 0.8, 0.8, 1)
Window.clearcolor = GREEN

SPLASH_SECONDS = 1.8


def short(addr):
    a = (addr or "").strip()
    return f"{a[:6]}...{a[-4:]}" if len(a) > 12 else a


def left_text(left):
    return "expired" if left <= 0 else f"{core.dur(left)} left"


# ---------------------------------------------------------------- widgets
class Splash(FloatLayout):
    """Logo on green, shown on top of the app for a moment."""

    def __init__(self, **kw):
        super().__init__(**kw)
        with self.canvas.before:
            Color(*GREEN)
            self._bg = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._upd, size=self._upd)
        if HAS_LOGO:
            self.add_widget(Image(source=LOGO, size_hint=(0.6, 0.6),
                                  pos_hint={"center_x": 0.5, "center_y": 0.5}))
        else:
            self.add_widget(Label(text="[b]dSOS[/b]", markup=True, font_size="48sp",
                                  color=WHITE, pos_hint={"center_x": 0.5, "center_y": 0.5}))

    def _upd(self, *_):
        self._bg.pos = self.pos
        self._bg.size = self.size

    def on_touch_down(self, touch):
        return True  # block taps while the splash is visible


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


# ---------------------------------------------------------------- app
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

        ui = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(8))

        # header: logo, wallet name + short address, network chip
        head = BoxLayout(size_hint_y=None, height=dp(56), spacing=dp(10))
        if HAS_LOGO:
            head.add_widget(Image(source=LOGO, size_hint=(None, 1), width=dp(52)))
        self.sub = Label(text="[b]Main wallet[/b]\n" + (short(cfg.get("addr", "")) or "enter address"),
                         markup=True, color=BLACK, halign="left", valign="middle")
        self.sub.bind(size=lambda i, s: setattr(i, "text_size", s))
        head.add_widget(self.sub)
        head.add_widget(Pill(text="Ethereum", color=WHITE, bold=True,
                             size_hint=(None, None), size=(dp(104), dp(34)),
                             pos_hint={"center_y": 0.5}))
        ui.add_widget(head)

        self.addr = TextInput(text=cfg.get("addr", ""), hint_text="Wallet address 0x...",
                              multiline=False, size_hint_y=None, height=dp(44))
        self.key = TextInput(text=cfg.get("key", ""), hint_text="Etherscan API key (optional)",
                             multiline=False, password=True,
                             size_hint_y=None, height=dp(44))
        btn = Button(text="Load", size_hint_y=None, height=dp(48),
                     background_normal="", background_color=BLUE, color=WHITE, bold=True)
        btn.bind(on_release=self.load)
        self.msg = Label(text="", size_hint_y=None, height=dp(24), color=BLACK)
        for w in (self.addr, self.key, btn, self.msg):
            ui.add_widget(w)

        sv = ScrollView()
        self.box = BoxLayout(orientation="vertical", spacing=dp(10), size_hint_y=None)
        self.box.bind(minimum_height=self.box.setter("height"))
        sv.add_widget(self.box)
        ui.add_widget(sv)

        # splash sits on top of everything at start
        root = FloatLayout()
        root.add_widget(ui)
        self.splash = Splash()
        root.add_widget(self.splash)
        return root

    def on_start(self):
        Clock.schedule_once(self.hide_splash, SPLASH_SECONDS)

    def hide_splash(self, *_):
        anim = Animation(opacity=0, duration=0.4)
        anim.bind(on_complete=lambda *a: self.root.remove_widget(self.splash))
        anim.start(self.splash)
        if self.addr.text.strip():
            self.load()  # auto-load the saved wallet

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
        self.box.clear_widgets()
        self.box.add_widget(Card("[b]Error[/b]\n" + escape_markup(m)))

    def show(self, d):
        self.msg.text = f"Block {d['block']:,} via {d['source']}"
        self.sub.text = f"[b]Main wallet[/b]\n{short(d['address'])}"
        b = self.box
        b.clear_widgets()
        b.add_widget(BalanceCard(d))
        if d["next_expiry"]:
            left = d["next_expiry"] - d["block"]
            b.add_widget(Card(
                f"[b]Next expiry in ~{core.dur(left)}[/b]\n"
                f"Redeem before block {d['next_expiry']:,}",
                bg=BLACK, fg=WHITE))
        b.add_widget(Card(
            f"Shared pool\n[b]{core.eth(d['pool_wei'])} ETH[/b] - {d['supply']:,} dSOS active"))
        b.add_widget(Card(
            f"Stake: [b]{'Staked' if d['staked'] else 'Not staked'}[/b]"
            f"{'  (can redeem)' if d['can_redeem'] else ''}\n"
            f"Cheapest gate offer: {core.eth(d['stake_need_wei'])} ETH\n"
            f"Credits: [b]{d['credits']}[/b] + {d['formable']} formable\n"
            f"Ledger push {d['push']}, trust {d['trust']}, effective {d['effective']}"))
        if not d["offers"]:
            b.add_widget(Card("No active offers."))
        colors = {"redeemable": "00a82d", "expiring": "0b0b0b", "expired": "b00021"}
        for o in d["offers"]:
            col = colors.get(o["status"], "0b0b0b")
            b.add_widget(Card(
                f"[b]{o['kind']}[/b]  {o['count']:,} dSOS  #{o['id']}"
                f"{'  PIN' if o['kind'] == 'G' else ''}   "
                f"[color={col}][b]{o['status'].capitalize()}[/b][/color]\n"
                f"{core.eth(o['count'] * core.UNIT)} ETH - {left_text(o['left'])}\n"
                f"Sweepable at block {o['sweepable_at']:,}"))


if __name__ == "__main__":
    DsosApp().run()
