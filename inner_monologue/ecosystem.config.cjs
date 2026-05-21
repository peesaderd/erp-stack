module.exports = {
  apps: [{
    name: 'inner-monologue-agent',
    script: '/usr/bin/python3',
    cwd: '/home/openhands/erp-stack',
    args: [
      '-m', 'inner_monologue.main',
      '--model', 'deepseek/deepseek-chat',
      '--workspace', '/home/openhands/erp-stack',
      'รัน Agent รอรับคำสั่ง...',
    ],
    env: {
      PYTHONPATH: '/home/openhands/erp-stack',
      DEEPSEEK_API_KEY: process.env.DEEPSEEK_API_KEY || '',
      GROQ_API_KEY: process.env.GROQ_API_KEY || '',
      MISTRAL_API_KEY: process.env.MISTRAL_API_KEY || '',
    },
    // Restart if memory exceeds 300MB
    max_memory_restart: '300M',
    // Log configuration
    error_file: '/home/openhands/erp-stack/logs/agent-error.log',
    out_file: '/home/openhands/erp-stack/logs/agent-out.log',
    log_file: '/home/openhands/erp-stack/logs/agent-combined.log',
    time: true,
    // Auto-restart on crash
    autorestart: true,
    max_restarts: 10,
    restart_delay: 3000,
  }],
};
