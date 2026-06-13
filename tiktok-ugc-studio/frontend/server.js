const express = require('express');
const path = require('path');
const { createProxyMiddleware } = require('http-proxy-middleware');

const app = express();
app.use(express.json());
const PORT = 8120;

// TikTok UGC Studio API proxy
app.use('/api/tiktok/ugc', createProxyMiddleware({
  target: 'http://localhost:8105',
  changeOrigin: true,
  pathRewrite: { '^/api/tiktok/ugc': '/' },
  proxyTimeout: 180000,
  timeout: 180000,
}));

// Product Scraper proxy
app.use('/api/tiktok/scraper', createProxyMiddleware({
  target: 'http://localhost:8106',
  changeOrigin: true,
  pathRewrite: { '^/api/tiktok/scraper': '/' },
  proxyTimeout: 60000,
  timeout: 60000,
}));

const fs = require('fs');


// Product Analyzer proxy
app.use('/api/tiktok/analyze', createProxyMiddleware({
  target: 'http://localhost:8106',
  changeOrigin: true,
  pathRewrite: { '^/api/tiktok/analyze': '/' },
  proxyTimeout: 120000,
  timeout: 120000,
}));


// Script generation endpoint (local fallback, no external API needed)
app.post('/api/tiktok/scripts/generate', (req, res) => {
  const { product_url, product_title, product_name, product_details, ugc_style } = req.body;
  
  const title = product_title || product_name || "";
  const details = product_details || "";
  const isBeauty = /ลิป|mask|มาส์ก|สบู่|blush|บลัช|ครีม|cream|serum|เซรั่ม/i.test(title + " " + details);
  
  // Build richer script from product details
  let hook = "";
  let value = "";
  let cta = "";
  
  if (isBeauty) {
    hook = "ไม่เชื่อใช่ไหมว่าตัวนี้ดีขนาดนี้! ✨";
    value = "ขอแนะนำ " + title + "\n" + details + "\nตัวนี้บอกเลยว่าดีจริง ใช้แล้วเห็นผลชัดเจน ผิวดีขึ้นแบบไม่น่าเชื่อ ลองดูได้เลย!";
    cta = "สั่งซื้อเลยที่ลิงก์ด้านล่าง! 🛍️ ส่งฟรีวันนี้! #ของดีบอกต่อ #สินค้าแนะนำ";
  } else if (ugc_style === "usage") {
    hook = "เดี๋ยวรู้เลยว่าตัวนี้ทำอะไรได้บ้าง! 🤯";
    value = "มาแกะกล่อง + ลองใช้ " + (title || "สินค้าตัวนี้") + "\n" + details + "\nคุณภาพดีเกินราคา แนะนำเลย!";
    cta = "กดลิงก์ด้านล่างเลย! ของใกล้หมดแล้ว 🔗 #ของมันต้องมี #รีวิวสินค้า";
  } else if (ugc_style === "review") {
    hook = "รีวิวแบบจริงใจ: มันดีจริงไหม? 🤔";
    value = "เราใช้ " + (title || "สินค้าตัวนี้") + " มาซักพักแล้ว\n" + details + "\นี่คือความจริงใจ ข้อดี ข้อเสีย มีครบ!";
    cta = "กดติดตามเพื่อดูรีวิวเพิ่มเติม! อย่าลืมเซฟไว้นะ 📌 #รีวิวของดี";
  } else {
    hook = "ต้องมีติดบ้าน! 🔥";
    value = "มาดู " + (title || "สินค้าตัวนี้") + "\n" + details + "\nใช้ดีจนต้องบอกต่อ คุ้มค่ามาก!";
    cta = "ลิงก์ในโปรไฟล์! สั่งเลยก่อนของหมด 🛒 #สินค้าดีบอกต่อ #ของใช้ประจำวัน";
  }
  
  res.json({
    script: { hook, value_proposition: value, cta },
    hook,
    value,
    cta
  });
});

// Serve video/media files from /api/tiktok/media/<filename>
app.get('/api/tiktok/media/:filename', (req, res) => {
  const safePath = path.resolve(__dirname, '../storage', path.basename(req.params.filename));
  if (fs.existsSync(safePath)) {
    res.sendFile(safePath);
  } else {
    res.status(404).json({ error: 'File not found' });
  }
});

// Serve static frontend files from a 'public' directory
const publicPath = path.join(__dirname, 'public');
app.use(express.static(publicPath));

// All other routes → index.html (SPA) — use middleware not route
app.use((req, res) => {
  res.sendFile(path.join(publicPath, 'index.html'));
});

app.listen(PORT, '0.0.0.0', () => {
  console.log(`TikTok UGC Studio Frontend running on http://0.0.0.0:${PORT}`);
  console.log(`  API: http://localhost:${PORT}/api/tiktok/ugc/ (→ :8105)`);
  console.log(`  API: http://localhost:${PORT}/api/tiktok/scraper/ (→ :8106)`);
});
