## SOS69069 dSOS
0xbD08A73E02BA266f5cC8c4c6a08348d806e61f2C

https://drive.google.com/file/d/12Xk0UGCUoU9j1wH8VC4S1nN3eUn4ebKo/view?usp=drivesdk

https://drive.google.com/file/d/1vJIiH9coovPRCiBbvgxm7t1H0WWmlBBW/view?usp=drivesdk

https://github.com/Taru8899/SOS69069dSOS/actions/runs/45618507218

MOCKUP
https://drive.google.com/drive/folders/1VGrpktFl4zJypb0syWv6AyHvn95UAqar

**dSOS** is a fully permissionless, no-admin smart contract that turns SOS ledger records into redeemable ETH slices (and vice-versa), while also running a shared ETH pool that only staked users can draw from via credits.

### Core Units
- 1 **slice** = 1 **dSOS** = **0.001 ETH**
- 1 **credit** = 0.001 ETH (from the pool)
- Everything is measured in whole slices. `totalSupply × 0.001 ETH` always equals the ETH currently locked in active offers.

### The Four Offer Types

| Type | Who holds the slices at creation? | How do you get ETH out? | Transferable? | Special rules |
|------|-----------------------------------|--------------------------|---------------|---------------|
| **S** | Chosen receiver | Free redeem (no records needed) | Yes (while > 1 day left) | Pure timed escrow / gift |
| **A** | The contract itself (escrow) | Seller confirms records → earns slices → redeems | No | Open to any seller |
| **B** | The contract itself (escrow) | Only the named address can confirm records | No | Named seller only |
| **G** | Chosen receiver | Redeem requires the correct PIN | No | Can become a **gate** |

### Main Flows

**1. Creating an offer**
- You send ETH (`msg.value` must be a multiple of 0.001 ETH).
- The contract mints the corresponding number of slices and locks the ETH (`totalEarmarked`).
- Delay of 0 becomes 1 block. Expiry is fixed at creation and cannot be changed.

**2. A / B offers (record → slices)**
1. Creator opens an A or B offer → ETH is escrowed, slices are minted to the contract.
2. Seller writes records on the external SOS ledger with a very specific payload that includes the offer ID + a salt created at offer creation time.
3. Seller calls `syncRecords` → contract checks the ledger, moves slices from the escrow into a personal offer belonging to the seller.
4. Seller redeems those slices for ETH before expiry.
5. After expiry anyone can `sweepOffer` → remaining unclaimed escrow goes into the pool forever.

**3. Redeeming**
- Before the expiry block, the current holder of an offer can redeem any number of its slices for ETH.
- G offers also require the correct PIN.
- A/B redemptions are **capped** by how many slices that user previously funded (`produced` vs `redeemed`). This is the only “allowance” in the system.
- S and G redemptions have no such cap.

**4. Sweeping**
- After expiry, anyone can call `sweepOffer`.
- Unredeemed slices / unconfirmed escrow are burned and the ETH goes into the pool.
- If the offer was flagged as a **gate**, the original donor is permanently **staked**.

### Gate & Staking
- A G offer with the minimum delay (1 block) becomes a gate if its value is **strictly greater** than  
  `0.001 ETH + current unallocated pool balance`.
- When that gate offer is later swept, the donor is staked forever.
- Only staked addresses can form and redeem **credits**.

### Credits (the only way to withdraw from the pool)
1. Be staked.
2. Call `syncCredits` → turns new SOS trust records addressed to you into credits (1 record = 1 credit).
3. After a 2-day cooldown, call `redeemCredit` → burns credits and receives ETH from the pool (subject to a tiny reserve).

Credits cannot be transferred. The pool can only shrink through credit redemptions.

### Nonce System
Almost every value-moving function takes an `expectedNonce` as its last argument. It must match the caller’s current `redeemNonce`. On success the nonce increases by 1. This gives strict ordering and prevents accidental double-execution of pending transactions.  
(The ordinary ERC-20 `transfer` is an exception — it still works for wallets but does not check a nonce.)

### ERC-20 Compatibility (display only)
- `name`, `symbol`, `decimals(0)`, `totalSupply`, `balanceOf` work.
- `Transfer` events are emitted correctly.
- `approve` / `allowance` / `transferFrom` are deliberately disabled.
- There is a custom `allowanceOf(user)` that only tracks the A/B produced/redeemed remaining quota.

### In one sentence
You lock ETH into timed offers; other people (or yourself) earn those slices by writing the right records on the SOS ledger or by holding a free/gifted S offer; after expiry leftover value goes into a shared pool that only people who have “paid the gate” (by creating a large enough short-lived G offer) can later withdraw from via credits.
