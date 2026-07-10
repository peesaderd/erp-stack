# Project Rules - calm-noether

## 🚨 Critical Environment Rules

- **ALWAYS Execute on Remote Cloud Server**: All server operations, database scripts, app installations, compilation builds (Docker compose), and runtime commands **MUST** be executed exclusively on the remote cloud server (`89.167.82.205`).
- **NEVER Run Local Backend/Frontend Servers**: Do not start any dev servers, databases, or script execution processes on the local machine (`localhost`). The local developer machine runs a local production ERP system, and running local developer instances of calm-noether will cause port conflicts, database corruption, or performance issues for the ERP.
- **SSH Deployment & Automation Flow**:
  - Always upload code changes to the remote server via SSH.
  - Rebuild containers on the remote server using remote Docker commands (via paramiko SSH scripts).
  - Use the preconfigured deployment Python scripts in the scratch directory for syncing.
