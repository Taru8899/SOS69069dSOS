"""Sell records page (A / B offers): see an escrow, write your records to the SOS ledger, confirm
them in dSOS. Builds the data; the wallet app signs and sends. The app holds no keys."""
import threading

from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.utils import escape_markup

import core
import sell
import strings as S
import tx
from design import FONT_TITLE
from page_tx import TxScreen
from theme import BLACK, BLUE, LEDGER_ADDR, LIGHT, WHITE, left_text, short
from widgets import Card, Choice, IconBtn, Overlay, PullScroll, label, make_input, text_label


class RecordsTxScreen(TxScreen):
    """A TxScreen whose transaction does not exist yet: the wallet first signs every record
    (eth_signTypedData_v4), then the batch is checked against the ledger and sent."""

    def __init__(self, app, plan, summary, rows, tip="", warn="", **kw):
        self.plan = plan                   # {"id", "donor", "hashes": [32 raw bytes, ...]}
        self.sigs = []
        self.final = None
        placeholder = {"to": LEDGER_ADDR.lower(), "value_wei": 0, "value_eth": "0", "data": "0x",
                       "params": {}, "plain": True, "ledger": True}
        super().__init__(app, placeholder, summary, "recordSignatureOne", rows, tip, warn, **kw)

    def start_dry_run(self):
        if not self.frm:
            self.sim_card.lbl.text = S.SIM_NEEDS_WALLET
            return
        self.sim_card.lbl.text = S.SELL_SIM_LATER.format(n=len(self.plan["hashes"]))

    # the base class calls ask_send(t0) once the wallet is connected: sign first, send later
    def ask_send(self, t):
        if self.final is not None:
            super().ask_send(self.final)
            return
        self.sign_next()

    def sign_next(self):
        if not self.alive:
            return
        n, i = len(self.plan["hashes"]), len(self.sigs)
        if i >= n:
            self.signed()
            return
        typed = tx.ledger_typed_data(self.frm, self.plan["donor"], self.plan["hashes"][i], "")
        self.show(S.SELL_SIGNING.format(i=i + 1, n=n, wallet=self.wallet.label()))
        self.sign_typed(typed, ("eth_signTypedData_v4", "eth_signTypedData_v3"))

    @staticmethod
    def _unsupported(text, code):
        """True when the wallet says it does not offer this signing method."""
        t = (text or "").lower()
        return code == -32601 or any(k in t for k in (
            "not exist", "not available", "method not found", "not supported", "unsupported",
            "not allowed", "invalid method"))

    def sign_typed(self, typed, methods):
        """Ask for a typed-data signature; when the wallet refuses the method, try the next one.
        (The record has no arrays, so v3 signs exactly the same message as v4.)"""
        method, rest = methods[0], methods[1:]

        def on_err(text, code=None):
            if rest and self._unsupported(text, code):
                self.note("%s refused, trying %s" % (method, rest[0]))
                self.sign_typed(typed, rest)
            elif self._unsupported(text, code):
                self.fail_final(S.SELL_NO_TYPED_SIGN, code)
            else:
                self.fail(text, code)
        self.request(method, [self.frm, typed], self.got_sig, S.TX_STEP_SIGN, on_err=on_err)

    def got_sig(self, result):
        if not self.alive:
            return
        try:
            sig = bytes.fromhex(str(result)[2:])
            if len(sig) != 65:
                raise ValueError("signature length")
        except Exception:  # noqa: BLE001
            self.fail("bad signature")
            return
        self.sigs.append(sig)
        self.sign_next()

    def signed(self):
        n = len(self.sigs)
        self.show(S.SELL_SIGNED.format(n=n))
        t = tx.ledger_batch_tx(self.frm, self.plan["donor"], self.plan["hashes"], self.sigs)
        threading.Thread(target=self._check, args=(t,), daemon=True).start()

    def _check(self, t):
        try:
            ok, reason = core.Chain("").simulate(self.frm, t["to"], t["data"], 0)
        except Exception:  # noqa: BLE001
            ok, reason = True, ""              # no node reachable: the chain decides
        Clock.schedule_once(lambda dt: self.checked(t, ok, reason))

    def checked(self, t, ok, reason):
        if not self.alive:
            return
        if not ok:
            self.busy = False
            self.sigs = []                     # signatures that the ledger refused are not reused
            self.show(S.SELL_SIGN_BAD.format(reason=escape_markup(self.reason_text(reason))),
                      bg=BLACK, fg=WHITE)
            self.refresh_buttons()
            return
        self.final = t
        self.t0 = t
        super().ask_send(t)

    def confirmed(self, h, ok, block, reason):
        super().confirmed(h, ok, block, reason)
        if ok and self.alive:
            self.status.text = S.SELL_WROTE_NEXT


