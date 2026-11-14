import { createGlue } from "./wc_glue.js";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const handlers = {};
let rejectConnect = false, failInit = false;
const fakeProvider = {
  session: null, accounts: [], chainId: 1,
  on(ev, fn) { handlers[ev] = fn; },
  async connect() {
    handlers.display_uri("wc:abc@2?relay-protocol=irn&symKey=00");
    await sleep(5);
    if (rejectConnect) { const e = new Error("User rejected"); e.code = 5000; throw e; }
    this.session = { peer: { metadata: { name: "TestWallet", redirect: { native: "testwallet://", universal: "https://tw.example/wc" } } } };
    this.accounts = ["0x08E5aaCaFAeFEf90d048AE4f97Cd4A8690E85fEE"];
  },
  async request({ method, params }) {
    if (method === "eth_sendTransaction") { if (params[0].data === "0xbad") { const e = new Error("User rejected the request"); e.code = 4001; throw e; } return "0x" + "ab".repeat(32); }
    if (method === "eth_signTypedData_v4") return "0x" + "11".repeat(65);
    throw new Error("unsupported " + method);
  },
  async disconnect() { this.session = null; },
};
const EP = { async init(o) { if (failInit) throw new Error("bad project id"); EP.opts = o; return fakeProvider; } };
const win = { __CFG: { projectId: "pid", name: "dSOS", description: "d", url: "https://x", rpc: "https://rpc" },
  addEventListener() {} };
const g = createGlue(EP, win);
g.boot();
let q = g.drain(); if (q[0].t !== "boot") throw new Error("boot");
await g.connect();
q = g.drain();
const types = q.map((m) => m.t);
if (types.join() !== "uri,session") throw new Error("connect msgs " + types);
const s = q[1];
if (s.accounts[0] !== "0x08E5aaCaFAeFEf90d048AE4f97Cd4A8690E85fEE" || s.native !== "testwallet://" || s.wallet !== "TestWallet") throw new Error("session " + JSON.stringify(s));
if (EP.opts.projectId !== "pid" || EP.opts.chains[0] !== 1 || EP.opts.showQrModal !== false) throw new Error("init opts");
// second connect reuses the session, no uri
await g.connect(); q = g.drain(); if (q.map((m) => m.t).join() !== "session") throw new Error("reconnect");
// requests
await g.request(7, "eth_sendTransaction", JSON.stringify([{ from: "0x1", to: "0x2", value: "0x0", data: "0x" }]));
await g.request(8, "eth_signTypedData_v4", JSON.stringify(["0x1", "{}"]));
await g.request(9, "eth_sendTransaction", JSON.stringify([{ data: "0xbad" }]));
q = g.drain();
if (q[0].id !== 7 || q[0].result.length !== 66) throw new Error("send result");
if (q[1].id !== 8 || q[1].result.length !== 132) throw new Error("sign result");
if (q[2].t !== "error" || q[2].code !== 4001) throw new Error("reject " + JSON.stringify(q[2]));
await g.disconnect(); q = g.drain(); if (q[0].t !== "disconnect") throw new Error("disconnect");
await g.request(10, "eth_sendTransaction", "[]"); q = g.drain();
if (q[0].t !== "error" || !/not connected/.test(q[0].error)) throw new Error("no session " + JSON.stringify(q));
// failed init is reported and can be retried
const g2 = createGlue({ async init() { throw new Error("bad project id"); } }, win);
await g2.connect(); q = g2.drain(); if (q[0].t !== "error" || q[0].error !== "bad project id" || q[0].id !== "connect") throw new Error("init error");
await g.resume();   // must not throw without relayer
console.log("JS glue OK");
