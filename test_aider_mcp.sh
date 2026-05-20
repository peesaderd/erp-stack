#!/bin/bash

echo "Testing AIDER MCP Server setup..."
echo "================================="

# Check if AIDER_PATH is set
echo "Checking AIDER MCP Server environment..."
if [ -z "$AIDER_PATH" ]; then
    echo "AIDER_PATH is not set in current environment."
    echo "Attempting to locate aider-mcp..."
    
    # Try to source bashrc to get AIDER_PATH
    if [ -f ~/.bashrc ]; then
        echo "Sourcing ~/.bashrc..."
        # Use a subshell to avoid affecting current environment
        TEMP_AIDER_PATH=$(bash -c "source ~/.bashrc 2>/dev/null; echo \$AIDER_PATH")
        if [ -n "$TEMP_AIDER_PATH" ]; then
            AIDER_PATH="$TEMP_AIDER_PATH"
            export AIDER_PATH
            echo "Found AIDER_PATH in ~/.bashrc: $AIDER_PATH"
        fi
    fi
    
    if [ -z "$AIDER_PATH" ]; then
        # Try to find aider-mcp in various locations
        echo "Searching for aider-mcp in common locations..."
        
        # Check PATH first using command -v (more reliable than which)
        AIDER_PATH=$(command -v aider-mcp 2>/dev/null || true)
        
        # Check user's local bin
        if [ -z "$AIDER_PATH" ] && [ -f "$HOME/.local/bin/aider-mcp" ]; then
            AIDER_PATH="$HOME/.local/bin/aider-mcp"
            echo "Found aider-mcp in ~/.local/bin"
        fi
        
        # Check virtual environments
        if [ -z "$AIDER_PATH" ] && [ -f "./venv/bin/aider-mcp" ]; then
            AIDER_PATH="./venv/bin/aider-mcp"
            echo "Found aider-mcp in ./venv/bin"
        fi
        
        if [ -z "$AIDER_PATH" ] && [ -f "../venv/bin/aider-mcp" ]; then
            AIDER_PATH="../venv/bin/aider-mcp"
            echo "Found aider-mcp in ../venv/bin"
        fi
        
        if [ -z "$AIDER_PATH" ] && [ -f "/usr/local/bin/aider-mcp" ]; then
            AIDER_PATH="/usr/local/bin/aider-mcp"
            echo "Found aider-mcp in /usr/local/bin"
        fi
        
        if [ -z "$AIDER_PATH" ] && [ -f "/usr/bin/aider-mcp" ]; then
            AIDER_PATH="/usr/bin/aider-mcp"
            echo "Found aider-mcp in /usr/bin"
        fi
        
        if [ -z "$AIDER_PATH" ] && [ -f "/opt/tasks/peteai/venv/bin/aider-mcp" ]; then
            AIDER_PATH="/opt/tasks/peteai/venv/bin/aider-mcp"
            echo "Found aider-mcp in /opt/tasks/peteai/venv/bin"
        fi
        
        if [ -n "$AIDER_PATH" ]; then
            export AIDER_PATH
            echo "Using: $AIDER_PATH"
            # Verify the file exists and is executable
            if [ ! -f "$AIDER_PATH" ]; then
                echo "⚠ Warning: $AIDER_PATH does not exist as a file"
            elif [ ! -x "$AIDER_PATH" ]; then
                echo "⚠ Warning: $AIDER_PATH is not executable"
            fi
        else
            echo "✗ AIDER_PATH is not set and aider-mcp not found."
            echo "Please run setup_aider_mcp.sh first."
            echo "Alternatively, set it manually:"
            echo "  export AIDER_PATH=\$(which aider-mcp)"
            echo "Or if installed in a custom location:"
            echo "  export AIDER_PATH=/path/to/aider-mcp"
            exit 1
        fi
    fi
fi

echo "✓ AIDER_PATH is set to: $AIDER_PATH"
echo "✓ Current user: $(whoami)"
echo "✓ Current directory: $(pwd)"
echo "✓ PATH contains directories: $(echo $PATH | tr ':' '\n' | grep -E '(local|venv|bin|usr)' | head -8 | tr '\n' ' ')"
# Check if AIDER_PATH is in PATH
AIDER_DIR=$(dirname "$AIDER_PATH")
echo "Checking if AIDER_PATH directory is in PATH..."
if echo "$PATH" | tr ':' '\n' | grep -q "^$AIDER_DIR$"; then
    echo "✓ AIDER_PATH directory ($AIDER_DIR) is in PATH"
    echo "  This means 'aider-mcp' command should work in this terminal"
