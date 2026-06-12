module.exports = {
  apps: [{
    name: 'product-scraper',
    cwd: '/home/openhands/erp-stack/modules/product',
    script: '/home/openhands/erp-stack/venv-browser-use/bin/python3',
    args: '-m uvicorn product.main:app --host 0.0.0.0 --port 8106',
    env: {
      PYTHONPATH: '/home/openhands/erp-stack/modules',
      PROXY_URL: 'http://peerawat…sword@gw.dataimpulse.com:823',
      PROXY_LIST: 'http://peerawat…sword@gw.dataimpulse.com:823',
    },
    max_restarts: 10,
    min_uptime: 5000,
  }]
}
