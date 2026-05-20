#!/bin/bash

# Setup script for aider-mcp
# Exit on error, but handle some cases where failure is expected
set -e

# Function to handle errors
error_handler() {
    # Check if we're already in the error handler to avoid infinite loops
    if [ -n "$IN_ERROR_HANDLER" ]; then
        exit 1
    fi
    IN_ERROR_HANDLER=1
    
    echo ""
    echo "========================================="
    echo "Setup failed! ✗"
    echo "========================================="
    echo "Error occurred at line: $1"
    echo "Command: $2"
    echo ""
    echo "Troubleshooting tips:"
    echo "1. Check if you have internet connectivity for package installation"
    echo "2. Ensure you have sufficient disk space"
    echo "3. Verify your user has sudo privileges"
    echo "4. Check system logs: sudo journalctl -xe"
    echo "5. Check installation logs in /tmp/ directory"
    exit 1
}

# Trap errors
trap 'error_handler ${LINENO} "$BASH_COMMAND"' ERR

# Check if script is executable, provide guidance if not
if [ ! -x "$0" ]; then
    echo "This script is not executable. Please run:"
    echo "  chmod +x $(basename "$0")"
    echo "Then run:"
    echo "  ./$(basename "$0")"
    exit 1
fi

# Check for sudo privileges early
echo "Checking for sudo privileges..."
if ! sudo -v &> /dev/null; then
    echo "Error: This script requires sudo privileges."
    echo "Please run with sudo or as a user with sudo access."
    exit 1
fi
echo "✓ Sudo privileges confirmed"

echo ""
echo "Setting up AIDER MCP Server..."
echo "=============================="

# Initialize variables
APT_UPDATED=0
USE_GET_PIP=0

# Check current directory and permissions
echo "Checking environment..."
CURRENT_DIR=$(pwd)
echo "Current directory: $CURRENT_DIR"
if [ ! -w "$CURRENT_DIR" ]; then
    echo "⚠ Warning: Current directory may not be writable"
fi

# Check if aider-mcp is already running
echo "Checking for existing aider-mcp processes..."
RUNNING_PROCESSES=$(pgrep -f "aider-mcp" | wc -l)
if [ "$RUNNING_PROCESSES" -gt 0 ]; then
    echo "⚠ Found $RUNNING_PROCESSES running aider-mcp process(es). Stopping them first..."
    # Temporarily disable set -e for these commands
    set +e
    echo "Stopping systemd service..."
    sudo systemctl stop aider-mcp 2>/dev/null
    echo "Stopping any remaining processes..."
    pkill -f "aider-mcp" 2>/dev/null
    sleep 2
    # Check if processes are still running
    STILL_RUNNING=$(pgrep -f "aider-mcp" | wc -l)
    if [ "$STILL_RUNNING" -gt 0 ]; then
        echo "⚠ Some processes still running. Force stopping..."
        pkill -9 -f "aider-mcp" 2>/dev/null
    fi
    # Re-enable set -e
    set -e
    echo "✓ Stopped existing processes"
else
    echo "✓ No existing aider-mcp processes found"
fi

# Check if aider-mcp is installed
echo "Checking if aider-mcp is installed..."
AIDER_INSTALLED=0
FOUND_AIDER_PATH=""

# First, check if it's in PATH
if command -v aider-mcp &> /dev/null; then
    # Use command -v to get the path (more reliable than which)
    FOUND_AIDER_PATH=$(command -v aider-mcp)
    echo "✓ aider-mcp found in PATH: $FOUND_AIDER_PATH"
    AIDER_INSTALLED=1
else
    # Check common installation locations
    echo "aider-mcp not found in PATH. Checking common locations..."
    
    # Check user's local bin
    if [ -f "$HOME/.local/bin/aider-mcp" ]; then
        FOUND_AIDER_PATH="$HOME/.local/bin/aider-mcp"
        echo "✓ aider-mcp found in ~/.local/bin"
        export PATH="$HOME/.local/bin:$PATH"
        AIDER_INSTALLED=1
    # Check virtual environment locations
    elif [ -f "./venv/bin/aider-mcp" ]; then
        FOUND_AIDER_PATH="./venv/bin/aider-mcp"
        echo "✓ aider-mcp found in ./venv/bin/"
        export PATH="./venv/bin:$PATH"
        AIDER_INSTALLED=1
    elif [ -f "../venv/bin/aider-mcp" ]; then
        FOUND_AIDER_PATH="../venv/bin/aider-mcp"
        echo "✓ aider-mcp found in ../venv/bin/"
        export PATH="../venv/bin:$PATH"
        AIDER_INSTALLED=1
    elif [ -f "/usr/local/bin/aider-mcp" ]; then
        FOUND_AIDER_PATH="/usr/local/bin/aider-mcp"
        echo "✓ aider-mcp found in /usr/local/bin"
        export PATH="/usr/local/bin:$PATH"
        AIDER_INSTALLED=1
    elif [ -f "/usr/bin/aider-mcp" ]; then
        FOUND_AIDER_PATH="/usr/bin/aider-mcp"
        echo "✓ aider-mcp found in /usr/bin"
        AIDER_INSTALLED=1
    fi
