// backend/server.js
import express from 'express';
import cors from 'cors';
import dotenv from 'dotenv';
import Stripe from 'stripe';
import jwt from 'jsonwebtoken';
import { spawn } from 'child_process';
import path from 'path';
import fs from 'fs';
import { fileURLToPath } from 'url';
import pg from 'pg';
import crypto from 'crypto';
import erpRouter from './router/erp.js';

dotenv.config();

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const app = express();
const port = process.env.PORT || 4000;

app.use(cors({ origin: process.env.FRONTEND_URL || '*' }));

// Use express.raw for stripe webhooks, express.json for others
app.use((req, res, next) => {
  if (req.originalUrl === '/webhook') {
    next();
  } else {
    express.json()(req, res, next);
  }
});

app.use('/api', erpRouter);

// Initialize PostgreSQL Pool to host erp_stack database
const dbUrl = process.env.DATABASE_URL || 'postgresql://openhands:OpenHands@ERP2026@127.0.0.1:5432/erp_stack';
const pool = new pg.Pool({
  connectionString: dbUrl,
  ssl: false
});

// Test connection
pool.query('SELECT NOW()', (err, res) => {
  if (err) {
    console.error('❌ Database connection failed:', err.message);
  } else {
    console.log('✅ Database connected successfully');
  }
});

const stripeSecret = process.env.STRIPE_SECRET_KEY || 'sk_test_mock_stripe_key_12345';
const stripe = new Stripe(stripeSecret, { apiVersion: '2023-10-16' });

// SHA-256 Hashing helper (compatible with TUS auth password_hash)
function hashPassword(password) {
  return crypto.createHash('sha256').update(password).digest('hex');
}

// Token helper
const jwtSecret = process.env.JWT_SECRET || 'change-me-in-production';
function generateToken(userId) {
  return jwt.sign({ sub: userId }, jwtSecret, { expiresIn: '72h' });
}

// JWT Authentication Middleware
function authenticate(req, res, next) {
  const authHeader = req.headers.authorization;
  if (!authHeader) return res.sendStatus(401);
  const token = authHeader.split(' ')[1];
  try {
    const payload = jwt.verify(token, jwtSecret);
    req.user = { id: payload.sub };
    next();
  } catch (e) {
    return res.sendStatus(403);
  }
}

// -----------------------------------
// Authentication Endpoints
// -----------------------------------

