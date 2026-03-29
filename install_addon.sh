#!/bin/bash
# Install OpenClaw Blender Bridge addon to the local Blender addons directory
# Run: bash install_addon.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ADDON_SRC="$SCRIPT_DIR/blender_addon/openclaw_blender_bridge.py"

# Find Blender version
BLENDER_BIN="/Applications/Blender.app/Contents/MacOS/Blender"
if [ ! -f "$BLENDER_BIN" ]; then
    echo "❌ Blender not found at /Applications/Blender.app"
    echo "Looking elsewhere..."
    BLENDER_BIN=$(mdfind "kMDItemFSName == 'Blender.app'" 2>/dev/null | head -1)
    if [ -n "$BLENDER_BIN" ]; then
        BLENDER_BIN="$BLENDER_BIN/Contents/MacOS/Blender"
    else
        echo "❌ Cannot find Blender. Install it first or copy the addon manually."
        exit 1
    fi
fi

BLENDER_VERSION=$("$BLENDER_BIN" --version 2>/dev/null | head -1 | grep -oE '[0-9]+\.[0-9]+' | head -1)
echo "✅ Found Blender $BLENDER_VERSION"

# Install to both possible addon locations
for ADDON_DIR in \
    "$HOME/Library/Application Support/Blender/$BLENDER_VERSION/scripts/addons" \
    "$HOME/Library/Application Support/Blender/$BLENDER_VERSION/scripts/addons_contrib"; do
    
    mkdir -p "$ADDON_DIR" 2>/dev/null || true
    if [ -d "$ADDON_DIR" ]; then
        cp "$ADDON_SRC" "$ADDON_DIR/openclaw_blender_bridge.py"
        echo "✅ Addon installed to: $ADDON_DIR"
        break
    fi
done

echo ""
echo "📋 Next steps:"
echo "  1. Open Blender"
echo "  2. Edit > Preferences > Add-ons"
echo "  3. Search for 'OpenClaw'"
echo "  4. Enable the addon (checkbox)"
echo "  5. The bridge auto-starts on port 9876"
echo ""
echo "Or the addon auto-registers on file load if installed correctly."
echo ""
echo "To verify: look for 'OpenClaw' tab in 3D Viewport sidebar (N key)"
