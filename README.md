## SOS69069 dSOS

0x75fEc69CcA3887FFB65254f1078e5c1B27B8F74A

**How this version works (plain language)**
There is one big shared ETH pool.  
People can put money in and later take money out, but with strict rules. The main new rule is a **staking gate**.

---

### 1. Putting money in

- Just sending ETH (`receive`) or using `donateCommon`  
  → You only get 1 tiny GasClaim token.  
  → You get **no** free balance. The ETH goes into the pool with no claim attached.

- Creating normal offers (B, T, P)  
  → You lock your ETH. You get **no free**.

- Creating a special G-offer (gated)  
  → You can get free, but only under certain conditions (see below).

---

### 2. The “Gate” (new staking ticket)

There is a special kind of G-offer that acts as a **ticket to redeem credits**:

- You create a G-offer with:
  - delay = 1 block
  - value > 0.06 ETH

- If someone **sweeps** that offer (after 1 block), you become **permanently staked**.
- If the receiver **redeems** it in time (with the PIN), the gate is cancelled and you are **not** staked.

**Only staked people can call `redeemCredit`.**

This is the main new protection.

---

### 3. Free balance (the thing that lets you form credits)

You only get free in these cases:

- When you create a G-offer that has delay ≥ 7200 blocks **and** value > 0.006 ETH  
  → You immediately get 0.006 ETH free.

- When that same G-offer is later redeemed (before it can be swept)  
  → You can get extra free based on how many 7200-block periods actually passed.

Sweeping a G-offer gives you **zero** free.

---

### 4. Credits

- You use your free balance + new trust records to form credits.
- Each credit locks some free into “trustCredits”.
- Only **staked** users can redeem credits for ETH.
- When you redeem a credit you get a sawtooth payout (usually a bit less than 0.006 ETH).

---

### 5. Offers timeline

Every offer has a time window:

- From creation until `sweepableAt` → the holder can redeem (G needs PIN).
- After `sweepableAt` → anyone can sweep it. The money stays in the pool forever and the original owner loses it.

---

### Simple summary of the new Gate

1. Want to redeem credits later?  
2. Create a special G-offer > 0.06 ETH with delay = 1.  
3. Let it get swept → you become staked forever.  
4. Now you can redeem credits.

If you redeem the gate offer yourself in time, you stay un-staked and cannot redeem credits.

That is the core new mechanism.

# dSOS

dSOS is an ownerless Solidity contract (0.8.36) that sits on top of the SOS69069 ledger at `0x7373DBC24Dcd785896E8Ac3d5372c6ced9B75a8A`. It handles ETH donations, offers (B/T/P transferable, G gated with a PIN), credits formed from trust records plus allowance, a sawtooth payout and a GasClaim token (GASC).

All state-changing functions use a reentrancy lock, except `syncCredits`. There is no owner, no admin and no upgrade path.

## Staking gate (`staked`)

- **How a user becomes staked:** by sweeping a **gate offer**. A gate offer is a G offer with delay of exactly 1 (a delay of 0 also becomes 1) and `msg.value > 0.06 ETH + unallocatedBalance` as it was before the offer. When anyone sweeps it, the donor becomes **permanently** staked, with no un-stake.
- **What the gate blocks:** `redeemCredit` and `redeemGasClaim` revert with `NotStaked` for unstaked callers.
- **What it does not block:** every other function, including `redeemOffer` (G, B, T and P), `transferOffer`, `sweepOffer`, `transferCredits`, `syncCredits`, the GASC `transfer`/`approve`/`transferFrom`, `receive` and `donateCommon`.
- **If the gate offer is redeemed instead of swept:** the flag is cleared and the donor is **not** staked.

## Constants and hard limits

| Name | Value | Meaning |
|---|---|---|
| `UNIT` | 0.006 ETH | Payout base; max free allowance bound into one credit |
| `MIN_RESERVE` | 0.000999 ETH | Floor above offer funds that payouts may never breach |
| `DEAD_ZONE_PAYOUT` | 0.0000033 ETH | Payout at sawtooth position 70 |
| `RATE_STEP` / `CYCLE_STEPS` / `BASE_RATE_PCT` / `DEAD_ZONE_POS` | 1001 / 71 / 30 / 70 | Sawtooth shape |
| `GAS_CLAIM_MINT` | 1 | GASC minted per donation call |
| `FREE_WINDOW` | 7200 blocks | One free-allowance step for G offers |
| `DEFAULT_DELAY` | 1 block | Used when `delayBlocks` is 0 |
| `GATE_FLOOR` / `GATE_DELAY` | 0.06 ETH / 1 block | Gate-offer thresholds |

