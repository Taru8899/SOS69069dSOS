import json
import os
import threading
import sys
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
                   set_visible, short)
from widgets import Card, Choice, NavBtn, Overlay, Panel, Pill, RoundBtn, Splash, label, make_input

Window.clearcolor = GREEN
Window.softinput_mode = "below_target"   # keep the focused field visible above the keyboard

# tab name -> function that fills that tab:  build(app, box, data)
PAGES = {
    "wallet": page_wallet.build,
    "offers": page_offers.build,
    "stake": page_stake.build,
    "credits": page_credits.build,
}


class RefreshScrollView(ScrollView):
    """Existing ScrollView with a small pull-down-to-refresh gesture at the top."""
    def __init__(self, refresh_callback=None, **kw):
        super().__init__(**kw)
        self.refresh_callback = refresh_callback
        self._pull_start = None

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos) and self.scroll_y >= 0.985 and touch.y >= self.top - dp(70):
            self._pull_start = touch.y
        return super().on_touch_down(touch)

    def on_touch_up(self, touch):
        start = self._pull_start
        self._pull_start = None
        handled = super().on_touch_up(touch)
        if start is not None and touch.y - start > dp(65) and self.scroll_y >= 0.90:
            if self.refresh_callback:
                self.refresh_callback()
            return True
        return handled