fi

if [ $AIDER_INSTALLED -eq 0 ]; then
    echo "aider-mcp not found. Attempting to install..."
    echo "---------------------------------------------"
    
    # Check for Python and pip
    echo "Step 1: Checking Python and pip installation..."
    
    # First, check if Python 3 is available
    if ! command -v python3 &> /dev/null; then
        echo "  Python3 not found. Installing python3..."
        
        # Check if apt is available
        if command -v apt-get &> /dev/null; then
            echo "  Using apt package manager..."
            # Only update once if we haven't already
            if [ "$APT_UPDATED" != "1" ]; then
                sudo apt-get update || {
                    echo "  ⚠ Failed to update package list. Continuing anyway..."
                }
                APT_UPDATED=1
            fi
            if sudo apt-get install -y python3 python3-venv; then
                echo "  ✓ python3 installed via apt"
            else
                echo "  ✗ Failed to install python3 via apt"
                echo "  Please install python3 manually and try again."
                trap - ERR
                exit 1
            fi
        else
            echo "  ✗ apt-get not found. Cannot install python3 automatically."
            echo "  Please install Python 3 manually:"
            echo "  - Debian/Ubuntu: sudo apt-get install python3"
            echo "  - RHEL/Fedora: sudo dnf install python3"
            echo "  - macOS: brew install python@3"
            echo "  - Or download from: https://www.python.org/downloads/"
            trap - ERR
            exit 1
        fi
    else
        echo "  ✓ Python3 is available: $(python3 --version 2>&1)"
    fi
    
    # Check for pip (pip3 or pip)
    PIP_CMD=""
    if command -v pip3 &> /dev/null; then
        PIP_CMD="pip3"
        echo "  ✓ pip3 is available"
    elif command -v pip &> /dev/null; then
        PIP_CMD="pip"
        echo "  ✓ pip is available"
    else
        echo "  pip not found. Installing python3-pip..."
        
        # First, ensure python3 is definitely available
        if ! command -v python3 &> /dev/null; then
            echo "  ✗ Python3 is not available even after earlier check"
            echo "  Please install Python3 manually and try again."
            trap - ERR
            exit 1
        fi
        
        # Try apt installation first if apt is available
        if command -v apt-get &> /dev/null; then
            echo "  Attempting to install via apt..."
            # Only update once if we haven't already
            if [ "$APT_UPDATED" != "1" ]; then
                sudo apt-get update 2>/dev/null || {
                    echo "  ⚠ Could not update package list (may be offline)"
                }
                APT_UPDATED=1
            fi
            
            # Check if apt is available and can install packages
            # Use a temporary file to capture output and check exit status
            if sudo apt-get install -y python3-pip python3-venv > /tmp/pip-install.log 2>&1; then
                echo "  ✓ Successfully installed via apt"
                cat /tmp/pip-install.log | tail -5
                # Set PIP_CMD since apt installation succeeded
                if command -v pip3 &> /dev/null; then
                    PIP_CMD="pip3"
                elif command -v pip &> /dev/null; then
                    PIP_CMD="pip"
                fi
            else
                echo "  ⚠ apt installation failed. Checking error..."
                cat /tmp/pip-install.log | tail -10
                
                # Check if the error is due to missing packages or network
                if grep -q "Unable to locate package" /tmp/pip-install.log; then
                    echo "  ⚠ Package not found in repositories. Trying get-pip.py..."
                elif grep -q "Failed to fetch" /tmp/pip-install.log; then
                    echo "  ⚠ Network error during package fetch. Trying get-pip.py..."
                else
                    echo "  ⚠ apt install failed. Trying get-pip.py as fallback..."
                fi
                USE_GET_PIP=1
            fi
        else
            echo "  ⚠ apt-get not found. Using get-pip.py..."
            USE_GET_PIP=1
        fi
        
        # Use get-pip.py if apt failed or isn't available
        if [ "$USE_GET_PIP" = "1" ]; then
            # Try alternative installation method using get-pip.py
            echo "  Downloading get-pip.py..."
            curl -sS https://bootstrap.pypa.io/get-pip.py -o /tmp/get-pip.py || {
                # Try alternative URL if primary fails
                echo "  Primary URL failed, trying alternative..."
                curl -sS https://raw.githubusercontent.com/pypa/get-pip/main/public/get-pip.py -o /tmp/get-pip.py || {
                    echo "  ✗ Failed to download get-pip.py"
                    echo "  Please check internet connectivity or install pip manually:"
                    echo "  - For Debian/Ubuntu: sudo apt-get install python3-pip"
                    echo "  - For other systems, see: https://pip.pypa.io/en/stable/installation/"
                    exit 1
                }
            }
            
            echo "  Running get-pip.py..."
            python3 /tmp/get-pip.py 2>&1 | tee /tmp/get-pip-install.log || {
                echo "  ✗ get-pip.py installation failed"
                echo "  Check /tmp/get-pip-install.log for details"
                echo "  Last 10 lines of get-pip.py log:"
                tail -10 /tmp/get-pip-install.log 2>/dev/null || echo "    (log file not found)"
                echo ""
                echo "  Common issues with get-pip.py:"
                echo "  1. Python version too old (need Python 3.7+)"
                echo "  2. Network connectivity issues"
                echo "  3. System packages missing (python3-dev, etc.)"
                echo "  4. Permission issues (try with sudo)"
                echo ""
                echo "  Alternative pip installation methods:"
                echo "  1. Use system package manager:"
                echo "     - Debian/Ubuntu: sudo apt-get install python3-pip"
                echo "     - RHEL/Fedora: sudo dnf install python3-pip"
                echo "     - macOS: brew install python3"
                echo "  2. Download and install manually from: https://pip.pypa.io/en/stable/installation/"
                # Disable error trap before exiting
                trap - ERR
                exit 1
            }
            
            # Clean up
            rm -f /tmp/get-pip.py 2>/dev/null || true
        fi
        
        # Determine which pip command was installed
        echo "  Verifying pip installation..."
        sleep 1  # Give system a moment to recognize new installation
        
        # Clear command hash
        hash -r 2>/dev/null || true
        
        # Check for pip3 first, then pip
        if command -v pip3 &> /dev/null; then
            PIP_CMD="pip3"
            echo "  ✓ pip3 installed successfully"
        elif command -v pip &> /dev/null; then
            PIP_CMD="pip"
            echo "  ✓ pip installed successfully"
        else
            # Last resort: check if python3 -m pip works
            if python3 -m pip --version &> /dev/null; then
                PIP_CMD="python3 -m pip"
                echo "  ✓ pip available via python3 -m pip"
            else
                echo "  ✗ pip installation appears to have failed"
                echo "  Tried: pip3, pip, and python3 -m pip"
                echo "  Please install pip manually and try again."
                trap - ERR
                exit 1
            fi
        fi
    fi
    
    # Verify pip is working and show version
    echo "  Verifying $PIP_CMD..."
    if $PIP_CMD --version &> /dev/null; then
        echo "  ✓ $PIP_CMD is working: $($PIP_CMD --version | head -1)"
    else
        echo "  ✗ $PIP_CMD is not working"
        echo "  Please check pip installation."
        trap - ERR
        exit 1
    fi
    
    # Upgrade pip if it's an older version
    echo "  Checking if pip needs upgrade..."
    $PIP_CMD install --upgrade pip --quiet 2>/dev/null || {
        echo "  ⚠ Could not upgrade pip (may not be necessary)"
    }
    
    echo "Step 2: Preparing for aider-mcp installation..."
    echo "  Checking system requirements..."
    # Check disk space
    AVAILABLE_SPACE=$(df -k . | tail -1 | awk '{print $4}')
    if [ "$AVAILABLE_SPACE" -lt 100000 ]; then
        echo "  ⚠ Low disk space available: $((AVAILABLE_SPACE / 1024))MB"
        echo "  Installation may fail if less than 100MB is available."
    else
        echo "  ✓ Sufficient disk space available: $((AVAILABLE_SPACE / 1024))MB"
    fi
    
    # Check internet connectivity
    echo "  Checking internet connectivity..."
    if curl -s --max-time 5 https://pypi.org > /dev/null; then
        echo "  ✓ Internet connectivity confirmed"
    else
        echo "  ⚠ Cannot reach PyPI. Installation may fail."
    fi
    
    # Install aider-mcp via pip
    echo "Step 3: Installing aider-mcp using $PIP_CMD..."
    echo "  This may take a moment..."
    
    # Check if aider-mcp is already installed via pip
    echo "  Checking if aider-mcp is already installed..."
    if $PIP_CMD list 2>/dev/null | grep -i aider-mcp > /dev/null; then
        echo "  ⚠ aider-mcp appears to be already installed via pip"
        echo "  Checking version..."
        $PIP_CMD show aider-mcp 2>/dev/null | grep -i version || true
        echo "  Reinstalling/upgrading..."
    fi
    
    # Try system-wide installation first
    echo "  Attempting system-wide installation..."
    if $PIP_CMD install aider-mcp > /tmp/aider-install.log 2>&1; then
        echo "  ✓ System-wide installation successful"
        cat /tmp/aider-install.log | tail -5
    else
        echo "  ⚠ System-wide installation failed. Trying user install..."
        echo "  Attempting user installation..."
        if $PIP_CMD install --user aider-mcp > /tmp/aider-install.log 2>&1; then
            echo "  ✓ User installation successful"
            cat /tmp/aider-install.log | tail -5
            # Add user bin to PATH
            USER_BIN="$HOME/.local/bin"
            export PATH="$USER_BIN:$PATH"
            echo "  ✓ Added $USER_BIN to PATH for this session"
            echo "  Note: For permanent access, add to your shell profile:"
            echo "    echo 'export PATH=\"\$HOME/.local/bin:\$PATH\"' >> ~/.bashrc"
        else
            echo "  ✗ Installation failed. Check the log: /tmp/aider-install.log"
            echo "  Last 15 lines of installation log:"
            tail -15 /tmp/aider-install.log
            echo ""
            echo "  Common installation issues and solutions:"
            echo "  1. Network issues: Check internet connectivity and proxy settings"
            echo "  2. Permission issues: Try with sudo or use --user flag"
            echo "  3. Package not found: Check if the package name is correct"
            echo "  4. Python version: Ensure Python 3.7+ is installed"
            echo "  5. pip version: Upgrade pip with: $PIP_CMD install --upgrade pip"
            echo ""
            echo "  You can try manual installation with these commands:"
            echo "    # Try with user installation:"
            echo "    $PIP_CMD install --user aider-mcp"
            echo ""
            echo "    # Try with verbose output to see details:"
            echo "    $PIP_CMD install -v aider-mcp 2>&1 | tail -20"
            echo ""
            echo "    # Check if package exists on PyPI:"
            echo "    curl -s https://pypi.org/pypi/aider-mcp/json | grep -i version"
            echo ""
            echo "  If the package doesn't exist, you may need to:"
            echo "  1. Check the correct package name"
            echo "  2. Install from a different source (GitHub, etc.)"
            echo "  3. Contact the package maintainer"
            echo ""
            echo "  For more help, check the error details above."
            # Disable error trap temporarily to avoid double error handling
            trap - ERR
            exit 1
        fi
    fi
    
    # Verify installation
    echo "Step 4: Verifying installation..."
    # Clear any command hash
    hash -r 2>/dev/null || true
    
    # Wait a moment for the system to recognize the new installation
    sleep 2
    
    # Try to find the installed aider-mcp
    FOUND_AIDER_PATH=""
    
    # Check multiple locations - in order of likelihood
    echo "  Searching for installed aider-mcp..."
    
    # First, check if it's now in PATH
    if command -v aider-mcp &> /dev/null; then
        FOUND_AIDER_PATH=$(command -v aider-mcp)
        echo "  ✓ Found aider-mcp via PATH: $FOUND_AIDER_PATH"
    else
        # Check common installation locations
        POSSIBLE_PATHS=(
            "$HOME/.local/bin/aider-mcp"
            "/usr/local/bin/aider-mcp" 
            "/usr/bin/aider-mcp"
            "/opt/local/bin/aider-mcp"
            "/opt/homebrew/bin/aider-mcp"
        )
        
        # Also check Python user site packages bin directory
        if python3 -c "import site; import os; print(os.path.join(site.USER_BASE, 'bin'))" &>/dev/null; then
            USER_BIN_DIR=$(python3 -c "import site; import os; print(os.path.join(site.USER_BASE, 'bin'))" 2>/dev/null)
            if [ -n "$USER_BIN_DIR" ]; then
                POSSIBLE_PATHS+=("$USER_BIN_DIR/aider-mcp")
            fi
        fi
        
        # Check Python site packages bin directory
        if python3 -c "import sys; import os; print(os.path.join(sys.prefix, 'bin'))" &>/dev/null; then
            SYS_BIN_DIR=$(python3 -c "import sys; import os; print(os.path.join(sys.prefix, 'bin'))" 2>/dev/null)
            if [ -n "$SYS_BIN_DIR" ]; then
                POSSIBLE_PATHS+=("$SYS_BIN_DIR/aider-mcp")
            fi
        fi
        
        for path in "${POSSIBLE_PATHS[@]}"; do
            if [ -f "$path" ]; then
                FOUND_AIDER_PATH="$path"
                echo "  ✓ Found aider-mcp at: $path"
                # Add its directory to PATH if not already there
                PATH_DIR=$(dirname "$path")
                if [[ ":$PATH:" != *":$PATH_DIR:"* ]]; then
                    export PATH="$PATH_DIR:$PATH"
                    echo "  ✓ Added $PATH_DIR to PATH"
                fi
                break
            fi
        done
    fi
    
    if [ -n "$FOUND_AIDER_PATH" ] && [ -f "$FOUND_AIDER_PATH" ]; then
        echo "  ✓ aider-mcp installation successful!"
        # Show installation details
        echo "  Installation details:"
        echo "    Location: $FOUND_AIDER_PATH"
        echo "    Permissions: $(ls -la "$FOUND_AIDER_PATH" | awk '{print $1}')"
        echo "    Size: $(ls -lh "$FOUND_AIDER_PATH" | awk '{print $5}')"
        
        # Check if executable
        if [ -x "$FOUND_AIDER_PATH" ]; then
            echo "    Executable: Yes"
            # Try to get version
            echo "    Version check:"
            if timeout 3 "$FOUND_AIDER_PATH" --version 2>/dev/null; then
                version=$("$FOUND_AIDER_PATH" --version 2>&1 | head -1)
                echo "      $version"
            elif timeout 3 "$FOUND_AIDER_PATH" -v 2>/dev/null; then
                version=$("$FOUND_AIDER_PATH" -v 2>&1 | head -1)
                echo "      $version"
            else
                echo "      (version info not available via --version or -v)"
                # Try help as a fallback
                if timeout 3 "$FOUND_AIDER_PATH" --help 2>&1 | head -1 > /dev/null; then
                    echo "      (but --help works, so binary is functional)"
                    # Test basic functionality
                    echo "      Testing basic functionality..."
                    if timeout 3 "$FOUND_AIDER_PATH" --help 2>&1 | grep -i "usage\|help\|command\|aider\|mcp" > /dev/null; then
                        echo "      ✓ Basic help output looks reasonable"
                    else
                        echo "      ⚠ Help output doesn't contain expected keywords"
                    fi
                else
                    echo "      ⚠ --help also failed - binary may not be functional"
                fi
            fi
        else
            echo "    Executable: No - attempting to fix permissions..."
            chmod +x "$FOUND_AIDER_PATH" 2>/dev/null || sudo chmod +x "$FOUND_AIDER_PATH" 2>/dev/null
            if [ -x "$FOUND_AIDER_PATH" ]; then
                echo "    ✓ Fixed permissions - now executable"
                # Test if it works after fixing permissions
                echo "    Testing after permission fix..."
                if timeout 3 "$FOUND_AIDER_PATH" --help 2>&1 | head -1 > /dev/null; then
                    echo "    ✓ Binary works after permission fix"
                else
                    echo "    ⚠ Binary still not working after permission fix"
                fi
            else
                echo "    ✗ Could not make executable - may need manual intervention"
            fi
        fi
    else
        echo "  ✗ Installation verification failed."
        echo "  The installation may have succeeded but aider-mcp cannot be located."
        echo "  Common issues:"
        echo "  1. The installation directory may not be in PATH"
        echo "  2. The binary may have a different name"
        echo "  3. There may have been a silent installation failure"
        echo ""
        echo "  Checked common locations:"
        printf "    %s\n" "${POSSIBLE_PATHS[@]}"
        echo ""
        echo "  Current PATH: $PATH"
        echo ""
        echo "  Installation log (/tmp/aider-install.log):"
        tail -20 /tmp/aider-install.log 2>/dev/null || echo "    (log file not found)"
        echo ""
        echo "  You can try:"
        echo "  1. Running the installation manually: $PIP_CMD install aider-mcp"
        echo "  2. Checking pip installation location: $PIP_CMD show -f aider-mcp"
        echo "  3. Looking for the binary: find ~/.local /usr/local -name 'aider-mcp' 2>/dev/null"
        trap - ERR
        exit 1
    fi
    echo "---------------------------------------------"
