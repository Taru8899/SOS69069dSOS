import os

from dotenv import load_dotenv

load_dotenv()

CHAIN_ID = 1  # Ethereum mainnet

DSOS_ADDRESS = "0x7Bd7c427b3c69e2a09603573ac875987c61ECAB8"
LEDGER_ADDRESS = "0x7373DBC24Dcd785896E8Ac3d5372c6ced9B75a8A"
MULTICALL3 = "0xcA11bde05977b3631167028862bE2a173976CA11"

ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY", "").strip()
ETHERSCAN_URL = "https://api.etherscan.io/v2/api"

_custom = os.getenv("RPC_URL", "").strip()
PUBLIC_RPCS = ([_custom] if _custom else []) + [
    "https://ethereum-rpc.publicnode.com",
    "https://eth.llamarpc.com",
    "https://rpc.ankr.com/eth",
    "https://cloudflare-eth.com",
]

DEFAULT_WALLET = os.getenv("WALLET_ADDRESS", "").strip()

UNIT_WEI = 10**15          # 0.001 ETH = 1 slice = 1 dSOS
BLOCK_TIME_SECONDS = 12
DAY_BLOCKS = 7200          # MIN_SEND_WINDOW (about 1 day)
