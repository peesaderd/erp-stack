/* Reward / Loyalty Service — PM2 ecosystem config */
module.exports = {
  apps: [{
    name: "reward",
    cwd: "/home/openhands/erp-stack/modules/reward",
    script: "/home/openhands/erp-stack/modules/reward/.venv/bin/uvicorn",
    args: "reward.main:app --host 0.0.0.0 --port 8121",
    interpreter: "none",
    env: {
      PORT: "8121",
      SCHEMA_ENGINE_URL: "http://localhost:8100",
      ERP_MODULAR_URL: "http://localhost:8102",
      POS_API_URL: "http://localhost:8114",
      PYTHONPATH: "/home/openhands/erp-stack/modules:/home/openhands/erp-stack",
    },
    env_file: "/home/openhands/erp-stack/.env",
    max_restarts: 5,
    restart_delay: 5000,
    watch: false,
    merge_logs: true,
    log_date_format: "YYYY-MM-DD HH:mm:ss",
  }]
};