else
    echo "✓ aider-mcp is already installed"
    # Show current installation details
    if [ -n "$FOUND_AIDER_PATH" ] && [ -f "$FOUND_AIDER_PATH" ]; then
        echo "  Location: $FOUND_AIDER_PATH"
        echo "  Version check:"
        if [ -x "$FOUND_AIDER_PATH" ]; then
            "$FOUND_AIDER_PATH" --version 2>/dev/null || "$FOUND_AIDER_PATH" -v 2>/dev/null || echo "    (version info not available)"
        else
            echo "    (cannot execute version check)"
        fi
    fi
fi

# Set AIDER_PATH to the location of aider-mcp
echo "Setting AIDER_PATH..."
if [ -n "$FOUND_AIDER_PATH" ]; then
    AIDER_PATH="$FOUND_AIDER_PATH"
    echo "✓ Using found path: $AIDER_PATH"
else
    # Try to find it using command -v
    if command -v aider-mcp &> /dev/null; then
        AIDER_PATH=$(command -v aider-mcp)
        echo "✓ Found via command -v: $AIDER_PATH"
    else
        echo "✗ Error: Could not determine AIDER_PATH"
        echo "  aider-mcp command is not available via 'command -v' even after installation."
        echo "  This usually means:"
        echo "  1. The installation directory is not in PATH"
        echo "  2. The binary is not executable"
        echo "  3. The installation failed silently"
        echo ""
        echo "  Please check:"
        echo "  1. Look for the binary: find ~/.local /usr/local -name 'aider-mcp' 2>/dev/null"
        echo "  2. Check if it's executable: ls -la \$(find ~/.local -name 'aider-mcp' 2>/dev/null | head -1)"
        echo "  3. Review installation log: /tmp/aider-install.log"
        echo "  4. Try running manually: python3 -m aider_mcp (if installed as module)"
        echo ""
        echo "  If you found the binary, add its directory to PATH:"
        echo "    export PATH=\"/path/to/directory:\$PATH\""
        trap - ERR
        exit 1
    fi
