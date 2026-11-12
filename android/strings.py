"""Every piece of text the app shows. Change wording HERE only.

Texts with {name} parts are templates: the pages fill them in with .format(...).
[b]..[/b] = bold, [size=..sp]..[/size] = size, [color=rrggbb]..[/color] = color.
"""

# ------------------------------------------------------------------ app shell
APP_TITLE = "dSOS"
SPLASH_FALLBACK = "[b]dSOS[/b]"
HEADER_WALLET = "[b]Main wallet[/b]\n{addr}"
HEADER_NO_ADDR = "enter address"
CHAIN_PILL = "Ethereum"

HINT_ADDRESS = "Wallet address 0x..."
HINT_API_KEY = "Etherscan API key (optional)"
BTN_LOAD = "Load"
BTN_PASTE = "Paste"
BTN_COPY = "Copy"

TAB_WALLET = "Wallet"
TAB_OFFERS = "Offers"
TAB_STAKE = "Stake"
TAB_CREDITS = "Credits"
TAB_PLUS = "+"

MSG_PASTED = "Pasted from clipboard"
MSG_CLIPBOARD_EMPTY = "Clipboard is empty or not readable"
MSG_CLIPBOARD_EMPTY_DOT = "Clipboard is empty or not readable."
MSG_LOADING = "Loading..."
MSG_BLOCK_VIA = "Block {block:,} via {source}"
MSG_LOAD_FIRST = "Load your wallet first, then tap Send."
MSG_COMING = "{name} is coming in the next step."

ERROR_CARD = "[b]Error[/b]\n{error}"
EMPTY_WALLET = "Enter your wallet address above and tap Load."
EMPTY_OTHER_TABS = "No data yet. Open the Wallet tab, enter your address and tap Load."

# ------------------------------------------------------------------ durations / status
EXPIRED = "expired"
LEFT = "{time} left"
DUR_DAYS = "{d}d {h}h"
DUR_HOURS = "{h}h {m}m"
DUR_MINUTES = "{m}m"
STATUS = {"redeemable": "Redeemable", "expiring": "Expiring", "expired": "Expired"}

# ------------------------------------------------------------------ errors from core / tx
ERR_BAD_WALLET = "Enter a valid 0x wallet address (42 characters)"
ERR_ALL_RPC = "All RPCs failed: {error}"
ERR_EMPTY_RESULT = "Empty result for {sig}"
ERR_ONLY_BTP = "Only B, T and P offers are supported here"
ERR_HOLDER_ADDR = "Holder must be a 0x address (42 characters)"
ERR_MIN_SLICE = "At least 1 slice"
ERR_MIN_WINDOW = "Window must be at least 1 block"
ERR_RECIPIENT_ADDR = "Recipient must be a 0x address (42 characters)"
ERR_MIN_SEND = "Send at least 1 dSOS"
ERR_USER_ADDR = "Wallet must be a 0x address (42 characters)"
ERR_MIN_CREDIT = "Redeem at least 1 credit"
ERR_STAKE_VALUE = "Stake amount must be a whole number of slices (0.001 ETH each)"
ERR_OFFER_ID = "Offer id must be 1 or higher"

# ------------------------------------------------------------------ shared offer card / rows
OFFER_CARD = (
    "[b]{kind}[/b]  {count:,} dSOS  #{id}{pin}   [color={color}][b]{status}[/b][/color]\n"
    "{eth} ETH - {left}\n"
    "Sendable: {sendable}   Sweepable at block {sweepable_at:,}")
OFFER_PIN_TAG = "  PIN"
YES = "yes"
NO = "no"
LINK_SEE_ALL = "See all"

# ------------------------------------------------------------------ wallet tab
WALLET_BALANCE = (
    "dSOS balance\n"
    "[size=44sp][b]{balance:,}[/b][/size] dSOS\n"
    "= {eth} ETH redeemable\n\n"
    "[color=0033ff][b]Sendable {sendable:,}[/b][/color]   "
    "[b]Expiring <1d {expiring:,}[/b]\n"
    "[color=b00021][b]Expired, unswept {expired:,}[/b][/color]")
