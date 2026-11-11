import json
import os
import threading

from kivy.animation import Animation
from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, Rectangle
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.utils import escape_markup

import core
import page_credits
import page_offers
import page_stake
import page_wallet
import util
from page_create import CreateScreen
from page_send import SendScreen
from theme import (BLACK, BLUE, GREEN, HAS_LOGO, LOGO, SPLASH_SECONDS, WHITE,
                   set_visible, short)
from widgets import Card, NavBtn, Pill, RoundBtn, Splash, label, make_input

Window.clearcolor = GREEN
Window.softinput_mode = "below_target"   # keep the focused field visible above the keyboard

# tab name -> function that fills that tab:  build(app, box, data)
PAGES = {
    "wallet": page_wallet.build,
    "offers": page_offers.build,
    "stake": page_stake.build,
    "credits": page_credits.build,
}


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
        plus.bind(on_release=lambda *_: self.open_create())
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

    # ---- overlays (Create offer, Send, Transaction ready)
    def open_overlay(self, w):
        self.overlays.append(w)
        self.root.add_widget(w)

    def open_create(self):
        self.open_overlay(CreateScreen(self))

    def open_send(self):
        if not self.data:
            self.msg.text = "Load your wallet first, then tap Send."
            return
        self.open_overlay(SendScreen(self))

    def coming(self, name):
        self.msg.text = f"{name} is coming in the next step."

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
        PAGES[p](self, b, d)


if __name__ == "__main__":
    DsosApp().run()