// Register Local Account
app.post('/api/auth/register', async (req, res) => {
  const { name, email, password } = req.body;
  if (!name || !email || !password) {
    return res.status(400).json({ error: 'Name, email, and password are required' });
  }

  try {
    // Check if user already exists
    const userCheck = await pool.query('SELECT * FROM users WHERE email = $1', [email]);
    if (userCheck.rows.length > 0) {
      return res.status(400).json({ error: 'Email already registered' });
    }

    const userId = crypto.randomUUID();
    const pwHash = hashPassword(password);

    await pool.query(
      `INSERT INTO users (id, email, name, avatar_url, password_hash, member_tier, credits, credits_used, is_active, created_at, updated_at)
       VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, NOW(), NOW())`,
      [userId, email, name, '', pwHash, 'bronze', 1.0, 0.0, true]
    );

    const token = generateToken(userId);
    res.json({
      ok: true,
      token,
      user: { id: userId, email, name, avatar_url: '', member_tier: 'bronze' }
    });
  } catch (error) {
    console.error('Register error:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

// Login Local Account
app.post('/api/auth/login', async (req, res) => {
  const { email, password } = req.body;
  if (!email || !password) {
    return res.status(400).json({ error: 'Email and password are required' });
  }

  try {
    const result = await pool.query('SELECT * FROM users WHERE email = $1', [email]);
    const user = result.rows[0];

    if (!user || user.password_hash !== hashPassword(password)) {
      return res.status(400).json({ error: 'Invalid email or password' });
    }

    if (!user.is_active) {
      return res.status(403).json({ error: 'Account is disabled' });
    }

    const token = generateToken(user.id);
    res.json({
      ok: true,
      token,
      user: {
        id: user.id,
        email: user.email,
        name: user.name,
        avatar_url: user.avatar_url || '',
        member_tier: user.member_tier || 'bronze'
      }
    });
  } catch (error) {
    console.error('Login error:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

// Fetch User Profile
app.get('/api/auth/me', authenticate, async (req, res) => {
  try {
    const result = await pool.query('SELECT id, email, name, avatar_url, member_tier, credits FROM users WHERE id = $1', [req.user.id]);
    const user = result.rows[0];
    if (!user) return res.status(404).json({ error: 'User not found' });
    res.json({ ok: true, user });
  } catch (error) {
    console.error('Fetch profile error:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

// Google OAuth Simulation Redirect
app.get('/api/auth/google/login', (req, res) => {
  // Since real OAuth requires domain mapping & verified DNS redirects, 
  // we redirect directly to a callback simulation that creates/finds user in the erp_stack database.
  const mockCode = 'google_mock_code_' + crypto.randomBytes(8).toString('hex');
  res.redirect(`/api/auth/google/callback?code=${mockCode}`);
});

// Google OAuth Simulation Callback
app.get('/api/auth/google/callback', async (req, res) => {
  const { code } = req.query;
  const mockEmail = `google_user_${code.slice(-6)}@gmail.com`;
  const mockName = `Google User ${code.slice(-6)}`;
  const mockAvatar = 'https://lh3.googleusercontent.com/a/default-user=s96-c';

  try {
    let result = await pool.query('SELECT * FROM users WHERE email = $1', [mockEmail]);
    let user = result.rows[0];

    if (!user) {
      const userId = crypto.randomUUID();
      await pool.query(
        `INSERT INTO users (id, email, name, avatar_url, password_hash, member_tier, credits, credits_used, is_active, created_at, updated_at)
         VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, NOW(), NOW())`,
        [userId, mockEmail, mockName, mockAvatar, '', 'bronze', 1.0, 0.0, true]
      );
      
      await pool.query(
        `INSERT INTO auth_providers (id, user_id, provider, provider_user_id, provider_email, created_at)
         VALUES ($1, $2, $3, $4, $5, NOW())`,
        [crypto.randomUUID(), userId, 'google', 'google_id_' + code.slice(-6), mockEmail]
      );
      
      result = await pool.query('SELECT * FROM users WHERE id = $1', [userId]);
      user = result.rows[0];
    }

    const token = generateToken(user.id);
    res.redirect(`/?token=${token}`);
  } catch (error) {
    console.error('Google OAuth callback error:', error);
    res.redirect('/?error=oauth_failed');
  }
});

// LINE OAuth Simulation Redirect
app.get('/api/auth/line/login', (req, res) => {
  const mockCode = 'line_mock_code_' + crypto.randomBytes(8).toString('hex');
  res.redirect(`/api/auth/line/callback?code=${mockCode}`);
});

// LINE OAuth Simulation Callback
app.get('/api/auth/line/callback', async (req, res) => {
  const { code } = req.query;
  const mockEmail = `line_user_${code.slice(-6)}@line.me`;
  const mockName = `LINE User ${code.slice(-6)}`;
  const mockAvatar = 'https://profile.line-scdn.net/default-avatar';

  try {
    let result = await pool.query('SELECT * FROM users WHERE email = $1', [mockEmail]);
    let user = result.rows[0];

    if (!user) {
      const userId = crypto.randomUUID();
      await pool.query(
        `INSERT INTO users (id, email, name, avatar_url, password_hash, member_tier, credits, credits_used, is_active, created_at, updated_at)
         VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, NOW(), NOW())`,
        [userId, mockEmail, mockName, mockAvatar, '', 'bronze', 1.0, 0.0, true]
      );
      
      await pool.query(
        `INSERT INTO auth_providers (id, user_id, provider, provider_user_id, provider_email, created_at)
         VALUES ($1, $2, $3, $4, $5, NOW())`,
        [crypto.randomUUID(), userId, 'line', 'line_id_' + code.slice(-6), mockEmail]
      );
      
      result = await pool.query('SELECT * FROM users WHERE id = $1', [userId]);
      user = result.rows[0];
    }

    const token = generateToken(user.id);
    res.redirect(`/?token=${token}`);
  } catch (error) {
    console.error('LINE OAuth callback error:', error);
    res.redirect('/?error=oauth_failed');
  }
});

// -----------------------------------
// App Store & Payments
// -----------------------------------

// Fetch App List
app.get('/api/apps', (req, res) => {
  const appsPath = path.join(__dirname, 'data', 'apps.json');
  const apps = JSON.parse(fs.readFileSync(appsPath, 'utf-8'));
  res.json(apps);
});

// Fetch Purchased App IDs for Logged-In User
app.get('/api/user/apps', authenticate, async (req, res) => {
  try {
    const result = await pool.query(
      `SELECT description AS app_id FROM transactions 
       WHERE user_id = $1 AND status = 'completed'`,
      [req.user.id]
    );
    const appIds = result.rows.map(row => row.app_id);
    res.json(appIds);
  } catch (error) {
    console.error('Fetch purchased apps error:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

// Fetch Billing Transaction History
app.get('/api/user/transactions', authenticate, async (req, res) => {
  try {
    const result = await pool.query(
      `SELECT id, amount, currency, payment_method, status, description AS app_id, created_at, completed_at
       FROM transactions WHERE user_id = $1 ORDER BY created_at DESC`,
      [req.user.id]
    );
    res.json(result.rows);
  } catch (error) {
    console.error('Fetch transactions error:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

// Create Stripe Checkout Session (or Mock Checkout redirection)
app.post('/api/create-checkout-session', authenticate, async (req, res) => {
  const { appId } = req.body;
  const appsPath = path.join(__dirname, 'data', 'apps.json');
  const apps = JSON.parse(fs.readFileSync(appsPath, 'utf-8'));
  const appInfo = apps.find(a => a.id === appId);
  if (!appInfo) return res.status(404).json({ error: 'App not found' });

  const amount = appInfo.price;
  const currency = appInfo.currency.toUpperCase();
  const txId = crypto.randomUUID();

  try {
    // Record pending transaction inside Postgres erp_stack database
    await pool.query(
      `INSERT INTO transactions (id, user_id, amount, currency, payment_method, payment_ref, status, description, metadata_json, created_at)
       VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, NOW())`,
      [txId, req.user.id, amount / 100.0, currency, 'stripe', txId, 'pending', appId, JSON.stringify({ appId })]
    );

    // If Stripe keys are not set, return mock checkout flow redirect
    if (!process.env.STRIPE_SECRET_KEY || process.env.STRIPE_SECRET_KEY.startsWith('sk_test_mock')) {
      return res.json({ url: `/payment-mock?session_id=${txId}&app_id=${appId}` });
    }

    // Real Stripe Integration
    const session = await stripe.checkout.sessions.create({
      payment_method_types: ['card'],
      line_items: [{
        price_data: {
          currency: currency.toLowerCase(),
          product_data: { name: appInfo.name, description: appInfo.description },
          unit_amount: amount,
        },
        quantity: 1
      }],
      mode: 'payment',
      success_url: `${process.env.FRONTEND_URL || 'http://localhost:8104'}/success?session_id=${txId}`,
      cancel_url: `${process.env.FRONTEND_URL || 'http://localhost:8104'}/cancel`,
      metadata: { txId, appId, userId: req.user.id },
    });

    // Update transaction payment reference to Stripe session ID
    await pool.query('UPDATE transactions SET payment_ref = $1 WHERE id = $2', [session.id, txId]);

    res.json({ url: session.url });
  } catch (error) {
    console.error('Checkout creation error:', error);
    res.status(500).json({ error: 'Stripe transaction creation failed' });
  }
});

// Mock Payment Complete Callback
app.post('/api/payment-complete', authenticate, async (req, res) => {
  const { sessionId } = req.body;
  try {
    const result = await pool.query(
      `UPDATE transactions SET status = 'completed', completed_at = NOW() 
       WHERE id = $1 AND user_id = $2 AND status = 'pending'`,
      [sessionId, req.user.id]
    );
    if (result.rowCount === 0) {
      return res.status(400).json({ error: 'Transaction not found or already completed' });
    }
    res.json({ success: true });
  } catch (error) {
    console.error('Complete payment error:', error);
    res.status(500).json({ error: 'Payment completion process failed' });
  }
});

// Stripe webhook (listen for completed payments)
app.post('/webhook', express.raw({ type: 'application/json' }), async (req, res) => {
  const sig = req.headers['stripe-signature'];
  let event;
  try {
    event = stripe.webhooks.constructEvent(req.body, sig, process.env.STRIPE_WEBHOOK_SECRET);
  } catch (err) {
    console.log(`⚠️ Webhook signature verification failed.`);
    return res.sendStatus(400);
  }

  if (event.type === 'checkout.session.completed') {
    const session = event.data.object;
    const txId = session.metadata.txId;
    
    try {
      await pool.query(
        `UPDATE transactions SET status = 'completed', completed_at = NOW() 
         WHERE (id = $1 OR payment_ref = $2) AND status = 'pending'`,
        [txId, session.id]
      );
      console.log(`✅ Payment succeeded for transaction ${txId}`);
    } catch (dbErr) {
      console.error('Webhook DB update failed:', dbErr);
    }
  }
  res.json({ received: true });
});

// OpenCode Model Select API Integration
app.get('/api/opencode/models', async (req, res) => {
  try {
    const response = await fetch('http://127.0.0.1:8777/v1/models');
    if (response.ok) {
      const data = await response.json();
      return res.json(data);
    }
  } catch (e) {
    console.warn("OpenCode proxy models fetch failed:", e.message);
  }
  // Fallback if proxy is down or rate limited
  const fallbackModels = [
    { id: "opencode-go/deepseek-v4-flash", name: "DeepSeek V4 Flash" },
    { id: "opencode-go/deepseek-v4-pro", name: "DeepSeek V4 Pro" },
    { id: "opencode-go/qwen3.6-plus", name: "Qwen 3.6 Plus" },
    { id: "opencode-go/qwen3.7-max", name: "Qwen 3.7 Max" },
    { id: "opencode-go/glm-5.2", name: "GLM 5.2" },
    { id: "opencode-go/kimi-k2.7-code", name: "Kimi K2.7 Code" }
  ];
  res.json({ object: "list", data: fallbackModels.map(m => ({ id: m.id, object: "model", name: m.name })) });
});

app.get('/api/opencode/active-model', async (req, res) => {
  try {
    const response = await fetch('http://127.0.0.1:8777/v1/active-model');
    if (response.ok) {
      const data = await response.json();
      return res.json(data);
    }
  } catch (e) {
    console.warn("OpenCode proxy active-model GET failed:", e.message);
  }
  res.json({ model: "opencode-go/deepseek-v4-flash" });
});

app.post('/api/opencode/active-model', async (req, res) => {
  const { model } = req.body;
  if (!model) return res.status(400).json({ error: "model parameter is required" });
  try {
    const response = await fetch('http://127.0.0.1:8777/v1/active-model', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ model })
    });
    if (response.ok) {
      const data = await response.json();
      return res.json(data);
    }
  } catch (e) {
    console.warn("OpenCode proxy active-model POST failed:", e.message);
  }
  res.status(502).json({ error: "Failed to communicate with OpenCode proxy" });
});

// -----------------------------------
// Script Execution API
// -----------------------------------
app.post('/api/execute', (req, res) => {
  const { appId } = req.body;
  const appsPath = path.join(__dirname, 'data', 'apps.json');
  const apps = JSON.parse(fs.readFileSync(appsPath, 'utf-8'));
  const appInfo = apps.find(a => a.id === appId);
  if (!appInfo) return res.status(404).json({ error: 'App not found' });

  const scriptPath = path.join(__dirname, appInfo.script);
  if (!fs.existsSync(scriptPath)) return res.status(500).json({ error: 'Script not found' });

  const proc = spawn('sh', [scriptPath]);
  let stdout = '';
  let stderr = '';
  proc.stdout.on('data', data => stdout += data.toString());
  proc.stderr.on('data', data => stderr += data.toString());
  proc.on('close', code => {
    res.json({ exitCode: code, stdout, stderr });
  });
});

app.listen(port, () => console.log(`🚀 Backend listening on http://localhost:${port}`));
