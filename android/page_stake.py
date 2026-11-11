"""Stake tab: status and how staking works."""

import core
import strings as S
from widgets import Card


def build(app, b, d):
    b.add_widget(Card(S.STAKE_STATUS.format(
        state=S.STAKE_STAKED if d["staked"] else S.STAKE_NOT_STAKED,
        redeem=S.STAKE_CAN_REDEEM if d["can_redeem"] else S.STAKE_CANNOT_REDEEM,
        eth=core.eth(d["stake_need_wei"]))))
    b.add_widget(Card(S.STAKE_HOW))
