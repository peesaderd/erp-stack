#!/bin/bash
cd /home/openhands/erp-stack
source venv-browser-use/bin/activate
export PYTHONPATH=/home/openhands/erp-stack/modules
python3 -c "
import sys, os
sys.path.insert(0, '/home/openhands/erp-stack/modules')
from media.main import app
import uvicorn
uvicorn.run(app, host='0.0.0.0', port=8103)
"
