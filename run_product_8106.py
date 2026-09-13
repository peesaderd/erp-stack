"""Runner for the Product Scraper service (port 8106).

Extracted from the previous pm2 inline `-c` args in ecosystem-product.config.js
so the app can be started/restarted cleanly via pm2.
"""
import os
import sys

os.environ["PLAYWRIGHT_BROWSERS_PATH"] = "/home/openhands/.cache/ms-playwright"
sys.path.insert(0, "/home/openhands/erp-stack/modules")

from product.main import app  # noqa: E402
import uvicorn  # noqa: E402


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8106)
