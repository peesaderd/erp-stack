const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

const edgePath = "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe";
const port = 9617;
const kdsUrl = "https://pos.m2igen.com/pos/kds";
const posUrl = "https://pos.m2igen.com/pos/restodash?type=dinein" + String.fromCharCode(38) + "table=T07";
const outDir = "C:\\Users\\ADMIN\\.gemini\\antigravity\\brain\\00f15b47-0b14-4bb2-93bf-bae12846dfe6";

const proc = spawn(edgePath, [
  '--headless=new',
  `--remote-debugging-port=${port}`,
  '--user-data-dir=C:\\Users\\ADMIN\\AppData\\Local\\Temp\\edge_debug_kds_stand',
  '--window-size=1280,800',
  'about:blank'
]);

async function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

async function run() {
  let tabs = null;
  for (let i = 0; i < 25; i++) {
    await sleep(300);
    try {
      const res = await fetch(`http://127.0.0.1:${port}/json/list`);
      tabs = await res.json();
      if (tabs && tabs.length > 0) break;
    } catch (e) {}
  }

  const pageTab = tabs.find(t => t.type === 'page') || tabs[0];
  const ws = new WebSocket(pageTab.webSocketDebuggerUrl);

  let msgId = 1;
  const callbacks = new Map();
  ws.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    if (msg.id && callbacks.has(msg.id)) {
      const cb = callbacks.get(msg.id);
      callbacks.delete(msg.id);
      cb(msg);
    }
  };

  function sendCmd(method, params = {}) {
    return new Promise((resolve) => {
      const id = ++msgId;
      callbacks.set(id, resolve);
      ws.send(JSON.stringify({ id, method, params }));
    });
  }

  ws.onopen = async () => {
    await sendCmd("Page.enable");
    await sendCmd("Runtime.enable");

    // 1. Tablet / Kitchen Landscape View (1280x800)
    await sendCmd("Emulation.setDeviceMetricsOverride", {
      width: 1280,
      height: 800,
      deviceScaleFactor: 1.5,
      mobile: false
    });
    console.log("Navigating to /pos/kds...");
    await sendCmd("Page.navigate", { url: kdsUrl });
    await sleep(3500);

    const shot1 = await sendCmd("Page.captureScreenshot", { format: "png" });
    fs.writeFileSync(path.join(outDir, "pos_kds_standalone_screen.png"), Buffer.from(shot1.result.data, 'base64'));
    console.log("Captured pos_kds_standalone_screen.png");

    // 2. Mobile Kitchen View (390x844)
    await sendCmd("Emulation.setDeviceMetricsOverride", {
      width: 390,
      height: 844,
      deviceScaleFactor: 2,
      mobile: true
    });
    await sleep(1000);

    const shot2 = await sendCmd("Page.captureScreenshot", { format: "png" });
    fs.writeFileSync(path.join(outDir, "pos_kds_standalone_mobile.png"), Buffer.from(shot2.result.data, 'base64'));
    console.log("Captured pos_kds_standalone_mobile.png");

    // 3. Go to POS and open KDS preview modal with the "จอครัวแยก (Standalone)" button
    await sendCmd("Emulation.setDeviceMetricsOverride", {
      width: 1280,
      height: 800,
      deviceScaleFactor: 1.5,
      mobile: false
    });
    await sendCmd("Page.navigate", { url: posUrl });
    await sleep(3500);

    await sendCmd("Runtime.evaluate", {
      expression: `(() => {
        const kdsBtn = document.querySelector('.quick-kds-btn');
        if (kdsBtn) kdsBtn.click();
      })()`
    });
    await sleep(800);

    const shot3 = await sendCmd("Page.captureScreenshot", { format: "png" });
    fs.writeFileSync(path.join(outDir, "pos_kds_modal_standalone_btn.png"), Buffer.from(shot3.result.data, 'base64'));
    console.log("Captured pos_kds_modal_standalone_btn.png");

    ws.close();
    proc.kill();
    process.exit(0);
  };
}
run();
