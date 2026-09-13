import sys
import os
from dotenv import load_dotenv

# Load env variables from auth/.env first, then fall back to repo-root .env
# (root .env holds the real GOOGLE_OAUTH / LINE_CHANNEL credentials).
base = os.path.dirname(os.path.abspath(__file__))
local_env = os.path.join(base, ".env")
root_env = os.path.join(base, "..", "..", ".env")
load_dotenv(local_env)
load_dotenv(root_env, override=True)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import uvicorn
from auth.main import app

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8101)
