/* ERP Leaderboard & Achievements Module — PM2 ecosystem config */
module.exports = {
  apps: [{
    name: "leaderboard-module",
    cwd: "/home/openhands/erp-stack/modules/leaderboard",
    script: "/home/openhands/erp-stack/venv-browser-use/bin/uvicorn",
    args: "main:app --host 0.0.0.0 --port 8125",
    interpreter: "none",
    env: {
      PORT: "8125",
      PYTHONPATH: "/home/openhands/erp-stack/modules/leaderboard:/home/openhands/erp-stack/modules",
    },
    max_restarts: 10,
    restart_delay: 3000,
    watch: false,
    merge_logs: true,
    log_date_format: "YYYY-MM-DD HH:mm:ss",
  }]
};