ACTION_SEND = "Send"
ACTION_CREATE = "Create"
ACTION_REDEEM = "Redeem"
ACTION_STAKE = "Stake"
ICON_SEND = ">"
ICON_CREATE = "+"
ICON_REDEEM = "<"
ICON_STAKE = "o"
NEXT_EXPIRY = "[b]Next expiry in ~{time}[/b]\nRedeem before block {block:,}"
ACTIVE_OFFERS = "Active offers"
NO_ACTIVE_OFFERS = "No active offers."
SHARED_POOL = "Shared pool\n[b]{eth} ETH[/b] - {supply:,} dSOS active"

# ------------------------------------------------------------------ offers tab
OFFERS_TITLE = "Offers ({n})"
OFFERS_HELP = (
    "[b]How to read this[/b]\n"
    "Sendable = not a G offer and more than 7,200 blocks (about 1 day) left.\n"
    "Expired offers still count in your balance until someone sweeps them.")

# ------------------------------------------------------------------ stake tab
STAKE_TITLE = "[b]Stake[/b]"
STAKE_PILL_STAKED = "Staked"
STAKE_PILL_NOT_STAKED = "Not staked"
STAKE_INTRO = "Stakers can form and redeem credits from their SOS trust records."
STAKE_REQUIRED_BOX = ("[size=14sp]Required now[/size]\n"
                      "[size=44sp][b]{eth}[/b][/size] [size=18sp]ETH[/size]")
STAKE_REQUIRED_NOTE = ("{n:,} slices · the smallest gate offer above the pool's "
                       "unallocated balance + 0.001 ETH")
STAKE_STEPS = (  # title, subtitle
    ("Create the gate offer", "A gated offer with a 1-block window."),
    ("Sweep it after the next block", "You become permanently staked."),
    ("Wait 14,400 blocks", "About 2 days before your first credit redeem."),
)
STAKE_STEP_TEXT = "[b]{title}[/b]\n[size=14sp]{sub}[/size]"
STAKE_DONATION_WARN = ("One-way donation. Once swept, the ETH stays in the shared pool "
                       "and cannot be redeemed.")
STAKE_CHECK = "I understand this donation is permanent."
STAKE_BTN = "Stake {eth} ETH"
STAKE_BTN_DONE = "Already staked"
STAKE_SWEEP = "Sweep mine"
STAKE_SWEEP_NONE = "No offers are ready to sweep yet."
STAKE_SWEEP_READY = "{n} offer{s} ready to sweep."
STAKE_SUMMARY = ("[b]Stake: create a gate offer[/b]\n{eth} ETH ({n:,} slices)\n"
                 "Holder {holder}, window 1 block, gated")
STAKE_ROWS = {"payable": "payable amount (ETH)", "to": "to (address)", "delay": "delayBlocks",
              "pin": "pinCommitment_", "hash": "payloadHash", "sig": "signature (bytes)"}
STAKE_TIP = ("metadata (string): leave it empty. The PIN commitment is random on purpose: "
             "nobody can redeem this offer, so its ETH can only be swept into the pool, and "
             "that is what stakes you. After the transaction is mined, wait one block and "
             "tap Sweep mine.")
STAKE_WARN = ("The offer only counts as a gate if its value is above the pool's unallocated "
              "balance + 0.001 ETH when it is mined. If the pool grew in between, the ETH is "
              "donated and you are not staked. Reload right before you send.")
STAKE_FN = "createOfferGated"
SWEEP_SUMMARY = ("[b]Sweep offer #{id}[/b]\nMoves its ETH into the shared pool\n"
                 "{pos} of {total} ready to sweep")
SWEEP_ROWS = {"id": "id (uint256)"}
SWEEP_TIP = ("Anyone can sweep an expired offer. If this was your gate offer, you become "
             "permanently staked. Sweep the rest one by one.")
SWEEP_WARN = "Sweeping burns the slices of this offer. Its ETH stays in the pool."
SWEEP_FN = "sweepOffer"

# ------------------------------------------------------------------ credits tab
CREDITS_TITLE = "[b]Credits[/b]"
CREDITS_PILL_STAKED = "Staked"
CREDITS_PILL_NOT_STAKED = "Not staked"
CREDITS_HELD_BOX = ("[size=14sp]Credits held[/size]\n[size=50sp][b]{n:,}[/b][/size]\n"
                    "[size=14sp]= {eth} ETH[/size]")
CREDITS_READY_BOX = ("[size=14sp]Ready to form[/size]\n"
                     "[size=36sp][color=0033ff][b]+{n:,}[/b][/color][/size]\n"
                     "[size=14sp]pending trust records[/size]")
