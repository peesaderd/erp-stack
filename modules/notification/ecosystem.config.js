/* ERP Notification Module — PM2 ecosystem config */
module.exports = {
  apps: [{
    name: "notification-module",
    cwd: "/home/openhands/erp-stack/modules/notification",
    script: "/home/openhands/erp-stack/venv-browser-use/bin/uvicorn",
    args: "main:app --host 0.0.0.0 --port 8126",
    interpreter: "none",
    env: {
      PORT: "8126",
      PYTHONPATH: "/home/openhands/erp-stack/modules/notification:/home/openhands/erp-stack/modules",
    },
    max_restarts: 10,
    restart_delay: 3000,
    watch: false,
    merge_logs: true,
    log_date_format: "YYYY-MM-DD HH:mm:ss",
  }]
};
