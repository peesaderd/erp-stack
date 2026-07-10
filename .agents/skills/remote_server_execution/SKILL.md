---
name: remote-server-execution
description: Enforces remote cloud server execution and deployment policies for all tasks in the calm-noether project, preventing local host port and resource conflicts with the active ERP system.
---

# Remote Server Execution Skill

This skill enforces strict rules and guides for developing, building, deploying, and testing code for the `calm-noether` project exclusively on the remote cloud server.

## 🚨 Core Rules & Constraints

1. **Zero Local Operations**:
   - Do **NOT** run `npm run dev`, `docker compose up`, or database migrations locally on the local machine.
   - The local host machine runs a local production ERP system. Port collisions (e.g., `5432`, `4000`, `3000`) or database writes on the local machine will break the ERP system.

2. **Server Information**:
   - **IP Address**: `89.167.82.205`
   - **SSH User**: `openhands`
   - **SSH Password**: `OpenHands@ERP2026`
   - **Target Project Directory**: `/home/openhands/calm-noether`

3. **Deployment Workflow**:
   - Always upload modifications using recursive SSH upload helpers.
   - Trigger Docker container rebuilds and restarts remotely via SSH:
     ```bash
     cd ~/calm-noether && sudo docker compose up -d --build
     ```
