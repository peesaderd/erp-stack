module.exports = {
  apps: [{
    name: 'product-scraper',
    script: '/home/openhands/erp-stack/run_product_8106.py',
    cwd: '/home/openhands/erp-stack',
    interpreter: '/home/openhands/erp-stack/venv-browser-use/bin/python3',
    env: {
      PYTHONPATH: '/home/openhands/erp-stack/modules',
      PLAYWRIGHT_BROWSERS_PATH: '/home/openhands/.cache/ms-playwright',
      NODE_ENV: 'production',
    },
    max_restarts: 10,
    min_uptime: 5000,
    kill_timeout: 10000,
    autorestart: true,
    restart_delay: 3000,
  }]
};
