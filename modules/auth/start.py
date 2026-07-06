import sys
import os
from dotenv import load_dotenv

# Load env variables from auth/.env
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
load_dotenv(env_path)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import uvicorn
from auth.main import app

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8101)
