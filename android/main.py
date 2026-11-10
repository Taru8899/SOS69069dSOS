import json
import os
import threading

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, RoundedRectangle
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.utils import escape_markup

import core

GREEN = (0, 0.659, 0.176, 1)
BLUE = (0, 0.2, 1, 1)
BLACK = (0.04, 0.04, 0.04, 1)
WHITE = (1, 1, 1, 1)
Window.clearcolor = GREEN


class Card(BoxLayout):
    def __init__(self, text, bg=WHITE, fg=BLACK, **kw):
        super().__init__(size_hint_y=None, padding=dp(14), **kw)
        with self.canvas.before:
            Color(*bg)
            self._r = RoundedRectangle(radius=[dp(18)])
        self.bind(pos=self._upd, size=self._upd)
        self.lbl = Label(text=text, markup=True, color=fg, halign="left",
                         valign="top", size_hint_y=None)
        self.lbl.bind(width=lambda i, w: setattr(i, "text_size", (w, None)))
        self.lbl.bind(texture_size=self._fit)
        self.add_widget(self.lbl)

    def _upd(self, *_):
        self._r.pos = self.pos
        self._r.size = self.size

    def _fit(self, inst, ts):
        inst.height = ts[1]
        self.height = ts[1] + dp(28)


class DsosApp(App):
    def build(self):
        self.title = "dSOS"
        self.cfg_path = os.path.join(self.user_data_dir, "cfg.json")
        cfg = {}
        try:
            with open(self.cfg_path) as f:
                cfg = json.load(f)
        except Exception:  # noqa: BLE001
            pass

        root = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(8))
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
            root.add_widget(w)

        sv = ScrollView()
        self.box = BoxLayout(orientation="vertical", spacing=dp(10), size_hint_y=None)
        self.box.bind(minimum_height=self.box.setter("height"))
        sv.add_widget(self.box)
        root.add_widget(sv)
        return root

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
        b = self.box
        b.clear_widgets()
        b.add_widget(Card(
            f"dSOS balance\n[size=40sp][b]{d['balance']:,}[/b][/size] dSOS\n"
            f"= {core.eth(d['value_wei'])} ETH redeemable\n\n"
            f"Sendable: [b]{d['sendable']:,}[/b]    Expiring <1d: [b]{d['expiring']:,}[/b]\n"
            f"Expired, unswept: [b]{d['expired']:,}[/b]"))
        if d["next_expiry"]:
            left = d["next_expiry"] - d["block"]
            b.add_widget(Card(
                f"Next expiry in ~{core.dur(left)}\nRedeem before block {d['next_expiry']:,}",
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
        for o in d["offers"]:
            b.add_widget(Card(
                f"[b]{o['kind']}[/b]  {o['count']:,} dSOS  #{o['id']}  [b]{o['status']}[/b]\n"
                f"{core.eth(o['count'] * core.UNIT)} ETH - {core.dur(o['left'])} left\n"
                f"Sweepable at block {o['sweepable_at']:,}"))


if __name__ == "__main__":
    DsosApp().run()
