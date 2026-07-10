// backend/router/erp.js
import { createProxyMiddleware } from 'http-proxy-middleware';
import { Router } from 'express';

const router = Router();

// Adjust target to your ERP server address and port
const ERP_TARGET = process.env.ERP_TARGET || 'http://10.0.0.5:8080';

router.use(
  '/erp',
  createProxyMiddleware({
    target: ERP_TARGET,
    changeOrigin: true,
    pathRewrite: { '^/api/erp': '' },
    onProxyReq: (proxyReq) => {
      // If ERP requires a token, set it here
      if (process.env.ERP_TOKEN) {
        proxyReq.setHeader('Authorization', `Bearer ${process.env.ERP_TOKEN}`);
      }
    },
  })
);

export default router;