- **Offer principal:** at most `uint96` max (about 7.9e10 ETH), and at least 1 wei.
- **Delay:** there is no minimum and no cap. The only limit is that `block.number + delay` must fit in `uint64`, otherwise `BadDelay`.
- **Offers per holder:** fewer than `uint32` max, otherwise `TooManyOffers`.
- **Offer ids:** start at 1.

## Sawtooth payout (face value)

- `pos = (|eff| / 1001) % 71`, where `eff` is the ledger's effective trust (trust minus push).
- If `pos == 70`, the face is 0.0000033 ETH.
- Otherwise the face is `0.006 × (30 + pos) / 100`, from 0.0018 ETH (pos 0) to 0.00594 ETH (pos 69).

## Funding

### `receive()`
- Sending ETH with `msg.value > 0` mints 1 GASC to the sender and emits `Donation`.
- A zero-value send does nothing and does not revert.
- It creates no free and no ledger record.
- The ETH becomes unallocated pool.

### `donateCommon(payloadHash, signature, metadata)` (payable)
- `msg.value` must be above 0, otherwise `InvalidValue`.
- It mints 1 GASC to the sender.
- It makes the ledger record **donor → ledger address**.
- It creates no free.

## Offers

### `createOffer(kind, to, delayBlocks, payloadHash, signature, metadata)` (payable, B/T/P only)
- `kind = G` reverts with `InvalidValue`.
- `to` must not be the zero address (`ZeroAddress`).
- `msg.value` must be above 0 and at most `uint96` max (`InvalidValue`).
- A `delayBlocks` of 0 becomes 1. `sweepableAt = block.number + delay`.
- It stores the offer and adds `msg.value` to `totalEarmarked`.
- **No free is ever created for B/T/P.**
- It makes the ledger record **donor → `to`**.
- The offer is not cancellable by the donor.

### `createOfferGated(to, delayBlocks, pinCommitment_, payloadHash, signature, metadata)` (payable, G only)
- `pinCommitment_` must not be zero (`InvalidValue`). The holder's PIN commitment is `keccak256(abi.encode(pin, donor, to))`.
- The same validity checks apply as in `createOffer`.
- **Free at creation:** if delay ≥ 7200 and value > 0.006 ETH, the donor's free goes up by exactly 0.006 ETH. Otherwise there is none.
- **Gate flag:** set if delay == 1 and `msg.value > 0.06 ETH + unallocatedBalance` as it was before this offer (see the staking gate section).
- It makes the ledger record **donor → `to`**.

### `transferOffer(id, to, payloadHash, signature, metadata)` (B/T/P only)
- The offer must be active (`OfferNotActive`).
- The caller must be the holder (`NotHolder`).
- G reverts with `NotTransferable`.
- It requires `block.number < sweepableAt`, otherwise `WindowClosed`.
- `to` must not be the zero address.
- Only the holder changes. The donor, delay, principal and sweep time stay the same.
- It makes the ledger record **holder → new holder**.

### `redeemOffer(id, pin, payloadHash, signature, metadata)`
- The offer must be active, and the caller must be the holder.
- It requires `block.number < sweepableAt`, otherwise `WindowClosed`. This applies to every kind.
- **G only:**
  - The PIN must match: `keccak256(abi.encode(pin, donor, msg.sender))` against the stored commitment, otherwise `BadOfferPin`.
  - **Extra free to the donor** (not the holder) is paid only if principal > 0.006 ETH and the offer's declared delay ≥ 7200. The amount is `min(principal, floor((block.number − createdAt) / 7200) × 0.006)` minus the free already granted at creation, if that is positive.
- The gate flag is cleared, so **the donor is not staked**.
- The offer closes, `totalEarmarked` drops by the principal, and the offer is removed from the holder's list.
- It makes the ledger record **holder → original donor**.
- It pays the **full principal** to the holder.
- B/T/P need no PIN and give no free. **No staking is required** for any offer kind.

### `sweepOffer(id)` (anyone, any kind)
- The offer must be active, and `block.number >= sweepableAt`, otherwise `TooEarly`.
- If the offer is a gate offer, **the donor becomes permanently staked**.
- The offer closes and `totalEarmarked` drops by the principal.
- The principal stays in the contract as unallocated pool. It never goes back to the donor, and the donor gets no extra free (what was given at creation stays).
- No ledger record is made and no ETH moves.

## Credits

### Forming credits (`_form`, run inside `syncCredits`, `redeemCredit` and `transferCredits`)
- `pending` is the ledger trust count minus `lastTrust`, if positive.
- Nothing forms if `pending == 0` or the user's free is 0.
- `formed = min(pending, ceil(free / 0.006))`.
- The ETH moved from free into trust credits is `min(formed × 0.006, free)`, and `credits` and `lastTrust` both go up by `formed`.
- So each credit needs 1 trust record and binds at most 0.006 ETH of free. The last credit may bind less. Trust records that cannot be backed stay pending.

