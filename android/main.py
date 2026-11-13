import json
import os
import threading
import traceback
import time

from kivy.animation import Animation
from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, Rectangle, Ellipse, Line
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
import strings as S
import util
from page_create import CreateScreen
from page_donate import DonateScreen
from page_redeem import RedeemScreen
from page_send import SendScreen
from wallet import Wallet
from theme import (BLACK, BLUE, GREEN, HAS_LOGO, LOGO, SPLASH_SECONDS, WHITE,
                   set_visible, short, APP_VERSION, APP_BUILD, APP_COMMIT,
                   MIN_SPLASH, MAX_SPLASH)
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


def _crash_path(app):
    return os.path.join(app.user_data_dir, "last_crash.txt")


def save_crash(app, exc):
    try:
        os.makedirs(app.user_data_dir, exist_ok=True)
        with open(_crash_path(app), "w") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S UTC\n"))
            f.write("".join(traceback.format_exception(type(exc), exc, exc.__traceback__)))
    except Exception:
        pass


def load_and_clear_crash(app):
    try:
        path = _crash_path(app)
        with open(path) as f:
            t = f.read()
        os.remove(path)
        return t
    except Exception:
        return None


class DsosApp(App):
    def build(self):
        self.title = S.APP_TITLE
        if HAS_LOGO:
            self.icon = LOGO
        self.cfg_path = os.path.join(self.user_data_dir, "cfg.json")
        cfg = {}
        try:
            with open(self.cfg_path) as f:
                cfg = json.load(f)
        except Exception:  # noqa: BLE001
            pass

        self.wallet = Wallet(self)
        self.data = None
        self.err = None
        self.page = "wallet"
        self.overlays = []

        # ---- top: header + status line + wallet inputs + scrolling page
        top = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(6))
        head = BoxLayout(size_hint_y=None, height=dp(56), spacing=dp(10))
        if HAS_LOGO:
            head.add_widget(Image(source=LOGO, size_hint=(None, 1), width=dp(52)))
        self.sub = label(S.HEADER_WALLET.format(addr=short(cfg.get("addr", "")) or S.HEADER_NO_ADDR))
        head.add_widget(self.sub)
        head.add_widget(Pill(text=S.CHAIN_PILL, color=WHITE, bold=True,
                             size_hint=(None, None), size=(dp(104), dp(34)),
                             pos_hint={"center_y": 0.5}))
        top.add_widget(head)

        self.msg = Label(text="", size_hint_y=None, height=dp(20), color=BLACK, font_size="13sp")
        top.add_widget(self.msg)

        # wallet inputs: created once and only hidden/shown, never re-parented
        self.addr = make_input(S.HINT_ADDRESS, cfg.get("addr", ""))
        self.key = make_input(S.HINT_API_KEY, cfg.get("key", ""), password=True)
        self.inputs = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(148),
                                spacing=dp(6))
        self.inputs.add_widget(self._with_paste(self.addr))
        self.inputs.add_widget(self._with_paste(self.key))
        load_btn = Button(text=S.BTN_LOAD, size_hint_y=None, height=dp(48),
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
        for name, lab in (("wallet", S.TAB_WALLET), ("offers", S.TAB_OFFERS)):
            nav.add_widget(self._tab(name, lab))
        plus = RoundBtn(text=S.TAB_PLUS, font_size="34sp", color=WHITE, bold=True, size_hint_x=0.9)
        plus.bind(on_release=lambda *_: self.open_create())
        nav.add_widget(plus)
        for name, lab in (("stake", S.TAB_STAKE), ("credits", S.TAB_CREDITS)):
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
        pb = Button(text=S.BTN_PASTE, size_hint=(None, 1), width=dp(72), background_normal="",
                    background_color=BLUE, color=WHITE, bold=True)
        pb.bind(on_release=lambda *_: self.paste_into(field))
        row.add_widget(pb)
        return row

    def paste_into(self, field):
        t = util.paste_text()
        if t:
            field.text = t
            self.msg.text = S.MSG_PASTED
        else:
            self.msg.text = S.MSG_CLIPBOARD_EMPTY

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
        try:
            self.overlays.append(w)
            self.root.add_widget(w)
        except Exception as e:  # noqa: BLE001
            save_crash(self, e)
            self.msg.text = "Overlay error: " + str(e)[:80]

    def open_create(self):
        self.open_overlay(CreateScreen(self))

    def open_send(self):
        if not self.data:
            self.msg.text = S.MSG_LOAD_FIRST
            return
        self.open_overlay(SendScreen(self))

    def open_redeem(self):
        if not self.data:
            self.msg.text = S.MSG_LOAD_FIRST_REDEEM
            return
        self.open_overlay(RedeemScreen(self))

    def open_donate(self):
        self.open_overlay(DonateScreen(self))

    def coming(self, name):
        self.msg.text = S.MSG_COMING.format(name=name)

    def close_top(self):
        if self.overlays:
            self.root.remove_widget(self.overlays.pop())

    def on_back(self, window, key, *args):
        if key == 27 and self.overlays:   # Android back button
            self.close_top()
            return True
        return False

    def on_pause(self):
        return True                      # the wallet app comes to the front while it approves

    def on_resume(self):
        self.wallet.on_resume()

    def on_start(self):
        Window.bind(on_keyboard=self.on_back)
        prev = load_and_clear_crash(self)
        if prev:
            # show last crash on next start (plan item)
            self.err = "Previous crash:\n" + prev[:600]
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
        self.msg.text = S.MSG_LOADING
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
        self.msg.text = S.MSG_BLOCK_VIA.format(block=d["block"], source=d["source"])
        self.sub.text = S.HEADER_WALLET.format(addr=short(d["address"]))
        self.render()

    # ---------------------------------------------------------- pages
    def render(self):
        b = self.box
        b.clear_widgets()
        p = self.page
        d = self.data
        set_visible(self.inputs, p == "wallet")
        if self.err:
            b.add_widget(Card(S.ERROR_CARD.format(error=escape_markup(self.err))))
        if d is None:
            if p == "wallet":
                if not self.err:
                    b.add_widget(Card(S.EMPTY_WALLET))
            else:
                b.add_widget(Card(S.EMPTY_OTHER_TABS))
            return
        try:
            PAGES[p](self, b, d)
        except Exception as e:  # noqa: BLE001
            save_crash(self, e)
            b.clear_widgets()
            b.add_widget(Card(
                "[b]Page error[/b]\n" + escape_markup(str(e)) +
                "\n\n[size=13sp]Saved for next start. Pull to reload or switch tabs.[/size]"))


if __name__ == "__main__":
    DsosApp().run()
