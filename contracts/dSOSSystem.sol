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

/// @title SOS69069 dSOS
/// @notice No-admin exchange of SOS records for ETH slices, plus a shared pool.
///
/// UNIT
///   1 slice = 1 dSOS = 0.001 ETH. 1 credit = 0.001 ETH. 1 SOS record = at least 1 slice.
///
/// NO ADMIN
///   No owner, no upgrade key, no privileged function. Every function is permissionless.
///   dSOS never writes to the SOS ledger. It only reads it (record exists / trust count).
///
/// OFFER TYPES
///   S  sendable, free redeem (no records, no cap). To an exact address. Sendable while MORE than
///      MIN_SEND_WINDOW blocks (1 day) remain.
///   A  open. The receiver is this contract. Any seller confirms records. Each record earns
///      `slicesPerRecord` (>= 1, no max) slices. Not sendable. Redeem is capped by what the redeemer produced.
///   B  named. Same as A but only the exact address B can confirm records.
///   G  gate offer with a PIN, as before. Redeeming needs the PIN. Swept gate offer stakes the donor.
///      Not sendable.
///
/// DEFAULTS
///   delayBlocks == 0 becomes DEFAULT_DELAY (1 block). The expiry cannot be changed after creation, so the
///   creator must pass a real delay for an offer to be usable.
///   For S, B and G a receiver of address(0) becomes DEAD. Passing this contract as receiver is rejected.
///   Open A offers have no receiver field: the receiver is this contract.
///
/// A / B FLOW
///   1. createOfferA / createOfferB: ETH is escrowed (earmarked) until the expiry block. The escrow slices
///      are minted to this contract. Funded slices must divide exactly by `slicesPerRecord`.
///   2. The seller writes records to the SOS ledger by themselves: signer = seller, intendedTo = the offer
///      creator, metadata = "", payloadHash = recordPayloadHash(id, seller, index) for index 0, 1, 2 ...
///   3. syncRecords: dSOS recomputes each record hash and asks the ledger whether it exists. Each confirmed
///      record moves `slicesPerRecord` slices from the escrow into the seller's own offer (same expiry, same
///      type). First come first served until the offer is full.
///      The payload hash contains the offer id and a salt taken from the creation block, so a record can
///      only count for one offer and only if it was signed after that offer existed.
///   4. The seller redeems before expiry (whole or by slice) for 0.001 ETH per slice.
///   5. After the expiry block anyone calls sweepOffer. Unconfirmed escrow and unredeemed slices go to
///      the pool. Sweeping never sends ETH, so it cannot be blocked.
///
/// CAP
///   produced[user] = slices the user funded in A and B offers (counted at creation, even if nobody
///   confirms them, so allowance can be bought by paying the pool).
///   redeemed[user] = slices the user redeemed from A and B offers.
///   A / B redeem requires redeemed + amount <= produced. S and G redeems and pool credit redeems
///   are not capped.
///
/// CREDITS
///   Credits = SOS trust records addressed to the user (1 record = 1 credit). Only staked users can form
///   and redeem credits. Credits cannot be transferred. Universal rate: 1 credit = 0.001 ETH from the pool.
///
/// POOL
///   Pool = contract balance that is not earmarked. Everything swept goes there. Nobody can withdraw it
///   except staked users redeeming credits.
///
/// NONCE
///   Every value-moving call takes `expectedNonce` as its last argument. It must equal redeemNonce(caller),
///   otherwise the call reverts with BadNonce. On success the nonce increases by 1 and every dSOS event of
///   that call carries the nonce used, so (address, nonce) identifies one action.
///   Covered: create (S, A, B, G), syncRecords, transferOffer, transferSlices, redeemOffer, redeemSlices,
///   redeemCredit, sweepOffer.
///   The wallet transfer(to, n) keeps the standard ERC-20 signature, so it cannot take a nonce: it
///   increases the nonce but does not check one. A plain ETH donation carries no data and is not counted.
///
/// TIME
///   Everything is measured in blocks: 7200 blocks = 1 day, 14400 blocks = 2 days.
///
/// ERC-20 VIEW (display only)
///   name / symbol / decimals (0) / totalSupply / balanceOf. totalSupply * UNIT always equals the ETH
///   locked in offers. Unconfirmed A / B escrow is held by this contract (balanceOf(dSOS)).
///   Transfer events: create S/G 0 -> receiver; create A/B 0 -> dSOS; confirm dSOS -> seller; send
///   sender -> recipient; redeem and sweep of a held offer holder -> 0; sweep of an escrow dSOS -> 0.
///
/// TWO FILES
///   dSOSOffers.sol holds the dSOSOffers module. This file holds dSOSSystem. Both files carry the same
///   ISOS69069 and DSOSStorage text (no import), so each compiles alone. This file holds dSOSSystem:
///   all storage and ETH, the wrappers of the 10 offer functions (each is a delegatecall into the module),
///   credits, views and the ERC-20 surface. Deploy dSOSOffers first, then dSOSSystem(moduleAddress).
///   The module address is immutable, so there is no upgrade path and no admin.
contract dSOSSystem is DSOSStorage {

    /// @notice The offer module that every offer function delegatecalls. Fixed at deployment.
    address public immutable OFFERS_MODULE;

    error NoModule();

    constructor(address offersModule) {
        if (offersModule.code.length == 0) revert NoModule();
        OFFERS_MODULE = offersModule;
    }

    // ---------------------------------------------------------------------
    // FUNDING
    // ---------------------------------------------------------------------

    /// @notice Plain ETH transfer. Adds to the pool (unallocated balance). Not nonce-counted.
    receive() external payable nonReentrant {
        if (msg.value > 0) {
            emit Donation(msg.sender, msg.value);
        }
    }

    // ---------------------------------------------------------------------
    // OFFER FUNCTIONS (delegatecall into dSOSOffers)
    // ---------------------------------------------------------------------

    /// @notice Create an S offer: `msg.value / UNIT` slices held by `to` from the start. Runs in dSOSOffers.
    function createOfferS(address to, uint256 delayBlocks, uint256 expectedNonce) external payable {
        _delegateOffer();
    }

    /// @notice Create a gated offer (G). Redeem needs the PIN. Not sendable. Runs in dSOSOffers.
    function createOfferGated(address to, uint256 delayBlocks, bytes32 pinCommitment_, uint256 expectedNonce) external payable {
        _delegateOffer();
    }

    /// @notice Create an open A offer. Any seller can confirm records, first come first served. Runs in dSOSOffers.
    function createOfferA(uint256 delayBlocks, uint256 slicesPerRecord, uint256 expectedNonce) external payable {
        _delegateOffer();
    }

    /// @notice Create a named B offer. Only `to` can confirm records. Runs in dSOSOffers.
    function createOfferB(address to, uint256 delayBlocks, uint256 slicesPerRecord, uint256 expectedNonce) external payable {
        _delegateOffer();
    }

    /// @notice Confirm up to `n` of the caller's next records for offer `id`. Runs in dSOSOffers.
    function syncRecords(uint256 id, uint256 n, uint256 expectedNonce) external returns (uint256 taken) {
        _delegateOffer();
    }

    /// @notice Transfer a whole S offer. Only while more than MIN_SEND_WINDOW blocks remain. Runs in dSOSOffers.
    function transferOffer(uint256 id, address to, uint256 expectedNonce) external {
        _delegateOffer();
    }

    /// @notice Transfer `slices` slices of an S offer. If fewer than all, the offer is split: Runs in dSOSOffers.
    function transferSlices(uint256 id, uint256 slices, address to, uint256 expectedNonce) external {
        _delegateOffer();
    }

    /// @notice Redeem a whole offer (all its remaining slices) before its expiry block. Runs in dSOSOffers.
    function redeemOffer(uint256 id, bytes32 pin, uint256 expectedNonce) external {
        _delegateOffer();
    }

    /// @notice Redeem `slices` slices of an offer for `slices * UNIT` ETH before its expiry block. Runs in dSOSOffers.
    function redeemSlices(uint256 id, uint256 slices, bytes32 pin, uint256 expectedNonce) external {
        _delegateOffer();
    }

    /// @notice Sweep an expired offer into the pool. Callable by anyone once `block.number >= sweepableAt`. Runs in dSOSOffers.
    function sweepOffer(uint256 id, uint256 expectedNonce) external {
        _delegateOffer();
    }

    /// @dev Forward the whole call to the module and return or revert with its result.
    ///      msg.sender, msg.value, storage and balance stay those of this contract.
    function _delegateOffer() private {
        address m = OFFERS_MODULE;
        assembly ("memory-safe") {
            calldatacopy(0, 0, calldatasize())
            let ok := delegatecall(gas(), m, 0, calldatasize(), 0, 0)
            returndatacopy(0, 0, returndatasize())
            switch ok
            case 0 { revert(0, returndatasize()) }
            default { return(0, returndatasize()) }
        }
    }

    // ---------------------------------------------------------------------
    // CREDITS, VIEWS, ERC-20 SURFACE
    // ---------------------------------------------------------------------

    /// @notice Form credits from the caller's pending SOS trust records.
    /// @dev    Requires `staked[msg.sender]`. One trust record = one credit. No ETH moves, so no nonce.
    function syncCredits() external returns (uint256 formed) {
        if (!staked[msg.sender]) revert NotStaked();
        formed = _form(msg.sender);
    }

    /// @notice Redeem `creditsToSpend` credits for ETH from the pool at `UNIT` per credit.
    /// @dev    Requires: staked, cooldown passed, enough credits, and
    ///         `balance >= totalEarmarked + MIN_RESERVE + creditsToSpend*UNIT`.
    ///         Not limited by the A/B cap. Writes nothing to the ledger.
    /// @param  creditsToSpend Number of credits to burn (>= 1).
    /// @param  expectedNonce  Caller's current redeemNonce.
    function redeemCredit(uint256 creditsToSpend, uint256 expectedNonce) external nonReentrant {
        uint256 nonce = _useNonce(expectedNonce);
        if (!staked[msg.sender]) revert NotStaked();
        if (block.number < uint256(stakedAt[msg.sender]) + STAKE_COOLDOWN) revert TooEarly();
        if (creditsToSpend == 0) revert ZeroAmount();

        _form(msg.sender);

        Account storage a = _acct[msg.sender];
        if (a.credits < creditsToSpend) revert InsufficientCredits();

        uint256 ethAmount = creditsToSpend * UNIT;
        if (address(this).balance < totalEarmarked + MIN_RESERVE + ethAmount) revert PoolTooThin();

        a.credits -= creditsToSpend;

        emit CreditRedeemed(msg.sender, creditsToSpend, ethAmount, nonce);
        _send(msg.sender, ethAmount);
    }

    /// @notice Full read of a held offer (S, G, or slices earned in A/B). `principal` = count * UNIT.
    function offers(uint256 id) external view returns (
        address donor,
        address holder,
        uint256 principal,
        bool active,
        OfferType kind,
        uint64 createdAt,
        uint64 sweepableAt,
        uint256 count
    ) {
        Offer storage o = _offers[id];
        return (
            o.donor, o.holder, uint256(o.count) * UNIT, o.active, o.kind,
            o.createdAt, o.sweepableAt, o.count
        );
    }

    /// @notice Full read of an A/B escrow.
    function sales(uint256 id) external view returns (
        address donor,
        address target,
        OfferType kind,
        bool active,
        uint256 slicesLeft,
        uint256 slicesPerRecord,
        uint256 recordsLeft,
        uint64 createdAt,
        uint64 sweepableAt,
        bytes32 salt
    ) {
        Sale storage s = _sales[id];
        donor           = s.donor;
        target          = s.target;
        kind            = s.kind;
        active          = s.active;
        slicesLeft      = s.slicesLeft;
        slicesPerRecord = s.perRecord;
        recordsLeft     = (s.active && slicesPerRecord != 0) ? slicesLeft / slicesPerRecord : 0;
        createdAt       = s.createdAt;
        sweepableAt     = s.sweepableAt;
        salt            = s.salt;
    }

    /// @notice Payload hash `seller` must sign for record `index` of A/B offer `id`.
    ///         Sign the ledger's EIP-712 Record with signer = seller, intendedTo = the offer creator,
    ///         this payloadHash and empty metadata, then write it to the ledger.
    function recordPayloadHash(uint256 id, address seller, uint256 index) external view returns (bytes32) {
        return _recordPayload(id, _sales[id].salt, seller, index);
    }

    /// @notice Hash identifying the NEXT action of `user`: user, action kind, amount, current nonce,
    ///         this contract and the chain. Kind codes: 0 credit redeem, 1 create, 2 confirm records,
    ///         3 send, 4 redeem offer, 5 sweep.
    function redeemPayloadHash(address user, uint8 kind, uint256 amount) external view returns (bytes32) {
        return keccak256(abi.encode(user, kind, amount, redeemNonce[user], address(this), block.chainid));
    }

    /// @notice How many more slices `user` may redeem from A and B offers.
    function allowanceOf(address user) external view returns (uint256) {
        uint256 p = produced[user];
        uint256 r = redeemed[user];
        return p > r ? p - r : 0;
    }

    /// @notice IDs of held offers of `holder` whose sweep window is open.
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

    /// @notice Current gate requirement (the offer total must be strictly greater).
    function gateRequirement() external view returns (uint256) {
        return GATE_FLOOR + unallocatedBalance();
    }

    /// @notice Exact `msg.value` of the cheapest gate offer.
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

    /// @notice Number of active held offers of `h`. Slices held: see `balanceOf`.
    function offerCountOf(address h) external view returns (uint256) {
        return offersHeldBy[h].length;
    }

    /// @notice All held offer ids of `h`.
    function offerIdsOf(address h) external view returns (uint256[] memory) {
        return offersHeldBy[h];
    }

    /// @notice ERC20-style display name.
    function name() external pure returns (string memory) { return "SOS69069 dSOS"; }

    /// @notice ERC20-style display symbol.
    function symbol() external pure returns (string memory) { return "dSOS"; }

    /// @notice ERC20-style display decimals (0).
    function decimals() external pure returns (uint8) { return 0; }

    /// @notice ERC20 view: number of active slices (dSOS) held by `a`. Each is 0.001 ETH.
    ///         balanceOf(dSOS) is the unconfirmed A/B escrow.
    function balanceOf(address a) external view returns (uint256) {
        return _slices[a];
    }

    /// @notice ERC20 wallet send: sends exactly `n` slices (dSOS) to `to`.
    /// @dev    Only S offers with more than MIN_SEND_WINDOW blocks left are sendable. Takes from the
    ///         caller's offers newest-in-list first and splits an offer when only part is needed.
    ///         Keeps the standard ERC-20 signature, so it cannot take a nonce: it increases the caller's
    ///         nonce but does not check one. Use `transferSlices` for a nonce-checked send.
    ///         Reverts NotEnoughSendable if fewer than `n` sendable slices.
    function transfer(address to, uint256 n) external nonReentrant returns (bool) {
        if (to == address(0)) revert ZeroAddress();
        if (to == msg.sender) revert SelfTransfer();
        if (to == address(this)) revert BadTarget();
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
            if (c.kind == OfferType.S && uint256(c.sweepableAt) > block.number + MIN_SEND_WINDOW) {
                uint256 t = c.count < remaining ? c.count : remaining;
                ids[picked] = oid;
                takes[picked] = t;
                ++picked;
                remaining -= t;
            }
        }
        if (remaining != 0) revert NotEnoughSendable();

        uint256 nonce = redeemNonce[msg.sender];
        redeemNonce[msg.sender] = nonce + 1;

        for (uint256 k; k < picked; ++k) {
            _move(ids[k], to, takes[k], nonce);
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
}
