// SPDX-License-Identifier: MIT
pragma solidity 0.8.36;

/// @title ISOS69069
/// @notice Read-only view of the SOS69069 ledger. dSOS NEVER writes to the ledger.
interface ISOS69069 {
    /// @notice EIP-712 struct hash of a record (signer, intendedTo, payloadHash, metadata).
    function recordStructHash(address signer, address intendedTo, bytes32 payloadHash, string calldata metadata) external pure returns (bytes32);

    /// @notice True once that exact signed record has been written to the ledger (each can exist once).
    function isRecordHashUsed(bytes32 structHash) external view returns (bool);

    /// @notice Number of records addressed to `user` (used for credits).
    function trustCountOf(address user) external view returns (uint256);
}

/// @title DSOSStorage
/// @notice Shared base of dSOSSystem and dSOSOffers: constants, errors, types, storage, events and the
///         helpers both use. Storage order here is the storage layout of dSOSSystem. Do not reorder.
abstract contract DSOSStorage {

    // ---------------------------------------------------------------------
    // CONSTANTS
    // ---------------------------------------------------------------------

    /// @notice Canonical SOS69069 ledger address.
    address public constant SOS69069_LEDGER = 0x7373DBC24Dcd785896E8Ac3d5372c6ced9B75a8A;

    /// @notice Typed reference to the ledger.
    ISOS69069 public constant SOS = ISOS69069(SOS69069_LEDGER);

    /// @notice Default receiver of S, B and G offers when none is given.
    address public constant DEAD = address(uint160(0xdead));

    /// @notice ETH value of one credit and of one slice / one dSOS (0.001 ETH).
    uint256 public constant UNIT           = 0.001 ether;

    /// @notice Minimum ETH the pool must retain after any credit payout.
    uint256 public constant MIN_RESERVE    = 0.000999 ether;

    /// @notice Applied when a caller passes `delayBlocks == 0` (1 block).
    uint256 public constant DEFAULT_DELAY  = 1;

    /// @notice Base value added to `unallocatedBalance()` to compute the gate requirement.
    uint256 public constant GATE_FLOOR     = 0.001 ether;

    /// @notice Required delay for a G offer to be eligible as a gate offer.
    uint256 public constant GATE_DELAY     = 1;

    /// @notice Blocks a new staker must wait before redeeming credits (2 days).
    uint256 public constant STAKE_COOLDOWN = 14400;

    /// @notice S offers are sendable only while MORE than this many blocks remain (1 day).
    uint256 public constant MIN_SEND_WINDOW = 7200;

    // ---------------------------------------------------------------------
    // ERRORS
    // ---------------------------------------------------------------------

    error ZeroAddress();
    error ZeroAmount();
    error InvalidValue();
    error BadRate();
    error BadTarget();
    error BadDelay();
    error BadNonce();
    error OfferNotActive();
    error OfferFull();
    error NotHolder();
    error NotTransferable();
    error SendWindowClosed();
    error SelfTransfer();
    error InsufficientSlices();
    error InsufficientCredits();
    error OverCap();
    error BadOfferPin();
    error TooEarly();
    error WindowClosed();
    error TooManyOffers();
    error NotStaked();
    error NotEnoughSendable();
    error PoolTooThin();
    error RecordNotFound();
    error LedgerMissing();
    error TransferFailed();
    error Reentrant();

    // ---------------------------------------------------------------------
    // TYPES
    // ---------------------------------------------------------------------

    /// @notice Offer kinds. G = gated, S = sendable free, A = open, B = named.
    enum OfferType { G, S, A, B }

    /// @notice Slices held by one holder. Two storage slots.
    struct Offer {
        address   holder;       // slot 0
        uint64    count;        // slot 0  remaining slices
        bool      active;       // slot 0
        bool      isGate;       // slot 0
        OfferType kind;         // slot 0
        address   donor;        // slot 1
        uint32    index;        // slot 1  position in offersHeldBy[holder]
        uint32    createdAt;    // slot 1  creation block
        uint32    sweepableAt;  // slot 1  expiry block
    }

    /// @notice Escrow of an A or B offer: ETH waiting for sellers to confirm records.
    struct Sale {
        address   donor;        // slot 0  creator of the offer, recipient of the records
        uint64    slicesLeft;   // slot 0  unconfirmed slices
        bool      active;       // slot 0
        OfferType kind;         // slot 0  A or B
        address   target;       // slot 1  address(this) for open, exact address B otherwise
        uint64    perRecord;    // slot 1  slices paid per confirmed record (>= 1)
        uint32    createdAt;    // slot 1
        uint32    sweepableAt;  // slot 2
        bytes32   salt;         // slot 3  fixed at creation, part of every record payload hash
    }

    /// @notice Per-account credit state.
    struct Account {
        uint256 lastTrust;
        uint256 credits;
    }

    // ---------------------------------------------------------------------
    // STORAGE
    // ---------------------------------------------------------------------

    mapping(uint256 => Offer)     internal _offers;
    mapping(uint256 => Sale)      internal _sales;
    mapping(uint256 => bytes32)   public  offerPinCommitment;
    mapping(address => bool)      public  staked;
    mapping(address => uint64)    public  stakedAt;
    mapping(address => Account)   internal _acct;
    mapping(address => uint256[]) public  offersHeldBy;
    mapping(address => uint256)   internal _slices;

    /// @notice saleId => seller => offer id that holds the seller's earned slices.
    mapping(uint256 => mapping(address => uint256)) public earnedOffer;

    /// @notice saleId => seller => next record index to confirm.
    mapping(uint256 => mapping(address => uint256)) public nextRecord;

    /// @notice Slices a user funded in A and B offers (counted at creation).
    mapping(address => uint256) public produced;

    /// @notice Slices a user redeemed from A and B offers.
    mapping(address => uint256) public redeemed;

    /// @notice The one per-address nonce. Every value-moving call must pass its current value.
    mapping(address => uint256) public redeemNonce;

    uint64  public nextOfferId = 1;
    bool    internal _locked;
    uint256 public totalEarmarked;
    uint256 public totalSupply;

    // ---------------------------------------------------------------------
    // EVENTS
    // ---------------------------------------------------------------------

    /// @dev `principal` is the total ETH of the offer. For open A offers `to` is this contract.
    event OfferCreated(uint256 indexed id, OfferType kind, address indexed donor, address indexed to, uint256 principal, uint256 nonce);
    /// @dev Extra data of an A or B offer.
    event SaleOpened(uint256 indexed id, address indexed donor, uint256 slicesPerRecord, uint256 records, bytes32 salt, uint256 nonce);
    /// @dev `earnedOfferId` is the seller's offer that received the slices, `earnedHeld` the slices it now holds.
    event RecordsSynced(uint256 indexed id, address indexed seller, uint256 records, uint256 slices, uint256 earnedOfferId, uint256 earnedHeld, uint256 nonce);
    /// @dev Emitted when an A or B escrow has no unconfirmed slices left.
    event SaleFilled(uint256 indexed id, address indexed lastSeller, uint256 nonce);
    /// @dev Emitted when a user's produced or redeemed counter changes.
    event AllowanceUpdated(address indexed user, uint256 totalProduced, uint256 totalRedeemed, uint256 nonce);
    event OfferTransferred(uint256 indexed id, address indexed from, address indexed to, uint256 nonce);
    event OfferSplit(uint256 indexed id, uint256 indexed newId, uint256 slices, uint256 nonce);
    /// @dev `principal` is the ETH paid out by this redeem.
    event OfferRedeemed(uint256 indexed id, address indexed donor, address indexed holder, uint256 principal, uint256 nonce);
    /// @dev `principal` is the ETH moved into the pool. `holder` is this contract for an A/B escrow.
    ///      `sweeper` is the caller whose nonce was used.
    event OfferSwept(uint256 indexed id, address indexed donor, address indexed holder, uint256 principal, address sweeper, uint256 nonce);
    event Donation(address indexed from, uint256 amount);
    event CreditsFormed(address indexed user, uint256 formed, uint256 credits);
    event CreditRedeemed(address indexed user, uint256 creditsSpent, uint256 ethPaid, uint256 nonce);
    event GateFlagged(uint256 indexed id, bool flagged);
    event Staked(address indexed user, uint64 atBlock);
    event Transfer(address indexed from, address indexed to, uint256 value);

    // ---------------------------------------------------------------------
    // MODIFIERS
    // ---------------------------------------------------------------------

    modifier nonReentrant() {
        if (_locked) revert Reentrant();
        _locked = true;
        _;
        _locked = false;
    }

    /// @dev Checks the caller's expected nonce, increases it, returns the nonce used.
    function _useNonce(uint256 expected) internal returns (uint256 n) {
        n = redeemNonce[msg.sender];
        if (expected != n) revert BadNonce();
        redeemNonce[msg.sender] = n + 1;
    }

    /// @dev Payload hash a seller must sign for record `index` of offer `saleId`.
    ///      Contains this contract, the chain, the offer id, the creation salt, the seller and the index.
    function _recordPayload(uint256 saleId, bytes32 salt, address seller, uint256 index) internal view returns (bytes32) {
        return keccak256(abi.encode(address(this), block.chainid, saleId, salt, seller, index));
    }

    /// @dev Move `amount` slices of S offer `id` from msg.sender to `to` (whole offer or split).
    ///      Does not emit the ERC-20 Transfer event; callers do.
    function _move(uint256 id, address to, uint256 amount, uint256 nonce) internal {
        Offer storage o = _offers[id];
        if (!o.active) revert OfferNotActive();
        if (o.holder != msg.sender) revert NotHolder();
        if (o.kind != OfferType.S) revert NotTransferable();
        if (uint256(o.sweepableAt) <= block.number + MIN_SEND_WINDOW) revert SendWindowClosed();
        if (to == address(0)) revert ZeroAddress();
        if (to == address(this)) revert BadTarget();
        if (to == msg.sender) revert SelfTransfer();
        if (amount == 0) revert ZeroAmount();

        uint256 have = o.count;
        if (amount > have) revert InsufficientSlices();

        if (amount == have) {
            _pop(msg.sender, o.index);
            o.index = _push(to, id);
            o.holder = to;
            emit OfferTransferred(id, msg.sender, to, nonce);
        } else {
            o.count = uint64(have - amount);
            uint256 nid = nextOfferId++;
            _offers[nid] = Offer({
                holder: to,
                count: uint64(amount),
                active: true,
                isGate: false,
                kind: o.kind,
                donor: o.donor,
                index: _push(to, nid),
                createdAt: o.createdAt,
                sweepableAt: o.sweepableAt
            });
            emit OfferSplit(id, nid, amount, nonce);
            emit OfferTransferred(nid, msg.sender, to, nonce);
        }

        _slices[msg.sender] -= amount;
        _slices[to] += amount;
    }

    /// @dev    Append offer id to holder's list.
    function _push(address holder, uint256 id) internal returns (uint32 idx) {
        uint256 len = offersHeldBy[holder].length;
        if (len >= type(uint32).max) revert TooManyOffers();
        idx = uint32(len);
        offersHeldBy[holder].push(id);
    }

    /// @dev    Swap-and-pop; updates the moved offer's index.
    function _pop(address holder, uint256 idx) internal {
        uint256[] storage arr = offersHeldBy[holder];
        if (arr.length == 0 || idx >= arr.length) revert OfferNotActive();
        unchecked {
            uint256 last = arr.length - 1;
            if (idx != last) {
                uint256 lastId = arr[last];
                arr[idx] = lastId;
                _offers[lastId].index = uint32(idx);
            }
            arr.pop();
        }
    }

    /// @dev    Forward ETH; revert on failure.
    function _send(address to, uint256 amount) internal {
        (bool ok, ) = to.call{value: amount}("");
        if (!ok) revert TransferFailed();
    }

    /// @notice Pool balance not earmarked for outstanding offers.
    function unallocatedBalance() public view returns (uint256) {
        uint256 bal = address(this).balance;
        return bal > totalEarmarked ? bal - totalEarmarked : 0;
    }
}

