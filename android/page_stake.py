"""Stake tab: required gate offer, steps, stake and sweep."""
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.label import Label

import core
import strings as S
import tx
from page_tx import TxScreen
from theme import (BLACK, BLUE, BROWN, CREAM, DARK_GREEN, LIGHT_GREEN, PILL_BG, WHITE,
                   short)
from widgets import Card, Check, Choice, Divider, Dot, LockIcon, Panel, Pill, Steps, label


class StakePage:
    def __init__(self, app, b, d):
        self.app = app
        self.d = d
        self.need = d["stake_need_wei"]
        self.sweep_ids = d["sweepable_ids"]
        staked = d["staked"]
        cool_ok = staked and d["block"] >= d["staked_at"] + d["cooldown"]

        # ---- title + status pill
        head = BoxLayout(size_hint_y=None, height=dp(48))
        head.add_widget(label(S.STAKE_TITLE, font_size="30sp"))
        head.add_widget(Pill(
            text=S.STAKE_PILL_STAKED if staked else S.STAKE_PILL_NOT_STAKED,
            bg=PILL_BG if staked else WHITE, color=DARK_GREEN if staked else BLACK, bold=True,
            size_hint=(None, None), size=(dp(120), dp(34)), pos_hint={"center_y": 0.5}))
        b.add_widget(head)

        # ---- card: what staking gives + required amount
        c1 = Panel(orientation="vertical", size_hint_y=None, height=dp(262), spacing=dp(8))
        top = BoxLayout(size_hint_y=None, height=dp(64), spacing=dp(14))
        top.add_widget(LockIcon(pos_hint={"center_y": 0.5}))
        top.add_widget(label(S.STAKE_INTRO, font_size="16sp"))
        c1.add_widget(top)
        c1.add_widget(Divider(color=BLACK))
        c1.add_widget(label(S.STAKE_REQUIRED_BOX.format(eth=core.eth(self.need)),
                            size_hint_y=None, height=dp(88)))
        c1.add_widget(label(S.STAKE_REQUIRED_NOTE.format(n=self.need // core.UNIT),
                            size_hint_y=None, height=dp(44), valign="top", font_size="13sp"))
        b.add_widget(c1)

        # ---- numbered steps
        steps = Steps(size_hint_y=None, height=dp(3 * 70))
        done = [staked, staked, cool_ok]
        active = 2 if staked and not cool_ok else (0 if not staked else -1)
        for i, (title, sub) in enumerate(S.STAKE_STEPS):
            row = BoxLayout(size_hint_y=None, height=dp(70), spacing=dp(14))
            left = FloatLayout(size_hint_x=None, width=dp(50))
            if done[i]:
                bg, fg = DARK_GREEN, WHITE
            elif i == active:
                bg, fg = BLUE, WHITE
            else:
                bg, fg = LIGHT_GREEN, BLACK
            left.add_widget(Dot(text=str(i + 1), bg=bg, color=fg,
                                pos_hint={"center_x": 0.5, "center_y": 0.5}))
            row.add_widget(left)
            row.add_widget(label(S.STAKE_STEP_TEXT.format(title=title, sub=sub)))
            steps.add_widget(row)
        steps.update_line()
        b.add_widget(steps)

        # ---- one-way donation warning
        b.add_widget(Card(S.STAKE_DONATION_WARN, bg=CREAM, fg=BROWN))

        # ---- confirmation tick
        crow = BoxLayout(size_hint_y=None, height=dp(52), spacing=dp(14))
        self.check = Check(on_change=lambda _a: self.refresh(), pos_hint={"center_y": 0.5})
        crow.add_widget(self.check)
        crow.add_widget(label(S.STAKE_CHECK, font_size="15sp"))
        b.add_widget(crow)

        # ---- buttons
        btns = BoxLayout(size_hint_y=None, height=dp(72), spacing=dp(12))
        self.stake_btn = Choice(base=BLUE, sel=BLUE, fg=WHITE, sel_fg=WHITE, bold=True,
                                font_size="18sp", size_hint_x=0.64)
        self.stake_btn.bind(on_release=lambda *_: self.on_stake())
        self.sweep_btn = Choice(base=LIGHT_GREEN, fg=BLACK, bold=True, font_size="17sp",
                                text=S.STAKE_SWEEP)
        self.sweep_btn.bind(on_release=lambda *_: self.on_sweep())
        btns.add_widget(self.stake_btn)
        btns.add_widget(self.sweep_btn)
        b.add_widget(btns)

        self.note = Label(text="", color=BLACK, font_size="13sp", size_hint_y=None,
                          height=dp(30), halign="center", valign="middle")
        self.note.bind(size=lambda i, s: setattr(i, "text_size", s))
        b.add_widget(self.note)
        self.refresh()

    def refresh(self):
        staked = self.d["staked"]
        self.stake_btn.text = (S.STAKE_BTN_DONE if staked
                               else S.STAKE_BTN.format(eth=core.eth(self.need)))
        self.stake_btn.set_enabled(not staked and self.check.active)
        n = len(self.sweep_ids)
        self.sweep_btn.set_enabled(n > 0)
        self.note.text = (S.STAKE_SWEEP_READY.format(n=n, s="" if n == 1 else "s")
                          if n else S.STAKE_SWEEP_NONE)

    # ---- transactions (built, never sent)
    def on_stake(self):
        if self.d["staked"] or not self.check.active:
            return
        holder = self.d["address"]
        try:
            t = tx.stake_tx(holder, self.need)
        except Exception as e:  # noqa: BLE001
            self.note.text = str(e)
            return
        p = t["params"]
        R = S.STAKE_ROWS
        rows = [(R["payable"], t["value_eth"], t["value_eth"]),
                (R["to"], p["to"], short(p["to"])),
                (R["delay"], p["delayBlocks"], p["delayBlocks"]),
                (R["pin"], p["pinCommitment_"], short(p["pinCommitment_"])),
                (R["hash"], p["payloadHash"], short(p["payloadHash"])),
                (R["sig"], "0x", "0x")]
        summary = S.STAKE_SUMMARY.format(eth=t["value_eth"], n=self.need // core.UNIT,
                                         holder=short(holder))
        self.app.safe_overlay(lambda: TxScreen(self.app, t, summary, S.STAKE_FN, rows,
                                       S.STAKE_TIP, S.STAKE_WARN))

    def on_sweep(self):
        if not self.sweep_ids:
            return
        oid = self.sweep_ids[0]
        t = tx.sweep_offer_tx(oid)
        summary = S.SWEEP_SUMMARY.format(id=oid, pos=1, total=len(self.sweep_ids))
        rows = [(S.SWEEP_ROWS["id"], str(oid), str(oid))]
        self.app.safe_overlay(lambda: TxScreen(self.app, t, summary, S.SWEEP_FN, rows,
                                       S.SWEEP_TIP, S.SWEEP_WARN))


def build(app, b, d):
    StakePage(app, b, d)
