const { createProxyMiddleware } = require('http-proxy-middleware');
const express = require('express');

const app = express();
const PORT = 54510;
const TARGET = 'http://localhost:54512';

app.use('/', createProxyMiddleware({
  target: TARGET,
  changeOrigin: true,
  ws: true,
  on: {
    proxyReq: (proxyReq, req, res) => {
      console.log('[Plane Proxy] ' + req.method + ' ' + req.url + ' -> ' + TARGET);
    },
    proxyRes: (proxyRes, req, res) => {
      proxyRes.headers['access-control-allow-origin'] = '*';
    },
    error: (err, req, res) => {
      console.error('[Plane Proxy] Error: ' + err.message);
      if (!res.headersSent) {
        res.writeHead(502, { 'Content-Type': 'text/plain' });
        res.end('Bad Gateway: Cannot reach Plane service');
      }
    }
  }
}));

app.listen(PORT, '0.0.0.0', () => {
  console.log('[Plane Proxy] Running on http://0.0.0.0:' + PORT + ' -> ' + TARGET);
});
