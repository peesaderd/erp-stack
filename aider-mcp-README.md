# AIDER MCP Server Setup

This directory contains setup scripts for the AIDER MCP Server.

## Quick Start

1. Navigate to the peteai directory:
   ```bash
   cd /opt/tasks/peteai
   ```

2. Make the setup script executable:
   ```bash
   chmod +x setup_aider_mcp.sh
   ```

3. Run the setup script:
   ```bash
   ./setup_aider_mcp.sh
   ```

If you encounter permission issues, you may need to run:
```bash
sudo chmod +x setup_aider_mcp.sh
```

## What the script does:

1. **Environment Check**: Verifies permissions and stops any running aider-mcp processes
2. **Python Verification**: Checks for Python 3 installation, installs if missing
3. **Pip Installation**: Installs pip (pip3 or pip) with multiple fallback methods
4. **System Preparation**: Checks disk space and internet connectivity
5. **aider-mcp Installation**: Installs aider-mcp via pip with detailed progress reporting
6. **Path Configuration**: Sets AIDER_PATH and updates shell profiles (~/.bashrc, ~/.profile)
7. **Service Setup**: Creates and verifies a systemd service with automatic restart
8. **Service Verification**: Starts the service and performs comprehensive health checks
9. **Troubleshooting**: Provides detailed error messages and recovery steps if any step fails

## Installation Details

The script handles multiple installation scenarios:

### Python Installation
- Checks for Python 3
- Installs via system package manager if available (apt, dnf, yum, etc.)
- Provides manual installation instructions if package manager not found
- Verifies Python is functional before proceeding

### Pip Installation (with multiple fallbacks)
1. **System package manager**: Uses apt, dnf, or yum if available
2. **Proper error capture**: Correctly checks installation success/failure
3. **get-pip.py fallback**: Downloads and runs `get-pip.py` from PyPA with alternative URLs
4. **Smart update**: Minimizes redundant package list updates
5. **Verification**: Checks for `pip3`, `pip`, or `python3 -m pip` with location detection
6. **Error handling**: Provides detailed error messages and manual installation instructions

### System Requirements Check
- Disk space verification (warns if <100MB available)
- Internet connectivity test to PyPI
- Directory permissions check

### aider-mcp Installation
- Checks if aider-mcp is already installed via pip before attempting installation
- System-wide installation attempted first (requires appropriate permissions)
- User installation fallback if system-wide fails (uses `--user` flag)
- Proper exit status checking with detailed error reporting
- Comprehensive verification with multiple location checks
- Automatic PATH adjustment if binary found outside PATH
- Permission fixing for non-executable binaries
- Detailed installation logging to `/tmp/aider-install.log` with error extraction
- Shows pip package information if already installed

### Path Configuration
- Sets `AIDER_PATH` environment variable using `command -v` (more reliable than `which`)
- Updates `~/.bashrc` and `~/.profile` with clean configuration
- Handles backup of existing configuration files
- Removes duplicate entries before adding new configuration
- Adds PATH export as a commented line by default (to avoid PATH conflicts)
- Provides clear instructions for enabling PATH if needed
- Uses portable shell commands for better compatibility across systems

### Service Management
- Creates systemd service with automatic restart
- Comprehensive service verification
- Detailed troubleshooting if service fails to start

## Managing the service

- Check status: `sudo systemctl status aider-mcp`
- Start service: `sudo systemctl start aider-mcp`
- Stop service: `sudo systemctl stop aider-mcp`
- Restart service: `sudo systemctl restart aider-mcp`
- View logs: `sudo journalctl -u aider-mcp -f`
- Follow logs: `sudo journalctl -u aider-mcp -f --tail=50`

## Testing the Installation

After setup, run the test script:
```bash
./test_aider_mcp.sh
```

This will verify:
- Service status and process running
- Python and pip availability
- aider-mcp installation and version
- Binary functionality and permissions
- Task file accessibility
- Basic API connectivity (if applicable)
- File reading capability (conceptual test)

The test script provides detailed diagnostics including:
- Version information extraction
- Permission checks and fixes
- Dependency verification
- Help output analysis
- File system accessibility
- PATH configuration checks

## Troubleshooting Common Issues

### aider-mcp Installation Fails
1. **Network issues**: Check internet connectivity and proxy settings
2. **Permission issues**: Try `sudo pip3 install aider-mcp` or `pip3 install --user aider-mcp`
3. **Package not found**: Verify the package name is correct
4. **Python version**: Ensure Python 3.7+ is installed
5. **pip version**: Upgrade pip with `pip3 install --upgrade pip`
6. **Check logs**: Review `/tmp/aider-install.log` for detailed error messages

### aider-mcp Command Not Found
1. **PATH issue**: The binary may be installed but not in PATH
   - Check common locations: `~/.local/bin`, `/usr/local/bin`, `/usr/bin`
   - Add to PATH: `export PATH="~/.local/bin:$PATH"`
2. **Binary not executable**: Fix with `chmod +x /path/to/aider-mcp`
3. **Installation incomplete**: Reinstall with `pip3 install --user aider-mcp`
4. **Multiple Python installations**: Check which Python installation pip is using

### Service Fails to Start
1. **Check logs**: `sudo journalctl -u aider-mcp -n 50`
2. **Verify binary path**: Ensure `AIDER_PATH` in service file is correct
3. **Check permissions**: The service user must have execute permission
4. **Port conflicts**: aider-mcp may need specific ports (check documentation)
5. **Dependencies missing**: Check if all required libraries are installed

### Task Files Not Accessible
1. **File permissions**: Ensure the service user can read `/opt/tasks/todo/`
2. **Path correctness**: Verify task files exist at expected locations
3. **File format**: Ensure files are valid markdown with proper syntax
4. **Service user permissions**: The aider-mcp service runs as your user, ensure it has read access

### Error Handling Improvements
The setup script includes enhanced error handling that:
- Prevents double error messages
- Provides specific troubleshooting guidance for each failure point
- Preserves installation logs in `/tmp/` for debugging
- Continues testing even if some components fail (test script)

## Environment Variables

- `AIDER_PATH`: Path to the aider-mcp executable (set in ~/.bashrc and ~/.profile)
  - Displayed during setup: "AIDER_PATH set to: /path/to/aider-mcp"
  - Verified in test script for correctness and accessibility
  - Automatically added to PATH if not already present

## Notes

- The service runs under the current user account
- Logs are available via journalctl (`sudo journalctl -u aider-mcp`)
- The setup script modifies ~/.bashrc and ~/.profile (backups are created)
- If installation fails, check logs in `/tmp/aider-install.log` and `/tmp/pip-install.log`
- After setup, you may need to start a new terminal or run `source ~/.bashrc` for AIDER_PATH to take effect
