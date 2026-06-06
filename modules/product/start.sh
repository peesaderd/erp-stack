#!/bin/bash
cd /home/openhands/erp-stack
source venv-browser-use/bin/activate
export PLAYWRIGHT_BROWSERS_PATH=/home/openhands/.cache/ms-playwright
export PYTHONPATH=/home/openhands/erp-stack/modules

python3 -c "
import sys
sys.path.insert(0, '/home/openhands/erp-stack/modules')
from product.main import app
import uvicorn
uvicorn.run(app, host='0.0.0.0', port=8106)
"
