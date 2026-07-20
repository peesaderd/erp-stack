module.exports = {
  apps: [{
    name: 'tiktok-ugc-studio',
    cwd: __dirname,
    script: __dirname + '/main.py',
    interpreter: '/usr/bin/python3',
    watch: false,
    env: {
      PFM_API_KEY: 'pfm_live_4qR2sT7hvEo6qFKMQssker',
      AITOEARN_URL: 'https://aitoearn.ai',
      AITOEARN_API_KEY: 'ai_wexpixpktm1RaXrFXtFkjnQIWTV9UX5or7RVKOyiOP8NJCT0',
      TIKTOK_AITOEARN_ACCOUNT_ID: 'tiktok_-0002TMst9pSO4krFHlfvM8HTY7Jz999H32U',
    },
  }, {
    name: 'scheduler',
    cwd: __dirname + '/../modules/scheduler',
    script: 'main.py',
    interpreter: '/usr/bin/python3',
    watch: false,
  }, {
    name: 'drive-service',
    cwd: __dirname + '/../modules/drive_service',
    script: 'main.py',
    interpreter: '/usr/bin/python3',
    watch: false,
  }]
};
