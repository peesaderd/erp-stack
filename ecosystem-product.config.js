module.exports = {
  apps: [{
    name: 'product-scraper',
    script: '/home/openhands/erp-stack/venv-browser-use/bin/python3',
    cwd: '/home/openhands/erp-stack',
    args: '-c "
import sys, os
os.environ[\"PLAYWRIGHT_BROWSERS_PATH\"] = \"/home/openhands/.cache/ms-playwright\"
sys.path.insert(0, \"/home/openhands/erp-stack/modules\")
from product.main import app
import uvicorn
uvicorn.run(app, host=\"0.0.0.0\", port=8106)
"',
    env: {
      PYTHONPATH: '/home/openhands/erp-stack/modules',
    },
    interpreter: 'none',
    max_restarts: 10,
    min_uptime: 5000,
  }]
};
