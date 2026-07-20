module.exports = {
  apps: [{
    name: 'inner-monologue-agent',
    script: '/usr/bin/python3',
    cwd: '/home/openhands/erp-stack',
    args: [
      '-m', 'inner_monologue.main',
      '--model', 'deepseek/deepseek-chat',
      '--workspace', '/home/openhands/erp-stack',
      '--memory-dir', '/home/openhands/erp-stack/.inner-monologue-memory',
      '--wait',
      '--task-dir', '/home/openhands/erp-stack/.agent-tasks',
    ],
    env: {
      PYTHONPATH: '/home/openhands/erp-stack',
      DEEPSEEK_API_KEY: 'sk-704a41bad6e249dc83a0f7e344871149',
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
    // Auto-restart on crash (--wait mode ไม่ควรตายนอกจาก error จริง)
    autorestart: true,
    max_restarts: 3,
    restart_delay: 5000,
  }],
};
