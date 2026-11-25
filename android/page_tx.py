"""Transaction page: dry run, "Send with wallet", and copy buttons for any other wallet."""
import threading
import time

from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.utils import escape_markup

import core
import strings as S
import tx
import util
from design import FONT_HELPER, FONT_TITLE
from theme import (BLACK, BLUE, DAPP_URL, DARK_GREEN, DSOS_ADDR, ETHERSCAN_ADDR, ETHERSCAN_TX,
                   ETHERSCAN_WRITE, LEDGER_ADDR, LIGHT, LIGHT_GREEN, RED, WHITE, short)
from widgets import home_btn, PullScroll, Card, Choice, Overlay, Panel, IconBtn, Tap, label

POLL_SECONDS = 4
POLL_TRIES = 45          # 45 x 4 s = 3 minutes
REQUEST_TIMEOUT = 120    # seconds to wait for the wallet to answer one request

REJECT_CODES = (4001, 5000)
REJECT_WORDS = ("user rejected", "rejected by user", "user denied", "denied by user",
                "request rejected", "user cancel", "cancelled by user", "canceled by user")


class TxScreen(Overlay):
    """Shows a ready transaction. The wallet app signs and sends it; the app holds no keys."""

    def __init__(self, app, t, summary, fn_name, rows, tip="", warn="", **kw):
        super().__init__(**kw)
        self.app = app
        self.t0 = t
        self.alive = True
        self.busy = False
        self.sent = False
        self.sign_on = False               # "Ledger record after success"
        self.rec_busy = False
        self.rec_hash = ""
        self.sim_ok = None                 # None = unknown, True = passes, False = would fail
        self.log = []                      # step log: what was asked, what the wallet answered
        self._open_reqs = set()
        self._req_no = 0
        self.frm = self._from_address()
        self.wallet = getattr(app, "wallet", None)

        col = BoxLayout(orientation="vertical")
        head = BoxLayout(size_hint_y=None, height=dp(64), padding=[dp(14), dp(8)], spacing=dp(6))
        back = IconBtn(icon="back", bg=WHITE, color=BLACK,
                        size_hint=(None, 1), width=dp(44))
        back.bind(on_release=lambda *_: self.close())
        head.add_widget(home_btn(app, before=self.close))
        head.add_widget(back)
        head.add_widget(label(S.TX_TITLE, font_size=FONT_TITLE))
        col.add_widget(head)

        self.status = label("", size_hint_y=None, height=dp(24), font_size=FONT_HELPER, bold=True,
                            padding=(dp(14), 0))
        col.add_widget(self.status)

        sv = PullScroll(on_pull=lambda: None)      # no reload on this page
        box = BoxLayout(orientation="vertical", spacing=dp(6), size_hint_y=None,
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
        self.sign_btn = None          # no "ledger record after success" button or help card
        self.sign_on = False
        # message areas + disconnect: an empty area is taken out, so it leaves no gap
        self.stack = BoxLayout(orientation="vertical", spacing=dp(6), size_hint_y=None)
        self.stack.bind(minimum_height=self.stack.setter("height"))
        self.out_box = self._msg_box()
        self.rec_box = self._msg_box()
        self.log_box = self._msg_box()
        self.disc_btn = Choice(base=LIGHT, fg=BLACK, text=S.TX_DISCONNECT, size_hint_y=None,
                               height=dp(40))
        self.disc_btn.bind(on_release=lambda *_: self.on_disconnect())
        box.add_widget(self.stack)
        self._sync_stack()

        # ---- copy values for another wallet
        box.add_widget(Card(S.TX_NOT_SENDER, bg=BLACK, fg=WHITE))
        box.add_widget(label(S.TX_COPY_ROWS_HEAD, size_hint_y=None, height=dp(24)))
        data = t["data"]
        box.add_widget(self.copy_row(S.TX_TO_LEDGER if t.get("ledger") else S.TX_TO, t["to"], short(t["to"])))
        if t["value_wei"]:
            box.add_widget(self.copy_row(S.TX_VALUE, t["value_eth"],
                                         S.TX_VALUE_SHOWN.format(eth=t["value_eth"])))
        if not t.get("plain"):
            box.add_widget(self.copy_row(S.TX_DATA, data, f"{data[:22]}...{data[-8:]}"))
            box.add_widget(label(S.TX_ETHERSCAN_HEAD.format(fn=fn_name),
                                 size_hint_y=None, height=dp(24)))
        else:
            box.add_widget(label(S.TX_NO_ETHERSCAN_FN, size_hint_y=None, height=dp(24)))
        for title, value, shown in rows:
            box.add_widget(self.copy_row(title, value, shown))
        if tip:
            box.add_widget(Card(tip))
        if not t.get("plain"):
            b1 = Choice(base=BLUE, fg=WHITE, text=S.TX_BTN_ETHERSCAN,
                        size_hint_y=None, height=dp(52), bold=True)
            b1.bind(on_release=lambda *_: self.open(ETHERSCAN_ADDR + LEDGER_ADDR + "#writeContract"
                                                if t.get("ledger") else ETHERSCAN_WRITE))
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

    def _msg_box(self):
        b = BoxLayout(orientation="vertical", spacing=dp(6), size_hint_y=None)
        b.bind(minimum_height=b.setter("height"))
        b.bind(children=lambda *_: self._sync_stack())
        return b

    def _sync_stack(self):
        want = [b for b in (self.out_box, self.rec_box, self.log_box) if b.children] + [self.disc_btn]
        if list(reversed(self.stack.children)) != want:
            self.stack.clear_widgets()
            for w in want:
                self.stack.add_widget(w)

    def close(self):
        self.alive = False
        if self.wallet:
            self.wallet.set_listener(None)
        self.app.close_top()

    def copy_row(self, title, value, shown):
        row = Panel(size_hint_y=None, height=dp(56), spacing=dp(8))
        row.add_widget(label(f"[size=14sp][b]{escape_markup(title)}[/b][/size]\n[b]{escape_markup(shown)}[/b]"))
        btn = Choice(base=BLUE, fg=WHITE, text=S.BTN_COPY, size_hint=(None, None),
                     size=(dp(72), dp(36)), pos_hint={"center_y": 0.5}, bold=True)
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

    def show(self, text, view_hash=None, bg=WHITE, fg=BLACK, copy_text=None, actions=()):
        """Replace the wallet message area. `view_hash` adds a tappable hash and a button;
        `copy_text` adds a Copy button for an error text."""
        self._fill(self.out_box, text, view_hash, bg, fg, copy_text, actions)

    def rec_show(self, text, view_hash=None, bg=WHITE, fg=BLACK, copy_text=None, actions=()):
        """Same, for the separate ledger-record area under the dSOS result."""
        self._fill(self.rec_box, text, view_hash, bg, fg, copy_text, actions, head=S.REC_HEAD)

    def _fill(self, box, text, view_hash, bg, fg, copy_text, actions, head=""):
        out_box = box
        out_box.clear_widgets()
        if head:
            out_box.add_widget(label(head, size_hint_y=None, height=dp(28)))
        if text:
            out_box.add_widget(Card(text, bg=bg, fg=fg))
        if view_hash:
            link = Tap(size_hint_y=None, height=dp(34))
            link.add_widget(label(S.TX_HASH_LINK.format(hash=short(view_hash)), font_size="15sp"))
            link.bind(on_release=lambda *_: self.open(ETHERSCAN_TX + view_hash))
            out_box.add_widget(link)
        if copy_text:
            cb = Choice(base=LIGHT, fg=BLACK, text=S.TX_ERR_COPY, size_hint_y=None, height=dp(44),
                        bold=True)
            cb.bind(on_release=lambda *_: self.copy(S.TX_ERR_COPY, copy_text))
            out_box.add_widget(cb)
        for label_text, fn in actions:
            ab = Choice(base=BLACK, fg=WHITE, text=label_text, size_hint_y=None, height=dp(46), bold=True)
            ab.bind(on_release=lambda *_w, f=fn: f())
            out_box.add_widget(ab)
        if view_hash:
            b = Choice(base=BLACK, fg=WHITE, text=S.TX_BTN_VIEW, size_hint_y=None, height=dp(48),
                       bold=True)
            b.bind(on_release=lambda *_: self.open(ETHERSCAN_TX + view_hash))
            out_box.add_widget(b)

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
        self.note("send pressed")
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
        self.ask_send(self.t0)             # the ledger record, if on, follows AFTER success

    # ------------------------------------------------------------ step log and requests
    def note(self, text):
        """Add a line to the Details card (shown under the buttons, with a Copy button)."""
        self.log.append("%s %s" % (time.strftime("%H:%M:%S"), text))
        if not self.alive:
            return
        self.log_box.clear_widgets()
        self.log_box.add_widget(Card(S.TX_LOG_HEAD + "\n" + escape_markup("\n".join(self.log[-16:]))))
        cb = Choice(base=LIGHT, fg=BLACK, text=S.TX_LOG_COPY, size_hint_y=None, height=dp(44), bold=True)
        cb.bind(on_release=lambda *_: self.copy(S.TX_LOG_COPY, "\n".join(self.log)))
        self.log_box.add_widget(cb)

    def request(self, method, params, on_ok, step, on_err=None, on_timeout=None):
        """Ask the wallet. Every reply (also a late one) is handled; after REQUEST_TIMEOUT seconds
        without an answer the screen says which step is waiting and offers Open wallet / Try again."""
        self._req_no += 1
        rid = self._req_no
        self._open_reqs.add(rid)
        self.note("ask %s" % method)

        def ok(result):
            late = rid not in self._open_reqs
            self._open_reqs.discard(rid)
            self.note("%sreply %s" % ("late " if late else "", str(result)[:80]))
            on_ok(result)

        def err(text, code=None):
            late = rid not in self._open_reqs
            self._open_reqs.discard(rid)
            self.note("%serror code=%s text=%s" % ("late " if late else "", code, str(text)[:160]))
            (on_err or self.fail)(text, code)

        self.wallet.request(method, params, ok, err)
        Clock.schedule_once(lambda dt: self._timeout(rid, step, on_timeout), REQUEST_TIMEOUT)

    def _timeout(self, rid, step, on_timeout=None):
        if rid not in self._open_reqs or not self.alive:
            return
        self._open_reqs.discard(rid)
        self.note("no answer after %d s (%s)" % (REQUEST_TIMEOUT, step))
        if on_timeout:
            on_timeout(step)
            return
        self.busy = False
        self.show(S.TX_TIMEOUT.format(step=step, wallet=self.wallet.label()), bg=RED, fg=WHITE,
                  actions=[(S.TX_BTN_OPEN_WALLET, lambda: self.wallet.open_wallet()),
                           (S.TX_BTN_TRY_AGAIN, lambda: self.on_wallet_send())])
        self.refresh_buttons()

    def ask_send(self, t):
        w = self.wallet
        params = [{"from": self.frm, "to": t["to"], "value": hex(int(t["value_wei"])),
                   "data": t["data"]}]
        self.show(S.TX_SENDING.format(wallet=w.label()))
        self.request("eth_sendTransaction", params, self.sent_ok, S.TX_STEP_SEND)

    def sent_ok(self, result):
        h = str(result)
        if not self.alive:                     # screen closed meanwhile: still report the outcome
            threading.Thread(target=self._watch, args=(h,), daemon=True).start()
            return
        self.busy = False
        self.sent = True
        self.show(S.TX_WAITING.format(hash=short(h)), view_hash=h)
        self.refresh_buttons()
        threading.Thread(target=self._watch, args=(h,), daemon=True).start()

    # ------------------------------------------------------------ result: poll the receipt
    def _watch(self, h):
        self._poll(h, self.confirmed)

    def _poll(self, h, done):
        chain = core.Chain(self.app.key.text)
        err = None
        for i in range(POLL_TRIES):
            try:
                rc = chain.receipt(h)
            except Exception as e:  # noqa: BLE001
                rc, err = None, str(e)
            if rc:
                ok = str(rc.get("status", "0x1")) == "0x1"
                block = int(rc.get("blockNumber") or "0x0", 16)
                reason = "" if ok else chain.failure_reason(h, rc)
                Clock.schedule_once(lambda dt: done(h, ok, block, reason))
                return
            time.sleep(POLL_SECONDS)
        Clock.schedule_once(lambda dt: done(h, None, 0, err or ""))

    def confirmed(self, h, ok, block, reason):
        self.note("result %s block=%s reason=%s" % ({True: "ok", False: "reverted", None: "pending"}[ok],
                                                    block, reason))
        if not self.alive:
            if ok is not None:
                self.app.notify_tx(h, ok, block, reason)
            return
        if ok is None:
            self.show(S.TX_PENDING.format(hash=short(h)), view_hash=h)
        elif ok:
            self.show(S.TX_OK.format(block=block, hash=short(h)), view_hash=h,
                      bg=LIGHT_GREEN, fg=DARK_GREEN)
            self.app.reload()
            self.rec_hash = h
            if self.sign_on and self.t0.get("rec"):
                self.rec_begin()
        else:
            txt = S.TX_FAILED.format(reason=escape_markup(reason) if reason else S.TX_FAILED_UNKNOWN,
                                     hash=short(h))
            self.show(txt, view_hash=h, bg=RED, fg=WHITE,
                      copy_text="%s %s" % (reason or S.TX_FAILED_UNKNOWN, h))

    def is_rejection(self, text, code):
        low = str(text).lower()
        return code in REJECT_CODES or any(w in low for w in REJECT_WORDS)

    def fail(self, text, code=None):
        """A raw error from the wallet (request failed or was declined)."""
        if not self.alive:
            return
        self.busy = False
        self.note("failed: code=%s text=%s" % (code, str(text)[:160]))
        if self.is_rejection(text, code):
            self.show(S.TX_REJECTED)
        else:
            self.show(S.TX_ERROR.format(error=escape_markup(str(text))), copy_text=str(text))
        self.refresh_buttons()

    def fail_final(self, text, code=None):
        """An error whose text is already the message to show."""
        if not self.alive:
            return
        self.busy = False
        if self.is_rejection(text, code):
            self.show(S.TX_REJECTED)
        else:
            self.show(escape_markup(str(text)), copy_text=str(text))
        self.refresh_buttons()

    def on_disconnect(self):
        if self.wallet and self.wallet.connected and not self.busy:
            self.wallet.disconnect()
            self.show(S.TX_DISCONNECTED)
            self.refresh_buttons()

    # ------------------------------------------------------------ ledger record: its own transaction
    def rec_actions(self):
        return [(S.BTN_REC_RETRY, lambda: self.rec_begin())]

    def rec_begin(self):
        """After the dSOS transaction succeeded: sign a record carrying its tx hash, then send
        SOS69069.recordSignature as a separate transaction."""
        w = self.wallet
        if self.rec_busy or not self.alive or not w:
            return
        self.rec_busy = True
        self.note("ledger record: start for %s" % self.rec_hash)
        w.set_listener(lambda text: self.alive and self.rec_show(text))
        if w.connected:
            self.rec_sign()
        else:
            self.rec_show(S.TX_CONNECTING)
            w.connect(self.rec_sign, self.rec_fail_final)

    def rec_sign(self):
        if not self.alive:
            return
        rec = self.t0["rec"]
        ph = bytes.fromhex(self.rec_hash[2:])
        typed = tx.ledger_typed_data(self.frm, rec["intended_to"], ph, tx.REC_META)
        self.rec_show(S.REC_SIGNING.format(wallet=self.wallet.label()))
        self.request("eth_signTypedData_v4", [self.frm, typed], self.rec_got_sig, S.TX_STEP_SIGN,
                     on_err=self.rec_fail, on_timeout=self.rec_timeout)

    def rec_got_sig(self, result):
        if not self.alive:
            return
        try:
            sig = bytes.fromhex(str(result)[2:])
            if len(sig) != 65:
                raise ValueError("signature length")
        except Exception:  # noqa: BLE001
            self.rec_fail_final(S.REC_ERROR.format(error="bad signature"))
            return
        threading.Thread(target=self._rec_verify, args=(sig,), daemon=True).start()

    def _rec_call(self, sig):
        rec = self.t0["rec"]
        return tx.ledger_check_call(self.frm, rec["intended_to"], bytes.fromhex(self.rec_hash[2:]),
                                    sig, tx.REC_META)

    def _rec_verify(self, sig):
        to, data = self._rec_call(sig)
        try:
            ok, reason = core.Chain("").simulate(self.frm, to, data, 0)
        except Exception:  # noqa: BLE001
            ok, reason = True, ""          # no node reachable: the chain decides
        Clock.schedule_once(lambda dt: self.rec_verified(sig, ok, reason))

    def rec_verified(self, sig, ok, reason):
        if not self.alive:
            return
        if not ok:
            self.rec_fail_final(S.REC_SIGN_BAD.format(reason=escape_markup(self.reason_text(reason))))
            return
        to, data = self._rec_call(sig)
        params = [{"from": self.frm, "to": to, "value": "0x0", "data": data}]
        self.rec_show(S.REC_SENDING.format(wallet=self.wallet.label()))
        self.request("eth_sendTransaction", params, self.rec_sent, S.TX_STEP_SEND,
                     on_err=self.rec_fail, on_timeout=self.rec_timeout)

    def rec_sent(self, result):
        h = str(result)
        if self.alive:
            self.rec_show(S.REC_WAITING.format(hash=short(h)), view_hash=h)
        threading.Thread(target=self._poll, args=(h, self.rec_confirmed), daemon=True).start()

    def rec_confirmed(self, h, ok, block, reason):
        self.rec_busy = False
        self.note("ledger record result %s block=%s reason=%s" % (
            {True: "ok", False: "reverted", None: "pending"}[ok], block, reason))
        if not self.alive:
            return
        if ok is None:
            self.rec_show(S.REC_PENDING.format(hash=short(h)), view_hash=h)
        elif ok:
            self.rec_show(S.REC_OK.format(block=block, hash=short(h)), view_hash=h,
                          bg=LIGHT_GREEN, fg=DARK_GREEN)
        else:
            why = escape_markup(self.reason_text(reason)) if reason else S.TX_FAILED_UNKNOWN
            self.rec_show(S.REC_FAILED.format(reason=why, hash=short(h)), view_hash=h, bg=RED, fg=WHITE,
                          copy_text="%s %s" % (reason or S.TX_FAILED_UNKNOWN, h), actions=self.rec_actions())

    def rec_fail(self, text, code=None):
        """A raw error from the wallet during the ledger step."""
        self.rec_busy = False
        self.note("ledger record failed: code=%s text=%s" % (code, str(text)[:160]))
        if not self.alive:
            return
        if self.is_rejection(text, code):
            self.rec_show(S.REC_CANCELLED, actions=self.rec_actions())
        else:
            self.rec_show(S.REC_ERROR.format(error=escape_markup(str(text))), copy_text=str(text),
                          actions=self.rec_actions())

    def rec_fail_final(self, text, code=None):
        self.rec_busy = False
        if not self.alive:
            return
        if self.is_rejection(text, code):
            self.rec_show(S.REC_CANCELLED, actions=self.rec_actions())
        else:
            self.rec_show(text if "\n" in str(text) else escape_markup(str(text)), copy_text=str(text),
                          actions=self.rec_actions())

    def rec_timeout(self, step):
        self.rec_busy = False
        if not self.alive:
            return
        self.rec_show(S.REC_TIMEOUT.format(step=step), bg=RED, fg=WHITE,
                      actions=[(S.TX_BTN_OPEN_WALLET, lambda: self.wallet.open_wallet())] + self.rec_actions())
