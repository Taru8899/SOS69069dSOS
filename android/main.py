import json
import os
import threading
import time
import traceback

from kivy.animation import Animation
from kivy.app import App
from kivy.base import ExceptionHandler, ExceptionManager
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, Rectangle
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.label import Label
from kivy.utils import escape_markup

import core
import page_activity
import page_credits
import page_offers
import page_stake
import page_wallet
import strings as S
import util
from page_create import CreateScreen
from page_donate import DonateScreen
from page_links import LinksScreen
from page_redeem import RedeemScreen
from page_send import SendScreen
from page_settings import SettingsScreen
from wallet import Wallet
from theme import BLACK, BLUE, GREEN, HAS_LOGO, LOGO, WHITE, set_visible, short
from widgets import (Caret, Card, ErrorBanner, LogoBtn, NavBtn, PillBtn, PullScroll, RoundBtn,
                     Tap, Welcome, label, make_input)

Window.clearcolor = GREEN
Window.softinput_mode = "below_target"   # keep the focused field visible above the keyboard

WELCOME_MIN = 2.0          # seconds the welcome screen stays at least (saved wallet)
WELCOME_MAX = 8.0          # ... and at most
WELCOME_NO_WALLET = 2.5    # no saved wallet: nothing to wait for

# tab name -> function that fills that tab:  build(app, box, data)
PAGES = {
    "wallet": page_wallet.build,
    "offers": page_offers.build,
    "stake": page_stake.build,
    "credits": page_credits.build,
}


class Catcher(ExceptionHandler):
    """Any exception inside a button/timer callback ends up here instead of closing the app."""

    def handle_exception(self, inst):
        app = App.get_running_app()
        try:
            if app is not None:
                app.report_error(inst)
        except Exception:  # noqa: BLE001
            pass
        return ExceptionManager.PASS


ExceptionManager.add_handler(Catcher())


