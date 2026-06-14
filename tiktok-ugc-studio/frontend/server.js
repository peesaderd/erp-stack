const express = require('express');
const path = require('path');
const http = require('http');
const app = express();
app.use(express.json());
const PORT = 8120;

// Direct proxy helper
function proxyTo(targetHost, targetPort) {
  return (req, res) => {
    const options = {
      hostname: targetHost,
      port: targetPort,
      path: req.path.replace(/^\/api\/tiktok\/ugc/, '').replace(/^\/api\/tiktok\/scraper/, '').replace(/^\/api\/tiktok\/analyze/, '') || '/',
      method: req.method,
      headers: { ...req.headers, host: targetHost + ':' + targetPort },
      timeout: 180000,
    };
    const proxy = http.request(options, (proxyRes) => {
      res.writeHead(proxyRes.statusCode, proxyRes.headers);
      proxyRes.pipe(res);
    });
    proxy.on('error', (e) => { res.status(500).json({ error: e.message }); });
    if (req.body && Object.keys(req.body).length > 0) {
      proxy.write(JSON.stringify(req.body));
    }
    req.on('data', chunk => proxy.write(chunk));
    req.on('end', () => proxy.end());
    proxy.end();
  };
}

// Proxy routes
app.all('/api/tiktok/ugc/*', proxyTo('localhost', 8105));
app.all('/api/tiktok/scraper/*', proxyTo('localhost', 8106));
app.all('/api/tiktok/analyze/*', proxyTo('localhost', 8106));

// Health
app.get('/health', (req, res) => res.json({ status: 'ok' }));

// Static
app.use(express.static(path.join(__dirname, 'public')));

// SPA fallback
app.use((req, res) => res.sendFile(path.join(__dirname, 'public', 'index.html')));

app.listen(PORT, '0.0.0.0', () => {
  console.log(`TUS Frontend v2 on :${PORT}`);
});