### `syncCredits()`
Forms credits for the caller, makes no ledger record, needs no staking, and has no reentrancy lock.

### `redeemCredit(r)`
`r` is `(payloadHash, signature, metadata)`.
1. **The caller must be staked** (`NotStaked`).
2. Credits are formed first.
3. The caller needs at least 1 credit (`NoCredit`).
4. `r.payloadHash` must equal `redeemPayloadHash(caller, 0, 1)` for the current nonce (`BadRedeemHash`).
5. `paid = min(sawtooth face, trustCredits / credits)`, with integer division. If that is 0, it reverts with `NothingToRedeem`.
6. The reserve check is `balance ≥ totalEarmarked + 0.000999 ETH + paid`, otherwise `PoolTooThin`. It reverts and does not pay a smaller amount.
7. One credit is burned, and `paid` comes out of trust credits.
8. If that was the last credit, any leftover trust credits go back to free.
9. The nonce goes up by 1.
10. It makes the ledger record **caller → ledger address** and pays `paid` to the caller.

### `transferCredits(to, amount, payloadHash, signature, metadata)`
- `to` must not be the zero address, `to` must not be the caller (`SelfTransfer`), and `amount` must be above 0.
- Credits are formed for the sender first, and the sender needs at least `amount` credits (`InsufficientCredits`).
- `moved = trustCredits × amount / credits` (floor). The credits and `moved` trust credits go to the receiver.
- **No staking is required** to send or receive. The receiver needs it only to redeem.
- It makes the ledger record **sender → `to`**.

## GasClaim token (GASC)

- The token name is "GasClaim" and the symbol is "GASC". `decimals()` returns 0, so 1 GASC equals 1 wei.
- `transfer(to, amount)` rejects the zero address and insufficient balance. `approve` sets an allowance. `transferFrom` treats an allowance of max `uint256` as unlimited, otherwise it deducts. None of these make a ledger record, and none need staking.

### `redeemGasClaim(amount, r)`
- **The caller must be staked** (`NotStaked`), `amount` must be above 0, and the caller must hold at least `amount` GASC.
- `r.payloadHash` must equal `redeemPayloadHash(caller, 1, amount)` (`BadRedeemHash`).
- The caller's free must be at least `amount` (`ExceedsAllowance`).
- The same reserve check applies.
- It burns the GASC and deducts free, then bumps the nonce.
- It makes the ledger record **caller → ledger address** and pays `amount` wei.

## Redeem signature rule

`redeemPayloadHash(user, kind, amount)` is `keccak256(abi.encode(user, kind, amount, redeemNonce[user], contract address, chainid))`. For kind 0, `amount` is forced to 1. Each successful redeem bumps the nonce, so a signed message works once.

## Views

- `offers(id)` returns donor, holder, principal, active, kind, recordHash, createdAt and sweepableAt.
- `sweepableOffers(holder)` returns the active offers held by `holder` that are (`block.number >= sweepableAt`).
- `allowanceOf(user)` returns `(free, trustCredits)`.
- `redemptionCredits(user)`, `lastTrust(user)`, `offerCountOf(h)`, `offerIdsOf(h)` read the stored values.
- `unallocatedBalance()` is `balance − (totalEarmarked + totalFree + totalTrustCredits)`, with a floor of 0.
- `poolBalance()` is the contract balance.
- `totalClaimable()` is `totalFree + totalTrustCredits`.
- `formableCredits(user)` is `min(pending, ceil(free / 0.006))`.
- `pendingCredits(user)` is credits plus `formableCredits`.
- `isEligible(user)` is true if that sum is above 0. It does not check staking.
- `ratePercentOf(eff)` is 0 at position 70, otherwise `30 + pos`.
- `quoteRedeemCredit(user)` returns `(ratePct, payout)`, where `payout = min(face, trustCredits / credits)` (0 share if no credits). It ignores staking and the reserve.
- `sawtoothPosition(user)` is `pos` for the user's current effective trust.
- `signerMetrics(user)` returns the ledger stats.
- Public variables are `offerPinCommitment`, `offerFreeAtCreate`, `offerIsGate`, `staked`, `offersHeldBy`, `nextOfferId`, `totalEarmarked`, `totalFree`, `totalTrustCredits`, `redeemNonce`, `balanceOf`, `allowance` and `totalSupply`.

## What the code does not limit

- **Free and trust credits are counters, not locked ETH.** Payouts check only `balance ≥ offers + 0.000999 ETH + payout`. If total claims exceed the pool, redeems are first-come, and later ones revert with `PoolTooThin`.
- There is no delay minimum or cap, and no limit on the number of credits or on trust records.
- `to` may be the donor's own address in an offer.
- The 0.006 ETH free at G creation is paid immediately and is never clawed back, even if the offer is redeemed early.
