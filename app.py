"""Streamlit dashboard (read-only):  streamlit run app.py"""
from pathlib import Path

import streamlit as st

from dsos import config
from dsos.service import fmt_blocks, load_summary, wei_to_eth

LOGO = Path("assets/logo.png")
st.set_page_config(page_title="dSOS", page_icon=str(LOGO) if LOGO.exists() else "🟩",
                   layout="centered")

st.markdown("""
<style>
.card{background:#fff;border-radius:24px;padding:20px 22px;margin-bottom:14px;color:#0b0b0b}
.big{font-size:56px;font-weight:800;line-height:1}
.sub{color:#555;font-size:14px}
.chip{display:inline-block;background:#f0f1f1;border-radius:16px;padding:10px 16px;margin:4px 6px 0 0}
.chip b{font-size:20px}
.banner{background:#0b0b0b;color:#fff;border-radius:22px;padding:16px 20px;margin-bottom:14px}
.badge{display:inline-block;width:44px;height:44px;line-height:44px;text-align:center;
 border-radius:12px;font-weight:800;color:#fff;background:#0033FF;margin-right:12px}
.badge.G{background:#fff;color:#0b0b0b;border:3px solid #0b0b0b;line-height:38px}
.pill{float:right;border-radius:16px;padding:6px 14px;font-weight:700;color:#fff;background:#00A82D}
.pill.expiring{background:#0b0b0b}.pill.expired{background:#b00020}
</style>""", unsafe_allow_html=True)


def card(html: str):
    st.markdown(f'<div class="card">{html}</div>', unsafe_allow_html=True)


@st.cache_data(ttl=30, show_spinner="Reading Ethereum…")
def fetch(addr: str):
    return load_summary(addr)


with st.sidebar:
    if LOGO.exists():
        st.image(str(LOGO), width=72)
    st.header("dSOS (read-only)")
    addr = st.text_input("Wallet address", value=config.DEFAULT_WALLET, placeholder="0x…")
    if st.button("Refresh"):
        fetch.clear()
    st.caption(f"dSOS: `{config.DSOS_ADDRESS}`")
    st.caption(f"Ledger: `{config.LEDGER_ADDRESS}`")
    st.caption("Etherscan API key: " + ("✅ set" if config.ETHERSCAN_API_KEY else "❌ not set (public RPC)"))

if not addr:
    st.info("Enter a wallet address in the sidebar.")
    st.stop()

try:
    s = fetch(addr)
except Exception as e:  # noqa: BLE001
    st.error(f"Could not load data: {e}")
    st.stop()

st.caption(f"{s.address}  ·  block {s.block:,}  ·  source: {s.source}")
tab_wallet, tab_offers, tab_stake, tab_credits = st.tabs(["Wallet", "Offers", "Stake", "Credits"])

with tab_wallet:
    card(f"""<div class="sub">dSOS balance</div>
<div class="big">{s.balance:,} <span style="font-size:22px">dSOS</span></div>
<div class="sub">≈ {wei_to_eth(s.value_wei)} ETH redeemable</div>
<span class="chip">🔵 Sendable<br><b>{s.sendable:,} dSOS</b></span>
<span class="chip">⚫ Expiring &lt; 1 day<br><b>{s.expiring:,} dSOS</b></span>
<span class="chip">🔴 Expired, unswept<br><b>{s.expired:,} dSOS</b></span>""")

    if s.next_expiry_block:
        left = s.next_expiry_block - s.block
        st.markdown(f'<div class="banner">⏰ Next expiry in ~{fmt_blocks(left)}<br>'
                    f'<span style="opacity:.8">Redeem before block {s.next_expiry_block:,}</span></div>',
                    unsafe_allow_html=True)
    card(f"""<div class="sub">Shared pool</div>
<b style="font-size:26px">{wei_to_eth(s.pool_balance_wei)} ETH</b>
<span class="sub"> · {s.pool_supply:,} dSOS active</span>""")


def render_offers(offers):
    if not offers:
        st.info("No active offers.")
    for o in offers:
        card(f"""<span class="pill {o.status}">{o.status.capitalize()}</span>
<span class="badge {o.kind}">{o.kind}</span>
<b>{o.count:,} dSOS · #{o.id}</b>{' · PIN' if o.kind == 'G' else ''}<br>
<span class="sub">{wei_to_eth(o.principal_wei)} ETH · {fmt_blocks(o.blocks_left)} left
 · sweepable at block {o.sweepable_at:,}</span>""")


with tab_wallet:
    st.subheader("Active offers")
    render_offers(s.offers[:5])
    if len(s.offers) > 5:
        st.caption(f"{len(s.offers) - 5} more in the Offers tab.")

with tab_offers:
    render_offers(s.offers)

with tab_stake:
    card(f"""<div class="sub">Status</div>
<b style="font-size:26px">{'Staked ✅' if s.staked else 'Not staked'}</b><br>
<span class="sub">Cheapest gate offer now: <b>{wei_to_eth(s.stake_requirement_wei)} ETH</b>
 (type G, delay 1 block)</span>""")
    if s.staked:
        st.write("Can redeem credits now." if s.can_redeem
                 else f"Cooldown left: {fmt_blocks(s.cooldown_blocks_left)}")
    st.caption("Reminder: redeeming any part of a gate offer clears its gate flag (no staking).")

with tab_credits:
    card(f"""<div class="sub">Credits held</div><div class="big">{s.credits}</div>
<div class="sub">+ {s.formable} formable from SOS trust records</div>""")
    st.write(f"Ledger: push **{s.ledger_push}**, trust **{s.ledger_trust}**, "
             f"effective **{s.ledger_effective}**")
    if not s.staked:
        st.caption("Only staked wallets can form and redeem credits.")
