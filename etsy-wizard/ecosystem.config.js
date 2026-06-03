module.exports = {
  apps: [{
    name: "etsy-wizard",
    cwd: "/home/openhands/erp-stack/etsy-wizard",
    script: "venv/bin/python3",
    args: "-m uvicorn main:app --host 0.0.0.0 --port 8104 --reload",
    env: {
      PYTHONPATH: "/home/openhands/erp-stack/etsy-wizard",
      LLM_API_KEY: "sk-704a41bad6e249dc83a0f7e344871149",
      LLM_MODEL: "deepseek-chat",
      LLM_PROVIDER: "deepseek",
      FAL_KEY: "5aa3fcba-eb64-4ff5-b79c-5a7387dca152:e19d89754ddf4bda7b71e0fb2b5eb83c",
    }
  }]
};