/// @title dSOSOffers
/// @notice Offer module of dSOSSystem: create (S, G, A, B), confirm records, send, redeem, sweep.
///         Runs ONLY through delegatecall from dSOSSystem, on the storage and ETH of dSOSSystem.
///         Deploy this first, then pass its address to the dSOSSystem constructor. No admin.
contract dSOSOffers is DSOSStorage {

    error NotDelegated();

    /// @dev The module's own address. A direct call to the module has address(this) == SELF and reverts.
    address private immutable SELF = address(this);

    modifier onlyDelegateCall() {
        if (address(this) == SELF) revert NotDelegated();
        _;
    }

    /// @notice Create an S offer: `msg.value / UNIT` slices held by `to` from the start.
    ///         Free redeem (no records, no cap). Sendable while more than MIN_SEND_WINDOW blocks remain.
    /// @param  to            Holder. address(0) means DEAD. Not this contract. May be the caller.
    /// @param  delayBlocks   Blocks until sweepable. 0 means DEFAULT_DELAY (1).
    /// @param  expectedNonce Caller's current redeemNonce.
    function createOfferS(address to, uint256 delayBlocks, uint256 expectedNonce) external payable onlyDelegateCall nonReentrant {
        uint256 nonce = _useNonce(expectedNonce);
        to = _receiver(to);
        uint256 id = _storeOffer(OfferType.S, to, delayBlocks, bytes32(0));
        emit OfferCreated(id, OfferType.S, msg.sender, to, msg.value, nonce);
    }

    /// @notice Create a gated offer (G). Redeem needs the PIN. Not sendable.
    /// @param  to             Holder. address(0) means DEAD. Not this contract.
    /// @param  delayBlocks    Blocks until sweepable. 0 means DEFAULT_DELAY (1), which makes it a gate offer.
    /// @param  pinCommitment_ keccak256(abi.encode(pin, donor, to)). Must be non-zero. Use the final `to`.
    /// @param  expectedNonce  Caller's current redeemNonce.
    function createOfferGated(address to, uint256 delayBlocks, bytes32 pinCommitment_, uint256 expectedNonce) external payable onlyDelegateCall nonReentrant {
        uint256 nonce = _useNonce(expectedNonce);
        if (pinCommitment_ == bytes32(0)) revert InvalidValue();
        to = _receiver(to);
        uint256 id = _storeOffer(OfferType.G, to, delayBlocks, pinCommitment_);
        emit OfferCreated(id, OfferType.G, msg.sender, to, msg.value, nonce);
    }

    /// @notice Create an open A offer. Any seller can confirm records, first come first served.
    ///         The receiver is this contract.
    /// @param  delayBlocks     Blocks until sweepable. 0 means DEFAULT_DELAY (1).
    /// @param  slicesPerRecord Slices paid per confirmed record. At least 1, no maximum.
    ///                         The funded slices must divide exactly by it.
    /// @param  expectedNonce   Caller's current redeemNonce.
    function createOfferA(uint256 delayBlocks, uint256 slicesPerRecord, uint256 expectedNonce) external payable onlyDelegateCall nonReentrant {
        uint256 nonce = _useNonce(expectedNonce);
        uint256 id = _storeSale(OfferType.A, address(this), delayBlocks, slicesPerRecord);
        emit OfferCreated(id, OfferType.A, msg.sender, address(this), msg.value, nonce);
        _announceSale(id, nonce);
    }

    /// @notice Create a named B offer. Only `to` can confirm records.
    /// @param  to              Exact seller. address(0) means DEAD (nobody can confirm). Not this contract.
    /// @param  delayBlocks     Blocks until sweepable. 0 means DEFAULT_DELAY (1).
    /// @param  slicesPerRecord Slices paid per confirmed record. At least 1, no maximum.
    /// @param  expectedNonce   Caller's current redeemNonce.
    function createOfferB(address to, uint256 delayBlocks, uint256 slicesPerRecord, uint256 expectedNonce) external payable onlyDelegateCall nonReentrant {
        uint256 nonce = _useNonce(expectedNonce);
        to = _receiver(to);
        uint256 id = _storeSale(OfferType.B, to, delayBlocks, slicesPerRecord);
        emit OfferCreated(id, OfferType.B, msg.sender, to, msg.value, nonce);
        _announceSale(id, nonce);
    }

    /// @notice Confirm up to `n` of the caller's next records for offer `id`.
    ///         Each record must already exist on the SOS ledger with signer = caller,
    ///         intendedTo = the offer creator, metadata = "" and payloadHash = recordPayloadHash(...).
    ///         Each confirmed record moves `slicesPerRecord` slices into the caller's own offer.
    ///         If fewer than `n` records are still wanted, only those are confirmed.
    /// @param  id            Offer id of an A or B offer.
    /// @param  n             Number of records to confirm (>= 1). Reverts if any of them is not on the ledger.
    /// @param  expectedNonce Caller's current redeemNonce.
    /// @return taken Records actually confirmed.
    function syncRecords(uint256 id, uint256 n, uint256 expectedNonce) external onlyDelegateCall nonReentrant returns (uint256 taken) {
        uint256 nonce = _useNonce(expectedNonce);

        Sale storage s = _sales[id];
        if (!s.active) revert OfferNotActive();
        if (block.number >= s.sweepableAt) revert WindowClosed();
        if (s.kind == OfferType.B && msg.sender != s.target) revert NotHolder();
        if (n == 0) revert ZeroAmount();
        if (SOS69069_LEDGER.code.length == 0) revert LedgerMissing();

        uint256 slices;
        (taken, slices) = _confirm(id, s, n);
        (uint256 oid, uint256 held) = _grant(id, s, msg.sender, slices);

        emit RecordsSynced(id, msg.sender, taken, slices, oid, held, nonce);
        if (!s.active) emit SaleFilled(id, msg.sender, nonce);
    }

    /// @notice Transfer a whole S offer. Only while more than MIN_SEND_WINDOW blocks remain.
    /// @param  id            Offer id.
    /// @param  to            New holder.
    /// @param  expectedNonce Caller's current redeemNonce.
    function transferOffer(uint256 id, address to, uint256 expectedNonce) external onlyDelegateCall nonReentrant {
        uint256 nonce = _useNonce(expectedNonce);
        uint256 amount = _offers[id].count;
        _move(id, to, amount, nonce);
        emit Transfer(msg.sender, to, amount);
    }

    /// @notice Transfer `slices` slices of an S offer. If fewer than all, the offer is split:
    ///         the caller keeps the rest and `to` receives a NEW offer id (same expiry).
    /// @param  id            Offer id.
    /// @param  slices        Slices to send (>= 1, <= the offer's remaining slices).
    /// @param  to            New holder.
    /// @param  expectedNonce Caller's current redeemNonce.
    function transferSlices(uint256 id, uint256 slices, address to, uint256 expectedNonce) external onlyDelegateCall nonReentrant {
        uint256 nonce = _useNonce(expectedNonce);
        _move(id, to, slices, nonce);
        emit Transfer(msg.sender, to, slices);
    }

    /// @notice Redeem a whole offer (all its remaining slices) before its expiry block.
    /// @dev    G needs the PIN. A and B are capped by the caller's allowance. S and G are not.
    /// @param  id            Offer id.
    /// @param  pin           PIN preimage; only meaningful for G offers.
    /// @param  expectedNonce Caller's current redeemNonce.
    function redeemOffer(uint256 id, bytes32 pin, uint256 expectedNonce) external onlyDelegateCall nonReentrant {
        uint256 nonce = _useNonce(expectedNonce);
        (address donor, uint256 eth) = _redeem(id, _offers[id].count, pin, nonce);
        emit OfferRedeemed(id, donor, msg.sender, eth, nonce);
        _send(msg.sender, eth);
    }

    /// @notice Redeem `slices` slices of an offer for `slices * UNIT` ETH before its expiry block.
    ///         The rest stays with the holder (same id, same expiry).
    /// @param  id            Offer id.
    /// @param  slices        Number of slices to redeem (>= 1, <= remaining).
    /// @param  pin           PIN preimage; only meaningful for G offers.
    /// @param  expectedNonce Caller's current redeemNonce.
    function redeemSlices(uint256 id, uint256 slices, bytes32 pin, uint256 expectedNonce) external onlyDelegateCall nonReentrant {
        uint256 nonce = _useNonce(expectedNonce);
        (address donor, uint256 eth) = _redeem(id, slices, pin, nonce);
        emit OfferRedeemed(id, donor, msg.sender, eth, nonce);
        _send(msg.sender, eth);
    }

    /// @notice Sweep an expired offer into the pool. Callable by anyone once `block.number >= sweepableAt`.
    /// @dev    Works for every type. For an A/B escrow the unconfirmed ETH goes to the pool (never back to
    ///         the creator). For a held offer the unredeemed slices go to the pool. If the offer was a gate
    ///         offer, the donor is permanently staked. No ETH is sent, so this cannot be blocked.
    /// @param  id            Offer id.
    /// @param  expectedNonce Caller's current redeemNonce.
    function sweepOffer(uint256 id, uint256 expectedNonce) external onlyDelegateCall nonReentrant {
        uint256 nonce = _useNonce(expectedNonce);

        Sale storage s = _sales[id];
        if (s.donor != address(0)) {
            _sweepSale(id, s, nonce);
            return;
        }

        Offer storage o = _offers[id];
        if (!o.active) revert OfferNotActive();
        if (block.number < o.sweepableAt) revert TooEarly();

        address donor = o.donor;
        address holder = o.holder;
        uint256 cnt = o.count;

        if (o.isGate) {
            staked[donor] = true;
            stakedAt[donor] = uint64(block.number);
            delete o.isGate;
            emit Staked(donor, uint64(block.number));
        }

        o.active = false;
        totalEarmarked -= cnt * UNIT;
        totalSupply -= cnt;
        _slices[holder] -= cnt;
        _pop(holder, o.index);
        delete offerPinCommitment[id];

        emit Transfer(holder, address(0), cnt);
        emit OfferSwept(id, donor, holder, cnt * UNIT, msg.sender, nonce);
    }

    /// @dev Default receiver is DEAD. This contract is never a valid S, B or G receiver.
    function _receiver(address to) private view returns (address) {
        if (to == address(0)) return DEAD;
        if (to == address(this)) revert BadTarget();
        return to;
    }

    /// @dev Validates value and delay. Returns the slice count and the expiry block.
    ///      `delayBlocks` must already be normalised (non-zero).
    function _checkValueDelay(uint256 delayBlocks) private view returns (uint256 cnt, uint256 sweepable) {
        if (msg.value == 0 || msg.value % UNIT != 0) revert InvalidValue();
        cnt = msg.value / UNIT;
        if (cnt > type(uint64).max) revert InvalidValue();

        sweepable = block.number + delayBlocks;
        if (sweepable > type(uint32).max) revert BadDelay();
    }

    /// @dev Store an S or G offer: slices are held by `to` from the start.
    function _storeOffer(OfferType kind, address to, uint256 delayBlocks, bytes32 pinC) private returns (uint256 id) {
        if (delayBlocks == 0) delayBlocks = DEFAULT_DELAY;
        (uint256 cnt, uint256 sweepable) = _checkValueDelay(delayBlocks);

        id = nextOfferId++;

        _offers[id] = Offer({
            holder: to,
            count: uint64(cnt),
            active: true,
            isGate: false,
            kind: kind,
            donor: msg.sender,
            index: _push(to, id),
            createdAt: uint32(block.number),
            sweepableAt: uint32(sweepable)
        });
        totalEarmarked += msg.value;
        totalSupply += cnt;
        _slices[to] += cnt;
        emit Transfer(address(0), to, cnt);

        if (kind == OfferType.G && delayBlocks == GATE_DELAY) {
            bool isGate = msg.value > GATE_FLOOR + unallocatedBalance();
            if (isGate) {
                _offers[id].isGate = true;
            }
            emit GateFlagged(id, isGate);
        }

        if (kind == OfferType.G) offerPinCommitment[id] = pinC;
    }

    /// @dev Store an A or B escrow. The escrow slices are minted to this contract; they move to a seller
    ///      when records are confirmed.
    function _storeSale(OfferType kind, address target, uint256 delayBlocks, uint256 perRecord) private returns (uint256 id) {
        if (delayBlocks == 0) delayBlocks = DEFAULT_DELAY;
        (uint256 cnt, uint256 sweepable) = _checkValueDelay(delayBlocks);
        if (perRecord == 0 || perRecord > cnt || cnt % perRecord != 0) revert BadRate();

        id = nextOfferId++;

        Sale storage s = _sales[id];
        s.donor       = msg.sender;
        s.slicesLeft  = uint64(cnt);
        s.active      = true;
        s.kind        = kind;
        s.target      = target;
        s.perRecord   = uint64(perRecord);
        s.createdAt   = uint32(block.number);
        s.sweepableAt = uint32(sweepable);
        s.salt        = keccak256(abi.encode(blockhash(block.number - 1), id, msg.sender));

        totalEarmarked += msg.value;
        totalSupply += cnt;
        _slices[address(this)] += cnt;
        produced[msg.sender] += cnt;
        emit Transfer(address(0), address(this), cnt);
    }

    /// @dev Emit the A/B specific events right after creation.
    function _announceSale(uint256 id, uint256 nonce) private {
        Sale storage s = _sales[id];
        emit SaleOpened(id, s.donor, s.perRecord, uint256(s.slicesLeft) / s.perRecord, s.salt, nonce);
        emit AllowanceUpdated(s.donor, produced[s.donor], redeemed[s.donor], nonce);
    }

    /// @dev Verify the caller's next records on the ledger and update the escrow and the caller's index.
    function _confirm(uint256 id, Sale storage s, uint256 n) private returns (uint256 taken, uint256 slices) {
        uint256 per = s.perRecord;
        taken = uint256(s.slicesLeft) / per; // records still wanted
        if (taken == 0) revert OfferFull();
        if (n < taken) taken = n;

        uint256 start = nextRecord[id][msg.sender];
        _verifyRecords(id, s.salt, s.donor, msg.sender, start, taken);
        nextRecord[id][msg.sender] = start + taken;

        slices = taken * per;
        s.slicesLeft -= uint64(slices);
        if (s.slicesLeft == 0) s.active = false;
    }

    /// @dev Reverts unless records `start .. start+count-1` of `seller` for this offer exist on the ledger.
    function _verifyRecords(
        uint256 id,
        bytes32 salt,
        address donor,
        address seller,
        uint256 start,
        uint256 count
    ) private view {
        for (uint256 i; i < count; ++i) {
            bytes32 ph = _recordPayload(id, salt, seller, start + i);
            bytes32 sh = SOS.recordStructHash(seller, donor, ph, "");
            if (!SOS.isRecordHashUsed(sh)) revert RecordNotFound();
        }
    }

    /// @dev Move `slices` from the escrow (held by this contract) into the seller's earned offer
    ///      (merge if still active, else create). Returns the earned offer id and the slices it now holds.
    function _grant(uint256 saleId, Sale storage s, address seller, uint256 slices) private returns (uint256 oid, uint256 held) {
        oid = earnedOffer[saleId][seller];
        if (oid != 0 && _offers[oid].active) {
            _offers[oid].count += uint64(slices);
        } else {
            oid = nextOfferId++;
            _offers[oid] = Offer({
                holder: seller,
                count: uint64(slices),
                active: true,
                isGate: false,
                kind: s.kind,
                donor: s.donor,
                index: _push(seller, oid),
                createdAt: s.createdAt,
                sweepableAt: s.sweepableAt
            });
            earnedOffer[saleId][seller] = oid;
        }
        held = _offers[oid].count;

        _slices[address(this)] -= slices;
        _slices[seller] += slices;
        emit Transfer(address(this), seller, slices);
    }

    /// @dev Redeem `amount` slices of offer `id` for msg.sender. Updates all state; the caller pays out.
    function _redeem(uint256 id, uint256 amount, bytes32 pin, uint256 nonce) private returns (address donor, uint256 ethAmount) {
        Offer storage o = _offers[id];
        if (!o.active) revert OfferNotActive();
        if (o.holder != msg.sender) revert NotHolder();
        if (block.number >= o.sweepableAt) revert WindowClosed();
        if (amount == 0) revert ZeroAmount();

        uint256 have = o.count;
        if (amount > have) revert InsufficientSlices();
        donor = o.donor;

        if (o.kind == OfferType.G) {
            bytes32 expected = offerPinCommitment[id];
            if (expected == bytes32(0) || keccak256(abi.encode(pin, donor, msg.sender)) != expected) {
                revert BadOfferPin();
            }
        } else if (o.kind != OfferType.S) {
            // A or B: redeemed total may never exceed produced total.
            uint256 used = redeemed[msg.sender] + amount;
            if (used > produced[msg.sender]) revert OverCap();
            redeemed[msg.sender] = used;
            emit AllowanceUpdated(msg.sender, produced[msg.sender], used, nonce);
        }

        if (o.isGate) {
            delete o.isGate;
        }

        if (amount == have) {
            o.active = false;
            _pop(msg.sender, o.index);
            delete offerPinCommitment[id];
        } else {
            o.count = uint64(have - amount);
        }

        ethAmount = amount * UNIT;
        totalEarmarked -= ethAmount;
        totalSupply -= amount;
        _slices[msg.sender] -= amount;
        emit Transfer(msg.sender, address(0), amount);
    }

    /// @dev Release the unconfirmed part of an A/B escrow into the pool and burn its slices.
    function _sweepSale(uint256 id, Sale storage s, uint256 nonce) private {
        if (!s.active) revert OfferNotActive();
        if (block.number < s.sweepableAt) revert TooEarly();

        uint256 left = s.slicesLeft;
        s.active = false;
        s.slicesLeft = 0;
        totalEarmarked -= left * UNIT;
        totalSupply -= left;
        _slices[address(this)] -= left;

        emit Transfer(address(this), address(0), left);
        emit OfferSwept(id, s.donor, address(this), left * UNIT, msg.sender, nonce);
    }
}
