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
MSG_LOAD_FIRST_REDEEM = "Load your wallet first, then tap Redeem."
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
ERR_SLICES = "Redeem at least 1 slice"

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
BTN_DONATE = "Donate"

# ------------------------------------------------------------------ offers tab (My offers)
OFFERS_TITLE = "[b]My offers[/b]"
OFFERS_SUMMARY = "{n} active · {slices:,} dSOS"
OFFERS_FILTERS = (("all", "All"), ("redeemable", "Redeemable"), ("expiring", "Expiring"),
                  ("expired", "Expired"))
OFFERS_EMPTY = "No offers in this view."
OC_TITLE = "[b]{count:,} dSOS · #{id}{pin}[/b]"
OC_SUB_FROM = "{eth} ETH · from {donor}"
OC_SUB_YOU = "{eth} ETH · created by you"
OC_SUB_GATED = "{eth} ETH · not sendable"
OC_SUB_EXPIRED = "Expired · anyone can sweep"
OC_LEFT = "{left} · expires block {block:,}"
OD_TITLE = "[b]Offer #{id}[/b]\n{count:,} dSOS · {eth} ETH · {left}"
OD_SLICES = "Slices to use"
OD_OF = "[size=26sp][b]{n}[/b][/size] of {total}"
OD_REDEEM = "Redeem {eth} ETH"
OD_TRANSFER = "Transfer {n}"
OD_SWEEP = "Sweep offer #{id}"
OD_NOTE_PARTIAL = ("The other {n} slice{s} stay with you with the same expiry. "
                   "Gated offers ask for the PIN.")
OD_NOTE_ALL = "This uses the whole offer. Gated offers ask for the PIN."
OD_NOTE_TRANSFER = "The recipient gets {n} slice{s} with the same expiry."
OD_NOTE_GATED = ("Enter the PIN, then tap Redeem. The PIN is checked against the chain first, so "
                 "a wrong one never reaches your wallet. Gated offers cannot be sent.")
OD_NOTE_EXPIRED = ("Expired offers cannot be redeemed or sent. Sweeping moves their ETH into "
                   "the shared pool.")
OD_SWEEP_SUMMARY = "[b]Sweep offer #{id}[/b]\nMoves its ETH into the shared pool"
OT_SUMMARY = "[b]Transfer {n} dSOS[/b]\nOffer #{id} - {kind}\nTo {to}"
OT_ROWS = {"id": "id (uint256)", "slices": "slices (uint256)", "to": "to (address)",
           "r": "r (tuple: paste as one value)"}
OT_TIP = ("On Etherscan paste the r value above into the single field called r. If you send "
          "fewer slices than the offer holds, the recipient gets a new offer with the same "
          "expiry. Send it from {wallet}.")
OT_WARN = "A transfer cannot be undone. Check the recipient address character by character."
OT_FN = "transferSlices"

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
WIN_RULE_GATED = "Gated offers are never sendable. The holder redeems them with the PIN."
CREATE_HOLDER = "[b]Holder[/b]"
HOLDER_ME = "[b]Myself[/b]\n{addr}"
HOLDER_ME_EMPTY = "enter address on Wallet tab"
HOLDER_OTHER = "[b]Another address[/b]\ntap to use my own address"
HINT_HOLDER = "Holder address 0x..."
CREATE_LEDGER = "Ledger record - choose when sending"
CREATE_LEDGER_SKIPPED = "Optional"
CREATE_BUTTON = "Create offer · {eth} ETH"
CREATE_NOTE = "Offers not redeemed before expiry can be swept into the shared pool."
CREATE_ERR_PIN = "Enter a PIN for a gated offer."
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
TX_NOT_SENDER = ("This app never holds your keys. Your wallet app signs and sends. Check every "
                 "value first, and test with a small amount. You can also copy the values below "
                 "into any wallet or website.")
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

# ------------------------------------------------------------------ redeem offers page
RO_TITLE = "[b]Redeem[/b]"
RO_AVAILABLE = "[size=13sp]Redeemable now[/size]\n[size=24sp][b]{n:,} dSOS[/b][/size]"
RO_AVAILABLE_ETH = "[size=13sp]= {eth} ETH[/size]"
RO_PICK = "[b]Pick an offer[/b]"
RO_ROW = "{kind}    #{id}    {left}    {count} dSOS"
RO_AMOUNT = ("[size=56sp][b]{n}[/b][/size] [size=18sp]dSOS[/size]\n"
             "[size=15sp]you receive {eth} ETH[/size]")
