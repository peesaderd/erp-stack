module.exports = {
  apps: [{
    name: "brain-server",
    cwd: "/home/openhands/erp-stack",
    script: "python3",
    args: "brain_server_v6.py",
    env: {
      LLM_API_KEY: "sk-placeholder-replace-in-production",
      LLM_MODEL: "deepseek-chat",
      LLM_PROVIDER: "deepseek",
      PORT: "8101"
    }
  }, {
    name: "openhands-proxy",
    cwd: "/home/openhands/erp-stack/pm2-proxies",
    script: "openhands-proxy.js",
    interpreter: "node",
    env: {
      NODE_ENV: "production"
    }
  }]
};
