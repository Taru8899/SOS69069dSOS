// SPDX-License-Identifier: MIT
pragma solidity 0.8.36;

/// @title ISOS69069
interface ISOS69069 {
    function recordSignature(address signer, address intendedTo, bytes32 payloadHash, bytes calldata signature, string calldata metadata) external;
    function recordStructHash(address signer, address intendedTo, bytes32 payloadHash, string calldata metadata) external pure returns (bytes32);
    function effectiveOf(address user) external view returns (int256);
    function trustCountOf(address user) external view returns (uint256);
    function statsOf(address user) external view returns (uint256 pushCount, uint256 trustCount, int256 effective);
}

/// @title SOS69069 dSOS
/// @notice Shared ETH pool with gated staking and simple credit redemption.
///
/// UNIT
///   1 credit = 0.001 ETH. Users can redeem any whole number of credits at once.
///
/// GATE
///   G-offer with delay == 1 and value > (0.001 ETH + current unallocatedBalance)
///   becomes a gate offer. When swept the donor becomes permanently staked.
///   New stakers must wait 14400 blocks before they can redeem.
///
/// CREDITS
///   Credits = pending SOS trust records (1 trust record = 1 credit).
///   Only staked users can form and redeem credits.
///   Credits cannot be transferred.
///
/// OFFERS
///   B/T/P are transferable. G is non-transferable and PIN-protected.
///   After redeem or sweep the offer is removed from the holder’s list.
contract dSOS {

    // CONSTANTS ============================================================

    address public constant SOS69069_LEDGER = 0x7373DBC24Dcd785896E8Ac3d5372c6ced9B75a8A;
    ISOS69069 public constant SOS = ISOS69069(SOS69069_LEDGER);

    uint256 public constant UNIT           = 0.001 ether;
    uint256 public constant MIN_RESERVE    = 0.000999 ether;
    uint256 public constant DEFAULT_DELAY  = 1;
    uint256 public constant GATE_FLOOR     = 0.001 ether;
    uint256 public constant GATE_DELAY     = 1;
    uint256 public constant STAKE_COOLDOWN = 14400;

    // ERRORS ===============================================================

    error ZeroAddress();
    error ZeroAmount();
    error InvalidValue();
    error OfferNotActive();
    error NotHolder();
    error NoCredit();
    error InsufficientCredits();
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

    // STORAGE ==============================================================

    enum OfferType { G, B, T, P }

    struct Offer {
        address   holder;
        uint96    principal;
        address   donor;
        bool      active;
        OfferType kind;
        uint32    index;
        uint64    createdAt;
        uint64    sweepableAt;
        bytes32   recordHash;
    }

    struct Account {
        uint256 lastTrust;
        uint256 credits;
    }

    struct Rec {
        bytes32 payloadHash;
        bytes   signature;
        string  metadata;
    }

    mapping(uint256 => Offer)     private _offers;
    mapping(uint256 => bytes32)   public  offerPinCommitment;
    mapping(uint256 => bool)      public  offerIsGate;
    mapping(address => bool)      public  staked;
    mapping(address => uint64)    public  stakedAt;
    mapping(address => Account)   private _acct;
    mapping(address => uint256[]) public  offersHeldBy;

    uint64  public nextOfferId = 1;
    bool    private _locked;
    uint256 public totalEarmarked;

    mapping(address => uint256) public redeemNonce;

    // EVENTS ===============================================================

    event OfferCreated(uint256 indexed id, OfferType kind, address indexed donor, address indexed to, uint256 principal);
    event OfferTransferred(uint256 indexed id, address indexed from, address indexed to);
    event OfferRedeemed(uint256 indexed id, address indexed donor, address indexed holder, uint256 principal);
    event OfferSwept(uint256 indexed id, address indexed donor, address indexed holder, uint256 principal);
    event Donation(address indexed from, uint256 amount);
    event CreditsFormed(address indexed user, uint256 formed, uint256 credits);
    event CreditRedeemed(address indexed user, uint256 creditsSpent, uint256 ethPaid);
    event LedgerRecordSkipped(address indexed signer, address indexed intendedTo, bytes32 payloadHash, bytes reason);
    event GateFlagged(uint256 indexed id, bool flagged);

    // MODIFIERS ============================================================

    modifier nonReentrant() {
        if (_locked) revert Reentrant();
        _locked = true;
        _;
        _locked = false;
    }

    // FUNDING ==============================================================

    receive() external payable nonReentrant {
        if (msg.value > 0) {
            emit Donation(msg.sender, msg.value);
        }
    }

    // OFFERS ===============================================================

    function createOffer(
        OfferType kind,
        address to,
        uint256 delayBlocks,
        bytes32 payloadHash,
        bytes calldata signature,
        string calldata metadata
    ) external payable nonReentrant {
        if (kind == OfferType.G) revert InvalidValue();

        bytes32 rh = SOS.recordStructHash(msg.sender, to, payloadHash, metadata);
        uint256 id = _storeOffer(kind, to, delayBlocks, bytes32(0), rh);

        _record(msg.sender, to, payloadHash, signature, metadata);
        emit OfferCreated(id, kind, msg.sender, to, msg.value);
    }

    function createOfferGated(
        address to,
        uint256 delayBlocks,
        bytes32 pinCommitment_,
        bytes32 payloadHash,
        bytes calldata signature,
        string calldata metadata
    ) external payable nonReentrant {
        if (pinCommitment_ == bytes32(0)) revert InvalidValue();

        bytes32 rh = SOS.recordStructHash(msg.sender, to, payloadHash, metadata);
        uint256 id = _storeOffer(OfferType.G, to, delayBlocks, pinCommitment_, rh);

        _record(msg.sender, to, payloadHash, signature, metadata);
        emit OfferCreated(id, OfferType.G, msg.sender, to, msg.value);
    }

    function _storeOffer(
        OfferType kind,
        address to,
        uint256 delayBlocks,
        bytes32 pinC,
        bytes32 rh
    ) private returns (uint256 id) {
        if (to == address(0)) revert ZeroAddress();
        if (msg.value == 0 || msg.value > type(uint96).max) revert InvalidValue();

        if (delayBlocks == 0) delayBlocks = DEFAULT_DELAY;
        uint256 sweepable = block.number + delayBlocks;
        if (sweepable > type(uint64).max) revert BadDelay();

        id = nextOfferId++;

        _offers[id] = Offer({
            holder: to,
            principal: uint96(msg.value),
            donor: msg.sender,
            active: true,
            kind: kind,
            index: _push(to, id),
            createdAt: uint64(block.number),
            sweepableAt: uint64(sweepable),
            recordHash: rh
        });
        totalEarmarked += msg.value;

        if (kind == OfferType.G && delayBlocks == GATE_DELAY) {
            bool isGate = msg.value > GATE_FLOOR + unallocatedBalance();
            if (isGate) offerIsGate[id] = true;
            emit GateFlagged(id, isGate);
        }

        if (kind == OfferType.G) offerPinCommitment[id] = pinC;
    }

    function transferOffer(
        uint256 id,
        address to,
        bytes32 payloadHash,
        bytes calldata signature,
        string calldata metadata
    ) external nonReentrant {
        Offer storage o = _offers[id];
        if (!o.active) revert OfferNotActive();
        if (o.holder != msg.sender) revert NotHolder();
        if (o.kind == OfferType.G) revert NotTransferable();
        if (block.number >= o.sweepableAt) revert WindowClosed();
        if (to == address(0)) revert ZeroAddress();
        if (to == msg.sender) revert SelfTransfer();

        _pop(msg.sender, o.index);
        o.index = _push(to, id);
        o.holder = to;

        _record(msg.sender, to, payloadHash, signature, metadata);
        emit OfferTransferred(id, msg.sender, to);
    }

    function redeemOffer(
        uint256 id,
        bytes32 pin,
        bytes32 payloadHash,
        bytes calldata signature,
        string calldata metadata
    ) external nonReentrant {
        Offer storage o = _offers[id];
        if (!o.active) revert OfferNotActive();
        if (o.holder != msg.sender) revert NotHolder();
        if (block.number >= o.sweepableAt) revert WindowClosed();

        address donor = o.donor;
        uint96 principal = o.principal;

        if (o.kind == OfferType.G) {
            bytes32 expected = offerPinCommitment[id];
            if (expected == bytes32(0) || keccak256(abi.encode(pin, donor, msg.sender)) != expected) {
                revert BadOfferPin();
            }
            delete offerPinCommitment[id];
        }

        delete offerIsGate[id];

        o.active = false;
        totalEarmarked -= principal;
        _pop(msg.sender, o.index);

        _record(msg.sender, donor, payloadHash, signature, metadata);
        emit OfferRedeemed(id, donor, msg.sender, principal);
        _send(msg.sender, principal);
    }

    function sweepOffer(uint256 id) external nonReentrant {
        Offer storage o = _offers[id];
        if (!o.active) revert OfferNotActive();
        if (block.number < o.sweepableAt) revert TooEarly();

        address donor = o.donor;
        address holder = o.holder;
        uint96 principal = o.principal;

        if (offerIsGate[id]) {
            staked[donor] = true;
            stakedAt[donor] = uint64(block.number);
            delete offerIsGate[id];
        }

        o.active = false;
        totalEarmarked -= principal;
        _pop(holder, o.index);
        delete offerPinCommitment[id];

        emit OfferSwept(id, donor, holder, principal);
    }

    // CREDITS ==============================================================

    function syncCredits() external returns (uint256 formed) {
        if (!staked[msg.sender]) revert NotStaked();
        formed = _form(msg.sender);
    }

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

    // VIEWS ================================================================

    function offers(uint256 id) external view returns (
        address donor,
        address holder,
        uint256 principal,
        bool active,
        OfferType kind,
        bytes32 recordHash,
        uint64 createdAt,
        uint64 sweepableAt
    ) {
        Offer storage o = _offers[id];
        return (o.donor, o.holder, o.principal, o.active, o.kind, o.recordHash, o.createdAt, o.sweepableAt);
    }

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

    function lastTrust(address user) external view returns (uint256) {
        return _acct[user].lastTrust;
    }

    function redemptionCredits(address user) external view returns (uint256) {
        return _acct[user].credits;
    }

    function unallocatedBalance() public view returns (uint256) {
        uint256 bal = address(this).balance;
        return bal > totalEarmarked ? bal - totalEarmarked : 0;
    }

    function gateRequirement() external view returns (uint256) {
        return GATE_FLOOR + unallocatedBalance();
    }

    function canRedeem(address user) external view returns (bool) {
        if (!staked[user]) return false;
        return block.number >= uint256(stakedAt[user]) + STAKE_COOLDOWN;
    }

    function poolBalance() external view returns (uint256) {
        return address(this).balance;
    }

    function formableCredits(address user) public view returns (uint256) {
        uint256 t = SOS.trustCountOf(user);
        uint256 last = _acct[user].lastTrust;
        return t > last ? t - last : 0;
    }

    function pendingCredits(address user) external view returns (uint256) {
        return _acct[user].credits + formableCredits(user);
    }

    function isEligible(address user) external view returns (bool) {
        return _acct[user].credits + formableCredits(user) > 0;
    }

    function offerCountOf(address h) external view returns (uint256) {
        return offersHeldBy[h].length;
    }

    function offerIdsOf(address h) external view returns (uint256[] memory) {
        return offersHeldBy[h];
    }

    function redeemPayloadHash(address user, uint8 kind, uint256 amount) external view returns (bytes32) {
        return _redeemHash(user, kind, amount);
    }

    function name() external pure returns (string memory) { return "SOS69069 dSOS"; }
    function symbol() external pure returns (string memory) { return "dSOS"; }

    // INTERNAL =============================================================

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

    function _redeemHash(address user, uint8 kind, uint256 amount) private view returns (bytes32) {
        return keccak256(abi.encode(user, kind, amount, redeemNonce[user], address(this), block.chainid));
    }

    function _push(address holder, uint256 id) private returns (uint32 idx) {
        uint256 len = offersHeldBy[holder].length;
        if (len >= type(uint32).max) revert TooManyOffers();
        idx = uint32(len);
        offersHeldBy[holder].push(id);
    }

    function _pop(address holder, uint256 idx) private {
        uint256[] storage arr = offersHeldBy[holder];
        if (arr.length == 0 || idx >= arr.length) revert OfferNotActive();
        uint256 last = arr.length - 1;
        if (idx != last) {
            uint256 lastId = arr[last];
            arr[idx] = lastId;
            _offers[lastId].index = uint32(idx);
        }
        arr.pop();
    }

    function _send(address to, uint256 amount) private {
        (bool ok, ) = to.call{value: amount}("");
        if (!ok) revert TransferFailed();
    }

    function _record(
        address signer,
        address intendedTo,
        bytes32 payloadHash,
        bytes calldata signature,
        string calldata metadata
    ) private {
        try SOS.recordSignature(signer, intendedTo, payloadHash, signature, metadata) {
        } catch (bytes memory reason) {
            emit LedgerRecordSkipped(signer, intendedTo, payloadHash, reason);
        }
    }
}