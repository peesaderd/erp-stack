module.exports = {
  apps: [{
    name: 'tiktok-ugc-studio',
    cwd: __dirname,
    script: 'uvicorn',
    args: 'main:app --host 0.0.0.0 --port 8105',
    interpreter: 'python3',
    watch: false,
    env: {
      PFM_API_KEY: 'pfm_live_4qR2sT7hvEo6qFKMQssker',
    },
  }, {
    name: 'scheduler',
    cwd: __dirname + '/../modules/scheduler',
    script: 'uvicorn',
    args: 'main:app --host 0.0.0.0 --port 8130',
    interpreter: 'python3',
    watch: false,
  }, {
    name: 'drive-service',
    cwd: __dirname + '/../modules/drive_service',
    script: 'uvicorn',
    args: 'main:app --host 0.0.0.0 --port 8132',
    interpreter: 'python3',
    watch: false,
  }]
};