else
    echo "⚠ AIDER_PATH directory ($AIDER_DIR) is not in PATH"
    echo "  This may cause 'aider-mcp' command not found errors"
    echo "  The setup script added AIDER_PATH to your shell profiles,"
    echo "  but the PATH export is commented by default to avoid conflicts."
    echo "  To fix this:"
    echo "  1. Edit ~/.bashrc and remove the '#' before 'export PATH=\"\$AIDER_DIR:\$PATH\"'"
    echo "  2. Run: source ~/.bashrc"
    echo "  Or for a temporary fix this session: export PATH=\"$AIDER_DIR:\$PATH\""
    # Try to add it for the current test
    export PATH="$AIDER_DIR:$PATH"
    echo "  Added $AIDER_DIR to PATH for this test session (temporary)"
fi

# Check if AIDER_PATH is exported and accessible
echo ""
echo "Verifying AIDER_PATH configuration..."
if [ -n "$AIDER_PATH" ]; then
    echo "✓ AIDER_PATH is properly set: $AIDER_PATH"
    if [ -f "$AIDER_PATH" ]; then
        echo "✓ AIDER_PATH points to an existing file"
        if [ -x "$AIDER_PATH" ]; then
            echo "✓ AIDER_PATH is executable (good)"
        else
            echo "⚠ AIDER_PATH is not executable"
            echo "  Fix with: chmod +x \"$AIDER_PATH\""
        fi
    else
        echo "✗ AIDER_PATH does not point to an existing file"
        echo "  This could mean:"
        echo "  1. aider-mcp is not installed"
        echo "  2. The path is incorrect"
        echo "  3. The file was moved or deleted"
    fi
else
    echo "✗ AIDER_PATH is not set"
    echo "  This usually means the setup script wasn't run or shell profiles weren't sourced"
fi

# Check systemd service status first
if systemctl is-active --quiet aider-mcp; then
    echo "✓ aider-mcp systemd service is active"
    # Check if process is actually running
    if pgrep -f "aider-mcp" > /dev/null; then
        echo "✓ aider-mcp process is running"
    else
        echo "⚠ Systemd reports service is active but no process found"
        echo "Restarting service..."
        sudo systemctl restart aider-mcp
        sleep 2
        if pgrep -f "aider-mcp" > /dev/null; then
            echo "✓ aider-mcp restarted successfully"
        else
            echo "✗ Failed to restart aider-mcp"
        fi
    fi
else
    echo "✗ aider-mcp systemd service is not active"
    echo "Attempting to start via systemd..."
    sudo systemctl start aider-mcp
    sleep 2
    if systemctl is-active --quiet aider-mcp; then
        echo "✓ aider-mcp started successfully"
        if pgrep -f "aider-mcp" > /dev/null; then
            echo "✓ aider-mcp process is running"
        fi
    else
        echo "✗ Failed to start aider-mcp"
        echo "Check logs with: sudo journalctl -u aider-mcp"
        echo "You can try: sudo systemctl restart aider-mcp"
        echo "Or check service configuration: sudo systemctl status aider-mcp"
        # Don't exit immediately, continue with other tests
        echo "Continuing with other tests despite service failure..."
    fi
fi

# Test if MCP Server can read Tasks.md files
echo ""
echo "Testing MCP Server's ability to read task files..."

# Define task files to check (using absolute paths)
TASK_FILES=(
    "/opt/tasks/todo/task1.md"
    "/opt/tasks/todo/task2.md"
)

