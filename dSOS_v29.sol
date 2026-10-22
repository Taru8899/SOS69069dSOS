// SPDX-License-Identifier: MIT
pragma solidity 0.8.36;

/// @title ISOS69069
/// @notice Minimal interface to the SOS69069 ledger used by dSOS for trust records.
interface ISOS69069 {
    /// @notice Records one verified EIP-712 signature on the ledger.
    function recordSignature(address signer, address intendedTo, bytes32 payloadHash, bytes calldata signature, string calldata metadata) external;

    /// @notice Computes the EIP-712 struct hash for a given record.
    function recordStructHash(address signer, address intendedTo, bytes32 payloadHash, string calldata metadata) external pure returns (bytes32);

    /// @notice Trust − Push, computed live by the ledger.
    function effectiveOf(address user) external view returns (int256);

    /// @notice Number of times `user` appears as `intendedTo`.
    function trustCountOf(address user) external view returns (uint256);

    /// @notice Convenience view: push, trust, effective.
    function statsOf(address user) external view returns (uint256 pushCount, uint256 trustCount, int256 effective);
}

/// @title SOS69069 dSOS
/// @notice Shared ETH pool with gated staking and simple credit redemption.
///
/// UNIT
///   1 credit = 0.001 ETH. 1 slice = 0.001 ETH. 1 dSOS = 1 slice.
///
/// OFFERS AND SLICES (quantity batches)
///   An offer is ONE stored record holding `count` slices. Creating it costs about the same gas
///   whether it holds 1 slice or 5000. `msg.value` must be an exact multiple of UNIT (0.001 ETH);
///   count = msg.value / UNIT. Any other value (including anything below 0.001 ETH) reverts
///   InvalidValue.
///   Slices of one offer share the same donor, type, expiry (`sweepableAt`) and ledger record.
///   B/T/P slices are transferable. G slices are non-transferable and PIN-protected.
///   A holder may redeem or send a whole offer, or only some of its slices.
///   Sending part of an offer splits it: the sender keeps the rest, the recipient gets a NEW offer
///   id with the sent slices and the same expiry.
///   Delay: `sweepableAt` is stored as uint32, so block.number + delayBlocks must fit in uint32.
///
/// GATE
///   A G offer with delay == 1 and total value > (0.001 ETH + current unallocatedBalance)
///   is a gate offer. When swept, the donor becomes permanently staked.
///   Redeeming any part of a gate offer clears its gate flag (the donor does NOT become staked).
///   Because offers are whole multiples of UNIT, `stakeRequirement()` is the smallest multiple of
///   0.001 ETH that is strictly greater than the gate requirement.
///   New stakers wait 14400 blocks before their first credit redemption.
///
/// CREDITS
///   Credits = pending SOS trust records (1 trust record = 1 credit).
///   Only staked users can form and redeem credits.
///   Credits cannot be transferred.
///
/// ERC-20 VIEW (display only)
///   1 dSOS = 1 slice = 0.001 ETH (decimals 0). Mint on create, burn on redeem/sweep, move on send.
///   `totalSupply` = number of active slices; `balanceOf(a)` = number of active slices held by a.
///   ETH value behind a balance = balanceOf(a) * 0.001 ETH, redeemable only before each offer's
///   `sweepableAt`; after that anyone can sweep the offer into the pool and the slices are burned.
///   `transfer(to, n)` sends exactly `n` slices (B/T/P only, with MORE than MIN_SEND_WINDOW blocks
///   left before expiry), taking from the sender's newest offers first and splitting an offer
///   when needed. Every slice is worth the
///   same, so the wallet send is exact: send 5 dSOS = send 0.005 ETH of redeemable value.
///   Not sendable by wallet: G slices, and slices of any offer with MIN_SEND_WINDOW (7200 blocks,
///   about one day) or fewer blocks left. A recipient therefore always gets slices with more than
///   that long left to redeem. To make an offer wallet-sendable, create it with
///   delayBlocks > MIN_SEND_WINDOW. `transferSlices` / `transferOffer` (by offer id) are not
///   limited by this window. Reverts NotEnoughSendable if fewer than `n` sendable slices.
///   A wallet send carries no ledger signature, so it writes no SOS record. Use `transferSlices`
///   or `transferOffer` with a signature if you want the record.
///   `approve` / `transferFrom` are not supported.
///   A wallet cannot create offers. Use the dApp or the Write Contract tab (createOffer /
///   createOfferGated). A plain ETH transfer to this contract is a donation, not an offer.
///   The recipient must redeem before `sweepableAt`; afterwards anyone can sweep the offer.
///
/// FALLBACKS
///   When the SOS ledger has no code at its address (local tests, forks without
///   the ledger deployed), `_structHash` falls back to a local keccak and
///   `_record` is skipped.
contract dSOS {

    // ---------------------------------------------------------------------
    // CONSTANTS
    // ---------------------------------------------------------------------

    /// @notice Canonical SOS69069 ledger address.
    address public constant SOS69069_LEDGER = 0x7373DBC24Dcd785896E8Ac3d5372c6ced9B75a8A;

    /// @notice Typed reference to the ledger.
    ISOS69069 public constant SOS = ISOS69069(SOS69069_LEDGER);

    /// @notice ETH value of one credit and of one slice / one dSOS (0.001 ETH).
    uint256 public constant UNIT           = 0.001 ether;

    /// @notice Minimum ETH the pool must retain after any credit payout.
    uint256 public constant MIN_RESERVE    = 0.000999 ether;

    /// @notice Applied when a caller passes `delayBlocks == 0`.
    uint256 public constant DEFAULT_DELAY  = 1;

    /// @notice Base value added to `unallocatedBalance()` to compute the gate requirement.
    uint256 public constant GATE_FLOOR     = 0.001 ether;

    /// @notice Required delay for a G offer to be eligible as a gate offer.
    uint256 public constant GATE_DELAY     = 1;

    /// @notice Blocks a new staker must wait before redeeming credits.
    uint256 public constant STAKE_COOLDOWN = 14400;

    /// @notice A wallet `transfer` only moves slices of offers that have MORE than this many
    ///         blocks left before `sweepableAt` (7200 blocks is about one day).
    uint256 public constant MIN_SEND_WINDOW = 7200;

    // ---------------------------------------------------------------------
    // ERRORS
    // ---------------------------------------------------------------------

    error ZeroAddress();
    error ZeroAmount();
    error InvalidValue();
    error OfferNotActive();
    error NotHolder();
    error NoCredit();
    error InsufficientCredits();
    error InsufficientSlices();
    error PoolTooThin();
    error TransferFailed();
    error Reentrant();
    error TooManyOffers();
    error SelfTransfer();
    error NotTransferable();
    error BadOfferPin();
    error TooEarly();
    error WindowClosed();
    error BadDelay();
    error BadRedeemHash();
    error NotStaked();
    error NotEnoughSendable();

    // ---------------------------------------------------------------------
    // TYPES
    // ---------------------------------------------------------------------

    /// @notice Offer kinds. G = gated, B/T/P = transferable non-gated.
    enum OfferType { G, B, T, P }

    /// @notice Offer record (one batch of `count` slices). Packed into 3 storage slots.
    struct Offer {
        address   holder;       // slot 0
        uint64    count;        // slot 0  remaining slices
        bool      active;       // slot 0
        bool      isGate;       // slot 0
        OfferType kind;         // slot 0
        address   donor;        // slot 1
        uint32    index;        // slot 1  position in offersHeldBy[holder]
        uint32    createdAt;    // slot 1
        uint32    sweepableAt;  // slot 1
        bytes32   recordHash;   // slot 2
    }

    /// @notice Per-account credit state.
    struct Account {
        uint256 lastTrust;
        uint256 credits;
    }

    /// @notice Signature envelope for redeem / partial functions.
    struct Rec {
        bytes32 payloadHash;
        bytes   signature;
        string  metadata;
    }

    // ---------------------------------------------------------------------
    // STORAGE
    // ---------------------------------------------------------------------

    mapping(uint256 => Offer)     private _offers;
    mapping(uint256 => bytes32)   public  offerPinCommitment;
    mapping(address => bool)      public  staked;
    mapping(address => uint64)    public  stakedAt;
    mapping(address => Account)   private _acct;
    mapping(address => uint256[]) public  offersHeldBy;
    mapping(address => uint256)   private _slices;

    uint64  public nextOfferId = 1;
    bool    private _locked;
    uint256 public totalEarmarked;
    uint256 public totalSupply;

    mapping(address => uint256) public redeemNonce;

    // ---------------------------------------------------------------------
    // EVENTS
    // ---------------------------------------------------------------------

    /// @dev `principal` is the total ETH of the batch (count * UNIT).
    event OfferCreated(uint256 indexed id, OfferType kind, address indexed donor, address indexed to, uint256 principal);
    event OfferTransferred(uint256 indexed id, address indexed from, address indexed to);
    /// @dev Emitted when part of offer `id` is sent: `newId` is the recipient's new offer.
    event OfferSplit(uint256 indexed id, uint256 indexed newId, uint256 slices);
    /// @dev `principal` is the ETH paid out by this redeem (slices * UNIT).
    event OfferRedeemed(uint256 indexed id, address indexed donor, address indexed holder, uint256 principal);
    /// @dev `principal` is the ETH of the remaining batch moved into the pool.
    event OfferSwept(uint256 indexed id, address indexed donor, address indexed holder, uint256 principal);
    event Donation(address indexed from, uint256 amount);
    event CreditsFormed(address indexed user, uint256 formed, uint256 credits);
    event CreditRedeemed(address indexed user, uint256 creditsSpent, uint256 ethPaid);
    event LedgerRecordSkipped(address indexed signer, address indexed intendedTo, bytes32 payloadHash, bytes reason);
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

    // ---------------------------------------------------------------------
    // FUNDING
    // ---------------------------------------------------------------------

    /// @notice Plain ETH transfer. Adds to the pool (unallocated balance).
    receive() external payable nonReentrant {
        if (msg.value > 0) {
            emit Donation(msg.sender, msg.value);
        }
    }

    // ---------------------------------------------------------------------
    // OFFERS: CREATE
    // ---------------------------------------------------------------------

    /// @notice Create a transferable offer (B=1, T=2, P=3) of `msg.value / UNIT` slices.
    /// @dev    `msg.value` must be a non-zero exact multiple of UNIT (0.001 ETH).
    ///         One stored record regardless of the slice count. Never yields credits.
    /// @param  kind        Must be B, T or P (G reverts with InvalidValue).
    /// @param  to          Recipient/holder. Must be non-zero.
    /// @param  delayBlocks Blocks until sweepable. 0 → DEFAULT_DELAY.
    /// @param  payloadHash Caller-supplied payload hash for the ledger record.
    /// @param  signature   EIP-712 signature for the ledger record.
    /// @param  metadata    Free-form metadata (ledger-limited).
    function createOffer(
        OfferType kind,
        address to,
        uint256 delayBlocks,
        bytes32 payloadHash,
        bytes calldata signature,
        string calldata metadata
    ) external payable nonReentrant {
        if (kind == OfferType.G) revert InvalidValue();

        bytes32 rh = _structHash(msg.sender, to, payloadHash, metadata);
        uint256 id = _storeOffer(kind, to, delayBlocks, bytes32(0), rh);

        _record(msg.sender, to, payloadHash, signature, metadata);
        emit OfferCreated(id, kind, msg.sender, to, msg.value);
    }

    /// @notice Create a gated offer (G=0) of `msg.value / UNIT` slices. Non-transferable;
    ///         redeem requires the PIN. All slices share the one PIN commitment.
    /// @dev    `msg.value` must be a non-zero exact multiple of UNIT (0.001 ETH).
    /// @param  to              Recipient/holder.
    /// @param  delayBlocks     Blocks until sweepable. 0 → DEFAULT_DELAY.
    /// @param  pinCommitment_  keccak256(abi.encode(pin, donor, to)). Must be non-zero.
    /// @param  payloadHash     Caller-supplied payload hash for the ledger record.
    /// @param  signature       EIP-712 signature for the ledger record.
    /// @param  metadata        Free-form metadata (ledger-limited).
    function createOfferGated(
        address to,
        uint256 delayBlocks,
        bytes32 pinCommitment_,
        bytes32 payloadHash,
        bytes calldata signature,
        string calldata metadata
    ) external payable nonReentrant {
        if (pinCommitment_ == bytes32(0)) revert InvalidValue();

        bytes32 rh = _structHash(msg.sender, to, payloadHash, metadata);
        uint256 id = _storeOffer(OfferType.G, to, delayBlocks, pinCommitment_, rh);

        _record(msg.sender, to, payloadHash, signature, metadata);
        emit OfferCreated(id, OfferType.G, msg.sender, to, msg.value);
    }

    /// @dev    Internal: store one batch offer, earmark its ETH, mark gate if eligible.
    function _storeOffer(
        OfferType kind,
        address to,
        uint256 delayBlocks,
        bytes32 pinC,
        bytes32 rh
    ) private returns (uint256 id) {
        if (to == address(0)) revert ZeroAddress();
        if (msg.value == 0 || msg.value % UNIT != 0) revert InvalidValue();
        uint256 cnt = msg.value / UNIT;
        if (cnt > type(uint64).max) revert InvalidValue();

        if (delayBlocks == 0) delayBlocks = DEFAULT_DELAY;
        uint256 sweepable = block.number + delayBlocks;
        if (sweepable > type(uint32).max) revert BadDelay();

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
            sweepableAt: uint32(sweepable),
            recordHash: rh
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

    // ---------------------------------------------------------------------
    // OFFERS: TRANSFER
    // ---------------------------------------------------------------------

    /// @notice Transfer a whole B/T/P offer (all its remaining slices). G is not transferable.
    /// @param  id          Offer id.
    /// @param  to          New holder. Must be non-zero and not the caller.
    /// @param  payloadHash Caller-supplied payload hash for the ledger record.
    /// @param  signature   EIP-712 signature for the ledger record.
    /// @param  metadata    Free-form metadata.
    function transferOffer(
        uint256 id,
        address to,
        bytes32 payloadHash,
        bytes calldata signature,
        string calldata metadata
    ) external nonReentrant {
        uint256 amount = _offers[id].count;
        _move(id, to, amount);

        _record(msg.sender, to, payloadHash, signature, metadata);
        emit Transfer(msg.sender, to, amount);
    }

    /// @notice Transfer `slices` slices of a B/T/P offer. If fewer than all, the offer is split:
    ///         the caller keeps the rest and `to` receives a NEW offer id (same expiry).
    /// @param  id     Offer id.
    /// @param  slices Number of slices to send (≥ 1, ≤ the offer's remaining slices).
    /// @param  to     New holder. Must be non-zero and not the caller.
    /// @param  r      Ledger record envelope (payloadHash, signature, metadata).
    function transferSlices(uint256 id, uint256 slices, address to, Rec calldata r) external nonReentrant {
        _move(id, to, slices);

        _record(msg.sender, to, r.payloadHash, r.signature, r.metadata);
        emit Transfer(msg.sender, to, slices);
    }

    /// @dev    Move `amount` slices of offer `id` from msg.sender to `to` (whole offer or split).
    ///         Does not emit the ERC-20 Transfer event; callers do.
    function _move(uint256 id, address to, uint256 amount) private {
        Offer storage o = _offers[id];
        if (!o.active) revert OfferNotActive();
        if (o.holder != msg.sender) revert NotHolder();
        if (o.kind == OfferType.G) revert NotTransferable();
        if (block.number >= o.sweepableAt) revert WindowClosed();
        if (to == address(0)) revert ZeroAddress();
        if (to == msg.sender) revert SelfTransfer();
        if (amount == 0) revert ZeroAmount();

        uint256 have = o.count;
        if (amount > have) revert InsufficientSlices();

        if (amount == have) {
            _pop(msg.sender, o.index);
            o.index = _push(to, id);
            o.holder = to;
            emit OfferTransferred(id, msg.sender, to);
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
                sweepableAt: o.sweepableAt,
                recordHash: o.recordHash
            });
            emit OfferSplit(id, nid, amount);
            emit OfferTransferred(nid, msg.sender, to);
        }

        _slices[msg.sender] -= amount;
        _slices[to] += amount;
    }

    // ---------------------------------------------------------------------
    // OFFERS: REDEEM / SWEEP
    // ---------------------------------------------------------------------

    /// @notice Redeem a whole offer (all its remaining slices) inside the redeem window.
    /// @dev    For G, the PIN must hash to `offerPinCommitment[id]`.
    ///         `isGate` is cleared on redeem (donor does NOT become staked).
    /// @param  id          Offer id.
    /// @param  pin         PIN preimage; only meaningful for G offers.
    /// @param  payloadHash Caller-supplied payload hash for the ledger record.
    /// @param  signature   EIP-712 signature for the ledger record.
    /// @param  metadata    Free-form metadata.
    function redeemOffer(
        uint256 id,
        bytes32 pin,
        bytes32 payloadHash,
        bytes calldata signature,
        string calldata metadata
    ) external nonReentrant {
        (address donor, uint256 eth) = _redeem(id, _offers[id].count, pin);

        _record(msg.sender, donor, payloadHash, signature, metadata);
        emit OfferRedeemed(id, donor, msg.sender, eth);
        _send(msg.sender, eth);
    }

    /// @notice Redeem `slices` slices of an offer for `slices * UNIT` ETH inside the redeem window.
    ///         The rest of the offer stays with the holder (same id, same expiry).
    /// @param  id     Offer id.
    /// @param  slices Number of slices to redeem (≥ 1, ≤ remaining).
    /// @param  pin    PIN preimage; only meaningful for G offers.
    /// @param  r      Ledger record envelope (payloadHash, signature, metadata).
    function redeemSlices(uint256 id, uint256 slices, bytes32 pin, Rec calldata r) external nonReentrant {
        (address donor, uint256 eth) = _redeem(id, slices, pin);

        _record(msg.sender, donor, r.payloadHash, r.signature, r.metadata);
        emit OfferRedeemed(id, donor, msg.sender, eth);
        _send(msg.sender, eth);
    }

    /// @dev    Redeem `amount` slices of offer `id` for msg.sender. Updates all state; the
    ///         caller records on the ledger and pays out `ethAmount`.
    function _redeem(uint256 id, uint256 amount, bytes32 pin) private returns (address donor, uint256 ethAmount) {
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

    /// @notice Sweep an expired offer. Its remaining ETH becomes unallocated.
    /// @dev    If the offer was a gate offer, the donor is permanently staked
    ///         and a `Staked` event is emitted.
    /// @param  id Offer id. Callable by anyone once `block.number >= sweepableAt`.
    function sweepOffer(uint256 id) external nonReentrant {
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
        emit OfferSwept(id, donor, holder, cnt * UNIT);
    }

    // ---------------------------------------------------------------------
    // CREDITS
    // ---------------------------------------------------------------------

    /// @notice Form credits from the caller's pending SOS trust records.
    /// @dev    Requires `staked[msg.sender]`. One trust record = one credit.
    function syncCredits() external returns (uint256 formed) {
        if (!staked[msg.sender]) revert NotStaked();
        formed = _form(msg.sender);
    }

    /// @notice Redeem `creditsToSpend` credits for ETH at `UNIT` per credit.
    /// @dev    Requires: staked, cooldown passed, enough credits, valid signature,
    ///         and `balance >= totalEarmarked + MIN_RESERVE + creditsToSpend*UNIT`.
    /// @param  creditsToSpend Number of credits to burn (≥ 1).
    /// @param  r              Signature envelope binding payloadHash to nonce.
    function redeemCredit(uint256 creditsToSpend, Rec calldata r) external nonReentrant {
        if (!staked[msg.sender]) revert NotStaked();
        if (block.number < uint256(stakedAt[msg.sender]) + STAKE_COOLDOWN) revert TooEarly();
        if (creditsToSpend == 0) revert ZeroAmount();

        _form(msg.sender);

        Account storage a = _acct[msg.sender];
        if (a.credits < creditsToSpend) revert InsufficientCredits();

        uint256 ethAmount = creditsToSpend * UNIT;
        if (r.payloadHash != _redeemHash(msg.sender, 0, ethAmount)) revert BadRedeemHash();

        if (address(this).balance < totalEarmarked + MIN_RESERVE + ethAmount) revert PoolTooThin();

        a.credits -= creditsToSpend;
        redeemNonce[msg.sender] += 1;

        _record(msg.sender, SOS69069_LEDGER, r.payloadHash, r.signature, r.metadata);
        emit CreditRedeemed(msg.sender, creditsToSpend, ethAmount);
        _send(msg.sender, ethAmount);
    }

    // ---------------------------------------------------------------------
    // VIEWS
    // ---------------------------------------------------------------------

    /// @notice Full read of an offer. `principal` = remaining slices * UNIT (ETH still behind it).
    function offers(uint256 id) external view returns (
        address donor,
        address holder,
        uint256 principal,
        bool active,
        OfferType kind,
        bytes32 recordHash,
        uint64 createdAt,
        uint64 sweepableAt,
        uint256 count
    ) {
        Offer storage o = _offers[id];
        return (
            o.donor, o.holder, uint256(o.count) * UNIT, o.active, o.kind,
            o.recordHash, o.createdAt, o.sweepableAt, o.count
        );
    }

    /// @notice IDs of offers held by `holder` whose sweep window is open.
    function sweepableOffers(address holder) external view returns (uint256[] memory ids) {
        uint256[] storage all = offersHeldBy[holder];
        uint256 n;
        for (uint256 i; i < all.length; ++i) {
            if (_offers[all[i]].active && block.number >= uint256(_offers[all[i]].sweepableAt)) ++n;
        }
        ids = new uint256[](n);
        uint256 j;
        for (uint256 i; i < all.length; ++i) {
            if (_offers[all[i]].active && block.number >= uint256(_offers[all[i]].sweepableAt)) {
                ids[j++] = all[i];
            }
        }
    }

    /// @notice Last `trustCountOf` snapshot consumed by `_form`.
    function lastTrust(address user) external view returns (uint256) {
        return _acct[user].lastTrust;
    }

    /// @notice Credits currently held by `user`.
    function redemptionCredits(address user) external view returns (uint256) {
        return _acct[user].credits;
    }

    /// @notice Pool balance not earmarked for outstanding offers.
    function unallocatedBalance() public view returns (uint256) {
        uint256 bal = address(this).balance;
        return bal > totalEarmarked ? bal - totalEarmarked : 0;
    }

    /// @notice Current gate requirement (the offer total must be strictly greater).
    function gateRequirement() external view returns (uint256) {
        return GATE_FLOOR + unallocatedBalance();
    }

    /// @notice Exact `msg.value` of the cheapest gate offer: the smallest multiple of UNIT
    ///         strictly greater than the gate requirement.
    function stakeRequirement() external view returns (uint256) {
        return ((GATE_FLOOR + unallocatedBalance()) / UNIT + 1) * UNIT;
    }

    /// @notice Whether `user` can call `redeemCredit` now.
    function canRedeem(address user) external view returns (bool) {
        if (!staked[user]) return false;
        return block.number >= uint256(stakedAt[user]) + STAKE_COOLDOWN;
    }

    /// @notice Raw ETH balance held by this contract.
    function poolBalance() external view returns (uint256) {
        return address(this).balance;
    }

    /// @notice Unused SOS trust records that could be formed into credits.
    function formableCredits(address user) public view returns (uint256) {
        uint256 t = SOS.trustCountOf(user);
        uint256 last = _acct[user].lastTrust;
        return t > last ? t - last : 0;
    }

    /// @notice Total credits the user could hold after `syncCredits`.
    function pendingCredits(address user) external view returns (uint256) {
        return _acct[user].credits + formableCredits(user);
    }

    /// @notice Whether `user` has any credits or formable credits.
    function isEligible(address user) external view returns (bool) {
        return _acct[user].credits + formableCredits(user) > 0;
    }

    /// @notice Number of active offers (batches) held by `h`. Slices held: see `balanceOf`.
    function offerCountOf(address h) external view returns (uint256) {
        return offersHeldBy[h].length;
    }

    /// @notice All offer ids currently held by `h`.
    function offerIdsOf(address h) external view returns (uint256[] memory) {
        return offersHeldBy[h];
    }

    /// @notice Hash the caller must sign for a redeem of `kind` / `amount`.
    function redeemPayloadHash(address user, uint8 kind, uint256 amount) external view returns (bytes32) {
        return _redeemHash(user, kind, amount);
    }

    /// @notice ERC20-style display name.
    function name() external pure returns (string memory) { return "SOS69069 dSOS"; }

    /// @notice ERC20-style display symbol.
    function symbol() external pure returns (string memory) { return "dSOS"; }

    /// @notice ERC20-style display decimals (0).
    function decimals() external pure returns (uint8) { return 0; }

    /// @notice ERC20 view: number of active slices (dSOS) held by `a`. Each is 0.001 ETH.
    function balanceOf(address a) external view returns (uint256) {
        return _slices[a];
    }

    /// @notice ERC20 wallet send: sends exactly `n` slices (dSOS) to `to`.
    /// @dev    Takes from the caller's offers newest-in-list first, skipping G offers and offers
    ///         with MIN_SEND_WINDOW blocks or fewer left, and splits an offer when only part of
    ///         it is needed. Every slice is worth exactly
    ///         UNIT, so the value sent is exactly `n * 0.001 ETH` of redeemable value.
    ///         Reverts with NotEnoughSendable if fewer than `n` sendable slices.
    ///         Writes no SOS ledger record (a plain wallet send has no signature); use
    ///         `transferSlices` / `transferOffer` for a signed record.
    /// @param  to Recipient. Must be non-zero, not the caller, not this contract.
    /// @param  n  Number of slices (dSOS) to send. Must be >= 1.
    /// @return Always true on success.
    function transfer(address to, uint256 n) external nonReentrant returns (bool) {
        if (to == address(0)) revert ZeroAddress();
        if (to == msg.sender) revert SelfTransfer();
        if (to == address(this)) revert NotTransferable();
        if (n == 0) revert ZeroAmount();

        uint256[] storage mine = offersHeldBy[msg.sender];
        uint256 cap = n < mine.length ? n : mine.length;
        uint256[] memory ids = new uint256[](cap);
        uint256[] memory takes = new uint256[](cap);
        uint256 picked;
        uint256 remaining = n;
        for (uint256 i = mine.length; i > 0 && remaining > 0; --i) {
            uint256 oid = mine[i - 1];
            Offer storage c = _offers[oid];
            if (c.kind != OfferType.G && uint256(c.sweepableAt) > block.number + MIN_SEND_WINDOW) {
                uint256 t = c.count < remaining ? c.count : remaining;
                ids[picked] = oid;
                takes[picked] = t;
                ++picked;
                remaining -= t;
            }
        }
        if (remaining != 0) revert NotEnoughSendable();

        for (uint256 k; k < picked; ++k) {
            _move(ids[k], to, takes[k]);
        }
        emit Transfer(msg.sender, to, n);
        return true;
    }

    /// @notice ERC20 allowances are not supported.
    function allowance(address, address) external pure returns (uint256) { return 0; }

    /// @notice Not supported.
    function approve(address, uint256) external pure returns (bool) { revert NotTransferable(); }

    /// @notice Not supported.
    function transferFrom(address, address, uint256) external pure returns (bool) { revert NotTransferable(); }

    // ---------------------------------------------------------------------
    // INTERNAL
    // ---------------------------------------------------------------------

    /// @dev    Uses SOS.recordStructHash when the ledger is deployed; otherwise
    ///         returns a local keccak so the contract is exercisable without SOS.
    function _structHash(
        address signer,
        address intendedTo,
        bytes32 payloadHash,
        string calldata metadata
    ) private view returns (bytes32) {
        if (SOS69069_LEDGER.code.length == 0) {
            return keccak256(abi.encode(signer, intendedTo, payloadHash, keccak256(bytes(metadata))));
        }
        return SOS.recordStructHash(signer, intendedTo, payloadHash, metadata);
    }

    /// @dev    Move pending trust into credits.
    function _form(address user) private returns (uint256 formed) {
        uint256 trust = SOS.trustCountOf(user);
        Account storage a = _acct[user];
        uint256 pending = trust > a.lastTrust ? trust - a.lastTrust : 0;
        if (pending == 0) return 0;

        a.credits += pending;
        a.lastTrust = trust;
        formed = pending;

        emit CreditsFormed(user, formed, a.credits);
    }

    /// @dev    Domain-separated redeem hash: user, kind, amount, nonce, contract, chain.
    function _redeemHash(address user, uint8 kind, uint256 amount) private view returns (bytes32) {
        return keccak256(abi.encode(user, kind, amount, redeemNonce[user], address(this), block.chainid));
    }

    /// @dev    Append offer id to holder's list.
    function _push(address holder, uint256 id) private returns (uint32 idx) {
        uint256 len = offersHeldBy[holder].length;
        if (len >= type(uint32).max) revert TooManyOffers();
        idx = uint32(len);
        offersHeldBy[holder].push(id);
    }

    /// @dev    Swap-and-pop; updates the moved offer's index.
    function _pop(address holder, uint256 idx) private {
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
    function _send(address to, uint256 amount) private {
        (bool ok, ) = to.call{value: amount}("");
        if (!ok) revert TransferFailed();
    }

    /// @dev    Optional ledger record. Skipped entirely when SOS has no code.
    function _record(
        address signer,
        address intendedTo,
        bytes32 payloadHash,
        bytes calldata signature,
        string calldata metadata
    ) private {
        if (SOS69069_LEDGER.code.length == 0) return;
        try SOS.recordSignature(signer, intendedTo, payloadHash, signature, metadata) {
        } catch (bytes memory reason) {
            emit LedgerRecordSkipped(signer, intendedTo, payloadHash, reason);
        }
    }
}
