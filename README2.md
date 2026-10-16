**Updated whole connected loop of dSOS + SOS ledger** 

### 1. Starting the loop – Locking ETH (createOffer)
- Anyone (Donor) can lock **any amount** of ETH to any address (Holder) by calling `createOffer{value: X}`.
- The ETH is locked inside the dSOS contract, earmarked, and non-cancellable.
- No SOS ledger record is written at this step.
- The only thing created is a transferable Offer that only the current Holder can redeem.

**How the Holder knows the ETH was locked to them**  
The offer is stored on-chain and indexed to the Holder’s address.  
It does **not** appear as a normal ERC-20 balance in a regular wallet.  
The Holder discovers it by:
- Querying the dSOS contract for their active offers (via the internal index/list the contract maintains), or
- Watching the `OfferCreated` (or equivalent) event, or
- Using a frontend / explorer that reads the dSOS offer mapping.

Once seen, the Holder can redeem it or transfer the offer to someone else.

### 2. Closing the locked-ETH leg – Redeem Offer
- Only the Holder can call `redeemOffer`.
- Two things happen atomically:
  1. The full locked ETH is sent to the Holder.
  2. A mandatory SOS ledger record is written:  
     `SOS.recordSignature(Holder → Donor)`
- This record increases the Donor’s `trustCountOf` by +1 on the external SOS69069 ledger.
- There is **no way** to take the locked ETH without creating this trust record.

### 3. Earning credits from SOS ledger activity
- Credits inside dSOS are not created by dSOS itself.
- They are derived purely from the external SOS ledger:  
  **1 credit = 1 new trust** that points to you (`trustCountOf` growth).
- The most common way a new trust appears via this system is exactly step 2 above (someone redeems an offer you funded).
- Other external SOS activity that increases your trust count also gives you credits.

### 4. Cashing out credits – Redeem from common pool (sawtooth)
- You burn 1 credit via `redeemCredit`.
- The contract pays you ETH from the **common pool** according to a sawtooth formula:
  - Payout ranges from 0 % to 100 % of **UNIT = 0.006 ETH**.
- This is the only place the 0.006 ETH figure matters.
- The common pool must have free ETH available (above the reserved amount that backs outstanding offers).
- Burning the credit does **not** write any new SOS ledger record.

### 5. How the common pool is filled
- Anyone can send ETH into the common pool via `receive()` or `donateCommon()`.
- Each non-zero donation also mints 1 wei of GasClaim (a separate micro-ERC20 redeemable 1:1 for wei).
- The pool only shrinks when people redeem credits or GasClaim.
- Outstanding offers are always protected by `totalEarmarked + MIN_RESERVE`.

### Complete circular flow
1. Donor locks ETH → creates Offer for Holder (Holder sees it on-chain via contract query / events / frontend).
2. Holder redeems → gets the ETH **and** creates a SOS trust record pointing to the Donor.
3. Donor’s `trustCountOf` rises → Donor receives 1 credit inside dSOS.
4. Donor (or anyone who later receives the credit) burns the credit → receives up to 0.006 ETH from the common pool (sawtooth).
5. The common pool is kept alive by voluntary donations.

**Key connections summary**
- Locked ETH ↔ mandatory SOS trust record (only via redeemOffer)
- SOS trust records ↔ credits inside dSOS
- Credits ↔ sawtooth ETH payout from the common pool (0–0.006 ETH)
- Common pool ↔ independent from locked offers (only needs free ETH to pay redemptions)
- Holder awareness ↔ on-chain offer indexed to their address (not a standard wallet token balance)