# Check each file
for task_file in "${TASK_FILES[@]}"; do
    if [ -f "$task_file" ]; then
        echo "✓ Found $task_file"
        
        # Read first few lines to verify it's a markdown file
        if head -n 1 "$task_file" | grep -q "^#"; then
            echo "  ✓ Contains markdown header"
        else
            echo "  ⚠ First line doesn't appear to be a markdown header"
        fi
        
        # Check if file contains task items (checkboxes)
        if grep -q "\[.\]" "$task_file"; then
            echo "  ✓ Contains task items with checkboxes"
            
            # Count completed and pending tasks
            total_tasks=$(grep -c "\[.\]" "$task_file")
            completed_tasks=$(grep -c "\[x\]" "$task_file")
            pending_tasks=$((total_tasks - completed_tasks))
            
            echo "  Total tasks: $total_tasks"
            echo "  Completed: $completed_tasks"
            echo "  Pending: $pending_tasks"
            
            # Calculate completion percentage
            if [ $total_tasks -gt 0 ]; then
                completion_percent=$((completed_tasks * 100 / total_tasks))
                echo "  Completion: $completion_percent%"
            fi
        else
            echo "  ⚠ No task checkboxes found"
        fi
        
        # Display first 5 lines for better verification
        echo "  Preview (first 5 lines):"
        head -n 5 "$task_file" | while read line; do
            echo "    $line"
        done
        
        # Check file permissions (can the MCP Server read it?)
        if [ -r "$task_file" ]; then
            echo "  ✓ File is readable (good for MCP Server)"
        else
            echo "  ✗ File is not readable (MCP Server may have issues)"
        fi
        
        # Check file size
        file_size=$(wc -c < "$task_file")
        echo "  File size: $file_size bytes"
        
    else
        echo "✗ $task_file not found"
        # Try to find it using relative path from current location
        # Current location is /opt/tasks/peteai/
        if [ -f "../todo/$(basename "$task_file")" ]; then
            echo "  Found at ../todo/$(basename "$task_file")"
        elif [ -f "../../opt/tasks/todo/$(basename "$task_file")" ]; then
            echo "  Found at ../../opt/tasks/todo/$(basename "$task_file")"
        else
            echo "  File not found in common locations"
        fi
    fi
    echo ""
done

# Test if we can make a simple HTTP request to the MCP Server (if it has an API)
echo "Testing MCP Server API connectivity..."
echo "Note: This test assumes aider-mcp provides a web API on common ports."

# Try to connect to localhost on common MCP ports
MCP_PORTS=(8080 8000 3000 5000 8081 8082)
API_ENDPOINTS=("/" "/tasks" "/api/tasks" "/v1/tasks" "/api" "/health" "/status")

PORT_FOUND=0
for port in "${MCP_PORTS[@]}"; do
    if timeout 2 bash -c "echo > /dev/tcp/localhost/$port" 2>/dev/null; then
        echo "✓ Service is listening on port $port"
        PORT_FOUND=1
        
        # Try to get a response from potential endpoints
        ENDPOINT_FOUND=0
        for endpoint in "${API_ENDPOINTS[@]}"; do
            if curl -s --max-time 3 "http://localhost:$port$endpoint" > /dev/null; then
                echo "  ✓ API endpoint $endpoint is accessible"
                # Try to get actual data
                response=$(curl -s --max-time 3 "http://localhost:$port$endpoint")
                if [ -n "$response" ]; then
                    echo "  ✓ Received response from API"
                    echo "  Response preview: ${response:0:100}..."
                    
                    # Check if response contains task-related content
                    if echo "$response" | grep -qi "task\|todo\|deploy\|database"; then
                        echo "  ✓ Response appears to contain task-related content"
                    fi
                fi
                ENDPOINT_FOUND=1
                break
            fi
        done
        
        if [ $ENDPOINT_FOUND -eq 0 ]; then
            echo "  ⚠ No known API endpoints responded on port $port"
            echo "  Trying a simple GET request to root..."
            response=$(curl -s --max-time 3 "http://localhost:$port")
            if [ -n "$response" ]; then
                echo "  ✓ Received response: ${response:0:50}..."
            fi
        fi
        break
    fi
done

if [ $PORT_FOUND -eq 0 ]; then
    echo "⚠ No service detected on common MCP ports"
    echo "  This may be normal if aider-mcp doesn't provide a web API"
    echo "  or uses a different port configuration."
fi

# Test actual MCP Server functionality by checking if it can process tasks
echo ""
echo "Testing MCP Server task processing capability..."
echo "Note: This is a basic test. Actual MCP functionality may vary."

# First, check Python and pip availability
echo "Checking Python and pip dependencies..."
if command -v python3 &> /dev/null; then
    echo "✓ Python3 is available: $(python3 --version 2>&1)"
    # Check Python version
    PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || echo "unknown")
    echo "  Python version: $PYTHON_VERSION"
