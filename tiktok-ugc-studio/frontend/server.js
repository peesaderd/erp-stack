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
    hook = "You will not believe how good this is! ✨";
    value = "Let me introduce you to " + title + ". " + details + ". This product is honestly amazing — the results speak for themselves.";
    cta = "Get yours now at the link below! 🛍️ FREE delivery today!";
  } else if (ugc_style === "usage") {
    hook = "Wait till you see what this can do! 🤯";
    value = "Unboxing and testing " + (title || "this product") + ". " + details + ". The quality is insane for the price.";
    cta = "Link in bio! Order now before stock runs out 🔗";
  } else if (ugc_style === "review") {
    hook = "Honest review: is it worth the hype? 🤔";
    value = "I've been using " + (title || "this product") + " for a while now. " + details + ". Here's my honest take — pros, cons, and everything.";
    cta = "Follow for more reviews! Don't forget to save this 📌";
  } else {
    hook = "You NEED this in your life! 🔥";
    value = "Check out " + (title || "this amazing product") + ". " + details + ". Perfect for everyday use. You won't regret it!";
    cta = "Link in bio! Free shipping available 🚚";
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
