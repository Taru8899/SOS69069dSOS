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
/// @notice One pool. Nobody can take out more ETH than free + trustCredits they hold.
///
/// ALLOWANCE (free)
///   receive / donateCommon → 1 GASC only. NO free.
///   createOfferGated (G) with delay >= 7200 AND value > UNIT → +UNIT free at creation.
///   G redeem (PIN, before sweepable) with value > UNIT → + more free for elapsed time.
///   B/T/P → NO free ever. G delay < 7200 → NO free ever.
///
/// CREDITS
///   1 credit = 1 new trust record + up to UNIT free (moved into trustCredits).
///   Redeem pays min(sawtooth face, trustCredits / credits).
///   Last leftover returns to free. Credits + pro-rata trustCredits are transferable.
///
/// OFFERS
///   IDs: G=0, B=1, T=2, P=3
///   B/T/P (1/2/3): transferable, full redeem by holder. Never any free.
///   G (0): NOT transferable, donor PIN required to redeem.
///   WINDOW (all kinds, same rule):
///     createdAt .. createdAt+delayBlocks  → holder may redeem (G: with PIN); B/T/P may be transferred
///     >= createdAt+delayBlocks           → anyone may sweep to unallocated pool;
///                                          redeem and transfer are closed
///   delayBlocks (chosen in createOffer / createOfferGated):
///     0 → DEFAULT_DELAY (1)
///     1 .. 7199 allowed, but NO free ever
///     no upper cap (only uint64 overflow guard)
///   G FREE (G only; only if value > UNIT and delay >= 7200):
///     at create  → freeAtCreate = UNIT
///     at redeem  → freeTotal = min(principal, floor(ELAPSED/7200) * UNIT), ELAPSED = blocks
///                  actually waited since creation (NOT the declared delay);
///                  freeRemainder = freeTotal - freeAtCreate, if > 0
///     at sweep   → 0 (donor receives NO additional free)
///   Sweep: principal stays in the unallocated pool. Never returns to donor.
///
/// REDEEM NONCE
///   redeemCredit and redeemGasClaim require the signed payloadHash to equal
///   redeemPayloadHash(user, kind, amount). Each successful redeem bumps the
///   nonce, so a signed redeem message can be used exactly once.
///
/// RESERVE
///   A payout may never leave balance below totalEarmarked + MIN_RESERVE.
///   A redeem that would breach it reverts (PoolTooThin); it does not pay less.
contract dSOS {

    // CONSTANTS ============================================================

    address public constant SOS69069_LEDGER = 0x7373DBC24Dcd785896E8Ac3d5372c6ced9B75a8A;
    ISOS69069 public constant SOS = ISOS69069(SOS69069_LEDGER);

    uint256 public constant UNIT              = 0.006 ether;
    uint256 public constant MIN_RESERVE       = 0.000999 ether;
    uint256 public constant DEAD_ZONE_PAYOUT  = 0.0000033 ether;
    uint256 public constant RATE_STEP         = 1001;
    uint256 public constant BASE_RATE_PCT     = 30;
    uint256 public constant CYCLE_STEPS       = 71;
    uint256 public constant DEAD_ZONE_POS     = 70;
    uint256 public constant GAS_CLAIM_MINT    = 1;

    uint256 public constant FREE_WINDOW       = 7200;   // free accrues per 7200-block chunk
    uint256 public constant DEFAULT_DELAY     = 1;      // blocks, for empty delay

    // ERRORS ===============================================================

    error ZeroAddress();
    error ZeroAmount();
    error InvalidValue();
    error OfferNotActive();
    error NotHolder();
    error NoCredit();
    error InsufficientCredits();
    error InsufficientBalance();
    error InsufficientAllowance();
    error ExceedsAllowance();
    error NothingToRedeem();
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

    // STORAGE ==============================================================

    /// @dev G=0, B=1, T=2, P=3
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
        uint256 free;
        uint256 trustCredits;
    }

    struct Rec {
        bytes32 payloadHash;
        bytes   signature;
        string  metadata;
    }

    mapping(uint256 => Offer)   private _offers;
    mapping(uint256 => bytes32) public  offerPinCommitment;
    mapping(uint256 => uint256) public  offerFreeAtCreate;
    mapping(address => Account) private _acct;
    mapping(address => uint256[]) public offersHeldBy;

    uint64  public nextOfferId = 1;
    bool    private _locked;
    uint256 public totalEarmarked;

    uint256 public totalFree;
    uint256 public totalTrustCredits;

    mapping(address => uint256) public redeemNonce;

    // GasClaim (minimal ERC20)
    mapping(address => uint256) public balanceOf;
    mapping(address => mapping(address => uint256)) public allowance;
    uint256 public totalSupply;

    // EVENTS ===============================================================

    event OfferCreated(uint256 indexed id, OfferType kind, address indexed donor, address indexed to, uint256 principal);
    event OfferTransferred(uint256 indexed id, address indexed from, address indexed to);
    event OfferRedeemed(uint256 indexed id, address indexed donor, address indexed holder, uint256 principal);
    event OfferSwept(uint256 indexed id, address indexed donor, address indexed holder, uint256 principal);
    event CommonDonation(address indexed donor, uint256 amount);
    event Donation(address indexed from, uint256 amount);
    event CreditsFormed(address indexed user, uint256 formed, uint256 ethBound, uint256 credits, uint256 trustCredits, uint256 push, uint256 trust);
    event CreditRedeemed(address indexed user, int256 eff, uint256 ratePct, uint256 paid);
    event CreditsTransferred(address indexed from, address indexed to, uint256 amount, uint256 trustCreditsMoved, int256 effAtSend, uint256 trustAtSend);
    event GasClaimRedeemed(address indexed user, uint256 amount);
    event Transfer(address indexed from, address indexed to, uint256 value);
    event Approval(address indexed owner, address indexed spender, uint256 value);

    // MODIFIERS ============================================================

    modifier nonReentrant() {
        if (_locked) revert Reentrant();
        _locked = true;
        _;
        _locked = false;
    }

    // =====================================================================
    // FUNDING
    // =====================================================================

    receive() external payable nonReentrant {
        if (msg.value > 0) {
            _mint(msg.sender, GAS_CLAIM_MINT);
            emit Donation(msg.sender, msg.value);
        }
    }

    function donateCommon(bytes32 payloadHash, bytes calldata signature, string calldata metadata) external payable nonReentrant {
        if (msg.value == 0) revert InvalidValue();
        _mint(msg.sender, GAS_CLAIM_MINT);
        SOS.recordSignature(msg.sender, SOS69069_LEDGER, payloadHash, signature, metadata);
        emit CommonDonation(msg.sender, msg.value);
    }

    // =====================================================================
    // OFFERS
    // =====================================================================

    /// @notice Create transferable offer (B=1, T=2, P=3). No free. Sweepable after delayBlocks.
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

        SOS.recordSignature(msg.sender, to, payloadHash, signature, metadata);
        emit OfferCreated(id, kind, msg.sender, to, msg.value);
    }

    /// @notice Create gated offer (G=0). Non-transferable.
    ///         pinCommitment = keccak256(abi.encode(pin, donor, to)).
    ///         Free granted only when delayBlocks >= 7200 and value > UNIT.
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

        SOS.recordSignature(msg.sender, to, payloadHash, signature, metadata);
        emit OfferCreated(id, OfferType.G, msg.sender, to, msg.value);
    }

    /// @notice Only B/T/P (1/2/3) can be transferred.
    function transferOffer(uint256 id, address to, bytes32 payloadHash, bytes calldata signature, string calldata metadata) external nonReentrant {
        Offer storage o = _offers[id];
        if (!o.active) revert OfferNotActive();
        if (o.holder != msg.sender) revert NotHolder();
        if (o.kind == OfferType.G) revert NotTransferable();
        if (block.number >= o.sweepableAt) revert WindowClosed();
        if (to == address(0)) revert ZeroAddress();

        _pop(msg.sender, o.index);
        o.index = _push(to, id);
        o.holder = to;

        SOS.recordSignature(msg.sender, to, payloadHash, signature, metadata);
        emit OfferTransferred(id, msg.sender, to);
    }

    /// @notice Holder redeems full principal.
    ///         Only inside [createdAt, sweepableAt). G also requires the correct PIN.
    ///         G redeem credits donor for blocks actually waited (see header).
    function redeemOffer(uint256 id, bytes32 pin, bytes32 payloadHash, bytes calldata signature, string calldata metadata) external nonReentrant {
        Offer storage o = _offers[id];
        if (!o.active) revert OfferNotActive();
        if (o.holder != msg.sender) revert NotHolder();

        address donor = o.donor;
        uint96 principal = o.principal;
        uint256 freeAtCreate = offerFreeAtCreate[id];

        if (block.number >= o.sweepableAt) revert WindowClosed();

        if (o.kind == OfferType.G) {
            bytes32 expected = offerPinCommitment[id];
            if (expected == bytes32(0) || keccak256(abi.encode(pin, donor, msg.sender)) != expected) {
                revert BadOfferPin();
            }
            delete offerPinCommitment[id];

            // Free for time actually waited, only for offers above UNIT.
            uint256 freeRemainder;
            if (principal > UNIT && uint256(o.sweepableAt) - uint256(o.createdAt) >= FREE_WINDOW) {
                uint256 elapsed = block.number - uint256(o.createdAt);
                uint256 freeTotal = (elapsed / FREE_WINDOW) * UNIT;
                if (freeTotal > principal) freeTotal = principal;
                freeRemainder = freeTotal > freeAtCreate ? freeTotal - freeAtCreate : 0;
            }
            if (freeRemainder > 0) {
                _acct[donor].free += freeRemainder;
                totalFree += freeRemainder;
            }
        }

        o.active = false;
        totalEarmarked -= principal;
        _pop(msg.sender, o.index);
        delete offerFreeAtCreate[id];

        SOS.recordSignature(msg.sender, donor, payloadHash, signature, metadata);
        emit OfferRedeemed(id, donor, msg.sender, principal);
        _send(msg.sender, principal);
    }

    /// @notice Once block.number >= sweepableAt, anyone may sweep any offer (G, B, T, P).
    ///         Full principal stays in the unallocated pool.
    ///         Donor receives NO additional free.
    function sweepOffer(uint256 id) external nonReentrant {
        Offer storage o = _offers[id];
        if (!o.active) revert OfferNotActive();
        if (block.number < o.sweepableAt) revert TooEarly();

        address donor = o.donor;
        address holder = o.holder;
        uint96 principal = o.principal;

        o.active = false;
        totalEarmarked -= principal;
        _pop(holder, o.index);
        delete offerPinCommitment[id];
        delete offerFreeAtCreate[id];

        emit OfferSwept(id, donor, holder, principal);
    }

    // =====================================================================
    // CREDITS
    // =====================================================================

    function syncCredits() external returns (uint256 formed) {
        (, , formed) = _form(msg.sender);
    }

    function redeemCredit(Rec calldata r) external nonReentrant {
        (int256 eff, , ) = _form(msg.sender);
        Account storage a = _acct[msg.sender];
        uint256 credits = a.credits;
        if (credits == 0) revert NoCredit();
        if (r.payloadHash != _redeemHash(msg.sender, 0, 1)) revert BadRedeemHash();

        uint256 face = _payoutFor(eff);
        uint256 share = a.trustCredits / credits;
        uint256 paid = face > share ? share : face;
        if (paid == 0) revert NothingToRedeem();

        if (address(this).balance < totalEarmarked + MIN_RESERVE + paid) revert PoolTooThin();

        a.credits = credits - 1;
        a.trustCredits -= paid;
        totalTrustCredits -= paid;

        if (credits == 1 && a.trustCredits != 0) {
            uint256 leftover = a.trustCredits;
            a.free += leftover;
            totalFree += leftover;
            totalTrustCredits -= leftover;
            a.trustCredits = 0;
        }

        redeemNonce[msg.sender] += 1;

        SOS.recordSignature(msg.sender, SOS69069_LEDGER, r.payloadHash, r.signature, r.metadata);

        uint256 ratePct = face == DEAD_ZONE_PAYOUT ? 0 : (face * 100) / UNIT;
        emit CreditRedeemed(msg.sender, eff, ratePct, paid);

        _send(msg.sender, paid);
    }

    function transferCredits(address to, uint256 amount, bytes32 payloadHash, bytes calldata signature, string calldata metadata) external nonReentrant {
        if (to == address(0)) revert ZeroAddress();
        if (to == msg.sender) revert SelfTransfer();
        if (amount == 0) revert ZeroAmount();

        (int256 effAtSend, uint256 trustAtSend, ) = _form(msg.sender);
        Account storage a = _acct[msg.sender];
        uint256 credits = a.credits;
        if (credits < amount) revert InsufficientCredits();

        uint256 moved = (a.trustCredits * amount) / credits;
        a.credits = credits - amount;
        a.trustCredits -= moved;

        _acct[to].credits += amount;
        _acct[to].trustCredits += moved;

        SOS.recordSignature(msg.sender, to, payloadHash, signature, metadata);
        emit CreditsTransferred(msg.sender, to, amount, moved, effAtSend, trustAtSend);
    }

    // =====================================================================
    // GASCLAIM
    // =====================================================================

    function gasClaimName() external pure returns (string memory) { return "GasClaim"; }
    function gasClaimSymbol() external pure returns (string memory) { return "GASC"; }
    function decimals() external pure returns (uint8) { return 18; }

    function transfer(address to, uint256 amount) external returns (bool) {
        if (to == address(0)) revert ZeroAddress();
        if (balanceOf[msg.sender] < amount) revert InsufficientBalance();
        balanceOf[msg.sender] -= amount;
        balanceOf[to] += amount;
        emit Transfer(msg.sender, to, amount);
        return true;
    }

    function approve(address spender, uint256 amount) external returns (bool) {
        allowance[msg.sender][spender] = amount;
        emit Approval(msg.sender, spender, amount);
        return true;
    }

    function transferFrom(address from, address to, uint256 amount) external returns (bool) {
        if (to == address(0)) revert ZeroAddress();
        if (balanceOf[from] < amount) revert InsufficientBalance();

        uint256 allowed = allowance[from][msg.sender];
        if (allowed != type(uint256).max) {
            if (allowed < amount) revert InsufficientAllowance();
            allowance[from][msg.sender] = allowed - amount;
        }

        balanceOf[from] -= amount;
        balanceOf[to] += amount;
        emit Transfer(from, to, amount);
        return true;
    }

    function redeemGasClaim(uint256 amount, Rec calldata r) external nonReentrant {
        if (amount == 0) revert ZeroAmount();
        if (balanceOf[msg.sender] < amount) revert InsufficientBalance();
        if (r.payloadHash != _redeemHash(msg.sender, 1, amount)) revert BadRedeemHash();

        Account storage a = _acct[msg.sender];
        if (a.free < amount) revert ExceedsAllowance();

        if (address(this).balance < totalEarmarked + MIN_RESERVE + amount) revert PoolTooThin();

        a.free -= amount;
        totalFree -= amount;
        _burn(msg.sender, amount);
        redeemNonce[msg.sender] += 1;

        SOS.recordSignature(msg.sender, SOS69069_LEDGER, r.payloadHash, r.signature, r.metadata);
        emit GasClaimRedeemed(msg.sender, amount);
        _send(msg.sender, amount);
    }

    // =====================================================================
    // VIEWS
    // =====================================================================

    function offers(uint256 id) external view returns (
        address donor, address holder, uint256 principal, bool active,
        OfferType kind, bytes32 recordHash, uint64 createdAt, uint64 sweepableAt
    ) {
        Offer storage o = _offers[id];
        return (o.donor, o.holder, o.principal, o.active, o.kind, o.recordHash, o.createdAt, o.sweepableAt);
    }

    function lastTrust(address user) external view returns (uint256) { return _acct[user].lastTrust; }
    function redemptionCredits(address user) external view returns (uint256) { return _acct[user].credits; }

    function allowanceOf(address user) external view returns (uint256 free, uint256 trustCredits) {
        Account storage a = _acct[user];
        return (a.free, a.trustCredits);
    }

    function unallocatedBalance() external view returns (uint256) {
        uint256 bal = address(this).balance;
        uint256 locked = totalEarmarked + totalFree + totalTrustCredits;
        return bal > locked ? bal - locked : 0;
    }

    function poolBalance() external view returns (uint256) { return address(this).balance; }

    function totalClaimable() external view returns (uint256) {
        return totalFree + totalTrustCredits;
    }

    function formableCredits(address user) public view returns (uint256) {
        Account storage a = _acct[user];
        uint256 t = SOS.trustCountOf(user);
        uint256 pending = t > a.lastTrust ? t - a.lastTrust : 0;
        uint256 byAllowance = (a.free + UNIT - 1) / UNIT;
        return pending < byAllowance ? pending : byAllowance;
    }

    function pendingCredits(address user) external view returns (uint256) {
        return _acct[user].credits + formableCredits(user);
    }

    function isEligible(address user) external view returns (bool) {
        return _acct[user].credits + formableCredits(user) > 0;
    }

    function ratePercentOf(int256 eff) external pure returns (uint256) {
        uint256 pos = _position(eff);
        return pos == DEAD_ZONE_POS ? 0 : BASE_RATE_PCT + pos;
    }

    function quoteRedeemCredit(address user) external view returns (uint256 ratePct, uint256 payout) {
        uint256 face = _payoutFor(SOS.effectiveOf(user));
        ratePct = face == DEAD_ZONE_PAYOUT ? 0 : (face * 100) / UNIT;
        Account storage a = _acct[user];
        uint256 share = a.credits == 0 ? 0 : a.trustCredits / a.credits;
        payout = face > share ? share : face;
    }

    function sawtoothPosition(address user) public view returns (uint256) {
        return _position(SOS.effectiveOf(user));
    }

    function signerMetrics(address user) external view returns (uint256, uint256, int256) {
        return SOS.statsOf(user);
    }

    function offerCountOf(address h) external view returns (uint256) { return offersHeldBy[h].length; }
    function offerIdsOf(address h) external view returns (uint256[] memory) { return offersHeldBy[h]; }

    function redeemPayloadHash(address user, uint8 kind, uint256 amount) external view returns (bytes32) {
        return _redeemHash(user, kind, amount);
    }

    function name() external pure returns (string memory) { return "SOS69069 dSOS"; }
    function symbol() external pure returns (string memory) { return "dSOS"; }

    // =====================================================================
    // INTERNAL
    // =====================================================================

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

        uint256 freeAtCreate = 0;
        if (kind == OfferType.G && delayBlocks >= FREE_WINDOW && msg.value > UNIT) {
            freeAtCreate = UNIT;
        }

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

        if (freeAtCreate > 0) {
            _acct[msg.sender].free += freeAtCreate;
            totalFree += freeAtCreate;
            offerFreeAtCreate[id] = freeAtCreate;
        }

        if (kind == OfferType.G) offerPinCommitment[id] = pinC;
    }

    function _form(address user) private returns (int256 eff, uint256 trust, uint256 formed) {
        uint256 push;
        (push, trust, eff) = SOS.statsOf(user);

        Account storage a = _acct[user];
        uint256 pending = trust > a.lastTrust ? trust - a.lastTrust : 0;
        uint256 f = a.free;
        if (pending == 0 || f == 0) return (eff, trust, 0);

        uint256 byAllowance = (f + UNIT - 1) / UNIT;
        formed = pending < byAllowance ? pending : byAllowance;

        uint256 take = formed * UNIT;
        if (take > f) take = f;

        a.free = f - take;
        totalFree -= take;

        a.trustCredits += take;
        totalTrustCredits += take;

        a.credits += formed;
        a.lastTrust += formed;

        emit CreditsFormed(user, formed, take, a.credits, a.trustCredits, push, trust);
    }

    function _position(int256 eff) private pure returns (uint256) {
        uint256 abs = eff >= 0 ? uint256(eff) : uint256(-(eff + 1)) + 1;
        return (abs / RATE_STEP) % CYCLE_STEPS;
    }

    function _payoutFor(int256 eff) private pure returns (uint256) {
        uint256 pos = _position(eff);
        if (pos == DEAD_ZONE_POS) return DEAD_ZONE_PAYOUT;
        return UNIT * (BASE_RATE_PCT + pos) / 100;
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

    function _mint(address to, uint256 amount) private {
        totalSupply += amount;
        balanceOf[to] += amount;
        emit Transfer(address(0), to, amount);
    }

    function _burn(address from, uint256 amount) private {
        balanceOf[from] -= amount;
        totalSupply -= amount;
        emit Transfer(from, address(0), amount);
    }
}