## SOS69069 dSOS

0x75fEc69CcA3887FFB65254f1078e5c1B27B8F74A

It's a fixed, ownerless smart contract. It has no owner, no admin and no upgrade path, so nobody can rescue or reverse anything. 
People can put money in and later take money out, but with strict rules. The main new rule is a **staking gate**.
All state-changing functions have a reentrancy lock, except `syncCredits`.

**The building blocks**
- **Pool:** ETH sitting in the contract. Sending ETH with `msg.value > 0` to `receive()` mints 1 GASC to you and adds the ETH to the unallocated pool. A zero-value send does nothing and doesn't revert.
- **GASC token:** name "GasClaim", symbol "GASC", `decimals()` is 0, so 1 GASC = 1 wei. You get 1 GASC per donation call (`GAS_CLAIM_MINT` = 1).
- **Offers:** ETH locked for a holder (`to`) with a delay. There are four kinds: B/T/P (`createOffer`) and G (`createOfferGated`).
- **Free allowance:** a counter, not locked ETH. Each credit binds at most `UNIT` = 0.006 ETH of it.
- **Trust records:** ledger entries (donor → recipient) that you receive. Each one can become 1 credit.
- **Credits:** formed from pending trust records plus free allowance. Redeeming one pays you ETH.
- **Staked:** a status you need before you can redeem credits or GASC.
- **Sawtooth:** your payout size depends on your effective trust (trust minus push).

## How to use it, step by step

1. **Donate (optional).**
   - Send ETH to the contract, or call `donateCommon(payloadHash, signature, metadata)`. It needs `msg.value > 0`, otherwise `InvalidValue`.
   - Both mint 1 GASC and create no free.
   - `donateCommon` also creates the ledger record donor → ledger address.
2. **Create an offer.**
   - `createOffer(kind, to, delayBlocks, payloadHash, signature, metadata)` is for B/T/P only. `kind = G` reverts with `InvalidValue`.
   - `to` can't be the zero address. `msg.value` must be above 0 and at most `uint96` max (about 7.9e10 ETH).
   - A `delayBlocks` of 0 becomes `DEFAULT_DELAY` = 1 block. `sweepableAt = block.number + delay`.
   - There is no minimum or cap on the delay, but `block.number + delay` must fit in `uint64`, otherwise `BadDelay`.
   - It never creates free. The ledger record is donor → `to`. The donor can't cancel the offer.
3. **Create a gated (G) offer.**
   - `createOfferGated(to, delayBlocks, pinCommitment_, ...)` needs a nonzero `pinCommitment_`. The commitment is `keccak256(abi.encode(pin, donor, to))`.
   - **Free at creation:** if delay ≥ `FREE_WINDOW` (7200 blocks) and value > 0.006 ETH, the donor's free rises by exactly 0.006 ETH. Otherwise there is none.
   - **Gate offer:** if delay == 1 and `msg.value > GATE_FLOOR` (0.06 ETH) + unallocated balance as it was before this offer, the offer is flagged as a gate offer.
4. **Holder acts before `sweepableAt`.**
   - `transferOffer(id, to, ...)` works for B/T/P only. G reverts with `NotTransferable`. It needs `block.number < sweepableAt`, otherwise `WindowClosed`. Only the holder changes. The ledger record is holder → new holder.
   - `redeemOffer(id, pin, ...)` also requires `block.number < sweepableAt`, for every kind. It pays the full principal to the holder and clears the gate flag, so the donor is not staked. The ledger record is holder → original donor.
   - For G, the PIN must match or you get `BadOfferPin`. The donor can also get extra free, but only if principal > 0.006 ETH and delay ≥ 7200. The amount is `min(principal, floor((block.number − createdAt) / 7200) × 0.006)` minus the free already granted at creation, if that is positive.
5. **If nobody redeems in time, anyone can call `sweepOffer(id)`** once `block.number >= sweepableAt`.
   - The principal stays in the pool forever. It never goes back to the donor.
   - If it was a gate offer, the donor becomes **permanently staked**. There is no un-stake.
   - No ETH moves and no ledger record is made.
6. **Form credits** with `syncCredits()`. It makes no ledger record and has no reentrancy lock.
   - `pending` is the ledger trust count minus `lastTrust`, if positive.
   - `formed = min(pending, ceil(free / 0.006))`.
   - The ETH moved from free into trust credits is `min(formed × 0.006, free)`.
   - Trust records you can't back with free stay pending.
7. **Redeem credit** with `redeemCredit(r)`, where `r` is `(payloadHash, signature, metadata)`. The steps run in this order:
   1. You must be staked (`NotStaked`).
   2. Credits are formed first.
   3. You need at least 1 credit (`NoCredit`).
   4. `r.payloadHash` must equal `redeemPayloadHash(caller, 0, 1)` for your current nonce (`BadRedeemHash`).
   5. `paid = min(sawtooth face, trustCredits / credits)`, with integer division. If that is 0, it reverts with `NothingToRedeem`.
   6. The reserve check is `balance ≥ totalEarmarked + 0.000999 ETH + paid`, otherwise `PoolTooThin`. It reverts and doesn't pay a smaller amount.
   7. One credit is burned, and `paid` comes out of trust credits.
   8. If that was your last credit, leftover trust credits go back to free.
   9. The nonce goes up by 1.
   10. The ledger record is caller → ledger address, and `paid` is sent to you.
