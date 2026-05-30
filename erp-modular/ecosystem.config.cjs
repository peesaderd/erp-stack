module.exports = {
  apps: [{
    name: "erp-modular",
    cwd: "/home/openhands/erp-stack/erp-modular",
    script: "uvicorn",
    args: "main:app --host 0.0.0.0 --port 8102 --reload",
    interpreter: "python3",
    env: {
      LLM_API_KEY: "sk-704a41bad6e249dc83a0f7e344871149",
      LLM_MODEL: "deepseek-chat",
      LLM_PROVIDER: "deepseek",
      DATABASE_URL: "sqlite:///./erp_modular.db",
      SECRET_KEY: "erp-modular-secret-key-change-in-production"
    }
  }]
};
