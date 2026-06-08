const express = require('express');
const path = require('path');
const { createProxyMiddleware } = require('http-proxy-middleware');

const app = express();
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
