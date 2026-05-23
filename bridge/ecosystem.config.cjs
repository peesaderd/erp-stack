module.exports = {
  apps: [{
    name: "erp-bridge",
    cwd: "/home/openhands/erp-stack/bridge",
    script: "bridge.py",
    interpreter: "python3",
    args: "--port 51517",
    env: {
      NODE_ENV: "production",
      PORT: "51517"
    },
    watch: false,
    max_memory_restart: "200M",
    error_file: "/home/openhands/erp-stack/bridge/logs/err.log",
    out_file: "/home/openhands/erp-stack/bridge/logs/out.log",
    log_date_format: "YYYY-MM-DD HH:mm:ss",
    merge_logs: true
  }]
};
