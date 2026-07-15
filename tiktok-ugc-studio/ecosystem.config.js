module.exports = {
  apps: [{
    name: 'tiktok-ugc-studio',
    cwd: __dirname,
    script: __dirname + '/main.py',
    interpreter: '/usr/bin/python3',
    watch: false,
    env: {
      PFM_API_KEY: 'pfm_live_4qR2sT7hvEo6qFKMQssker',
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