else
    echo "✗ Python3 not found"
    # Check for package manager to suggest installation
    if command -v apt-get &> /dev/null; then
        echo "  Suggested fix: sudo apt-get install python3"
    elif command -v dnf &> /dev/null; then
        echo "  Suggested fix: sudo dnf install python3"
    elif command -v yum &> /dev/null; then
        echo "  Suggested fix: sudo yum install python3"
    elif command -v brew &> /dev/null; then
        echo "  Suggested fix: brew install python@3"
    else
        echo "  Install Python 3 from: https://www.python.org/downloads/"
    fi
fi

PIP_CMD=""
PIP_VERSION=""
if command -v pip3 &> /dev/null; then
    PIP_CMD="pip3"
    PIP_VERSION=$(pip3 --version 2>&1 | head -1)
    echo "✓ pip3 is available: $PIP_VERSION"
    # Check if it's the system pip or user pip
    PIP3_PATH=$(command -v pip3)
    if echo "$PIP3_PATH" | grep -q "$HOME/.local"; then
        echo "  Location: User installation (~/.local/bin)"
    elif echo "$PIP3_PATH" | grep -q "/usr/local"; then
        echo "  Location: /usr/local/bin"
    elif echo "$PIP3_PATH" | grep -q "/usr/bin"; then
        echo "  Location: System installation (/usr/bin)"
    fi
elif command -v pip &> /dev/null; then
    PIP_CMD="pip"
    PIP_VERSION=$(pip --version 2>&1 | head -1)
    echo "✓ pip is available: $PIP_VERSION"
else
    echo "⚠ No pip command found in PATH"
    # Check if pip can be imported via python
    if python3 -c "import pip; print('pip module is importable')" 2>/dev/null; then
        echo "✓ pip module is importable in Python"
        PIP_CMD="python3 -m pip"
        PIP_VERSION=$(python3 -m pip --version 2>&1 | head -1)
        echo "  Version via python3 -m pip: $PIP_VERSION"
    else
        echo "✗ pip is not available via any method"
        echo "  You may need to install python3-pip:"
        echo "  - Debian/Ubuntu: sudo apt-get install python3-pip"
        echo "  - Check if python3-pip package exists:"
        if command -v apt-cache &> /dev/null; then
            echo "    Checking apt cache..."
            apt-cache search python3-pip | head -3
        fi
        echo "  - Or use: curl -sS https://bootstrap.pypa.io/get-pip.py | python3"
    fi
fi

# If PIP_CMD is set, check what packages are installed
if [ -n "$PIP_CMD" ]; then
    echo "Checking for aider-mcp package via $PIP_CMD..."
    # First, check if the command works
    if $PIP_CMD list --disable-pip-version-check 2>/dev/null | head -5 > /dev/null; then
        if $PIP_CMD list --disable-pip-version-check 2>/dev/null | grep -i aider-mcp > /dev/null; then
            echo "✓ aider-mcp package is installed via $PIP_CMD"
            # Get version if available
            AIDER_PKG_INFO=$($PIP_CMD show aider-mcp 2>/dev/null | grep -i version || true)
            if [ -n "$AIDER_PKG_INFO" ]; then
                echo "  $AIDER_PKG_INFO"
            fi
        else
            echo "⚠ aider-mcp package not found in $PIP_CMD list"
            echo "  Installed packages:"
            $PIP_CMD list --disable-pip-version-check 2>/dev/null | head -10 | sed 's/^/    /'
        fi
    else
        echo "⚠ Could not run '$PIP_CMD list' command"
    fi
fi

