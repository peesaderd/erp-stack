const { createProxyMiddleware } = require('http-proxy-middleware');
const express = require('express');
const app = express();
const PORT = 3003;
const OH = "http://127.0.0.1:3001";
const GW = "http://127.0.0.1:18789";
const LG = "http://127.0.0.1:2024";

const wsOpts = {
  target: GW,
  changeOrigin: true,
  ws: true,
  on: {
    proxyReqWs: (proxyReq, req, socket, opts, head) => {
      proxyReq.setHeader("Sec-WebSocket-Extensions", "");
    }
  }
};

app.use("/gateway", createProxyMiddleware(wsOpts));
app.use("/langgraph", createProxyMiddleware({target: LG, changeOrigin: true, ws: true}));
app.use("/api", createProxyMiddleware({target: OH, changeOrigin: true, ws: true}));
app.use("/socket.io", createProxyMiddleware({target: OH, changeOrigin: true, ws: true}));
app.use("/", createProxyMiddleware({target: OH, changeOrigin: true, ws: true}));

app.listen(PORT, "0.0.0.0", () => console.log("[OH-Proxy] :" + PORT));
