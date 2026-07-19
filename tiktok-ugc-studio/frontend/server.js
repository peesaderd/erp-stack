const express = require('express');
const path = require('path');
const http = require('http');
const app = express();
const PORT = 8120;

// Proxy helper — strips /api/tiktok prefix, sends to target
function proxyTo(host, port, stripPrefix) {
  stripPrefix = stripPrefix || '/api/tiktok';
  return (req, res) => {
    const queryStr = req.url.includes('?') ? req.url.slice(req.url.indexOf('?')) : '';
    const targetPath = (req.path.replace(stripPrefix, '') || '/') + queryStr;
    
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
// Image-storage → image-gen (port 8110) directly
app.all('/api/tiktok/image-storage/*', (req, res) => {
  const filename = req.path.replace('/api/tiktok/image-storage/', '');
  http.get('http://localhost:8110/storage/images/' + filename, (proxyRes) => {
    res.writeHead(proxyRes.statusCode, { 'Content-Type': proxyRes.headers['content-type'] || 'image/jpeg', 'Content-Length': proxyRes.headers['content-length'] });
    proxyRes.pipe(res);
  }).on('error', () => res.status(404).json({ error: 'not found' }));
});
// Scraper & analyze go to port 8106 (scraper service)
app.all('/api/tiktok/scraper/*', proxyTo('localhost', 8106, '/api/tiktok'));
app.all('/api/tiktok/analyze/*', proxyTo('localhost', 8106, '/api/tiktok'));
// Everything else /api/tiktok/* goes to 8105 (TikTok UGC backend)
app.all('/api/tiktok/*', proxyTo('localhost', 8105, '/api/tiktok'));

// Direct video proxy (no /api/tiktok prefix — nginx sends /tiktok/ as /)
app.get('/static/videos/:filename', (req, res) => {
  http.get('http://localhost:8105/static/videos/' + req.params.filename, (proxyRes) => {
    res.writeHead(proxyRes.statusCode, { 
      'Content-Type': proxyRes.headers['content-type'] || 'video/mp4',
      'Content-Length': proxyRes.headers['content-length'],
      'Accept-Ranges': 'bytes',
    });
    proxyRes.pipe(res);
  }).on('error', () => res.status(404).json({ error: 'video not found' }));
});

// Also handle image storage directly
app.get('/storage/images/:filename', (req, res) => {
  http.get('http://localhost:8110/storage/images/' + req.params.filename, (proxyRes) => {
    res.writeHead(proxyRes.statusCode, { 
      'Content-Type': proxyRes.headers['content-type'] || 'image/jpeg',
      'Content-Length': proxyRes.headers['content-length'],
    });
    proxyRes.pipe(res);
  }).on('error', () => res.status(404).json({ error: 'image not found' }));
});

// Health — before json middleware
app.get('/health', (req, res) => res.json({ status: 'ok' }));

// JSON middleware for non-proxy routes
app.use(express.json());

// Proxy product images → calm-noether (8108) for HTTPS mixed-content fix
app.get("/ugc/static/product_images/:filename", (req, res) => {
  http.get("http://localhost:8108/product_images/" + req.params.filename, (proxyRes) => {
    res.writeHead(proxyRes.statusCode, {
      "Content-Type": proxyRes.headers["content-type"] || "image/jpeg",
      "Content-Length": proxyRes.headers["content-length"],
      "Cache-Control": "public, max-age=86400",
    });
    proxyRes.pipe(res);
  }).on("error", () => res.status(404).json({ error: "image not found" }));
});

// Proxy TUS static files (videos) BEFORE static middleware
// nginx sends /tiktok/static/videos/xxx without stripping /tiktok prefix
app.use((req, res, next) => {
  // Match both /static/videos/* and /tiktok/static/videos/*
  const videoMatch = req.path.match(/^\/?(?:tiktok\/)?static\/videos\/(.+)$/);
  if (videoMatch) {
    const target = 'http://localhost:8105/static/videos/' + videoMatch[1];
    http.get(target, (proxyRes) => {
      res.writeHead(proxyRes.statusCode, proxyRes.headers);
      proxyRes.pipe(res);
    }).on('error', () => res.status(404).json({ error: 'video not found' }));
    return;
  }
  next();
});

// Static files
app.use(express.static(path.join(__dirname, 'public')));

// SPA fallback
app.use((req, res) => res.sendFile(path.join(__dirname, 'public', 'index.html')));

app.listen(PORT, '0.0.0.0', () => {
  console.log(`TUS Frontend v3 on :${PORT}`);
});
