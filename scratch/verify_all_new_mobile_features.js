const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

const edgePath = "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe";
const port = 9615;
const targetUrl = "https://pos.m2igen.com/pos/restodash?type=dinein" + String.fromCharCode(38) + "table=T07";
const outDir = "C:\\Users\\ADMIN\\.gemini\\antigravity\\brain\\00f15b47-0b14-4bb2-93bf-bae12846dfe6";

const proc = spawn(edgePath, [
  '--headless=new',
  `--remote-debugging-port=${port}`,
  '--user-data-dir=C:\\Users\\ADMIN\\AppData\\Local\\Temp\\edge_debug_verify_features',
  '--window-size=390,844',
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
    await sendCmd("Emulation.setDeviceMetricsOverride", {
      width: 390,
      height: 844,
      deviceScaleFactor: 2,
      mobile: true
    });
    await sendCmd("Page.navigate", { url: targetUrl });
    await sleep(3500);

    // Dismiss alarm if any
    await sendCmd("Runtime.evaluate", {
      expression: `(() => {
        const btn = document.querySelector('.alarm-btn-dismiss');
        if (btn) btn.click();
      })()`
    });
    await sleep(600);

    // 1. Screenshot 1: Main POS screen with Bottom Nav & Compact Cards
    const shot1 = await sendCmd("Page.captureScreenshot", { format: "png" });
    fs.writeFileSync(path.join(outDir, "pos_mobile_bottom_nav.png"), Buffer.from(shot1.result.data, 'base64'));
    console.log("Captured pos_mobile_bottom_nav.png");

    // 2. Open Table Modal to verify direct table checkout button
    await sendCmd("Runtime.evaluate", {
      expression: `(() => {
        const tablePill = document.querySelector('.quick-pill-btn') || document.querySelectorAll('.m-nav-tab')[1];
        if (tablePill) tablePill.click();
      })()`
    });
    await sleep(800);

    const shot2 = await sendCmd("Page.captureScreenshot", { format: "png" });
    fs.writeFileSync(path.join(outDir, "pos_mobile_table_modal_direct_pay.png"), Buffer.from(shot2.result.data, 'base64'));
    console.log("Captured pos_mobile_table_modal_direct_pay.png");

    // 3. Click direct checkout button on table OR select table with order
    await sendCmd("Runtime.evaluate", {
      expression: `(() => {
        const payBtn = document.querySelector('.btn-table-checkout-direct');
        if (payBtn) {
          payBtn.click();
        } else {
          const occupiedCard = document.querySelector('.table-card.is-occupied, .table-card.is-served') || document.querySelector('.table-card');
          if (occupiedCard) occupiedCard.click();
        }
      })()`
    });
    await sleep(800);

    const shot3 = await sendCmd("Page.captureScreenshot", { format: "png" });
    fs.writeFileSync(path.join(outDir, "pos_mobile_direct_payment_screen.png"), Buffer.from(shot3.result.data, 'base64'));
    console.log("Captured pos_mobile_direct_payment_screen.png");

    // Close payment modal
    await sendCmd("Runtime.evaluate", {
      expression: `(() => {
        const closeBtn = document.querySelector('.payment-modal-header .modal-close-btn');
        if (closeBtn) closeBtn.click();
      })()`
    });
    await sleep(500);

    // 4. Open Settings view via Bottom Nav
    await sendCmd("Runtime.evaluate", {
      expression: `(() => {
        const tabs = document.querySelectorAll('.m-nav-tab');
        const settingsTab = tabs[tabs.length - 1]; // Last tab is Settings
        if (settingsTab) settingsTab.click();
      })()`
    });
    await sleep(800);

    const shot4 = await sendCmd("Page.captureScreenshot", { format: "png" });
    fs.writeFileSync(path.join(outDir, "pos_mobile_settings_responsive.png"), Buffer.from(shot4.result.data, 'base64'));
    console.log("Captured pos_mobile_settings_responsive.png");

    // Return to POS, open Unpaid Orders modal via Bottom Nav
    await sendCmd("Runtime.evaluate", {
      expression: `(() => {
        const tabs = document.querySelectorAll('.m-nav-tab');
        if (tabs[0]) tabs[0].click(); // Back to POS
      })()`
    });
    await sleep(500);

    await sendCmd("Runtime.evaluate", {
      expression: `(() => {
        const unpaidTab = document.querySelector('.m-nav-unpaid-tab');
        if (unpaidTab) unpaidTab.click();
      })()`
    });
    await sleep(800);

    const shot5 = await sendCmd("Page.captureScreenshot", { format: "png" });
    fs.writeFileSync(path.join(outDir, "pos_mobile_unpaid_orders_modal.png"), Buffer.from(shot5.result.data, 'base64'));
    console.log("Captured pos_mobile_unpaid_orders_modal.png");

    ws.close();
    proc.kill();
    process.exit(0);
  };
}
run();
