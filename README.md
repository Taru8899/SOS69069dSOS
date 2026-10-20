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