RO_MAX = "Max {n}"
RO_BUTTON = "Redeem {n} dSOS"
RO_BUTTON_EMPTY = "Redeem"
RO_NOTE = "Redeem before block {block:,}. The ETH is paid straight to your wallet."
RO_ERR_NONE = "Nothing can be redeemed right now."
RO_ERR_AMOUNT = "Pick an amount."
RO_GATED = ("{n} gated offer{s} ({slices} dSOS) need a PIN and are not listed here. "
            "Redeem them in the Offers tab.")
RO_SWEEP_TITLE = "[b]Expired offers[/b]"
RO_SWEEP_HELP = ("Expired offers can no longer be redeemed. Sweeping moves their ETH into the "
                 "shared pool.")
RO_SWEEP_ROW = "[b]#{id}[/b]  {kind}  {count} dSOS"
RO_SWEEP_ROW_UNKNOWN = "[b]#{id}[/b]"
RO_SWEEP_BTN = "Sweep"
RO_SUMMARY = "[b]Redeem {n} dSOS[/b]\nOffer #{id} - {kind}\n= {eth} ETH paid to your wallet"
RO_ROWS = {"id": "id (uint256)", "slices": "slices (uint256)", "pin": "pin (bytes32)",
           "r": "r (tuple: paste as one value)"}
RO_TIP = ("On Etherscan paste the r value above into the single field called r. The pin is all "
          "zeros because this offer has no PIN. Send it from {wallet} before block {block:,}.")
RO_WARN = "Redeemed slices are burned and the ETH is paid out. This cannot be undone."
RO_FN = "redeemSlices"

# ------------------------------------------------------------------ errors added in v7
ERR_PIN_EMPTY = "Enter the PIN."
ERR_PIN_BYTES = "The PIN must be 32 bytes."
ERR_AMOUNT_ETH = "Enter an amount in ETH, for example 0.01."
ERR_AMOUNT_ZERO = "The amount must be above 0."
ERR_AMOUNT_DECIMALS = "ETH has at most 18 decimal places."

# ------------------------------------------------------------------ dry run (eth_call before sending)
SIM_RUNNING = "[b]Dry run[/b]\nChecking this transaction against the chain..."
SIM_OK = "[b]Dry run passed[/b]\nThe contract would accept this transaction right now."
SIM_FAIL = "[b]Dry run failed[/b]\n{reason}\nNothing was sent. Fix this first."
SIM_UNKNOWN = ("[b]Dry run unavailable[/b]\n{error}\nYou can still send it, but the wallet may "
               "show a failure.")
SIM_NEEDS_WALLET = "[b]Dry run skipped[/b]\nLoad your wallet address first."
REVERT_TEXT = {
    "BadDelay": "The window is too long for this contract.",
    "BadOfferPin": "Wrong PIN for this offer.",
    "BadRedeemHash": "The redeem hash is out of date (nonce or amount changed). Reload and build it again.",
    "InsufficientCredits": "You do not have that many credits.",
    "InsufficientSlices": "The offer has fewer slices than you asked for.",
    "InvalidValue": "The ETH amount must be a whole number of slices (0.001 ETH each).",
    "NoCredit": "No credit available.",
    "NotEnoughSendable": "Fewer sendable slices than that. Gated, expiring and expired offers cannot be wallet-sent.",
    "NotHolder": "This wallet does not hold that offer.",
    "NotStaked": "This wallet is not staked yet.",
    "NotTransferable": "That cannot be sent (gated offers and the contract itself are blocked).",
    "OfferNotActive": "That offer is no longer active.",
    "PoolTooThin": "The pool cannot pay this amount right now.",
    "Reentrant": "The contract is busy. Try again.",
    "SelfTransfer": "You cannot send to yourself.",
    "TooEarly": "Too early: the stake cool-down or the offer's window is not over yet.",
    "TooManyOffers": "The holder already has too many offers.",
    "TransferFailed": "The ETH payout failed.",
    "WindowClosed": "The offer's redeem window has closed. Sweep it instead.",
    "ZeroAddress": "The zero address is not allowed.",
    "ZeroAmount": "The amount must be at least 1.",
    "InsufficientFunds": "This wallet does not hold enough ETH for the amount plus gas.",
    "InvalidSignature": "The ledger rejected the signature.",
    "DuplicatePayloadHash": "That ledger record already exists.",
    "MetadataTooLong": "The metadata is too long (64 characters at most).",
    "revert": "The contract would reject this transaction.",
}
REVERT_UNKNOWN = "The contract would reject this transaction ({name})."

