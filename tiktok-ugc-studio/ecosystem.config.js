module.exports = {
  apps: [{
    name: 'tiktok-ugc-studio',
    cwd: __dirname,
    script: 'uvicorn',
    args: 'main:app --host 0.0.0.0 --port 8105',
    interpreter: 'python3',
    watch: false,
  }]
};
