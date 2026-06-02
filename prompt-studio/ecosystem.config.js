module.exports = {
  apps: [{
    name: 'prompt-studio',
    cwd: '/home/openhands/erp-stack/prompt-studio',
    script: 'venv/bin/uvicorn',
    args: 'main:app --host 0.0.0.0 --port 8107',
    interpreter: 'none',
    env: {
      PROMPT_MODE: 'file',
      PROMPT_BASE_PATH: '/home/openhands/erp-stack/prompt-studio/prompts',
    },
  }]
};
