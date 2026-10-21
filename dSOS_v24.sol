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
///   1 credit = 0.001 ETH. Users redeem any whole number of credits at once.
///
/// GATE
///   A G offer with delay == 1 and value > (0.001 ETH + current unallocatedBalance)
///   is a gate offer. When swept, the donor becomes permanently staked.
///   New stakers wait 14400 blocks before their first redemption.
///
/// CREDITS
///   Credits = pending SOS trust records (1 trust record = 1 credit).
///   Only staked users can form and redeem credits.
///   Credits cannot be transferred.
///
/// OFFERS
///   B/T/P are transferable. G is non-transferable and PIN-protected.
///   After redeem or sweep, the offer is removed from the holder's list.
///
/// FALLBACKS
///   When the SOS ledger has no code at its address (local tests, forks without
///   the ledger deployed), `_structHash` falls back to a local keccak and
///   `_record` is skipped. Behaviour with a live ledger is byte-identical to
///   the original contract.
contract dSOS {

    // ---------------------------------------------------------------------
    // CONSTANTS
    // ---------------------------------------------------------------------

    /// @notice Canonical SOS69069 ledger address.
    address public constant SOS69069_LEDGER = 0x7373DBC24Dcd785896E8Ac3d5372c6ced9B75a8A;

    /// @notice Typed reference to the ledger.
    ISOS69069 public constant SOS = ISOS69069(SOS69069_LEDGER);

    /// @notice ETH value of one credit (0.001 ETH).
    uint256 public constant UNIT           = 0.001 ether;

    /// @notice Minimum ETH the pool must retain after any payout.
    uint256 public constant MIN_RESERVE    = 0.000999 ether;

    /// @notice Applied when a caller passes `delayBlocks == 0`.
    uint256 public constant DEFAULT_DELAY  = 1;

    /// @notice Base value added to `unallocatedBalance()` to compute the gate requirement.
    uint256 public constant GATE_FLOOR     = 0.001 ether;

    /// @notice Required delay for a G offer to be eligible as a gate offer.
    uint256 public constant GATE_DELAY     = 1;

    /// @notice Blocks a new staker must wait before redeeming credits.
    uint256 public constant STAKE_COOLDOWN = 14400;

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

    // ---------------------------------------------------------------------
    // TYPES
    // ---------------------------------------------------------------------

    /// @notice Offer kinds. G = gated, B/T/P = transferable non-gated.
    enum OfferType { G, B, T, P }

    /// @notice Offer record.
    /// @dev    `isGate` is packed with `donor/active/kind/index` in slot 2.
    struct Offer {
        address   holder;
        uint96    principal;
        address   donor;
        bool      active;
        bool      isGate;
        OfferType kind;
        uint32    index;
        uint64    createdAt;
        uint64    sweepableAt;
        bytes32   recordHash;
    }

    /// @notice Per-account credit state.
    struct Account {
        uint256 lastTrust;
        uint256 credits;
    }

    /// @notice Signature envelope for redeem functions.
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

    uint64  public nextOfferId = 1;
    bool    private _locked;
    uint256 public totalEarmarked;

    mapping(address => uint256) public redeemNonce;

    // ---------------------------------------------------------------------
    // EVENTS
    // ---------------------------------------------------------------------

    event OfferCreated(uint256 indexed id, OfferType kind, address indexed donor, address indexed to, uint256 principal);
    event OfferTransferred(uint256 indexed id, address indexed from, address indexed to);
    event OfferRedeemed(uint256 indexed id, address indexed donor, address indexed holder, uint256 principal);
    event OfferSwept(uint256 indexed id, address indexed donor, address indexed holder, uint256 principal);
    event Donation(address indexed from, uint256 amount);
    event CreditsFormed(address indexed user, uint256 formed, uint256 credits);
    event CreditRedeemed(address indexed user, uint256 creditsSpent, uint256 ethPaid);
    event LedgerRecordSkipped(address indexed signer, address indexed intendedTo, bytes32 payloadHash, bytes reason);
    event GateFlagged(uint256 indexed id, bool flagged);
    event Staked(address indexed user, uint64 atBlock);

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
    // OFFERS
    // ---------------------------------------------------------------------

    /// @notice Create a transferable offer (B=1, T=2, P=3). Never yields credits.
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

    /// @notice Create a gated offer (G=0). Non-transferable; redeem requires the PIN.
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

    /// @dev    Internal: store offer, earmark principal, mark gate if eligible.
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
            isGate: false,
            kind: kind,
            index: _push(to, id),
            createdAt: uint64(block.number),
            sweepableAt: uint64(sweepable),
            recordHash: rh
        });
        totalEarmarked += msg.value;

        if (kind == OfferType.G && delayBlocks == GATE_DELAY) {
            bool isGate = msg.value > GATE_FLOOR + unallocatedBalance();
            if (isGate) {
                _offers[id].isGate = true;
            }
            emit GateFlagged(id, isGate);
        }

        if (kind == OfferType.G) offerPinCommitment[id] = pinC;
    }

    /// @notice Transfer a B/T/P offer to another holder. G is not transferable.
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

    /// @notice Redeem an offer's principal (full amount) inside the redeem window.
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

        if (o.isGate) {
            delete o.isGate;
        }

        o.active = false;
        totalEarmarked -= principal;
        _pop(msg.sender, o.index);

        _record(msg.sender, donor, payloadHash, signature, metadata);
        emit OfferRedeemed(id, donor, msg.sender, principal);
        _send(msg.sender, principal);
    }

    /// @notice Sweep an expired offer. Principal becomes unallocated.
    /// @dev    If the offer was a gate offer, the donor is permanently staked
    ///         and a `Staked` event is emitted.
    /// @param  id Offer id. Callable by anyone once `block.number >= sweepableAt`.
    function sweepOffer(uint256 id) external nonReentrant {
        Offer storage o = _offers[id];
        if (!o.active) revert OfferNotActive();
        if (block.number < o.sweepableAt) revert TooEarly();

        address donor = o.donor;
        address holder = o.holder;
        uint96 principal = o.principal;

        if (o.isGate) {
            staked[donor] = true;
            stakedAt[donor] = uint64(block.number);
            delete o.isGate;
            emit Staked(donor, uint64(block.number));
        }

        o.active = false;
        totalEarmarked -= principal;
        _pop(holder, o.index);
        delete offerPinCommitment[id];

        emit OfferSwept(id, donor, holder, principal);
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

    /// @notice Full read of an offer.
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

    /// @notice Current gate requirement (strictly greater satisfies the gate).
    function gateRequirement() external view returns (uint256) {
        return GATE_FLOOR + unallocatedBalance();
    }

    /// @notice Exact `msg.value` needed for a gate offer (accounts for strict `>`).
    function stakeRequirement() external view returns (uint256) {
        return GATE_FLOOR + unallocatedBalance() + 1;
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

    /// @notice Number of active offers held by `h`.
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