fi

# Export AIDER_PATH and ensure it's available
export AIDER_PATH
echo "✓ AIDER_PATH exported and set to: $AIDER_PATH"
echo "  This is the full path to the aider-mcp executable"

# Ensure the directory containing aider-mcp is in PATH
AIDER_DIR=$(dirname "$AIDER_PATH")
echo "Checking if $AIDER_DIR is in PATH..."
if [[ ":$PATH:" != *":$AIDER_DIR:"* ]]; then
    echo "⚠ AIDER_PATH directory is not in PATH"
    echo "  This means 'aider-mcp' command may not work in all terminals"
    echo "  Adding $AIDER_DIR to PATH for this session..."
    export PATH="$AIDER_DIR:$PATH"
    echo "✓ Updated PATH to include $AIDER_DIR"
    echo "  Note: The setup script will also update your shell profiles (~/.bashrc, ~/.profile)"
    echo "        to make this change permanent"
else
    echo "✓ AIDER_PATH directory is already in PATH"
    echo "  'aider-mcp' command should work in this terminal"
fi

# Final verification that aider-mcp command works
echo ""
echo "Performing final verification of aider-mcp installation..."
echo "----------------------------------------------------------"

# First check if it's in PATH
echo "Checking if 'aider-mcp' command is available in PATH..."
if command -v aider-mcp &> /dev/null; then
    AIDER_ACTUAL_PATH=$(command -v aider-mcp)
    echo "✓ 'aider-mcp' command is available in PATH"
    echo "  Executable found at: $AIDER_ACTUAL_PATH"
    echo "  This means you can run 'aider-mcp' from any directory"
