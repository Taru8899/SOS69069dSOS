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
from page_economics import EconomicsScreen
from page_redeem import RedeemScreen
from page_sell import SellScreen
from page_send import SendScreen
from page_settings import SettingsScreen
from wallet import Wallet
from design import PLUS_D, PLUS_OUT, HEADER_LINE_H, HEADER_H, LOGO_W, NAV_H, FONT_BODY, FONT_HELPER
from theme import (BLACK, BUILD, BLUE, GREEN, HAS_LOGO, LOGO, LIGHT, WHITE, WELCOME_MAX, WELCOME_MIN,
                   WELCOME_NO_WALLET, short)
from widgets import (Chevron, Card, Choice, ErrorBanner, IconBtn, LogoBtn, NavTab, Panel, PillBtn, PullScroll,
                     Tap, Welcome, label, make_input)

Window.clearcolor = GREEN
Window.softinput_mode = "below_target"   # keep the focused field visible above the keyboard


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
        self.ui = {"offers_tab": "offers", "act_scope": "contract", "act_filter": "all",
                   "offer_sel": None, "act_sel": None, "offers_filter": None}
        self.activity = {}        # scope -> activity.Store (cleared by reload)

        root = FloatLayout()
        self.root_box = root
        main = BoxLayout(orientation="vertical", spacing=0)     # full width: no outer margin
        self.main = main

        # ---- header: logo (+ large caret), "My wallet" text, Ethereum pill
        head = BoxLayout(size_hint_y=None, height=dp(HEADER_H), spacing=dp(10),
                         padding=[dp(14), dp(4), dp(14), dp(2)])
        self.head = head
        logo_col = BoxLayout(orientation="vertical", size_hint=(None, 1), width=dp(LOGO_W))
        if HAS_LOGO:
            self.logo = LogoBtn(source=LOGO, size_hint=(1, 1))      # the whole column: 68 dp logo
            self.logo.bind(on_release=lambda *_: self.go_home())
            logo_col.add_widget(self.logo)
        head.add_widget(logo_col)
        # "Main wallet" / underlined address + triangle right after it; tap = wallet panel
        title = Tap(orientation="vertical")
        title.bind(on_release=lambda *_: self.toggle_drawer())
        title.add_widget(BoxLayout())                      # equal spacers keep the two lines together
        title.add_widget(label(S.HEADER_TITLE, size_hint_y=None, height=dp(HEADER_LINE_H)))
        addr_row = BoxLayout(size_hint_y=None, height=dp(HEADER_LINE_H), spacing=dp(6))
        self.sub = Label(text=self._head_text(short(cfg.get("addr", "")) or S.HEADER_NO_ADDR),
                         markup=True, color=BLACK, font_size=FONT_BODY, halign="left",
                         valign="middle", size_hint=(None, 1))
        self.sub.bind(texture_size=lambda i, ts: setattr(i, "width", ts[0]))
        self.chev = Chevron(pos_hint={"center_y": 0.5})
        addr_row.add_widget(self.sub)
        addr_row.add_widget(self.chev)
        addr_row.add_widget(BoxLayout())
        title.add_widget(addr_row)
        title.add_widget(BoxLayout())
        head.add_widget(title)
        pill = PillBtn(text=S.CHAIN_PILL, color=WHITE, bold=True, size_hint=(None, None),
                       size=(dp(124), dp(38)), pos_hint={"center_y": 0.5})
        pill.bind(on_release=lambda *_: self.open_settings())
        head.add_widget(pill)
        main.add_widget(head)

        self.msg = Label(text="", size_hint_y=None, height=dp(20), color=BLACK, font_size=FONT_HELPER, bold=True)
        main.add_widget(self.msg)

        # ---- drawer (Etherscan key + wallet address + Load): a panel that floats over the top
        # of the body. It is added to the body only while open, so folded it takes no space.
        self.addr = make_input(S.HINT_ADDRESS, cfg.get("addr", ""))
        self.key = make_input(S.HINT_API_KEY, cfg.get("key", ""), password=True)
        self.drawer = Panel(orientation="vertical", size_hint=(None, None), spacing=dp(8),
                            padding=dp(12), bg=LIGHT)
        self.drawer.size = (dp(300), dp(12 * 2 + 3 * 50 + 2 * 8))
        self.drawer.add_widget(self._with_paste(self.key))
        self.drawer.add_widget(self._with_paste(self.addr))
        # Load (70 %) on the left, Exit (30 %) on the right: Exit disconnects the wallet
        btn_row = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(8))
        load_btn = Choice(base=BLUE, fg=WHITE, text=S.BTN_LOAD, bold=True, size_hint_x=0.7)
        load_btn.bind(on_release=self.load)
        exit_btn = Choice(base=BLACK, fg=WHITE, text=S.BTN_EXIT, bold=True, size_hint_x=0.3)
        exit_btn.bind(on_release=self.exit_wallet)
        self.load_btn, self.exit_btn = load_btn, exit_btn
        btn_row.add_widget(load_btn)
        btn_row.add_widget(exit_btn)
        self.drawer.add_widget(btn_row)

        # ---- body: the page (scrolls, pull to reload) and, on top of it, overlay pages
        self.body = FloatLayout()
        self.body.bind(width=self._fit_drawer)
        self.sv = PullScroll(size_hint=(1, 1), pos_hint={"x": 0, "y": 0})
        self.box = BoxLayout(orientation="vertical", spacing=dp(10), size_hint_y=None,
                             padding=[dp(14), dp(4), dp(14), dp(16)])
        self.box.bind(minimum_height=self.box.setter("height"))
        self.sv.add_widget(self.box)
        self.body.add_widget(self.sv)
        main.add_widget(self.body)

        # ---- bottom bar (always visible, full width)
        nav = BoxLayout(size_hint_y=None, height=dp(NAV_H))
        self.nav = nav
        with nav.canvas.before:
            Color(*BLACK)
            nav_bg = Rectangle()
        nav.bind(pos=lambda i, p: setattr(nav_bg, "pos", p),
                 size=lambda i, s: setattr(nav_bg, "size", s))
        self.nav_btns = {}
        for name, lab, ic in (("send", S.TAB_SEND, "send"), ("receive", S.ACTION_RECEIVE, "recv")):
            nav.add_widget(self._tab(name, lab, ic))
        # the "+" circle: PLUS_OUT (10 %) of it sticks out above the top edge of the bar
        plus_cell = FloatLayout(size_hint_x=0.9)
        plus = IconBtn(icon="plus", bg=BLUE, color=WHITE, icon_size=30, size_hint=(None, None),
                       size=(dp(PLUS_D + 6), dp(PLUS_D + 6)))      # IconBtn draws a circle 6 dp smaller
        plus.bind(on_release=lambda *_: self.open_create())
        self.plus = plus

        def place_plus(*_):
            plus.center_x = plus_cell.center_x
            plus.center_y = plus_cell.top + dp(PLUS_OUT * PLUS_D) - dp(PLUS_D) / 2
        plus_cell.bind(pos=place_plus, size=place_plus)
        plus_cell.add_widget(plus)
        place_plus()
        nav.add_widget(plus_cell)
        for name, lab, ic in (("sell", S.TAB_SELL, "list"), ("redeem", S.TAB_REDEEM, "credits")):
            nav.add_widget(self._tab(name, lab, ic))
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
        row = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(6))
        row.add_widget(field)
        pb = Choice(base=BLUE, fg=WHITE, text=S.BTN_PASTE, bold=True, size_hint=(None, 1),
                    width=dp(72))
        pb.bind(on_release=lambda *_: self.paste_into(field))
        row.add_widget(pb)
        return row

    def paste_into(self, field):
        t = util.paste_text()
        if t:
            field.text = t
            self.say(S.MSG_PASTED)
        else:
            self.say(S.MSG_CLIPBOARD_EMPTY)

    def _fit_drawer(self, *_):
        w = max(dp(240), self.body.width - dp(28))
        self.drawer.width = w
        self.drawer.pos_hint = {"x": dp(14) / max(self.body.width, 1), "top": 1}

    def set_drawer(self, show, animate=True):
        self.drawer_open = bool(show)
        self.chev.set_open(self.drawer_open, animate=animate)
        if self.drawer_open:
            self.close_all()                  # the panel and a page are never open together
        if self.drawer_open and self.drawer.parent is None:
            self._fit_drawer()
            self.drawer.pos_hint = {"x": dp(14) / max(self.body.width, 1), "top": 1}
            self.body.add_widget(self.drawer)
        elif not self.drawer_open and self.drawer.parent is not None:
            self.drawer.parent.remove_widget(self.drawer)

    def toggle_drawer(self):
        self.set_drawer(not self.drawer_open)

    def set_offers_tab(self, tab):
        self.ui["offers_tab"] = tab
        self.render()

    def go_home(self):
        self.close_all()
        self.set_page("wallet")

    def say(self, text, secs=6):
        """Short message under the header; it goes away after `secs` seconds and when the page
        changes, and the 'Block ... via ...' line comes back."""
        self.msg.text = text
        if getattr(self, "_say_ev", None) is not None:
            self._say_ev.cancel()
        self._say_ev = Clock.schedule_once(lambda dt: self.restore_msg(), secs)

    def restore_msg(self):
        d = self.data
        self.msg.text = S.MSG_BLOCK_VIA.format(block=d["block"], source=d["source"]) if d else ""

    def notify_tx(self, h, ok, block, reason):
        """Result of a transaction whose screen was closed meanwhile."""
        if ok:
            self.say(S.TX_OK_SHORT.format(hash=short(h), block=block), 10)
            self.reload()
        else:
            why = reason or S.TX_FAILED_UNKNOWN
            self.show_banner(S.TX_FAILED_SHORT.format(hash=short(h), reason=why),
                             "%s\n%s" % (why, h))

    def _head_text(self, addr):
        return "[u]" + addr + "[/u]"

    def _toggle_overlay(self, cls):
        """Open the page; a second tap on the same header link closes it again."""
        if self.overlays and isinstance(self.overlays[-1], cls):
            self.close_all()
            return
        self.close_all()
        self.open_overlay(cls(self))

    def open_settings(self):
        self._toggle_overlay(SettingsScreen)

    def open_economics(self):
        if not self.data:
            self.say(S.ECON_NEED_DATA)
            return
        self._toggle_overlay(EconomicsScreen)

    def open_offers(self, flt=None):
        """Offers tab (not Activity) with a filter: used by the Wallet chips."""
        self.close_all()
        self.ui["offers_tab"] = "offers"
        self.ui["offers_filter"] = flt
        self.set_page("offers")

    # ---------------------------------------------------------- tabs
    def _tab(self, name, text, icon):
        b = NavTab(icon, text)
        b.bind(on_release=lambda *_: self.tab_tap(name))
        self.nav_btns[name] = b
        return b

    def _mark_tabs(self):
        # Send, Receive and Sell open overlays (no highlight); Redeem also covers the Stake page
        on = {"credits": "redeem", "stake": "redeem"}.get(self.page, "")
        tabs = {SendScreen: "send", RedeemScreen: "receive", SellScreen: "sell"}
        other = (CreateScreen, DonateScreen, EconomicsScreen, SettingsScreen)
        for w in reversed(self.overlays):       # topmost page decides; transaction pages inherit
            if type(w) in tabs:
                on = tabs[type(w)]
                break
            if isinstance(w, other):
                on = ""
                break
        for name, b in self.nav_btns.items():
            b.set_active(name == on)

    def tab_tap(self, name):
        self.close_all()
        if name == "send":
            self.open_send()
        elif name == "receive":
            self.open_redeem()
        elif name == "sell":
            self.open_sell()
        elif name == "redeem":
            self.set_page("credits")
        else:
            self.set_page(name)

    def set_page(self, name):
        if self.msg.text and self.data:
            self.restore_msg()
        self.page = name
        self._mark_tabs()
        self.render()
        self.sv.scroll_y = 1

    # ---------------------------------------------------------- overlays (inside the body)
    def open_overlay(self, w):
        if self.drawer_open:
            self.set_drawer(False)
        self.overlays.append(w)
        self.body.add_widget(w)
        self._mark_tabs()

    def open_create(self):
        self.close_all()
        self.open_overlay(CreateScreen(self))

    def refresh_lefts(self, blk):
        """Re-measure every offer's time left against a fresh block (the data was read earlier)."""
        d = self.data
        if not d or not blk or blk < d.get("block", 0):
            return
        d["block"] = blk
        for o in d["offers"]:
            o["left"] = o["sweepable_at"] - blk
            o["sendable"] = o["kind"] == "S" and o["left"] > core.WINDOW + core.SEND_MARGIN

    def open_send(self):
        if not self.data:
            self.say(S.MSG_LOAD_FIRST)
            return
        if getattr(self, "_send_opening", False):
            return
        self._send_opening = True

        def work():
            try:
                blk = core.Chain(self.key.text).block()
            except Exception:  # noqa: BLE001
                blk = 0
            Clock.schedule_once(lambda dt: self._open_send(blk))
        threading.Thread(target=work, daemon=True).start()

    def _open_send(self, blk):
        self._send_opening = False
        self.refresh_lefts(blk)
        self.open_overlay(SendScreen(self))

    def open_redeem(self):
        if not self.data:
            self.say(S.MSG_LOAD_FIRST_REDEEM)
            return
        self.open_overlay(RedeemScreen(self))

    def open_donate(self):
        self.open_overlay(DonateScreen(self))

    def open_sell(self, sale_id=None):
        """Sell SOS records to an A / B offer (needs the wallet loaded: it reads your next records)."""
        if not self.data:
            self.say(S.MSG_LOAD_FIRST_SELL)
            return
        self.open_overlay(SellScreen(self, sale_id))

    def coming(self, name):
        self.say(S.MSG_COMING.format(name=name))

    def close_top(self):
        if self.overlays:
            self.body.remove_widget(self.overlays.pop())
            self._mark_tabs()

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
        self.say(S.ACT_OFFER_NOT_MINE.format(id=oid))
        return False

    def on_back(self, window, key, *args):
        if key == 27 and self.overlays:   # Android back button
            self.close_top()
            return True
        if key == 27 and self.page in ("credits", "stake"):
            self.go_home()
            return True
        return False

    def on_pause(self):
        return True                      # the wallet app comes to the front while it approves

    def on_resume(self):
        self.wallet.on_resume()

    def layout_report(self):
        """Positions and sizes of the shell parts: for pasting into a bug report."""
        try:
            from kivy.metrics import Metrics
            dens = Metrics.density
        except Exception:  # noqa: BLE001
            dens = "?"
        out = [f"window={tuple(Window.size)} density={dens} build={BUILD}"]
        for n in ("head", "msg", "body", "sv", "box", "nav", "drawer"):
            w = getattr(self, n, None)
            if w is None:
                continue
            try:
                out.append("%s pos=%s size=%s in_tree=%s" % (
                    n, tuple(round(v) for v in w.pos), tuple(round(v) for v in w.size),
                    w.parent is not None))
            except Exception as e:  # noqa: BLE001
                out.append(f"{n}: {e}")
        out.append("overlays=%d page=%s drawer_open=%s" % (len(self.overlays), self.page,
                                                            self.drawer_open))
        return "\n".join(out)

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

    def exit_wallet(self, *_):
        """Exit: end the WalletConnect session. The loaded data stays on screen."""
        try:
            self.wallet.disconnect()
        except Exception:  # noqa: BLE001
            pass
        self.say(S.MSG_WALLET_DISCONNECTED)

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
            if not self.overlays:              # opening the panel would close the page the person is on
                self.set_drawer(True)
            return
        self.activity.clear()
        self.msg.text = S.MSG_RELOADING
        self.load()

    def pull_overlay(self):
        """Pull down on Send / Redeem / Donate / Economics: read the wallet again, then build that page
        again from the new data."""
        top = self.overlays[-1] if self.overlays else None
        if top is None or not self.addr.text.strip():
            self.reload()
            return
        self._after_load = lambda cls=type(top): self._reopen(cls)
        self.reload()

    def _reopen(self, cls):
        if not self.overlays or type(self.overlays[-1]) is not cls:
            return                              # the person went somewhere else meanwhile
        self.close_top()
        if cls is SendScreen:
            self.open_send()
        elif cls is RedeemScreen:
            self.open_redeem()
        elif cls is DonateScreen:
            self.open_donate()
        elif cls is EconomicsScreen:
            self.open_economics()

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
        self._after_load = None
        self.set_drawer(True)                  # let the person fix the address / key
        self.render()

    def show(self, d):
        self.loading = False
        self.loaded_once = True
        self.data = d
        self.err = None
        self.msg.text = S.MSG_BLOCK_VIA.format(block=d["block"], source=d["source"])
        self.sub.text = self._head_text(short(d["address"]))
        self.render()
        again, self._after_load = getattr(self, "_after_load", None), None
        if again:
            again()

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
