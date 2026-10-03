const fs = require("fs");
const path = require("path");

class DeepSeekHashWasm {
  constructor() {
    this.cachedTextEncoder = new TextEncoder();
    this.offset = 0;
    this.wasmInstance = null;
    this.cachedUint8Memory = null;
  }

  async init(wasmPath) {
    const wasmBuffer = fs.readFileSync(wasmPath);
    const { instance } = await WebAssembly.instantiate(wasmBuffer, { wbg: {} });
    this.wasmInstance = instance.exports;
  }

  getCachedUint8Memory() {
    if (!this.cachedUint8Memory?.byteLength) {
      this.cachedUint8Memory = new Uint8Array(this.wasmInstance.memory.buffer);
    }
    return this.cachedUint8Memory;
  }

  encodeString(text, allocate, reallocate) {
    const strLength = text.length;
    let ptr = allocate(strLength, 1) >>> 0;
    const memory = this.getCachedUint8Memory();
    let asciiLength = 0;

    for (; asciiLength < strLength; asciiLength++) {
      if (text.charCodeAt(asciiLength) > 127) break;
      memory[ptr + asciiLength] = text.charCodeAt(asciiLength);
    }

    if (asciiLength !== strLength) {
      if (asciiLength > 0) text = text.slice(asciiLength);
      ptr = reallocate(ptr, strLength, asciiLength + text.length * 3, 1) >>> 0;
      const result = this.cachedTextEncoder.encodeInto(
        text,
        this.getCachedUint8Memory().subarray(ptr + asciiLength, ptr + asciiLength + text.length * 3)
      );
      asciiLength += result.written;
      ptr = reallocate(ptr, asciiLength + text.length * 3, asciiLength, 1) >>> 0;
    }

    this.offset = asciiLength;
    return ptr;
  }

  calculateHash(challenge, prefix, difficulty) {
    try {
      const retptr = this.wasmInstance.__wbindgen_add_to_stack_pointer(-16);
      const ptr0 = this.encodeString(
        challenge,
        this.wasmInstance.__wbindgen_export_0,
        this.wasmInstance.__wbindgen_export_1
      );
      const len0 = this.offset;
      const ptr1 = this.encodeString(
        prefix,
        this.wasmInstance.__wbindgen_export_0,
        this.wasmInstance.__wbindgen_export_1
      );
      const len1 = this.offset;

      this.wasmInstance.wasm_solve(retptr, ptr0, len0, ptr1, len1, difficulty);

      const dv = new DataView(this.wasmInstance.memory.buffer);
      const status = dv.getInt32(retptr + 0, true);
      const value = dv.getFloat64(retptr + 8, true);

      return status === 0 ? -1 : Math.round(value);
    } finally {
      this.wasmInstance.__wbindgen_add_to_stack_pointer(16);
    }
  }
}

function solveWithJS(challenge, prefix, difficulty) {
  try {
    const { U } = require("./deepseek-pow-solver.cjs");
    const createHash = () => {
      const self = {};
      self._sponge = new U({ capacity: 256, padding: 6 });
      self.update = (s) => {
        self._sponge.absorb(Buffer.from(s, "utf8"));
        return self;
      };
      self.digest = (fmt) => self._sponge.squeeze(6).toString(fmt || "hex");
      self.copy = () => {
        const c = {};
        c._sponge = self._sponge.copy();
        c.update = (s) => {
          c._sponge.absorb(Buffer.from(s, "utf8"));
          return c;
        };
        c.digest = (fmt) => c._sponge.squeeze(6).toString(fmt || "hex");
        return c;
      };
      return self;
    };

    const h = createHash();
    h.update(prefix);

    for (let nonce = 0; nonce < difficulty; nonce++) {
      if (h.copy().update(String(nonce)).digest("hex") === challenge) {
        return nonce;
      }
    }
  } catch (err) {
    // fallback error
  }
  return -1;
}

async function main() {
  let rawInput = process.argv[2];
  if (!rawInput) {
    rawInput = fs.readFileSync(0, "utf-8");
  }

  let challengeData;
  try {
    challengeData = JSON.parse(rawInput);
  } catch (e) {
    console.error(JSON.stringify({ error: "Invalid JSON input: " + e.message }));
    process.exit(1);
  }

  const { algorithm, challenge, salt, difficulty, expire_at, expireAt } = challengeData;
  const expiry = expire_at ?? expireAt;
  const prefix = `${salt}_${expiry}_`;

  let answer = -1;

  // 1. Try WASM solver
  try {
    const wasmPath = path.join(__dirname, "sha3_wasm_bg.wasm");
    if (fs.existsSync(wasmPath)) {
      const wasmSolver = new DeepSeekHashWasm();
      await wasmSolver.init(wasmPath);
      answer = wasmSolver.calculateHash(challenge, prefix, difficulty);
    }
  } catch (err) {
    // wasm failed, proceed to JS fallback
  }

  // 2. Fallback to JS solver if wasm did not find or failed
  if (answer === undefined || answer === null || answer < 0) {
    answer = solveWithJS(challenge, prefix, difficulty);
  }

  process.stdout.write(JSON.stringify({ answer }));
}

main().catch((err) => {
  process.stdout.write(JSON.stringify({ error: err.message, answer: -1 }));
  process.exit(0);
});
