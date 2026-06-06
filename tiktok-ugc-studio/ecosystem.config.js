module.exports = {
  apps: [{
    name: 'tiktok-ugc-studio',
    script: 'venv/bin/uvicorn',
    args: 'main:app --host 0.0.0.0 --port 8105',
    cwd: __dirname,
    interpreter: 'none',
    env: {
      LLM_API_KEY: process.env.LLM_API_KEY || '',
      LLM_BASE_URL: process.env.LLM_BASE_URL || 'https://api.deepseek.com',
      LLM_MODEL: process.env.LLM_MODEL || 'deepseek-chat',
      WAVESPEED_API_KEY: 'wsk_live_whbPT_ai2ZUpxq3I2tcjPwDj3JuYuFcEPCn7OSdM-bU',
      FAL_API_KEY: process.env.FAL_API_KEY || process.env.FAL_KEY || '',
    },
    max_restarts: 10,
    min_uptime: '10s',
  }]
};
