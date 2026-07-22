"""LINE Bot Service — Entry point

Usage:
    python3 start.py
"""

import os
import sys
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)

# Add parent to path so shared module is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from line_bot.main import app

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "8140"))
    host = os.environ.get("HOST", "0.0.0.0")
    uvicorn.run(app, host=host, port=port, reload=False)