else
    echo "⚠ 'aider-mcp' command not found in PATH"
    echo "  Current PATH: $PATH"
    echo "  Configured AIDER_PATH: $AIDER_PATH"
    echo "  This is normal if you haven't sourced your shell profiles yet."
    echo "  Common reasons and solutions:"
    echo "  1. Shell profiles not sourced: Run 'source ~/.bashrc' or open a new terminal"
    echo "  2. Different shell: Check ~/.profile or shell-specific config files"
    echo "  3. PATH not updated: The directory may need to be manually added to PATH"
    echo ""
    echo "  For now, using AIDER_PATH directly: $AIDER_PATH"
    AIDER_ACTUAL_PATH="$AIDER_PATH"
fi

# Test basic functionality
echo ""
echo "Testing basic functionality of aider-mcp..."
echo "Running: $AIDER_ACTUAL_PATH --help"
if timeout 3 "$AIDER_ACTUAL_PATH" --help 2>&1 | head -1 > /dev/null; then
    echo "✓ aider-mcp --help works (basic functionality confirmed)"
    # Test if it can run without errors
    if timeout 3 "$AIDER_ACTUAL_PATH" --help 2>&1 | grep -i "usage\|help\|command" > /dev/null; then
        echo "✓ Help output contains expected keywords (usage, help, command, etc.)"
        echo "  This indicates aider-mcp is functioning correctly"
    else
        echo "⚠ Help output doesn't contain expected keywords (but command runs)"
        echo "  This may be normal if aider-mcp has a different help format"
    fi
