module.exports = {
  apps: [{
    name: "bridge-server",
    cwd: __dirname,
    script: "uvicorn",
    args: "app:app --host 0.0.0.0 --port 54517 --reload",
    interpreter: "python3",
    watch: false,
    max_restarts: 10,
    restart_delay: 5000,
    env: {
      PYTHONPATH: __dirname,
    },
  }],
};