# ------------------------------------------------------------------ send with wallet (transaction page)
TX_BTN_WALLET = "Send with wallet"
TX_BTN_WALLET_BUSY = "Waiting for your wallet..."
TX_BTN_WALLET_BLOCKED = "Send with wallet (dry run failed)"
TX_BTN_VIEW = "View on Etherscan"
TX_LEDGER_OFF = "Ledger record: off"
TX_LEDGER_ON = "Ledger record: on"
TX_LEDGER_HELP = ("[b]Ledger record[/b]\nOn: your wallet first signs a record for the SOS ledger "
                  "(a second approval), and it is sent together with the transaction. Off: no record "
                  "is written and the action works the same.")
TX_WALLET_UNAVAILABLE = ("The wallet link is not available on this device. Use the copy buttons "
                         "below.")
TX_WC_NO_PROJECT = "The WalletConnect project id is not set (WC_PROJECT_ID in theme.py)."
TX_WC_NOT_READY = ("The wallet link did not start: {error}. Check your internet connection and try "
                   "again.")
TX_CONNECTING = "Opening your wallet to connect..."
TX_CONNECT_PASTE = ("No wallet app opened. The connection link is copied: paste it into your "
                    "wallet's WalletConnect field.")
TX_CONNECTED = "Connected to {wallet}: {addr}"
TX_WRONG_ACCOUNT = ("Your wallet is on {got} but this app loaded {want}. Switch the account in "
                    "your wallet, or load that address.")
TX_SIGNING = "Approve the signature in {wallet}..."
TX_SIGN_BAD = "The signature did not verify on the ledger ({reason}). Nothing was sent."
TX_SENDING = "Approve the transaction in {wallet}..."
TX_OPEN_WALLET = "Open {wallet} to approve."
TX_SENT = "Sent. Transaction {hash}"
TX_SENT_NOTE = "Reload from the Wallet tab in a minute to see the result."
TX_REJECTED = "Cancelled in the wallet. Nothing was sent."
TX_ERROR = "Wallet error: {error}"
TX_DISCONNECT = "Disconnect wallet"
TX_DISCONNECTED = "Wallet disconnected."
TX_PEER_DEFAULT = "your wallet"
TX_COPY_ROWS_HEAD = "[b]Or copy the values into another wallet[/b]"
TX_NO_ETHERSCAN_FN = "[b]Plain ETH transfer (no function)[/b]"

# ------------------------------------------------------------------ donate page
DONATE_TITLE = "[b]Donate to the pool[/b]"
DONATE_INTRO = "ETH sent here joins the shared pool and cannot be taken back."
DONATE_HINT = "Amount in ETH, e.g. 0.01"
DONATE_AMOUNTS = ("0.001", "0.01", "0.1")
DONATE_BUTTON = "Donate {eth} ETH"
DONATE_BUTTON_EMPTY = "Donate"
DONATE_NOTE = ("A donation raises the pool's unallocated balance, so the stake requirement "
               "goes up too.")
DONATE_SUMMARY = "[b]Donate {eth} ETH[/b]\nPlain ETH transfer to the dSOS contract"
DONATE_TIP = ("In any wallet: send {eth} ETH on Ethereum to the contract address above, with no "
              "data. The contract's receive function adds it to the pool.")
DONATE_WARN = "A donation is permanent. The ETH stays in the shared pool."

# ------------------------------------------------------------------ gated offers (create + redeem)
CREATE_PIN_HINT = "PIN or passphrase (keep it secret)"
CREATE_PIN_NOTE = ("The holder needs this PIN to redeem. Only a hash goes on-chain: your text is "
                   "hashed with keccak256 (a 0x + 64 hex value is used as it is), the same rule "
                   "as the dApp.")