else
    echo "⚠ aider-mcp --help failed - binary may have issues"
    echo "  Trying alternative verification methods..."
    if python3 -c "import aider_mcp" 2>/dev/null; then
        echo "✓ aider-mcp is importable as Python module"
        echo "  This means the Python package is installed correctly"
    else
        echo "✗ aider-mcp is not working as expected"
        echo "  Possible issues:"
        echo "  1. Binary may be corrupted"
        echo "  2. Missing dependencies"
        echo "  3. Installation incomplete"
        echo "  Check logs: /tmp/aider-install.log"
    fi
fi

# Add to shell profile for persistence
echo "Adding AIDER_PATH and PATH configuration to shell profiles..."

# Function to update a shell profile file
update_shell_profile() {
    local profile_file="$1"
    
    if [ ! -f "$profile_file" ]; then
        echo "  ⚠ $profile_file not found, skipping"
        return
    fi
    
    echo "  Processing $profile_file..."
    
    # Backup the file
    if cp "$profile_file" "$profile_file.backup.aider" 2>/dev/null; then
        echo "    ✓ Created backup: $profile_file.backup.aider"
    else
        echo "    ⚠ Could not backup $profile_file"
    fi
    
    # Create a temporary file
    local temp_file
    temp_file=$(mktemp)
    
    # Remove existing AIDER MCP Server configuration
    # First, remove the configuration block
    # We'll use awk to remove lines between markers
    awk '
    BEGIN { in_block=0 }
    /^# AIDER MCP Server configuration/ { in_block=1; next }
    /^export AIDER_PATH=/ && in_block { next }
    /^export PATH=".*AIDER_DIR.*"/ && in_block { next }
    /^export PATH=".*aider-mcp.*"/ && in_block { next }
    /^[[:space:]]*$/ && in_block && /^[[:space:]]*$/ { next }
    { 
        if (in_block && /^[^#]/ && !/^export/) {
            in_block=0
        }
        if (!in_block) print
    }
    ' "$profile_file" > "$temp_file" 2>/dev/null || {
        # If awk fails, fall back to simpler method
        echo "    ⚠ Using simple cleanup method"
        grep -v "# AIDER MCP Server configuration" "$profile_file" | \
        grep -v "export AIDER_PATH=" | \
        grep -v "export PATH=.*AIDER_DIR" | \
        grep -v "export PATH=.*aider-mcp" > "$temp_file" 2>/dev/null || cat "$profile_file" > "$temp_file"
    }
    
    # Add new configuration
    {
        echo ""
        echo "# AIDER MCP Server configuration"
        echo "# Added by AIDER MCP Server setup script"
        echo "export AIDER_PATH=\"$AIDER_PATH\""
        # Check if AIDER_DIR needs to be added to PATH
        # We'll add a comment about it
        echo "# To add aider-mcp to PATH, uncomment the following line:"
        echo "# export PATH=\"\$AIDER_DIR:\$PATH\""
        echo ""
    } >> "$temp_file"
    
    # Replace the original file
    if mv "$temp_file" "$profile_file"; then
        echo "    ✓ Updated $profile_file"
        echo "    ⚠ Note: PATH line is commented by default"
        echo "    To enable, edit the file and remove the '#' before 'export PATH'"
    else
        echo "    ✗ Failed to update $profile_file"
        rm -f "$temp_file" 2>/dev/null || true
        return 1
    fi
    
    return 0
}