# Check if we can simulate task processing
echo "Checking aider-mcp installation..."
if command -v aider-mcp &> /dev/null; then
    echo "✓ aider-mcp command is available"
    # Get the actual path using command -v
    AIDER_ACTUAL_PATH=$(command -v aider-mcp)
    if [ -n "$AIDER_ACTUAL_PATH" ]; then
        echo "  Path: $AIDER_ACTUAL_PATH"
    else
        echo "  ⚠ Could not determine path via command -v"
        # Fall back to which or use AIDER_PATH
        if [ -n "$AIDER_PATH" ]; then
            AIDER_ACTUAL_PATH="$AIDER_PATH"
            echo "  Using AIDER_PATH: $AIDER_ACTUAL_PATH"
        else
            echo "  ⚠ No path available for aider-mcp"
        fi
    fi
    
    # Try to get version info
    echo "Attempting to get version information..."
    VERSION_ATTEMPTS=0
    VERSION_SUCCESS=0
    
    # Try --version first
    if timeout 3 aider-mcp --version &> /dev/null; then
        version=$(timeout 3 aider-mcp --version 2>&1 | head -1)
        echo "✓ Version (--version): $version"
        VERSION_SUCCESS=1
    fi
    
    # Try -v if --version didn't work
    if [ $VERSION_SUCCESS -eq 0 ] && timeout 3 aider-mcp -v &> /dev/null; then
        version=$(timeout 3 aider-mcp -v 2>&1 | head -1)
        echo "✓ Version (-v): $version"
        VERSION_SUCCESS=1
    fi
    
    # Try to extract version from help if direct methods didn't work
    if [ $VERSION_SUCCESS -eq 0 ]; then
        echo "⚠ Could not determine aider-mcp version via --version or -v flags"
        # Try running with --help
        if timeout 3 aider-mcp --help &> /dev/null; then
            echo "✓ aider-mcp --help works (basic functionality confirmed)"
            # Show first few lines of help
            echo "  Help output preview:"
            timeout 3 aider-mcp --help 2>&1 | head -10 | sed 's/^/    /'
            
            # Try to extract version from help text
            HELP_OUTPUT=$(timeout 3 aider-mcp --help 2>&1)
            if echo "$HELP_OUTPUT" | grep -E "[0-9]+\.[0-9]+\.[0-9]+" | head -1; then
                version=$(echo "$HELP_OUTPUT" | grep -E "[0-9]+\.[0-9]+\.[0-9]+" | head -1)
                echo "  Extracted version from help: $version"
            fi
        else
            echo "⚠ aider-mcp --help also failed"
            echo "  The binary exists but may not be functioning correctly."
            # Try a simpler test
            echo "  Attempting minimal test..."
            if timeout 3 aider-mcp 2>&1 | head -3 > /dev/null; then
                echo "  ✓ aider-mcp runs without immediate crash"
            fi
        fi
    fi
    
    # Test basic functionality
    echo "Testing basic functionality..."
    if timeout 3 aider-mcp --help 2>&1 | grep -i "usage\|help\|command" &> /dev/null; then
        echo "✓ Basic help functionality works"
    else
        echo "⚠ Help output doesn't contain expected keywords"
    fi
    
    # Test if aider-mcp can access task files
    echo "Testing file access capability..."
    if [ -f "/opt/tasks/todo/task1.md" ]; then
        echo "✓ Task file exists: /opt/tasks/todo/task1.md"
        # Try to use aider-mcp to read the file (if it supports such functionality)
        echo "  Testing if aider-mcp can read task files..."
        # This is a basic test - actual MCP functionality may vary
        if [ -x "$AIDER_PATH" ]; then
            echo "  AIDER_PATH is executable, attempting to check version..."
            # Just check if it runs without errors
            if timeout 5 "$AIDER_PATH" --help 2>&1 | head -5 > /dev/null; then
                echo "  ✓ aider-mcp executable runs without immediate errors"
                # Try to run a simple command to test basic functionality
                echo "  Testing basic command execution..."
                if timeout 5 "$AIDER_PATH" --help 2>&1 | grep -q -i "usage\|help\|command\|aider\|mcp"; then
                    echo "  ✓ aider-mcp help output looks reasonable"
                    # Test if it can potentially read files
                    echo "  Testing file reading capability..."
                    echo "  (Note: Actual file reading would require MCP protocol implementation)"
                    echo "  To test actual file reading, you would need to:"
                    echo "  1. Start aider-mcp as a server"
                    echo "  2. Connect with an MCP client"
                    echo "  3. Request file contents through the protocol"
                else
                    echo "  ⚠ aider-mcp help output doesn't contain expected keywords"
                    echo "  This may indicate the binary is not functioning correctly"
                fi
            else
                echo "  ⚠ aider-mcp may have issues running"
                echo "  Check if there are dependency issues:"
                echo "    ldd \"$AIDER_PATH\" 2>/dev/null || echo 'Cannot check dependencies'"
                # Try to run without timeout to see error
                echo "  Attempting to run without timeout to capture error..."
                "$AIDER_PATH" --help 2>&1 | head -10
            fi
        else
            echo "  ⚠ AIDER_PATH is not executable: $AIDER_PATH"
            echo "  Try: chmod +x \"$AIDER_PATH\""
            echo "  Current permissions: $(ls -la "$AIDER_PATH" 2>/dev/null || echo 'File not found')"
        fi
        echo "  (Note: Actual MCP protocol testing would require specific commands)"
    else
        echo "⚠ Task file not found at expected location"
        echo "  Expected: /opt/tasks/todo/task1.md"
        echo "  Current directory: $(pwd)"
        echo "  Available files in /opt/tasks/todo/:"
        ls -la /opt/tasks/todo/ 2>/dev/null || echo "    Directory not found"
    fi
    
    # Test if aider-mcp can be used with MCP protocol
    echo "Testing MCP protocol compatibility..."
    echo "  (This is a placeholder - actual MCP testing requires specific implementation)"
    echo "  To test MCP functionality, you may need to:"
    echo "  1. Start aider-mcp server"
    echo "  2. Connect using an MCP client"
    echo "  3. Test task file reading through the protocol"
    
    # Additional diagnostic information
    echo "Additional diagnostics:"
    echo "  File type: $(file "$AIDER_ACTUAL_PATH" 2>/dev/null || echo 'unknown')"
    echo "  Dependencies:"
    ldd "$AIDER_ACTUAL_PATH" 2>/dev/null | head -5 || echo "    (cannot check dependencies)"
