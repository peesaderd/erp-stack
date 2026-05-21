module.exports = {
  apps: [{
    name: 'inner-monologue-agent',
    script: '/usr/bin/python3',
    cwd: '/home/openhands/erp-stack',
    args: [
      '-m', 'inner_monologue.main',
      '--model', 'mistral/mistral-large-latest',
      '--workspace', '/home/openhands/erp-stack',
      'รัน Agent รอรับคำสั่ง...',
    ],
    env: {
      MISTRAL_API_KEY: process.env.MISTRAL_API_KEY || '',
    },
    // Restart if memory exceeds 200MB
    max_memory_restart: '200M',
    // Log configuration
    error_file: './logs/agent-error.log',
    out_file: './logs/agent-out.log',
    log_file: './logs/agent-combined.log',
    time: true,
    // Auto-restart on crash
    autorestart: true,
    max_restarts: 5,
    restart_delay: 5000,
  }],
};