# Update both shell profiles
echo ""
echo "Updating shell profiles:"
update_shell_profile ~/.bashrc
update_shell_profile ~/.profile

echo ""
echo "✓ Shell profiles updated with AIDER_PATH configuration"
echo "  Note: The PATH export is commented by default to avoid PATH conflicts."
echo "  If 'aider-mcp' command doesn't work, edit ~/.bashrc and uncomment the PATH line."
echo "  Then run: source ~/.bashrc"

# Create log directory
echo "Creating log directory..."
sudo mkdir -p /var/log/aider-mcp
sudo chown $USER:$USER /var/log/aider-mcp
echo "✓ Log directory created: /var/log/aider-mcp"

# Create a systemd service for better management
echo "Creating systemd service for aider-mcp..."
SERVICE_FILE="/etc/systemd/system/aider-mcp.service"

# Check if service already exists and backup
if [ -f "$SERVICE_FILE" ]; then
    sudo cp "$SERVICE_FILE" "$SERVICE_FILE.backup"
    echo "⚠ Existing service file backed up"
fi

cat << EOF | sudo tee "$SERVICE_FILE" > /dev/null
[Unit]
Description=AIDER MCP Server
After=network.target
StartLimitIntervalSec=0

[Service]
Type=simple
User=$USER
Environment="AIDER_PATH=$AIDER_PATH"
ExecStart=$AIDER_PATH
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=aider-mcp