CREATE_GATE_WARN = ("A gated offer with a 1-block window above {eth} ETH counts as a gate offer: "
                    "once swept you become staked and the ETH is donated. Use a longer window "
                    "unless that is what you want.")
CREATE_GATED_SUMMARY = ("[b]Create gated offer[/b]\n{slices} dSOS = {eth} ETH\n"
                        "Window {blocks:,} blocks\nHolder {holder}\nProtected by your PIN")
CREATE_GATED_ROWS = {"payable": "payable amount (ETH)", "to": "to (address)",
                     "delay": "delayBlocks", "pin": "pinCommitment_", "hash": "payloadHash",
                     "sig": "signature (bytes)"}
CREATE_GATED_TIP = ("metadata (string): leave it empty. Give the PIN to the holder privately: it "
                    "is not part of this data. Only that holder can redeem, with the PIN.")
CREATE_GATED_FN = "createOfferGated"
OD_PIN_HINT = "PIN for this offer"
OD_PIN_NEEDED = "Enter the PIN first."
OD_PIN_CHECKING = "Checking the PIN against the chain..."
OD_PIN_BAD = "That PIN does not match this offer. Nothing was built."
OD_PIN_ERROR = "Could not read the offer's PIN hash: {error}"
OD_NOTE_GATED_ACTIVE = "The PIN is checked against the chain before anything is sent."
RO_TIP_PIN = ("The pin value is the 32-byte form of your PIN that matches this offer's on-chain "
              "hash. Send it from {wallet} before block {block:,}.")

# ------------------------------------------------------------------ wallet link metadata (shown in the wallet)
WC_APP_NAME = "dSOS"
WC_APP_DESC = "dSOS companion app. It never holds keys: your wallet signs and sends."

# ------------------------------------------------------------------ v8: shell, drawer, settings, links
BTN_CLOSE = "Close"
BTN_OPEN = "Open"
BTN_BACK_HOME = "Wallet"
DRAWER_SAVED_HINT = "Add your wallet address, then tap Load."
MSG_RELOADING = "Reloading..."
MSG_NEED_ADDRESS = "Add your wallet address first."
MSG_PULL = "Pull down to reload"
SETTINGS_TITLE = "Settings"
SETTINGS_INTRO = ("[b]Contracts[/b]\nBoth are on Ethereum mainnet. Copy an address or open it on "
                  "Etherscan.")
SETTINGS_DSOS = "dSOS contract"
SETTINGS_LEDGER = "SOS69069 ledger"
SETTINGS_VERSION = "[b]App version[/b]\n{build}"
SETTINGS_COPIED = "{title} copied"
SETTINGS_OPEN_FAILED = "Could not open the link. Copy it instead."
LINKS_TITLE = "Ethereum links"
LINKS_NEED_ADDRESS = "Load your wallet first to open it on Etherscan."
LINK_TILES = [
    # key, caption, glyph, colour
    ("wallet", "Etherscan\nmy wallet", "W", (0.0, 0.2, 1, 1)),
    ("read", "dSOS contract\nRead", "R", (0.02, 0.66, 0.21, 1)),
    ("write", "dSOS contract\nWrite", "Wr", (0.9, 0.55, 0.0, 1)),
    ("ledger", "SOS69069\nledger", "L", (0.45, 0.2, 0.85, 1)),
    ("dapp", "dSOS dApp", "d", (0.04, 0.04, 0.04, 1)),
    ("github", "GitHub\nrepo", "G", (0.35, 0.37, 0.4, 1)),
]

# ------------------------------------------------------------------ v8: welcome
WELCOME_RATE = "1 dSOS = 1 slice = 0.001 ETH"
WELCOME_SLOGAN = "Decentralized.\nTrustless. Yours."
WELCOME_CONNECTING = "Connecting..."

# ------------------------------------------------------------------ v8: errors
ERR_BANNER = "Something went wrong:\n{text}"
ERR_LAST_RUN = "The app stopped last time. Last step: {step}"
ERR_PAGE = "[b]This page could not be built[/b]\n{error}"
CREATE_ERR_DRY = "The chain refused this transaction: {reason}"
CREATE_ERR_TEXT = "[b]Cannot create:[/b] {text}"
CREATE_CHECKING = "Checking with the chain..."
PIN_SHOW = "Show"
PIN_HIDE = "Hide"