class DsosApp(App):
    def build(self):
        self.title = S.APP_TITLE
        if HAS_LOGO:
            self.icon = LOGO
        self.cfg_path = os.path.join(self.user_data_dir, "cfg.json")
        self.crash_path = os.path.join(self.user_data_dir, "crash.txt")
        self.crumb_path = os.path.join(self.user_data_dir, "breadcrumb.txt")
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
        self.banner = None
        self.loaded_once = False
        self.loading = False
        self.drawer_open = False
        # page state that must survive a reload
        self.ui = {"offers_tab": "offers", "act_scope": "mine", "act_filter": "all",
                   "offer_sel": None, "act_sel": None}
        self.activity = {}        # scope -> activity.Store (cleared by reload)

        root = FloatLayout()
        self.root_box = root
        main = BoxLayout(orientation="vertical", padding=[dp(10), dp(6), dp(10), 0],
                         spacing=dp(4))

        # ---- header: logo (+ tiny caret), "My wallet" text, Ethereum pill
        head = BoxLayout(size_hint_y=None, height=dp(66), spacing=dp(10))
        logo_col = BoxLayout(orientation="vertical", size_hint=(None, 1), width=dp(52))
        if HAS_LOGO:
            self.logo = LogoBtn(source=LOGO, size_hint=(1, 1))
            self.logo.bind(on_release=lambda *_: self.go_home())
            logo_col.add_widget(self.logo)
        self.caret = Caret()
        self.caret.bind(on_release=lambda *_: self.toggle_drawer())
        logo_col.add_widget(self.caret)
        head.add_widget(logo_col)
        title = Tap(orientation="vertical")
        title.bind(on_release=lambda *_: self.open_settings())
        self.sub = label(S.HEADER_WALLET.format(addr=short(cfg.get("addr", "")) or S.HEADER_NO_ADDR))
        title.add_widget(self.sub)
        head.add_widget(title)
        pill = PillBtn(text=S.CHAIN_PILL, color=WHITE, bold=True, size_hint=(None, None),
                       size=(dp(104), dp(34)), pos_hint={"center_y": 0.5})
        pill.bind(on_release=lambda *_: self.open_links())
        head.add_widget(pill)
        main.add_widget(head)

        self.msg = Label(text="", size_hint_y=None, height=dp(20), color=BLACK, font_size="13sp")
        main.add_widget(self.msg)

        # ---- drawer: Etherscan key + wallet address + Load (created once, only hidden/shown)
        self.addr = make_input(S.HINT_ADDRESS, cfg.get("addr", ""))
        self.key = make_input(S.HINT_API_KEY, cfg.get("key", ""), password=True)
        self.drawer = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(148),
                                spacing=dp(6))
        self.drawer.add_widget(self._with_paste(self.key))
        self.drawer.add_widget(self._with_paste(self.addr))
        load_btn = Button(text=S.BTN_LOAD, size_hint_y=None, height=dp(48),
                          background_normal="", background_down="", background_color=BLUE,
                          color=WHITE, bold=True)
        load_btn.bind(on_release=self.load)
        self.drawer.add_widget(load_btn)
        main.add_widget(self.drawer)

        # ---- body: the page (scrolls, pull to reload) and, on top of it, overlay pages
        self.body = FloatLayout()
        self.sv = PullScroll(size_hint=(1, 1))
        self.box = BoxLayout(orientation="vertical", spacing=dp(10), size_hint_y=None)
        self.box.bind(minimum_height=self.box.setter("height"))
        self.sv.add_widget(self.box)
        self.body.add_widget(self.sv)
        main.add_widget(self.body)

        # ---- bottom bar (always visible)
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
        main.add_widget(nav)
        root.add_widget(main)

        # ---- welcome screen on top of everything at start
        self.splash = Welcome()
        root.add_widget(self.splash)
        self.splash.start()

        self.set_drawer(not self.addr.text.strip(), animate=False)
        self.render()
        self._mark_tabs()
        return root

    # ---------------------------------------------------------- header / drawer
    def _with_paste(self, field):
        row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(6))
        row.add_widget(field)
        pb = Button(text=S.BTN_PASTE, size_hint=(None, 1), width=dp(72), background_normal="",
                    background_down="", background_color=BLUE, color=WHITE, bold=True)
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

    def set_drawer(self, show, animate=True):
        self.drawer_open = bool(show)
        self.caret.set_open(self.drawer_open)
        set_visible(self.drawer, self.drawer_open)

    def toggle_drawer(self):
        self.set_drawer(not self.drawer_open)

    def set_offers_tab(self, tab):
        self.ui["offers_tab"] = tab
        self.render()

    def go_home(self):
        self.close_all()
        self.set_page("wallet")

    def open_settings(self):
        self.close_all()
        self.open_overlay(SettingsScreen(self))

    def open_links(self):
        self.close_all()
        self.open_overlay(LinksScreen(self))

    # ---------------------------------------------------------- tabs
    def _tab(self, name, text):
        b = NavBtn(text=text)
        b.bind(on_release=lambda *_: self.tab_tap(name))
        self.nav_btns[name] = b
        return b

    def _mark_tabs(self):
        for name, b in self.nav_btns.items():
            on = name == self.page
            b.color = WHITE if on else (0.6, 0.62, 0.62, 1)
            b.bold = on

    def tab_tap(self, name):
        self.close_all()
        self.set_page(name)

    def set_page(self, name):
        self.page = name
        self._mark_tabs()
        self.render()
        self.sv.scroll_y = 1

    # ---------------------------------------------------------- overlays (inside the body)
    def open_overlay(self, w):
        self.overlays.append(w)
        self.body.add_widget(w)

    def open_create(self):
        self.close_all()
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
            self.body.remove_widget(self.overlays.pop())

    def close_all(self):
        while self.overlays:
            self.close_top()

    def go_offer(self, oid):
        """From an Activity row: show offer #oid on the Offers tab (if it is in the list)."""
        self.close_all()
        if self.data and any(o["id"] == oid for o in self.data["offers"]):
            self.ui["offers_tab"] = "offers"
            self.ui["offer_sel"] = oid
            self.set_page("offers")
            return True
        self.msg.text = S.ACT_OFFER_NOT_MINE.format(id=oid)
        return False

    def on_back(self, window, key, *args):
        if key == 27 and self.overlays:   # Android back button
            self.close_top()
            return True
        return False

    def on_pause(self):
        return True                      # the wallet app comes to the front while it approves

    def on_resume(self):
        self.wallet.on_resume()

    # ---------------------------------------------------------- errors
    def crumb(self, step):
        """Write the step we are about to do: if the app dies natively this is what we know."""
        try:
            os.makedirs(self.user_data_dir, exist_ok=True)
            with open(self.crumb_path, "w") as f:
                f.write(step)
        except Exception:  # noqa: BLE001
            pass

    def report_error(self, exc):
        text = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        try:
            os.makedirs(self.user_data_dir, exist_ok=True)
            with open(self.crash_path, "w") as f:
                f.write(text)
        except Exception:  # noqa: BLE001
            pass
        self.show_banner(f"{type(exc).__name__}: {exc}", text)

    def show_banner(self, short_text, full_text):
        if getattr(self, "banner", None) is not None:
            self.root_box.remove_widget(self.banner)
            self.banner = None
        b = ErrorBanner(S.ERR_BANNER.format(text=short_text), full_text, self.close_banner,
                        pos_hint={"top": 1})
        self.banner = b
        self.root_box.add_widget(b)

    def close_banner(self, b=None):
        if self.banner is not None:
            self.root_box.remove_widget(self.banner)
            self.banner = None
        for p in (self.crash_path,):
            try:
                os.remove(p)
            except OSError:
                pass

    def check_last_run(self):
        """Show what went wrong in the previous run (a Python crash text, or the last step)."""
        try:
            with open(self.crash_path) as f:
                txt = f.read()
            if txt.strip():
                self.show_banner(txt.strip().splitlines()[-1], txt)
                return
        except OSError:
            pass
        try:
            with open(self.crumb_path) as f:
                step = f.read().strip()
            if step and step != "ok":
                self.show_banner(S.ERR_LAST_RUN.format(step=step), step)
        except OSError:
            pass

    # ---------------------------------------------------------- start / welcome
    def on_start(self):
        Window.bind(on_keyboard=self.on_back)
        self.check_last_run()
        self.t0 = time.time()
        self.has_saved = bool(self.addr.text.strip())
        if self.has_saved:
            self.load()
        Clock.schedule_interval(self.welcome_tick, 0.2)

    def welcome_tick(self, dt):
        el = time.time() - self.t0
        if self.has_saved:
            done = (self.loaded_once and el >= WELCOME_MIN) or el >= WELCOME_MAX
        else:
            done = el >= WELCOME_NO_WALLET
        if done:
            self.hide_splash()
            return False
        return True

    def hide_splash(self, *_):
        sp = self.splash
        if sp is None:
            return
        self.splash = None
        anim = Animation(opacity=0, duration=0.4)

        def gone(*a):
            sp.stop()
            if sp.parent is not None:
                sp.parent.remove_widget(sp)
        anim.bind(on_complete=gone)
        anim.start(sp)

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
        if not self.addr.text.strip():
            self.msg.text = S.MSG_NEED_ADDRESS
            self.set_drawer(True)
            self.loaded_once = True
            return
        self.loading = True
        self.msg.text = S.MSG_LOADING
        self.set_drawer(False)                 # the key and address fold back into the logo
        threading.Thread(target=self._work, args=(self.addr.text, self.key.text),
                         daemon=True).start()

    def reload(self):
        """Pull-to-reload: wallet data again, and the Activity lists with it."""
        if not self.addr.text.strip():
            self.msg.text = S.MSG_NEED_ADDRESS
            self.set_drawer(True)
            return
        self.activity.clear()
        self.msg.text = S.MSG_RELOADING
        self.load()

    def _work(self, addr, key):
        try:
            d = core.Chain(key).load(addr)
            Clock.schedule_once(lambda dt: self.show(d))
        except Exception as e:  # noqa: BLE001
            m = str(e)
            Clock.schedule_once(lambda dt: self.fail(m))

    def fail(self, m):
        self.loading = False
        self.loaded_once = True
        self.msg.text = ""
        self.err = m
        self.set_drawer(True)                  # let the person fix the address / key
        self.render()

    def show(self, d):
        self.loading = False
        self.loaded_once = True
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
        self.crumb("render " + p)
        try:
            if self.err:
                b.add_widget(Card(S.ERROR_CARD.format(error=escape_markup(self.err))))
            if d is None:
                if not (p == "wallet" and self.err):
                    b.add_widget(Card(S.EMPTY_WALLET if p == "wallet" else S.EMPTY_OTHER_TABS))
            else:
                PAGES[p](self, b, d)
        except Exception as e:  # noqa: BLE001
            b.clear_widgets()
            b.add_widget(Card(S.ERR_PAGE.format(error=escape_markup(f"{type(e).__name__}: {e}"))))
            self.report_error(e)
        self.crumb("ok")


if __name__ == "__main__":
    DsosApp().run()