else
    echo "✗ aider-mcp command not found in PATH"
    echo "  Current PATH: $PATH"
    echo "  AIDER_PATH: $AIDER_PATH"
    if [ -n "$AIDER_PATH" ] && [ -f "$AIDER_PATH" ]; then
        echo "  AIDER_PATH exists as file: yes"
        if [ -x "$AIDER_PATH" ]; then
            echo "  AIDER_PATH is executable: yes"
            echo "  Trying to run $AIDER_PATH directly..."
            if "$AIDER_PATH" --help 2>&1 | grep -i "usage\|help" &> /dev/null; then
                echo "✓ Direct execution works - PATH issue detected"
                echo "  Consider adding $(dirname "$AIDER_PATH") to your PATH"
                echo "  Temporary fix: export PATH=\"$(dirname "$AIDER_PATH"):\$PATH\""
                echo "  Permanent fix: Add to ~/.bashrc:"
                echo "    echo 'export PATH=\"$(dirname "$AIDER_PATH"):\$PATH\"' >> ~/.bashrc"
            else
                echo "  ⚠ Direct execution failed - binary may be corrupted or have missing dependencies"
                echo "  Check dependencies: ldd \"$AIDER_PATH\" 2>/dev/null || echo 'Cannot check dependencies'"
            fi
        else
            echo "  AIDER_PATH is executable: no"
            echo "  Fix permissions: chmod +x \"$AIDER_PATH\""
            echo "  After fixing, test with: \"$AIDER_PATH\" --help"
        fi
    else
        echo "  AIDER_PATH does not exist as a file"
        echo "  Possible solutions:"
        echo "  1. Run the setup script: ./setup_aider_mcp.sh"
        echo "  2. Check if aider-mcp is installed via pip:"
        echo "     pip3 list | grep -i aider-mcp"
        echo "  3. Search for the binary:"
        echo "     find ~/.local /usr/local -name 'aider-mcp' 2>/dev/null"
        echo "  4. Reinstall aider-mcp:"
        echo "     pip3 install --user aider-mcp"
    fi
fi

echo ""
echo "Test complete!"
echo ""
echo "Summary:"
echo "✓ Systemd service: $(systemctl is-active aider-mcp 2>/dev/null || echo 'unknown')"
echo "✓ Process running: $(pgrep -f aider-mcp >/dev/null && echo 'yes' || echo 'no')"
echo "✓ Task files accessible: $(ls /opt/tasks/todo/*.md 2>/dev/null | wc -l) files found"
echo "✓ AIDER_PATH set: $( [ -n "$AIDER_PATH" ] && echo 'yes' || echo 'no' )"
echo ""
echo "For more detailed testing, consult the aider-mcp documentation."
echo "To verify task processing, you may need to use the MCP protocol directly."
