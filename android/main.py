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


class NavBtn(Button):
    """Flat bottom-bar tab."""

    def __init__(self, **kw):
        super().__init__(background_normal="", background_down="",
                         background_color=(0, 0, 0, 0), font_size="14sp", **kw)


class RoundBtn(Button):
    """Round blue button in the middle of the bottom bar."""

    def __init__(self, **kw):
        super().__init__(background_normal="", background_down="",
                         background_color=(0, 0, 0, 0), **kw)
        with self.canvas.before:
            Color(*BLUE)
            self._e = Ellipse()
        self.bind(pos=self._upd, size=self._upd)

    def _upd(self, *_):
        d = min(self.width, self.height) - dp(6)
        self._e.size = (d, d)
        self._e.pos = (self.center_x - d / 2, self.center_y - d / 2)


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
    lab = Label(text=f"[b]{text}[/b]", markup=True, color=BLACK, halign="left",
                valign="middle", font_size="18sp")
    lab.bind(size=lambda i, s: setattr(i, "text_size", s))
    row.add_widget(lab)
    if link_text:
        btn = NavBtn(text=f"[u]{link_text}[/u]", markup=True, color=BLACK,
                     size_hint_x=None, width=dp(90))
        btn.bind(on_release=lambda *_: on_link())
        row.add_widget(btn)
    return row


class DsosApp(App):
    PAGES = ["wallet", "offers", "stake", "credits", "create"]

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

        # ---- top: header + status line + scrolling page
        top = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(6))
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
        top.add_widget(head)

        self.msg = Label(text="", size_hint_y=None, height=dp(20), color=BLACK, font_size="13sp")
        top.add_widget(self.msg)

        # inputs live on the Wallet page (re-added on each render)
        self.addr = TextInput(text=cfg.get("addr", ""), hint_text="Wallet address 0x...",
                              multiline=False, size_hint_y=None, height=dp(44))
        self.key = TextInput(text=cfg.get("key", ""), hint_text="Etherscan API key (optional)",
                             multiline=False, password=True,
                             size_hint_y=None, height=dp(44))
        self.load_btn = Button(text="Load", size_hint_y=None, height=dp(48),
                               background_normal="", background_color=BLUE,
                               color=WHITE, bold=True)
        self.load_btn.bind(on_release=self.load)

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
        for name, label in (("wallet", "Wallet"), ("offers", "Offers")):
            nav.add_widget(self._tab(name, label))
        plus = RoundBtn(text="+", font_size="34sp", color=WHITE, bold=True, size_hint_x=0.9)
        plus.bind(on_release=lambda *_: self.set_page("create"))
        nav.add_widget(plus)
        for name, label in (("stake", "Stake"), ("credits", "Credits")):
            nav.add_widget(self._tab(name, label))

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

    def _tab(self, name, label):
        b = NavBtn(text=label)
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

    def on_start(self):
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

        if p == "wallet":
            for w in (self.addr, self.key, self.load_btn):
                b.add_widget(w)
        if self.err:
            b.add_widget(Card("[b]Error[/b]\n" + escape_markup(self.err)))
        if p == "create":
            self.page_create(b)
            return
        if d is None:
            if p != "wallet":
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

    def page_create(self, b):
        b.add_widget(Card(
            "[size=20sp][b]Create offer[/b][/size]\n"
            "Not available yet. This version only reads data and never sends transactions.\n\n"
            "Send, Create, Redeem and Stake need a signing wallet. They come in the next versions."))


if __name__ == "__main__":
    DsosApp().run()
