// Drive headless Chrome over CDP: open a page, run steps, screenshot.
// Usage: node --experimental-websocket cdp-shot.mjs <port> <url> <outPng> <stepsJson>
import { readFileSync, writeFileSync } from "node:fs";

const [port, url, outPng, stepsFile] = process.argv.slice(2);
const steps = JSON.parse(readFileSync(stepsFile, "utf8"));
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const target = await (await fetch(`http://127.0.0.1:${port}/json/new?about:blank`, { method: "PUT" })).json();
const ws = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((r) => ws.addEventListener("open", r, { once: true }));
let id = 0;
const pending = new Map();
ws.addEventListener("message", (e) => {
  const msg = JSON.parse(e.data);
  if (msg.id && pending.has(msg.id)) {
    pending.get(msg.id)(msg);
    pending.delete(msg.id);
  }
});
const send = (method, params = {}) =>
  new Promise((resolve, reject) => {
    const n = ++id;
    pending.set(n, (m) => (m.error ? reject(new Error(`${method}: ${m.error.message}`)) : resolve(m.result)));
    ws.send(JSON.stringify({ id: n, method, params }));
  });
const evaluate = async (expression) => {
  const r = await send("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true });
  if (r.exceptionDetails) throw new Error(r.exceptionDetails.exception?.description || "eval failed");
  return r.result.value;
};

const [w, h] = (steps.viewport || "1280x800").split("x").map(Number);
await send("Emulation.setDeviceMetricsOverride", { width: w, height: h, deviceScaleFactor: 1, mobile: w < 768 });
await send("Page.enable");
// Optional script run before any page script, e.g. to stub a browser API the app reads at load.
if (steps.preload) await send("Page.addScriptToEvaluateOnNewDocument", { source: steps.preload });
await send("Page.navigate", { url });
await sleep(steps.loadWaitMs ?? 8000);

const log = [];
for (const step of steps.actions || []) {
  if (step.eval) log.push({ eval: step.label ?? "eval", value: await evaluate(step.eval) });
  if (step.key) {
    for (let i = 0; i < (step.times ?? 1); i++) {
      const k = { key: step.key, code: step.key, windowsVirtualKeyCode: step.keyCode, nativeVirtualKeyCode: step.keyCode, modifiers: step.modifiers ?? 0 };
      if (step.text) await send("Input.dispatchKeyEvent", { type: "keyDown", text: step.text, unmodifiedText: step.text, ...k });
      else await send("Input.dispatchKeyEvent", { type: "rawKeyDown", ...k });
      await send("Input.dispatchKeyEvent", { type: "keyUp", ...k });
      await sleep(150);
      if (step.probe) log.push({ key: `${step.key} #${i + 1}`, value: await evaluate(step.probe) });
    }
  }
  if (step.tabUntil) {
    let presses = 0;
    while (presses < (step.max ?? 60) && !(await evaluate(step.tabUntil))) {
      const k = { key: "Tab", code: "Tab", windowsVirtualKeyCode: 9, nativeVirtualKeyCode: 9 };
      await send("Input.dispatchKeyEvent", { type: "rawKeyDown", ...k });
      await send("Input.dispatchKeyEvent", { type: "keyUp", ...k });
      presses++;
      await sleep(80);
    }
    log.push({ tabUntil: step.label ?? "tabUntil", presses, reached: await evaluate(step.tabUntil) });
  }
  if (step.click) {
    const [x, y] = step.click;
    for (const type of ["mouseMoved", "mousePressed", "mouseReleased"])
      await send("Input.dispatchMouseEvent", { type, x, y, button: "left", buttons: type === "mousePressed" ? 1 : 0, clickCount: 1 });
    await sleep(step.after ?? 600);
    if (step.probe) log.push({ click: step.click, value: await evaluate(step.probe) });
  }
  if (step.waitMs) await sleep(step.waitMs);
}

const shot = await send("Page.captureScreenshot", { format: "png" });
writeFileSync(outPng, Buffer.from(shot.data, "base64"));
console.log(JSON.stringify(log, null, 2));
ws.close();
// Close the tab we opened, so repeated runs don't leave pages running in the shared profile.
await fetch(`http://127.0.0.1:${port}/json/close/${target.id}`).catch(() => {});
