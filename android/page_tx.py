"""Transaction page: dry run, "Send with wallet", and copy buttons for any other wallet."""
import threading

from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.utils import escape_markup

import core
import strings as S
import tx
import util
from theme import (BLACK, BLUE, DAPP_URL, DSOS_ADDR, ETHERSCAN_TX, ETHERSCAN_WRITE, LIGHT,
                   WHITE, short)
from widgets import PullScroll, Card, Choice, Overlay, Panel, RoundBtn, label

REJECT_CODES = (4001, 5000)


class TxScreen(Overlay):
    """Shows a ready transaction. The wallet app signs and sends it; the app holds no keys."""

    def __init__(self, app, t, summary, fn_name, rows, tip="", warn="", **kw):
        super().__init__(**kw)
        self.app = app
        self.t0 = t
        self.alive = True
        self.busy = False
        self.sent = False
        self.sign_on = False
        self.sim_ok = None                 # None = unknown, True = passes, False = would fail
        self.frm = self._from_address()
        self.wallet = getattr(app, "wallet", None)

        col = BoxLayout(orientation="vertical")
        head = BoxLayout(size_hint_y=None, height=dp(72), padding=[dp(14), dp(10)], spacing=dp(14))
        back = RoundBtn(text=S.ICON_BACK, font_size="26sp", bold=True, bg=WHITE, color=BLACK,
                        size_hint=(None, 1), width=dp(56))
        back.bind(on_release=lambda *_: self.close())
        head.add_widget(back)
        head.add_widget(label(S.TX_TITLE, font_size="24sp"))
        col.add_widget(head)

        self.status = label("", size_hint_y=None, height=dp(22), font_size="13sp",
                            padding=(dp(14), 0))
        col.add_widget(self.status)

        sv = PullScroll()
        box = BoxLayout(orientation="vertical", spacing=dp(10), size_hint_y=None,
                        padding=[dp(14), 0, dp(14), dp(20)])
        box.bind(minimum_height=box.setter("height"))
        self.box = box

        box.add_widget(Card(summary))
        self.sim_card = Card(S.SIM_RUNNING)
        box.add_widget(self.sim_card)

        # ---- send with wallet
        self.send_btn = Choice(base=BLUE, fg=WHITE, text=S.TX_BTN_WALLET, bold=True,
                               font_size="18sp", size_hint_y=None, height=dp(58))
        self.send_btn.bind(on_release=lambda *_: self.on_wallet_send())
        box.add_widget(self.send_btn)
        self.sign_btn = None
        if t.get("rec"):
            self.sign_btn = Choice(base=LIGHT, fg=BLACK, text=S.TX_LEDGER_OFF, bold=True,
                                   size_hint_y=None, height=dp(46))
            self.sign_btn.bind(on_release=lambda *_: self.toggle_sign())
            box.add_widget(self.sign_btn)
            box.add_widget(Card(S.TX_LEDGER_HELP))
        self.out_box = BoxLayout(orientation="vertical", spacing=dp(8), size_hint_y=None)
        self.out_box.bind(minimum_height=self.out_box.setter("height"))
        box.add_widget(self.out_box)
        self.disc_btn = Choice(base=LIGHT, fg=BLACK, text=S.TX_DISCONNECT, size_hint_y=None,
                               height=dp(40))
        self.disc_btn.bind(on_release=lambda *_: self.on_disconnect())
        box.add_widget(self.disc_btn)

        # ---- copy values for another wallet
        box.add_widget(Card(S.TX_NOT_SENDER, bg=BLACK, fg=WHITE))
        box.add_widget(label(S.TX_COPY_ROWS_HEAD, size_hint_y=None, height=dp(30)))
        data = t["data"]
        box.add_widget(self.copy_row(S.TX_TO, DSOS_ADDR, short(DSOS_ADDR)))
        if t["value_wei"]:
            box.add_widget(self.copy_row(S.TX_VALUE, t["value_eth"],
                                         S.TX_VALUE_SHOWN.format(eth=t["value_eth"])))
        if not t.get("plain"):
            box.add_widget(self.copy_row(S.TX_DATA, data, f"{data[:22]}...{data[-8:]}"))
            box.add_widget(label(S.TX_ETHERSCAN_HEAD.format(fn=fn_name),
                                 size_hint_y=None, height=dp(30)))
        else:
            box.add_widget(label(S.TX_NO_ETHERSCAN_FN, size_hint_y=None, height=dp(30)))
        for title, value, shown in rows:
            box.add_widget(self.copy_row(title, value, shown))
        if tip:
            box.add_widget(Card(tip))
        if not t.get("plain"):
            b1 = Choice(base=BLUE, fg=WHITE, text=S.TX_BTN_ETHERSCAN,
                        size_hint_y=None, height=dp(52), bold=True)
            b1.bind(on_release=lambda *_: self.open(ETHERSCAN_WRITE))
            box.add_widget(b1)
        b2 = Choice(base=BLACK, fg=WHITE, text=S.TX_BTN_DAPP,
                    size_hint_y=None, height=dp(52), bold=True)
        b2.bind(on_release=lambda *_: self.open(DAPP_URL))
        box.add_widget(b2)
        box.add_widget(Card(warn or S.TX_DEFAULT_WARN))

        sv.add_widget(box)
        col.add_widget(sv)
        self.add_widget(col)

        self.refresh_buttons()
        self.start_dry_run()

    # ------------------------------------------------------------ helpers
    def _from_address(self):
        a = ""
        try:
            a = self.app.addr.text.strip()
        except Exception:  # noqa: BLE001
            pass
        return a if tx.valid_address(a) else ""

    def close(self):
        self.alive = False
        if self.wallet:
            self.wallet.set_listener(None)
        self.app.close_top()

    def copy_row(self, title, value, shown):
        row = Panel(size_hint_y=None, height=dp(68), spacing=dp(8))
        row.add_widget(label(f"[size=12sp]{escape_markup(title)}[/size]\n[b]{escape_markup(shown)}[/b]"))
        btn = Button(text=S.BTN_COPY, size_hint=(None, None), size=(dp(72), dp(40)),
                     pos_hint={"center_y": 0.5}, background_normal="",
                     background_color=BLUE, color=WHITE, bold=True)
        btn.bind(on_release=lambda *_: self.copy(title, value))
        row.add_widget(btn)
        return row

    def copy(self, title, value):
        ok = util.copy_text(value)
        self.status.text = S.TX_COPIED.format(title=title) if ok else S.TX_COPY_FAILED

    def open(self, url):
        if not util.open_url(url):
            self.status.text = S.TX_OPEN_FAILED

    def refresh_buttons(self):
        w = self.wallet
        if self.busy:
            self.send_btn.text = S.TX_BTN_WALLET_BUSY
        elif self.sim_ok is False:
            self.send_btn.text = S.TX_BTN_WALLET_BLOCKED
        else:
            self.send_btn.text = S.TX_BTN_WALLET
        self.send_btn.set_enabled(not self.busy and not self.sent and self.sim_ok is not False)
        if self.sign_btn:
            self.sign_btn.text = S.TX_LEDGER_ON if self.sign_on else S.TX_LEDGER_OFF
            self.sign_btn.set_selected(self.sign_on)
            self.sign_btn.set_enabled(not self.busy and not self.sent)
        self.disc_btn.set_enabled(bool(w and w.connected) and not self.busy)

    def toggle_sign(self):
        if self.busy or self.sent:
            return
        self.sign_on = not self.sign_on
        self.refresh_buttons()

    def show(self, text, view_hash=None):
        """Replace the wallet message area."""
        self.out_box.clear_widgets()
        if text:
            self.out_box.add_widget(Card(text))
        if view_hash:
            b = Choice(base=BLACK, fg=WHITE, text=S.TX_BTN_VIEW, size_hint_y=None, height=dp(48),
                       bold=True)
            b.bind(on_release=lambda *_: self.open(ETHERSCAN_TX + view_hash))
            self.out_box.add_widget(b)

    # ------------------------------------------------------------ dry run (eth_call)
    def start_dry_run(self):
        if not self.frm:
            self.sim_card.lbl.text = S.SIM_NEEDS_WALLET
            return
        t = self.t0
        threading.Thread(target=self._dry_worker,
                         args=(t["to"], t["data"], t["value_wei"]), daemon=True).start()

    def _dry_worker(self, to, data, value):
        try:
            ok, reason = core.Chain("").simulate(self.frm, to, data, value)
            Clock.schedule_once(lambda dt: self.dry_done(ok, reason, None))
        except Exception as e:  # noqa: BLE001
            m = str(e)
            Clock.schedule_once(lambda dt: self.dry_done(None, "", m))

    def dry_done(self, ok, reason, err):
        if not self.alive:
            return
        self.sim_ok = ok
        if ok is None:
            self.sim_card.lbl.text = S.SIM_UNKNOWN.format(error=escape_markup(err or ""))
        elif ok:
            self.sim_card.lbl.text = S.SIM_OK
        else:
            self.sim_card.lbl.text = S.SIM_FAIL.format(reason=escape_markup(self.reason_text(reason)))
        self.refresh_buttons()

    @staticmethod
    def reason_text(reason):
        txt = S.REVERT_TEXT.get(reason)
        if txt:
            return txt
        return S.REVERT_UNKNOWN.format(name=reason)

    # ------------------------------------------------------------ send with wallet
    def on_wallet_send(self):
        if self.busy or self.sent or self.sim_ok is False:
            return
        w = self.wallet
        why = w.unavailable() if w else S.TX_WALLET_UNAVAILABLE
        if why:
            self.show(why)
            return
        if not self.frm:
            self.show(S.SIM_NEEDS_WALLET)
            return
        self.busy = True
        self.refresh_buttons()
        w.set_listener(lambda text: self.alive and self.show(text))
        if w.connected:
            self.after_connect()
        else:
            self.show(S.TX_CONNECTING)
            w.connect(self.after_connect, self.fail_final)

    def after_connect(self):
        if not self.alive:
            return
        w = self.wallet
        got = (w.accounts[0] if w.accounts else "").lower()
        if got != self.frm.lower():
            self.fail_final(S.TX_WRONG_ACCOUNT.format(got=short(got) or "?", want=short(self.frm)))
            return
        self.show(S.TX_CONNECTED.format(wallet=w.label(), addr=short(got)))
        if self.sign_on and self.t0.get("rec"):
            self.ask_signature()
        else:
            self.ask_send(self.t0)

    def ask_signature(self):
        rec = self.t0["rec"]
        w = self.wallet
        typed = tx.ledger_typed_data(self.frm, rec["intended_to"], rec["payload_hash"], "")
        self.show(S.TX_SIGNING.format(wallet=w.label()))
        w.request("eth_signTypedData_v4", [self.frm, typed], self.got_signature, self.fail)

    def got_signature(self, result):
        if not self.alive:
            return
        try:
            sig = bytes.fromhex(str(result)[2:])
            if len(sig) != 65:
                raise ValueError("signature length")
        except Exception:  # noqa: BLE001
            self.fail_final(S.TX_ERROR.format(error="bad signature"))
            return
        threading.Thread(target=self._verify_worker, args=(sig,), daemon=True).start()

    def _verify_worker(self, sig):
        rec = self.t0["rec"]
        to, data = tx.ledger_check_call(self.frm, rec["intended_to"], rec["payload_hash"], sig, "")
        try:
            ok, reason = core.Chain("").simulate(self.frm, to, data, 0)
        except Exception:  # noqa: BLE001
            ok, reason = True, ""          # no node reachable: a bad record is only skipped, not harmful
        Clock.schedule_once(lambda dt: self.verified(sig, ok, reason))

    def verified(self, sig, ok, reason):
        if not self.alive:
            return
        if not ok:
            self.fail_final(S.TX_SIGN_BAD.format(reason=self.reason_text(reason)))
            return
        self.ask_send(self.t0["rec"]["make"](sig, ""))

    def ask_send(self, t):
        w = self.wallet
        params = [{"from": self.frm, "to": t["to"], "value": hex(int(t["value_wei"])),
                   "data": t["data"]}]
        self.show(S.TX_SENDING.format(wallet=w.label()))
        w.request("eth_sendTransaction", params, self.sent_ok, self.fail)

    def sent_ok(self, result):
        if not self.alive:
            return
        h = str(result)
        self.busy = False
        self.sent = True
        self.show(S.TX_SENT.format(hash=short(h)) + "\n" + S.TX_SENT_NOTE, view_hash=h)
        self.refresh_buttons()
        Clock.schedule_once(lambda dt: self.app.load(), 45)   # refresh the data once it is mined

    def is_rejection(self, text, code):
        low = str(text).lower()
        return code in REJECT_CODES or "reject" in low or "denied" in low or "cancel" in low

    def fail(self, text, code=None):
        """A raw error from the wallet (request failed or was declined)."""
        if not self.alive:
            return
        self.busy = False
        if self.is_rejection(text, code):
            self.show(S.TX_REJECTED)
        else:
            self.show(S.TX_ERROR.format(error=escape_markup(str(text))))
        self.refresh_buttons()

    def fail_final(self, text, code=None):
        """An error whose text is already the message to show."""
        if not self.alive:
            return
        self.busy = False
        if self.is_rejection(text, code):
            self.show(S.TX_REJECTED)
        else:
            self.show(escape_markup(str(text)))
        self.refresh_buttons()

    def on_disconnect(self):
        if self.wallet and self.wallet.connected and not self.busy:
            self.wallet.disconnect()
            self.show(S.TX_DISCONNECTED)
            self.refresh_buttons()
