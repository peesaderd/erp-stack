/* LINE Bot Service — PM2 ecosystem config */
module.exports = {
  apps: [{
    name: "line-bot",
    cwd: "/home/openhands/erp-stack/modules/line_bot",
    script: "venv/bin/uvicorn",
    args: "main:app --host 0.0.0.0 --port 8140 --reload",
    interpreter: "",
    env: {
      PORT: "8140",
      HOST: "0.0.0.0",
      ERP_MODULAR_URL: "http://localhost:8102",
      POS_API_URL: "http://localhost:8114",
    },
    env_file: "/home/openhands/erp-stack/.env",
    max_restarts: 5,
    restart_delay: 5000,
    watch: false,
    merge_logs: true,
    log_date_format: "YYYY-MM-DD HH:mm:ss",
  }]
};
