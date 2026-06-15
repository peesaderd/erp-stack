module.exports = {
  apps: [
    {
      name: "tus-video",
      script: "tus_video_service.py",
      cwd: "/home/openhands/erp-stack/tiktok-ugc-studio",
      interpreter: "python3",
      env: {
        PORT: "8111",
        PYTHONPATH: "/home/openhands/erp-stack/tiktok-ugc-studio"
      },
      exec_mode: "fork",
      instances: 1,
      watch: false,
      max_restarts: 10,
      restart_delay: 3000
    }
  ]
};
