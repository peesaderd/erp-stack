const express = require('express');
const path = require('path');
const http = require('http');
const app = express();
const PORT = 8120;

// Proxy helper — no express.json() so raw body passes through
function proxyTo(host, port) {
  return (req, res) => {
    const targetPath = req.path
      .replace('/api/tiktok/ugc', '')
      .replace('/api/tiktok/scraper', '')
      .replace('/api/tiktok/analyze', '') || '/';
    
    const options = {
      hostname: host,
      port,
      path: targetPath,
      method: req.method,
      headers: { ...req.headers, host: host + ':' + port, connection: 'close' },
      timeout: 180000,
    };

    const proxyReq = http.request(options, (proxyRes) => {
      res.writeHead(proxyRes.statusCode, proxyRes.headers);
      proxyRes.pipe(res);
    });

    proxyReq.on('error', (e) => {
      if (!res.headersSent) res.status(500).json({ error: e.message });
    });

    req.pipe(proxyReq);
  };
}

// Proxy routes BEFORE express.json() to preserve raw body
app.all('/api/tiktok/ugc/*', proxyTo('localhost', 8105));
app.all('/api/tiktok/scraper/*', proxyTo('localhost', 8106));
app.all('/api/tiktok/analyze/*', proxyTo('localhost', 8106));
app.all('/api/tiktok/image-storage/*', proxyTo('localhost', 8105));

// Legacy image-storage fallback (direct to image-gen)
app.all('/api/tiktok/image-storage/*', (req, res) => {
  const filename = req.path.replace('/api/tiktok/image-storage/', '');
  http.get('http://localhost:8110/storage/images/' + filename, (proxyRes) => {
    res.writeHead(proxyRes.statusCode, { 'Content-Type': proxyRes.headers['content-type'] || 'image/jpeg', 'Content-Length': proxyRes.headers['content-length'] });
    proxyRes.pipe(res);
  }).on('error', () => res.status(404).json({ error: 'not found' }));
});

// Health — before json middleware
app.get('/health', (req, res) => res.json({ status: 'ok' }));

// JSON middleware for non-proxy routes
app.use(express.json());

// Static files
app.use(express.static(path.join(__dirname, 'public')));

// SPA fallback
app.use((req, res) => res.sendFile(path.join(__dirname, 'public', 'index.html')));

app.listen(PORT, '0.0.0.0', () => {
  console.log(`TUS Frontend v3 on :${PORT}`);
});
