---
name: telegram-notifications
description: Send notifications or messages to Telegram when a task is completed, when requested by the user, or when a background timer triggers.
---

Use this skill to notify the user on Telegram.

### Requirements
- A Telegram Bot Token.
- A Telegram Chat ID (or channel username).

### Setup Env Variables
You can configure these environment variables in your workspace `.env` file:
- `TELEGRAM_NOTIFY_TOKEN`: Your Telegram Bot Token.
- `TELEGRAM_NOTIFY_CHAT_ID`: Your Telegram Chat ID.

### Usage
Run the helper python script located at `scripts/send_telegram.py` using `run_command`:
```bash
python scripts/send_telegram.py --message "Task completed successfully!"
```
If environment variables are not set, you can pass them as arguments:
```bash
python scripts/send_telegram.py --token <bot_token> --chat-id <chat_id> --message "Hello!"
```
