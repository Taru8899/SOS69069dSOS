import { EthereumProvider } from "@walletconnect/ethereum-provider";
import { createGlue } from "./wc_glue.js";

window.DsosWC = createGlue(EthereumProvider, window);
window.DsosWC.boot();
