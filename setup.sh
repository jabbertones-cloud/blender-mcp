#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════════
# OpenClaw Blender MCP - Setup Script
# ═══════════════════════════════════════════════════════════════════════════════
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [ -x "$SCRIPT_DIR/.venv/bin/python3.12" ]; then
    PYTHON_BIN="$SCRIPT_DIR/.venv/bin/python3.12"
elif [ -x "$SCRIPT_DIR/.venv/bin/python3" ]; then
    PYTHON_BIN="$SCRIPT_DIR/.venv/bin/python3"
elif command -v python3 &>/dev/null; then
    PYTHON_BIN="$(command -v python3)"
else
    echo -e "${RED}python3 not found. Install Python first.${NC}"
    exit 1
fi
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "═══════════════════════════════════════════════════════════"
echo "  OpenClaw Blender MCP - Setup"
echo "═══════════════════════════════════════════════════════════"

# 1. Install Python dependencies
echo -e "\n${YELLOW}[1/4] Installing Python dependencies...${NC}"
"$PYTHON_BIN" -m pip install mcp pydantic httpx 2>/dev/null || "$PYTHON_BIN" -m pip install --break-system-packages mcp pydantic httpx

# 2. Find Blender
echo -e "\n${YELLOW}[2/4] Locating Blender...${NC}"
BLENDER_APP=""
if [ -d "/Applications/Blender.app" ]; then
    BLENDER_APP="/Applications/Blender.app"
    BLENDER_BIN="/Applications/Blender.app/Contents/MacOS/Blender"
elif command -v blender &>/dev/null; then
    BLENDER_BIN="$(which blender)"
    BLENDER_APP="$BLENDER_BIN"
else
    echo -e "${RED}Blender not found! Please install Blender first.${NC}"
    exit 1
fi
echo -e "${GREEN}Found Blender: $BLENDER_APP${NC}"

# 3. Install addon
echo -e "\n${YELLOW}[3/4] Installing Blender addon...${NC}"
ADDON_SRC="$SCRIPT_DIR/blender_addon/openclaw_blender_bridge.py"
# Detect Blender version for addon path
BLENDER_VERSION=$("$BLENDER_BIN" --version 2>/dev/null | head -1 | grep -oE '[0-9]+\.[0-9]+' | head -1)
if [ -n "$BLENDER_VERSION" ]; then
    ADDON_DIR="$HOME/Library/Application Support/Blender/$BLENDER_VERSION/scripts/addons"
    mkdir -p "$ADDON_DIR"
    cp "$ADDON_SRC" "$ADDON_DIR/openclaw_blender_bridge.py"
    echo -e "${GREEN}Addon installed to: $ADDON_DIR${NC}"
else
    echo -e "${YELLOW}Could not detect version. Manual install needed:${NC}"
    echo "  Blender > Edit > Preferences > Add-ons > Install > $ADDON_SRC"
fi

# 4. Write Claude config snippet
echo -e "\n${YELLOW}[4/4] Generating Claude MCP config...${NC}"
cat > "$SCRIPT_DIR/claude_mcp_config.json" <<EOF
{
  "mcpServers": {
    "blender": {
      "command": "$PYTHON_BIN",
      "args": ["$SCRIPT_DIR/server/blender_mcp_server.py"],
      "env": {}
    },
    "blender-2": {
      "command": "$PYTHON_BIN",
      "args": ["$SCRIPT_DIR/server/blender_mcp_server.py"],
      "env": {
        "BLENDER_PORT": "9877",
        "OPENCLAW_PORT": "9877"
      }
    },
    "blender-3": {
      "command": "$PYTHON_BIN",
      "args": ["$SCRIPT_DIR/server/blender_mcp_server.py"],
      "env": {
        "BLENDER_PORT": "9878",
        "OPENCLAW_PORT": "9878"
      }
    }
  }
}
EOF
echo -e "${GREEN}Config written to: $SCRIPT_DIR/claude_mcp_config.json${NC}"

echo ""
echo "═══════════════════════════════════════════════════════════"
echo -e "${GREEN}  Setup complete!${NC}"
echo "═══════════════════════════════════════════════════════════"
echo ""
echo "Next steps:"
echo "  1. Open Blender"
echo "  2. The addon auto-starts (or: View > Sidebar > OpenClaw tab > Start)"
echo "  3. Add the config to your Claude settings:"
echo "     cat $SCRIPT_DIR/claude_mcp_config.json"
echo ""
echo "Quick test:"
echo "  python3 $SCRIPT_DIR/tests/qa_runner.py"
echo "  python3 $SCRIPT_DIR/scripts/blender_healthcheck.py"
echo ""