class SellScreen(Overlay):
    def __init__(self, app, sale_id=None, **kw):
        super().__init__(**kw)
        self.app = app
        self.d = app.data
        self.me = self.d["address"].strip()
        self.sale = None
        self.state = None
        self.block = self.d.get("block", 0)
        self.alive = True

        col = BoxLayout(orientation="vertical")
        head = BoxLayout(size_hint_y=None, height=dp(72), padding=[dp(14), dp(10)], spacing=dp(14))
        back = IconBtn(icon="back", bg=WHITE, color=BLACK, size_hint=(None, 1), width=dp(56))
        back.bind(on_release=lambda *_: self.close())
        head.add_widget(back)
        head.add_widget(label(S.SELL_TITLE, font_size=FONT_TITLE))
        col.add_widget(head)

        sv = PullScroll()
        form = BoxLayout(orientation="vertical", spacing=dp(8), size_hint_y=None,
                         padding=[dp(14), 0, dp(14), dp(20)])
        form.bind(minimum_height=form.setter("height"))
        self.form = form
        self.intro = Card(S.SELL_INTRO)

        row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(6))
        self.id_in = make_input(S.HINT_SELL_ID, str(sale_id) if sale_id else "", filt="int")
        go = Choice(base=BLUE, fg=WHITE, text=S.BTN_SELL_LOAD, bold=True, size_hint=(None, 1), width=dp(90))
        go.bind(on_release=lambda *_: self.load())
        row.add_widget(self.id_in)
        row.add_widget(go)
        self.row = row

        # message / offer info / open offers: an empty one is taken out, so it leaves no gap
        self.msg = text_label("", font_size="13sp")
        self.msg.bind(text=lambda *_: self._sync())
        self.info = self._box()
        self.open_box = self._box()
        self._sync()

        sv.add_widget(form)
        col.add_widget(sv)
        self.add_widget(col)
        self.k_in = self.n_in = None
        self.load_open()
        if sale_id:
            self.load()

    def _box(self):
        b = BoxLayout(orientation="vertical", spacing=dp(8), size_hint_y=None)
        b.bind(minimum_height=b.setter("height"))
        b.bind(children=lambda *_: self._sync())
        return b

    def _sync(self):
        want = [self.intro, self.row]
        if self.msg.text:
            want.append(self.msg)
        want += [b for b in (self.info, self.open_box) if b.children]
        if list(reversed(self.form.children)) != want:
            self.form.clear_widgets()
            for w in want:
                self.form.add_widget(w)

    def close(self):
        self.alive = False
        self.app.close_top()

    def chain(self):
        return core.Chain(self.app.key.text)

    # ------------------------------------------------------------ open offers list
    def load_open(self):
        self.open_box.clear_widgets()
        self.open_box.add_widget(label(S.SELL_OPEN_LOADING, size_hint_y=None, height=dp(28)))

        def work():
            try:
                found = sell.open_sales(self.chain(), self.block)
                err = ""
            except Exception as e:  # noqa: BLE001
                found, err = [], str(e) or e.__class__.__name__
            Clock.schedule_once(lambda dt: self.open_loaded(found, err))
        threading.Thread(target=work, daemon=True).start()

    def open_loaded(self, found, err):
        if not self.alive:
            return
        b = self.open_box
        b.clear_widgets()
        b.add_widget(label(S.SELL_OPEN_TITLE, size_hint_y=None, height=dp(28)))
        if err:
            b.add_widget(Card(S.SELL_ERROR.format(error=escape_markup(err))))
        elif not found:
            b.add_widget(label(S.SELL_OPEN_NONE, size_hint_y=None, height=dp(60), valign="top",
                               font_size="13sp"))
        for s in found:
            btn = Choice(base=WHITE, size_hint_y=None, height=dp(60), halign="left", padding_x=dp(14),
                         font_size="13sp",
                         text=S.SELL_OPEN_ROW.format(id=s["id"], kind=s["kind"], per=s["per_record"],
                                                     records=s["records_left"],
                                                     time=left_text(s["sweepable_at"] - self.block)))
            btn.bind(size=lambda i, sz: setattr(i, "text_size", (sz[0] - dp(28), sz[1])))
            btn.bind(on_release=lambda _w, i=s["id"]: self.pick(i))
            b.add_widget(btn)

    def pick(self, sale_id):
        self.id_in.text = str(sale_id)
        self.load()

    # ------------------------------------------------------------ one offer
    def load(self):
        t = self.id_in.text.strip()
        if not t.isdigit() or int(t) < 1:
            self.msg.text = S.SELL_BAD_ID
            return
        sid = int(t)
        self.msg.text = S.SELL_LOADING.format(id=sid)
        self.info.clear_widgets()

        def work():
            try:
                ch = self.chain()
                blk = ch.block()
                sale = sell.load_sale(ch, sid)
                st = sell.seller_state(ch, sale, self.me) if sale else None
                res = (blk, sale, st, "")
            except Exception as e:  # noqa: BLE001
                res = (0, None, None, str(e) or e.__class__.__name__)
            Clock.schedule_once(lambda dt: self.loaded(sid, *res))
        threading.Thread(target=work, daemon=True).start()

    def loaded(self, sid, blk, sale, st, err):
        if not self.alive:
            return
        if err:
            self.msg.text = S.SELL_ERROR.format(error=escape_markup(err))
            return
        if blk:
            self.block = blk
        if sale is None:
            self.msg.text = S.SELL_NOT_SALE
            return
        self.msg.text = ""
        self.sale, self.state = sale, st
        self.render_info()

    def render_info(self):
        s, st = self.sale, self.state
        b = self.info
        b.clear_widgets()
        ok, why = sell.can_sell(s, self.me, self.block)
        left = s["sweepable_at"] - self.block
        named = S.SELL_INFO_NAMED.format(target=short(s["target"])) if s["kind"] == "B" else ""
        b.add_widget(Card(S.SELL_INFO.format(
            id=s["id"], kind=s["kind"], donor=short(s["donor"]), named=named, per=s["per_record"],
            records=s["records_left"], slices=s["slices_left"], block=s["sweepable_at"],
            time=left_text(left),
            state=S.SELL_STATE_OPEN if s["active"] and left > 0 else S.SELL_STATE_CLOSED)))
        capped = S.SELL_MINE_CAPPED.format(n=st["scanned"]) if s["records_left"] > st["scanned"] else ""
        earned = S.SELL_EARNED_ID.format(id=st["earned"]) if st["earned"] else S.SELL_EARNED_NONE
        b.add_widget(Card(S.SELL_MINE.format(nxt=st["next"], ready=st["ready"], capped=capped, earned=earned)))

        if not ok:
            dead = why == "named" and s["kind"] == "B" and s["target"].lower() == tx.DEAD.lower()
            b.add_widget(Card(S.SELL_WHY_DEAD if dead else S.SELL_WHY[why], bg=BLACK, fg=WHITE))
        need = max(0, s["records_left"] - st["ready"])
        if ok:
            b.add_widget(label(S.SELL_HOW_MANY, size_hint_y=None, height=dp(24)))
            self.k_in = make_input(S.HINT_SELL_K.format(max=tx.SELL_BATCH_MAX),
                                   str(max(1, min(need, tx.SELL_BATCH_MAX))), filt="int")
            b.add_widget(self.k_in)
            w = Choice(base=BLUE, fg=WHITE, bold=True, size_hint_y=None, height=dp(52),
                       text=S.BTN_SELL_WRITE_NONE)
            w.bind(on_release=lambda *_: self.on_write())
            b.add_widget(w)
            self.n_in = make_input(S.HINT_SELL_N, str(max(1, st["ready"])), filt="int")
            b.add_widget(self.n_in)
            sy = Choice(base=LIGHT, fg=BLACK, bold=True, size_hint_y=None, height=dp(52),
                        text=S.BTN_SELL_SYNC_NONE)
            sy.bind(on_release=lambda *_: self.on_sync())
            b.add_widget(sy)
        if left <= 0 and s["active"]:
            sw = Choice(base=LIGHT, fg=BLACK, bold=True, size_hint_y=None, height=dp(52),
                        text=S.BTN_SELL_SWEEP)
            sw.bind(on_release=lambda *_: self.on_sweep())
            b.add_widget(sw)
        rl = Choice(base=WHITE, bold=True, size_hint_y=None, height=dp(44), text=S.BTN_SELL_LOAD)
        rl.bind(on_release=lambda *_: self.load())
        b.add_widget(rl)

    # ------------------------------------------------------------ transactions (built, never sent)
    def _int(self, field):
        t = field.text.strip() if field is not None else ""
        return int(t) if t.isdigit() else 0

    def on_write(self):
        s, st = self.sale, self.state
        need = max(0, s["records_left"] - st["ready"])
        if need < 1:
            self.msg.text = S.SELL_ERR_NOTHING_WRITE
            return
        k = min(self._int(self.k_in), tx.SELL_BATCH_MAX, need)
        if k < 1:
            self.msg.text = S.SELL_ERR_K
            return
        self.msg.text = S.SELL_PLANNING
        start = st["next"] + st["ready"]

        def work():
            try:
                hashes = sell.record_hashes(self.chain(), s["id"], self.me, start, k)
                err = ""
            except Exception as e:  # noqa: BLE001
                hashes, err = [], str(e) or e.__class__.__name__
            Clock.schedule_once(lambda dt: self.write_ready(hashes, err))
        threading.Thread(target=work, daemon=True).start()

    def write_ready(self, hashes, err):
        if not self.alive:
            return
        if err:
            self.msg.text = S.SELL_ERROR.format(error=escape_markup(err))
            return
        self.msg.text = ""
        s = self.sale
        plan = {"id": s["id"], "donor": s["donor"], "hashes": hashes}
        n = len(hashes)
        summary = S.SELL_WRITE_SUMMARY.format(n=n, id=s["id"], donor=short(s["donor"]))
        R = S.SELL_WRITE_ROWS
        rows = [(R["signer"], self.me, short(self.me)), (R["to"], s["donor"], short(s["donor"])),
                (R["n"], str(n), str(n))]
        self.app.open_overlay(RecordsTxScreen(self.app, plan, summary, rows, S.SELL_WRITE_TIP,
                                              S.SELL_WRITE_WARN))

    def on_sync(self):
        s, st = self.sale, self.state
        n = self._int(self.n_in)
        if n < 1 or n > st["ready"]:
            self.msg.text = S.SELL_ERR_N
            return
        try:
            t = tx.sync_records_tx(s["id"], n, nonce=self.d["redeem_nonce"])
        except Exception as e:  # noqa: BLE001
            self.msg.text = str(e)
            return
        p, R = t["params"], S.SYNC_RECORDS_ROWS
        rows = [(R["id"], p["id"], p["id"]), (R["n"], p["n"], p["n"]),
                (R["nonce"], p["expectedNonce"], p["expectedNonce"])]
        summary = S.SYNC_RECORDS_SUMMARY.format(n=n, id=s["id"], per=s["per_record"])
        self.app.open_overlay(TxScreen(self.app, t, summary, S.SYNC_RECORDS_FN, rows,
                                       S.SYNC_RECORDS_TIP, S.SYNC_RECORDS_WARN))

    def on_sweep(self):
        s = self.sale
        t = tx.sweep_offer_tx(s["id"], nonce=self.d["redeem_nonce"])
        rows = [(S.SWEEP_ROWS["id"], str(s["id"]), str(s["id"])),
                (S.SWEEP_ROWS["nonce"], t["params"]["expectedNonce"], t["params"]["expectedNonce"])]
        self.app.open_overlay(TxScreen(self.app, t, S.OD_SWEEP_SUMMARY.format(id=s["id"]), S.SWEEP_FN, rows,
                                       S.SWEEP_TIP, S.SWEEP_WARN))