CREDITS_SYNC = "Sync credits"
CREDITS_ROW_STAKED_SINCE = "Staked since block"
CREDITS_ROW_COOLDOWN = "{n:,}-block cooldown"
CREDITS_ROW_POOL = "Pool can pay out"
CREDITS_ROW_NONCE = "Redeem nonce"
CREDITS_PASSED = "Passed"
CREDITS_DASH = "-"
CREDITS_REDEEM_TITLE = "Redeem credits"
CREDITS_RATE = "1 credit = 0.001 ETH"
CREDITS_AMOUNT = "[size=50sp][b]{n}[/b][/size]\n[size=15sp]you receive {eth} ETH[/size]"
CREDITS_REDEEM_BTN = "Redeem {n} {word}"
CREDITS_WORD_ONE = "credit"
CREDITS_WORD_MANY = "credits"
CREDITS_FOOTNOTE = "Credits come from your SOS trust records and cannot be transferred."
CREDITS_ERR_NOT_STAKED = "This wallet is not staked yet, so it cannot redeem credits."
CREDITS_ERR_COOLDOWN = "Cooldown not finished: {time} left."
CREDITS_ERR_NONE = "You have no credits to redeem."
CREDITS_ERR_POOL = "The pool cannot pay this amount right now."
SYNC_SUMMARY = "[b]Sync credits[/b]\nForms {n} {word} from your pending trust records."
SYNC_TIP = ("syncCredits has no parameters. On Etherscan just press Write. "
            "Use the same wallet that holds the credits.")
SYNC_WARN = "Only a staked wallet can sync credits. If the call fails, check the Stake tab."
SYNC_FN = "syncCredits"
REDEEM_SUMMARY = ("[b]Redeem {n} {word}[/b]\n= {eth} ETH paid to your wallet\n"
                  "Redeem nonce {nonce}")
REDEEM_ROWS = {"n": "creditsToSpend (uint256)", "r": "r (tuple: paste as one value)"}
REDEEM_TIP = ("On Etherscan paste the r value above into the single field called r. "
              "Its payloadHash only fits redeem nonce {nonce} and this exact amount, and "
              "the transaction must come from {wallet}. If anything changes first, reload "
              "the app and build it again.")
REDEEM_WARN = "Redeeming burns the credits and cannot be undone."
REDEEM_FN = "redeemCredit"

# ------------------------------------------------------------------ shared page chrome
ICON_BACK = "<"
ICON_MINUS = "-"
ICON_PLUS = "+"

# ------------------------------------------------------------------ create offer page
CREATE_TITLE = "[b]Create offer[/b]"
CREATE_TYPE = "[b]Type[/b]"
CREATE_TYPES = (  # code, title, subtitle, color
    ("B", "Basic", "Sendable", "0033ff"),
    ("T", "Type T", "Sendable", "0b0b0b"),
    ("P", "Type P", "Sendable", "00a82d"),
    ("G", "Gated", "PIN - not sendable", "0b0b0b"),
)
CREATE_SLICES = "Slices (dSOS)"
CREATE_EACH = "0.001 ETH each"
CREATE_SLICES_VALUE = "[size=54sp][b]{n}[/b][/size]\n= {eth} ETH"
CREATE_WINDOW = "[b]Redeem window[/b]"
WINDOW_CUSTOM = "Custom"
HINT_CUSTOM_BLOCKS = "Window in blocks (7200 = about 1 day)"
WIN_NOTE = "{blocks:,} blocks{expires}. {rule}"
WIN_EXPIRES = " - expires near block {block:,}"
WIN_RULE_OK = "Windows over 7,200 blocks stay sendable from your wallet."
WIN_RULE_SHORT = "Windows of 7,200 blocks or less are NOT sendable from a wallet."
CREATE_HOLDER = "[b]Holder[/b]"
HOLDER_ME = "[b]Myself[/b]\n{addr}"
HOLDER_ME_EMPTY = "enter address on Wallet tab"
HOLDER_OTHER = "[b]Another address[/b]\ntap to use my own address"
HINT_HOLDER = "Holder address 0x..."
CREATE_LEDGER = "Ledger record - optional signature"
CREATE_LEDGER_SKIPPED = "Skipped"
CREATE_BUTTON = "Create offer · {eth} ETH"
CREATE_NOTE = "Offers not redeemed before expiry can be swept into the shared pool."
CREATE_ERR_GATED = "Gated offers need a PIN. Coming in the next step."
CREATE_ERR_WINDOW = "Enter the window in blocks."
CREATE_ERR_OWN_ADDR = "Enter your address on the Wallet tab first."
CREATE_ERR_HOLDER = "Holder needs a valid 0x address."
CREATE_SUMMARY = ("[b]Create {kind} offer[/b]\n{slices} dSOS = {eth} ETH\n"
                  "Window {blocks:,} blocks\nHolder {holder}")