class DsosApp(App):
    def build(self):
        self.title = S.APP_TITLE
        if HAS_LOGO:
            self.icon = LOGO
        self.cfg_path = os.path.join(self.user_data_dir, "cfg.json")
        self.crash_path = os.path.join(self.user_data_dir, "last_crash.txt")
        self._previous_crash = ""
        try:
            if os.path.isfile(self.crash_path):
                with open(self.crash_path, "r", encoding="utf-8") as f:
                    self._previous_crash = f.read()[-12000:]
                os.remove(self.crash_path)  # show this report once on the next launch
        except Exception:
            self._previous_crash = ""
        self._install_exception_hooks()
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
        self.offers_mode = "offers"
        self.activity_scope = "mine"
        self.activity_filter = "all"
        self.activity = []
        self.activity_loading = False
        self.activity_error = None

        # ---- top: header + status line + wallet inputs + scrolling page
        top = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(6))
        head = BoxLayout(size_hint_y=None, height=dp(56), spacing=dp(10))
        logo_btn = Button(text="" if HAS_LOGO else "dSOS", size_hint=(None, 1), width=dp(52),
                          background_normal=LOGO if HAS_LOGO else "",
                          background_down=LOGO if HAS_LOGO else "",
                          background_color=(1, 1, 1, 1) if HAS_LOGO else BLUE,
                          color=WHITE, bold=True)
        logo_btn.bind(on_release=lambda *_: self.set_page("wallet"))
        head.add_widget(logo_btn)
        self.sub = label(S.HEADER_WALLET.format(addr=short(cfg.get("addr", "")) or S.HEADER_NO_ADDR))
        head.add_widget(self.sub)
        menu_btn = Button(text="☰", size_hint=(None, 1), width=dp(42), background_normal="",
                          background_color=BLUE, color=WHITE, font_size="22sp")
        menu_btn.bind(on_release=lambda *_: self.open_drawer())
        head.add_widget(menu_btn)
        chain_btn = Button(text=S.CHAIN_PILL, size_hint=(None, None), size=(dp(104), dp(34)),
                           pos_hint={"center_y": 0.5}, background_normal="",
                           background_color=BLACK, color=WHITE, bold=True)
        chain_btn.bind(on_release=lambda *_: self.open_launcher())
        head.add_widget(chain_btn)
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
        self.load_btn = load_btn
        self.inputs.add_widget(load_btn)

        self.sv = RefreshScrollView(refresh_callback=self.load)
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
        self._root_widget = root
        self.render()
        self._mark_tabs()
        if self._previous_crash:
            Clock.schedule_once(lambda *_: self._display_previous_crash(), 0.2)
        return root

    def _modal(self, title, width=0.90):
        overlay = Overlay()
        backdrop = Button(text="", background_normal="", background_color=(0, 0, 0, 0.58),
                          size_hint=(1, 1), pos=(0, 0))
        backdrop.bind(on_release=lambda *_: self.close_top())
        overlay.add_widget(backdrop)
        panel = Panel(bg=WHITE, orientation="vertical", spacing=dp(10), padding=dp(16),
                      size_hint=(width, 0.92), pos_hint={"center_x": 0.5, "center_y": 0.5})
        title_row = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
        title_row.add_widget(label(title, font_size="22sp"))
        close = Button(text="×", size_hint=(None, 1), width=dp(44), background_normal="",
                       background_color=BLACK, color=WHITE, font_size="24sp")
        close.bind(on_release=lambda *_: self.close_top())
        title_row.add_widget(close)
        panel.add_widget(title_row)
        overlay.add_widget(panel)
        self.open_overlay(overlay)
        return panel

    def _move_inputs(self, parent):
        if self.inputs.parent is not None:
            self.inputs.parent.remove_widget(self.inputs)
        parent.add_widget(self.inputs)

    def open_drawer(self):
        panel = self._modal("dSOS · Menu", width=0.90)
        panel.add_widget(label("My wallet", font_size="18sp", size_hint_y=None, height=dp(34)))
        self._move_inputs(panel)
        settings = Choice(base=BLUE, fg=WHITE, text="My wallet · Settings", bold=True, size_hint_y=None, height=dp(48))
        settings.bind(on_release=lambda *_: self.open_settings())
        panel.add_widget(settings)
        refresh = Choice(base=GREEN, fg=WHITE, text="Load / Refresh wallet", bold=True, size_hint_y=None, height=dp(48))
        refresh.bind(on_release=lambda *_: self.load())
        panel.add_widget(refresh)
        panel.add_widget(label("Ethereum mainnet · read-only Activity", font_size="12sp", size_hint_y=None, height=dp(28)))

    def open_settings(self):
        if self.overlays:
            self.close_top()  # settings replaces the menu rather than stacking over it
        panel = self._modal("My wallet · Settings", width=0.92)
        panel.add_widget(label("Wallet address and Etherscan API key", font_size="13sp",
                               size_hint_y=None, height=dp(32)))
        self._move_inputs(panel)
        panel.add_widget(Card("Your wallet remains external. This app prepares transactions; signing and broadcasting are handled by your connected wallet."))

    def open_launcher(self):
        panel = self._modal("Ethereum", width=0.92)
        panel.add_widget(label("Choose a dSOS section", font_size="14sp", size_hint_y=None, height=dp(30)))
        tiles = BoxLayout(orientation="vertical", spacing=dp(8))
        choices = (("Wallet", lambda: self.set_page("wallet")),
                   ("Offers", lambda: self.set_page("offers")),
                   ("Stake", lambda: self.set_page("stake")),
                   ("Credits", lambda: self.set_page("credits")),
                   ("Create offer", self.open_create),
                   ("Send", self.open_send))
        for caption, action in choices:
            tile = Choice(base=WHITE, sel=BLUE, text=caption, bold=True, font_size="17sp",
                          size_hint_y=None, height=dp(52))
            def choose(_w, fn=action):
                self.close_top()
                fn()
            tile.bind(on_release=choose)
            tiles.add_widget(tile)
        panel.add_widget(tiles)

    def _install_exception_hooks(self):
        app = self
        old_sys_hook = sys.excepthook
        def sys_hook(exc_type, exc, tb):
            app._record_crash("Uncaught exception", "".join(traceback.format_exception(exc_type, exc, tb)))
            try:
                old_sys_hook(exc_type, exc, tb)
            except Exception:
                pass
        sys.excepthook = sys_hook
        if hasattr(threading, "excepthook"):
            old_thread_hook = threading.excepthook
            def thread_hook(args):
                app._record_crash("Background thread exception", "".join(traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback)))
                try:
                    old_thread_hook(args)
                except Exception:
                    pass
            threading.excepthook = thread_hook
        class KivyExceptionHandler(ExceptionHandler):
            def handle_exception(self, exception):
                app._record_crash("Kivy callback exception", "".join(traceback.format_exception(type(exception), exception, exception.__traceback__)))
                return ExceptionManager.HANDLED
        self._kivy_exception_handler = KivyExceptionHandler()
        try:
            ExceptionManager.add_handler(self._kivy_exception_handler)
        except Exception:
            pass

    def _record_crash(self, title, detail):
        report = f"{title}\n{time.strftime('%Y-%m-%d %H:%M:%S')}\n\n{detail}"
        try:
            os.makedirs(self.user_data_dir, exist_ok=True)
            with open(self.crash_path, "w", encoding="utf-8") as f:
                f.write(report[-30000:])
        except Exception:
            pass
        try:
            Clock.schedule_once(lambda *_: self._show_crash(report), 0)
        except Exception:
            pass

    def _show_crash(self, report):
        self.err = report
        if getattr(self, "box", None):
            try:
                self.box.clear_widgets()
                self.box.add_widget(Card("[color=bb001f][b]Application error[/b][/color]\n" + escape_markup(report[-7000:])))
            except Exception:
                pass

    def _display_previous_crash(self):
        if self._previous_crash:
            self._show_crash("Previous session crash report\n\n" + self._previous_crash)
            self._previous_crash = ""

    def safe_build(self, builder, box, data):
        try:
            builder(self, box, data)
        except Exception as exc:
            detail = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
            self._record_crash("Page build failed", detail)
            box.clear_widgets()
            box.add_widget(Card("[color=bb001f][b]Page could not be rendered[/b][/color]\n" + escape_markup(str(exc))))

    def safe_overlay(self, factory):
        try:
            self.open_overlay(factory())
        except Exception as exc:
            detail = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
            self._record_crash("Overlay construction failed", detail)

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
        self.overlays.append(w)
        self.root.add_widget(w)

    def open_create(self):
        self.safe_overlay(lambda: CreateScreen(self))

    def open_send(self):
        if not self.data:
            self.msg.text = S.MSG_LOAD_FIRST
            return
        self.safe_overlay(lambda: SendScreen(self))

    def open_redeem(self):
        if not self.data:
            self.msg.text = S.MSG_LOAD_FIRST_REDEEM
            return
        self.safe_overlay(lambda: RedeemScreen(self))

    def open_donate(self):
        self.safe_overlay(lambda: DonateScreen(self))

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
        self._splash_started = time.time()
        self._splash_hidden = False
        Clock.schedule_once(self.hide_splash, 8.0)  # hard timeout even if the network stalls
        if self.addr.text.strip():
            self.load()
        else:
            Clock.schedule_once(self.hide_splash, 2.5)

    def _release_splash(self):
        if self._splash_hidden:
            return
        elapsed = time.time() - getattr(self, "_splash_started", time.time())
        remaining = max(0.0, 2.0 - elapsed)
        if remaining:
            Clock.schedule_once(self.hide_splash, remaining)
        else:
            self.hide_splash()

    def hide_splash(self, *_):
        if getattr(self, "_splash_hidden", False):
            return
        self._splash_hidden = True
        try:
            if getattr(self.splash, "_spin_event", None):
                self.splash._spin_event.cancel()
        except Exception:
            pass
        try:
            anim = Animation(opacity=0, duration=0.35)
            def remove(*_a):
                try:
                    if self.splash.parent:
                        self.root.remove_widget(self.splash)
                except Exception:
                    pass
            anim.bind(on_complete=remove)
            anim.start(self.splash)
        except Exception:
            try:
                if self.splash.parent:
                    self.root.remove_widget(self.splash)
            except Exception:
                pass

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
        address, api_key = self.addr.text, self.key.text
        if self.overlays:
            self.close_top()
        self.msg.text = S.MSG_LOADING
        threading.Thread(target=self._work, args=(address, api_key),
                         daemon=True).start()

    def _work(self, addr, key):
        try:
            d = core.Chain(key).load(addr)
            Clock.schedule_once(lambda dt: self.show(d))
        except Exception as e:  # noqa: BLE001
            m = str(e)
            Clock.schedule_once(lambda dt: self.fail(m))

    def fail(self, m):
        try:
            self.splash.set_status("Connection error · wallet data unavailable")
        except Exception:
            pass
        self._release_splash()
        self.msg.text = ""
        self.err = m
        self.render()

    def show(self, d):
        try:
            self.splash.set_status("Ethereum connected · wallet loaded")
        except Exception:
            pass
        self._release_splash()
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
        if self.err:
            b.add_widget(Card(S.ERROR_CARD.format(error=escape_markup(self.err))))
        if d is None:
            if p == "wallet":
                if not self.err:
                    b.add_widget(Card(S.EMPTY_WALLET))
            else:
                b.add_widget(Card(S.EMPTY_OTHER_TABS))
            return
        self.safe_build(PAGES[p], b, d)


if __name__ == "__main__":
    DsosApp().run()
