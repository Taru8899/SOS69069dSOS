## SOS69069 dSOS

0x7Bd7c427b3c69e2a09603573ac875987c61ECAB8

### Part 1 – Simple explanation

dSOS is a shared ETH pool on Ethereum.  

You can lock ETH into offers. Each offer is made of “slices”. One slice is always worth exactly 0.001 ETH. You can put many slices into one offer, so creating a large offer costs almost the same gas as a small one.

There are two kinds of offers:

- **Normal offers (B, T, P)** – can be sent to other people and redeemed by the holder before they expire.
- **Gated offers (G)** – locked with a secret PIN. Only the person who knows the PIN can redeem them. These cannot be transferred.

If nobody redeems an offer before the time limit, anyone can “sweep” it. The ETH then stays in the shared pool forever and the original owner loses it.

To take money out of the pool you must first become **staked**. You do this by creating a special short G-offer (called a gate) and letting it be swept. After that you must wait about two days (14 400 blocks). Then you can turn your SOS trust records into credits and redeem them for ETH (1 credit = 0.001 ETH).

Important points:
- Once you are staked you stay staked forever.
- Gate offers are permanent donations to the pool.
- Always test with small amounts first.

---

### Part 2 – Technical description

**Unit & accounting**  
- `UNIT = 0.001 ether`  
- 1 credit = 1 slice = 1 dSOS = `UNIT`  
- Offers are quantity batches: one storage record holds `count` slices.  
- `msg.value` must be an exact multiple of `UNIT`.

**Offers**  
- Four types: `G` (gated), `B`, `T`, `P` (transferable).  
- `createOffer` / `createOfferGated` create a single batch.  
- Partial redeem (`redeemSlices`) and partial transfer (`transferSlices`) are supported; transferring part of a batch splits it into a new offer id with the same `sweepableAt`.  
- Wallet `transfer(to, n)` moves exactly `n` slices from the sender’s newest B/T/P offers that still have more than `MIN_SEND_WINDOW` (7200) blocks left.  
- After `sweepableAt` anyone may call `sweepOffer`; principal becomes unallocated and the slices are burned.

**Gate / Staking**  
- A G-offer with `delayBlocks == 1` and `msg.value > GATE_FLOOR + unallocatedBalance()` is flagged as a gate.  
- Sweeping a gate sets `staked[donor] = true` and records `stakedAt`.  
- `STAKE_COOLDOWN = 14400` blocks must pass before the staker can call `redeemCredit`.

**Credits**  
- Credits are formed 1:1 from SOS ledger trust records via `syncCredits` (requires stake).  
- `redeemCredit(creditsToSpend, Rec)` burns credits and pays `creditsToSpend * UNIT`.  
- Requires valid EIP-712-style payload hash bound to the user’s redeem nonce.  
- Credits are non-transferable.

**Safety & ledger**  
- All state-changing functions are `nonReentrant`.  
- Ledger writes are optional (`try/catch`); failure emits `LedgerRecordSkipped` and does not revert the transaction.  
- Pool invariant on credit redemption: `balance ≥ totalEarmarked + MIN_RESERVE + payout`.

**ERC-20 view**  
- `decimals() = 0`  
- `balanceOf` = number of active slices held  
- `totalSupply` = total active slices  
- `approve` / `transferFrom` are disabled.

---

**Merged version (ready to use)**

dSOS is a shared ETH pool on Ethereum where value is handled in fixed slices of 0.001 ETH.  

Users create offers that can contain any number of slices in a single storage record. Normal offers (B/T/P) are transferable and can be sent from a wallet; gated offers (G) are protected by a PIN and cannot be transferred. Both kinds can be redeemed by the holder before a deadline. After the deadline anyone may sweep the offer, at which point the ETH stays in the pool permanently.

To withdraw from the pool a user must first become staked by creating and allowing the sweep of a short gate offer (G, delay = 1, value strictly above the current gate requirement). Newly staked addresses must wait 14 400 blocks before they can redeem. Credits are created 1:1 from SOS trust records and are redeemed at the rate of 1 credit = 0.001 ETH. Credits cannot be transferred.

The contract exposes a minimal ERC-20 view (decimals 0) so wallets can display and send slices. Wallet sends only move slices that still have more than 7200 blocks of lifetime left. All critical operations are protected by a reentrancy guard, and interactions with the external SOS ledger are non-blocking.