[Install]
WantedBy=multi-user.target
EOF

# Verify service file was created
if [ ! -f "$SERVICE_FILE" ]; then
    echo "✗ Error: Failed to create systemd service file."
    exit 1
fi
echo "✓ Service file created: $SERVICE_FILE"

# Verify service file content
echo "Verifying service file content..."
if sudo grep -q "ExecStart=$AIDER_PATH" "$SERVICE_FILE"; then
    echo "✓ Service file contains correct ExecStart path"
else
    echo "⚠ Warning: Service file may not have correct ExecStart path"
    echo "Service file content:"
    sudo cat "$SERVICE_FILE"
fi

# Reload systemd and enable the service
echo "Configuring systemd service..."
sudo systemctl daemon-reload
sudo systemctl enable aider-mcp.service
echo "✓ Service enabled to start on boot"

# Start the service
echo "Starting aider-mcp service..."
sudo systemctl restart aider-mcp.service

# Check if service started successfully
echo "Waiting for service to start..."
MAX_WAIT=15
for i in $(seq 1 $MAX_WAIT); do
    if systemctl is-active --quiet aider-mcp.service; then
        echo "✓ aider-mcp service is running (started in ${i}s)"
        # Get the PID to verify
        SERVICE_PID=$(systemctl show --property=MainPID --value aider-mcp.service)
        if [ "$SERVICE_PID" -gt 0 ]; then
            echo "✓ Service PID: $SERVICE_PID"
        fi
        break
    fi
    echo -n "."
    sleep 1
    if [ $i -eq $MAX_WAIT ]; then
        echo ""
        echo "✗ aider-mcp service failed to start within $MAX_WAIT seconds"
        echo "Checking service status..."
        sudo systemctl status aider-mcp.service --no-pager
        echo ""
        echo "Checking recent logs..."
        sudo journalctl -u aider-mcp.service -n 30 --no-pager
        echo ""
        echo "Troubleshooting tips:"
        echo "1. Check if $AIDER_PATH exists:"
        if [ -f "$AIDER_PATH" ]; then
            echo "   ✓ File exists"
            if [ -x "$AIDER_PATH" ]; then
                echo "   ✓ File is executable"
            else
                echo "   ✗ File is not executable - run: chmod +x \"$AIDER_PATH\""
            fi
        else
            echo "   ✗ File does not exist"
        fi
        echo "2. Check file permissions: ls -la $AIDER_PATH"
        echo "3. Check if port conflicts exist (aider-mcp may need specific ports)"
        echo "4. Try running manually: $AIDER_PATH --help"
        echo "5. Check system logs: sudo journalctl -xe | tail -50"
        echo "6. Check if dependencies are missing: ldd \"$AIDER_PATH\" 2>/dev/null || echo 'Cannot check dependencies'"
        echo ""
        echo "You can also try:"
        echo "  sudo systemctl daemon-reload"
        echo "  sudo systemctl restart aider-mcp"
        echo "  sudo systemctl status aider-mcp --no-pager -l"
        # Disable error trap before exiting to avoid double error handling
        trap - ERR
        exit 1
    fi
done

# Get service status
echo ""
echo "Service status:"
sudo systemctl status aider-mcp.service --no-pager -l | head -20

echo ""
echo "========================================="
echo "Setup complete! ✓"
echo "========================================="
echo ""
echo "AIDER MCP Server is running as a systemd service."
echo ""
echo "📋 Useful commands:"
echo "  Check status: sudo systemctl status aider-mcp"
echo "  View logs:    sudo journalctl -u aider-mcp -f"
echo "  Stop service: sudo systemctl stop aider-mcp"
echo "  Start service: sudo systemctl start aider-mcp"
echo "  Restart:      sudo systemctl restart aider-mcp"
echo ""
echo "🔍 To test the setup, run: ./test_aider_mcp.sh"
echo ""
echo "📝 Important notes about configuration:"
echo "   1. AIDER_PATH has been added to ~/.bashrc and ~/.profile"
echo "   2. The PATH export is COMMENTED by default in your shell profiles"
echo "      This prevents potential PATH conflicts with other software."
echo ""
echo "   If 'aider-mcp' command doesn't work:"
echo "   1. Edit ~/.bashrc and remove the '#' before 'export PATH=\"\$AIDER_DIR:\$PATH\"'"
echo "   2. Run: source ~/.bashrc"
echo "   Or open a new terminal window after making the change."
echo ""
echo "   You can also use the full path directly: $AIDER_PATH"
echo ""
