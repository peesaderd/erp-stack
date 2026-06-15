module.exports = {
  apps: [
    {
      name: "modules-video",
      script: "main.py",
      cwd: "/home/openhands/erp-stack/modules/video",
      interpreter: "python3",
      env: {
        PORT: "8111",
        PYTHONPATH: "/home/openhands/erp-stack/modules"
      },
      exec_mode: "fork",
      instances: 1,
      watch: false,
      max_restarts: 10,
      restart_delay: 3000
    }
  ]
};
