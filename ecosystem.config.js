module.exports = {
  apps: [
    {
      name: 'tiktok-ugc-studio',
      cwd: '/home/openhands/erp-stack/tiktok-ugc-studio',
      script: './venv/bin/python3',
      args: '-m uvicorn main:app --host 0.0.0.0 --port 8105',
      autorestart: true,
      max_restarts: 10,
      restart_delay: 5000,
      env: {
        NODE_ENV: 'production',
      },
    },
    {
      name: 'image-gen',
      cwd: '/home/openhands/erp-stack/modules/image',
      script: '/usr/bin/python3',
      args: '-m uvicorn main:app --host 0.0.0.0 --port 8110',
      autorestart: true,
      max_restarts: 10,
      restart_delay: 5000,
    },
    {
      name: 'video-gen',
      cwd: '/home/openhands/erp-stack/modules/video',
      script: '/usr/bin/python3',
      args: '-m uvicorn main:app --host 0.0.0.0 --port 8111',
      autorestart: true,
      max_restarts: 10,
      restart_delay: 5000,
    },
    {
      name: 'prompt-builder',
      cwd: '/home/openhands/erp-stack/prompt-builder-service',
      script: '/usr/bin/python3',
      args: '-m uvicorn app:app --host 0.0.0.0 --port 8117',
      autorestart: true,
      max_restarts: 10,
      restart_delay: 5000,
    },
  ],
};