CREATE_ROWS = {"payable": "payable amount (ETH)", "kind": "kind (uint8)", "to": "to (address)",
               "delay": "delayBlocks", "hash": "payloadHash", "sig": "signature (bytes)"}
CREATE_TIP = "metadata (string): leave it empty."
CREATE_FN = "createOffer"

# ------------------------------------------------------------------ send page
SEND_TITLE = "[b]Send dSOS[/b]"
SEND_AVAILABLE = "[size=13sp]Available to send[/size]\n[size=24sp][b]{avail:,} dSOS[/b][/size]"
SEND_OF_HELD = "[size=13sp]of {held:,} held\n≈ {eth} ETH[/size]"
SEND_TO = "[b]To[/b]"
HINT_RECIPIENT = "Recipient address 0x..."
SEND_MAX = "Max {n}"
SEND_AMOUNT = ("[size=56sp][b]{n}[/b][/size] [size=18sp]dSOS[/size]\n"
               "[size=15sp]= {eth} ETH redeemable value[/size]")
SEND_TAKEN_FROM = "[b]Taken from your newest offers[/b]"
SEND_ROW_ID = "[b]#{id}[/b]  -  {left}{split}"
SEND_ROW_SPLIT = "  -  split"
SEND_ROW_AMOUNT = "[b]{take} dSOS[/b]"
SEND_BLOCKED = "{stuck} dSOS can't be sent here: {parts}. Send those from My offers."
SEND_BLOCKED_GATED = "{n} gated offer{s}"
SEND_BLOCKED_SHORT = "{n} with under a day left"
SEND_BLOCKED_EXPIRED = "{n} expired"
SEND_BLOCKED_JOIN = " and "
SEND_BUTTON = "Send {n} dSOS"
SEND_BUTTON_EMPTY = "Send"
SEND_NOTE = "Wallet sends write no ledger record. The recipient gets over a day to redeem."
SEND_ERR_NO_WALLET = "Load your wallet first (Wallet tab)."
SEND_ERR_NOTHING = "Nothing can be sent from the wallet right now."
SEND_ERR_ADDRESS = "Enter a valid 0x recipient address."
SEND_ERR_SELF = "You cannot send to yourself."
SEND_ERR_CONTRACT = "You cannot send to the dSOS contract."
SEND_ERR_ZERO = "You cannot send to the zero address."
SEND_ERR_AMOUNT = "Pick an amount."
SEND_SUMMARY = "[b]Send {n} dSOS[/b]\n= {eth} ETH redeemable value\nTo {to}"
SEND_ROWS = {"to": "to (address)", "n": "n (uint256)"}
SEND_TIP = ("dSOS is a standard token with 0 decimals. You can also send it from any wallet's "
            "Send token screen: add the token {token} and send {n}.")
SEND_WARN = "A send cannot be undone. Check the recipient address character by character."
SEND_FN = "transfer"

# ------------------------------------------------------------------ transaction ready page
TX_TITLE = "[b]Transaction ready[/b]"
TX_NOT_SENDER = ("This app cannot sign or send yet. Send the transaction from a wallet or "
                 "website that can call contracts (see the buttons below). Check every value "
                 "first, and test with a small amount.")
TX_TO = "To (dSOS contract)"
TX_VALUE = "Value (ETH)"
TX_VALUE_SHOWN = "{eth} ETH"
TX_DATA = "Data (hex)"
TX_ETHERSCAN_HEAD = "[b]Etherscan Write Contract: {fn}[/b]"
TX_BTN_ETHERSCAN = "Open Etherscan Write Contract"
TX_BTN_DAPP = "Open dApp in browser"
TX_DEFAULT_WARN = ("Offers not redeemed before expiry can be swept into the shared pool, "
                   "and that ETH is gone for good.")
TX_COPIED = "Copied: {title}"
TX_COPY_FAILED = "Copy failed on this phone."
TX_OPEN_FAILED = "Could not open the browser."