8. **Move credits** with `transferCredits(to, amount, ...)`.
   - `to` can't be the zero address or yourself (`SelfTransfer`), and `amount` must be above 0.
   - You need at least `amount` credits (`InsufficientCredits`).
   - `moved = trustCredits × amount / credits` (floor).
   - The receiver doesn't need to be staked to receive, only to redeem. The ledger record is sender → `to`.
9. **Redeem GASC** with `redeemGasClaim(amount, r)`.
   - You must be staked, `amount` must be above 0, and you must hold at least `amount` GASC.
   - `r.payloadHash` must equal `redeemPayloadHash(caller, 1, amount)`, and your free must be at least `amount` (`ExceedsAllowance`).
   - The same reserve check applies. It burns the GASC, deducts free, bumps the nonce, records caller → ledger address, and pays `amount` wei.

**Payout size (sawtooth)**
- `pos = (|eff| / 1001) % 71`, with `RATE_STEP` = 1001 and `CYCLE_STEPS` = 71.
- Face is `0.006 × (30 + pos) / 100`, so `BASE_RATE_PCT` = 30 and the range is 0.0018 ETH (pos 0) to 0.00594 ETH (pos 69).
- At `DEAD_ZONE_POS` = 70 the face is `DEAD_ZONE_PAYOUT` = 0.0000033 ETH.

**Redeem signature rule:** `redeemPayloadHash(user, kind, amount)` is `keccak256(abi.encode(user, kind, amount, redeemNonce[user], contract address, chainid))`. For kind 0, `amount` is forced to 1. Each successful redeem bumps the nonce, so a signed message works once.

**Useful read-only views:** `offers(id)`, `sweepableOffers(holder)`, `allowanceOf(user)` → (free, trustCredits), `redemptionCredits`, `lastTrust`, `offerCountOf`, `offerIdsOf`, `unallocatedBalance()`, `poolBalance()`, `totalClaimable()`, `formableCredits`, `pendingCredits`, `isEligible` (doesn't check staking), `ratePercentOf`, `quoteRedeemCredit` (ignores staking and the reserve), `sawtoothPosition`, `signerMetrics`.

Public variables: `offerPinCommitment`, `offerFreeAtCreate`, `offerIsGate`, `staked`, `offersHeldBy`, `nextOfferId`, `totalEarmarked`, `totalFree`, `totalTrustCredits`, `redeemNonce`, `balanceOf`, `allowance`, `totalSupply`.

## Risky practices to avoid

- **Treating free or credits as real, locked money.** They are counters. Payouts only check `balance ≥ offers + 0.000999 ETH + payout`. If total claims exceed the pool, redeems are first-come, and late ones revert with `PoolTooThin`.
- **Sending ETH you expect back.** The donor can't cancel offers. Swept principal stays in the pool for good, and there is no admin to fix mistakes.
- **Delay 0 or 1.** Both become 1 block, so the offer is almost always sweepable before the holder can act. The principal is lost to the pool, and a gate offer permanently stakes the donor. Redeeming requires `block.number < sweepableAt`.
- **Huge delays.** There is no cap, so you can lock funds for an absurdly long time. Only `uint64` overflow (`BadDelay`) stops you.
- **Wrong `to`.** The zero address is rejected, but any other wrong address becomes the holder. B/T/P can be transferred by the holder only. G can never be transferred.
- **Losing the PIN on a G offer.** The PIN is `keccak256(abi.encode(pin, donor, msg.sender))`, so it only works for the right donor and holder pair. A wrong or lost PIN means `BadOfferPin`, and the offer will likely be swept.
- **Expecting free from the wrong places.** `receive()`, `donateCommon` and B/T/P offers never create free. G offers give 0.006 ETH of free only with delay ≥ 7200 and value > 0.006 ETH. That free is paid immediately and never clawed back, even if you redeem early.
- **Trying to redeem without being staked.** Both `redeemCredit` and `redeemGasClaim` revert with `NotStaked`. Staking only happens when a gate offer you donated is swept, and that can't be undone.
- **Stale redeem hashes.** The nonce changes after every successful redeem. Rebuild the hash from the current nonce each time, with the right contract address and chain ID.
- **Expecting small payouts to be profitable.** Payouts are at most 0.00594 ETH, and only 0.0000033 ETH at position 70. Gas costs can exceed that.
- **`transferCredits` surprises.** The amount moved is `trustCredits × amount / credits`, rounded down. The receiver still needs to be staked to redeem.
- **Large amounts.** Start with tiny test amounts, verify the contract address and chain, and never send more than you can afford to lose. This is not financial advice.