# ------------------------------------------------------------------ v8: Offers | Activity
OFFERS_SWITCH = [("offers", "Offers"), ("activity", "Activity")]
ACT_SCOPES = [("mine", "Mine"), ("contract", "Contract")]
ACT_FILTERS = [("all", "All"), ("created", "Created"), ("received", "Received"),
               ("sent", "Sent"), ("redeemed", "Redeemed"), ("swept", "Swept"),
               ("stake", "Stake & Credits"), ("donation", "Donations"),
               ("ledger", "Ledger"), ("failed", "Failed")]
ACT_LOADING = "Loading activity..."
ACT_EMPTY = "No activity found in this range."
ACT_NEED_ADDRESS = "Load your wallet first to see your activity."
ACT_ERROR = "[b]Could not load activity[/b]\n{error}"
ACT_NO_KEY = ("Showing about the last 7 days from public nodes. Add an Etherscan key for the full "
              "history and for failed transactions.")
ACT_WINDOW = "Covers blocks {lo:,} to {hi:,}."
ACT_COMPLETE = "Full history loaded."
ACT_TRUNCATED = "More than 10,000 events: the oldest are not shown."
ACT_LOAD_OLDER = "Load older"
ACT_TX_NOTE = "Failed transactions could not be read: {error}"
ACT_COUNT = "{n} items"
ACT_ICONS = {"created": ("+", (0.02, 0.66, 0.21, 1)), "received": ("<", (0.0, 0.2, 1, 1)),
             "sent": (">", (0.04, 0.04, 0.04, 1)), "redeemed": ("$", (0.02, 0.66, 0.21, 1)),
             "redeemed_by": ("$", (0.04, 0.04, 0.04, 1)), "swept": ("S", (0.45, 0.3, 0.0, 1)),
             "staked": ("o", (0.0, 0.2, 1, 1)), "formed": ("c", (0.0, 0.2, 1, 1)),
             "credit_redeemed": ("$", (0.02, 0.66, 0.21, 1)),
             "donation": ("d", (0.45, 0.2, 0.85, 1)), "ledger": ("L", (0.45, 0.2, 0.85, 1)),
             "failed": ("!", (0.69, 0, 0.13, 1))}
ACT_TITLE = {
    "created": "Created {amt} · #{id}",
    "received": "Received {amt}{idpart}",
    "sent": "Sent {amt}{idpart}",
    "redeemed": "Redeemed {amt} · #{id}",
    "redeemed_by": "Your offer was redeemed · #{id}",
    "swept": "Swept {amt} · #{id}",
    "staked": "Staked",
    "formed": "Credits formed · {amt}",
    "credit_redeemed": "Credits redeemed · {amt}",
    "donation": "Donation",
    "ledger": "Ledger record",
    "failed": "Failed · {fn}",
}
ACT_AMT_DSOS = "{n} dSOS"
ACT_AMT_UNKNOWN = "dSOS"
ACT_AMT_CREDITS = "{n} credits"
ACT_IDPART = " · #{id}"
ACT_SUB = "{eth}{when}block {block:,}"
ACT_SUB_ETH = "{eth} ETH · "
ACT_SUB_WHEN = "{ago} · "
ACT_SUB_WHEN_APPROX = "~{ago} · "
ACT_NOW_STAKED = "you are now staked"
ACT_FAILED_SUB = "reverted"
ACT_DETAIL_TX = "Transaction"
ACT_DETAIL_FROM = "From"
ACT_DETAIL_TO = "To"
ACT_DETAIL_BLOCK = "Block {block:,}"
ACT_BTN_ETHERSCAN = "Open on Etherscan"
ACT_BTN_OFFER = "Go to offer #{id}"
ACT_OFFER_NOT_MINE = "Offer #{id} is not in your list (it may belong to someone else)."
ACT_COPIED = "Transaction hash copied"
BTN_RETRY = "Retry"
SETTINGS_LAYOUT = ("[b]Layout report[/b]\nIf something looks misplaced, copy this and send it.")
SETTINGS_LAYOUT_COPY = "Copy layout report"
