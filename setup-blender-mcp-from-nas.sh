#!/bin/bash
# setup-blender-mcp-from-nas.sh
# Run this on the M3 Max (or any new machine) AFTER cloning the blender-mcp repo.
# It mounts the Synology NAS over SMB and creates symlinks for all the heavy
# directories that live on NAS instead of in git.
#
# Usage:
#   cd ~/claw-repos/blender-mcp        # or wherever you cloned it
#   bash setup-blender-mcp-from-nas.sh
#
# Prereqs:
#   - macOS Finder logged in to NAS at smb://192.168.1.164/home at least once
#     (so credentials are saved to Keychain)
#   - SMAT account has read/write on the NAS home share
#   - You have already `git clone`'d the repo

set -u

NAS_HOST=192.168.1.164
NAS_USER=SMAT
NAS_SHARE=home
NAS_MOUNT=/Volumes/home
NAS_PATH="$NAS_MOUNT/blender-mcp-shared"

# Resolve repo root (script can be run from anywhere inside the repo)
REPO=$(cd "$(dirname "$0")" && pwd)
if [ ! -f "$REPO/README.md" ] || ! grep -q "blender" "$REPO/README.md" 2>/dev/null; then
  echo "ERROR: This doesn't look like the blender-mcp repo. Run from repo root."
  exit 1
fi

# 1. Mount the NAS if not already mounted
if [ ! -d "$NAS_MOUNT" ] || ! mount | grep -q "$NAS_HOST.*$NAS_SHARE"; then
  echo "Mounting NAS at $NAS_MOUNT ..."
  mkdir -p "$NAS_MOUNT" 2>/dev/null
  open "smb://${NAS_USER}@${NAS_HOST}/${NAS_SHARE}"
  echo "A Finder window should have opened to authenticate. Complete the login,"
  echo "then re-run this script. (If credentials are saved, mount is silent.)"

  # Wait briefly for mount to come up
  for i in 1 2 3 4 5 6 7 8 9 10; do
    sleep 2
    if mount | grep -q "$NAS_HOST.*$NAS_SHARE"; then break; fi
  done
fi

if ! mount | grep -q "$NAS_HOST.*$NAS_SHARE"; then
  echo "ERROR: NAS share is not mounted. Open Finder -> Go -> Connect to Server -> smb://$NAS_HOST/$NAS_SHARE"
  exit 1
fi

# 2. Verify the shared directory exists on NAS
if [ ! -d "$NAS_PATH" ]; then
  echo "ERROR: $NAS_PATH does not exist on the NAS."
  echo "Has the migration been run from the source machine yet?"
  exit 1
fi

# 3. Create symlinks for every directory that lives on NAS
DIRS=(renders exports models assets bridge_renders portfolio_curated_best portfolio_forensic_v4 data)

echo "Creating symlinks under $REPO ..."
for d in "${DIRS[@]}"; do
  src="$NAS_PATH/$d"
  dst="$REPO/$d"

  if [ ! -d "$src" ]; then
    echo "  skip $d (not on NAS)"
    continue
  fi

  if [ -L "$dst" ]; then
    # Already a symlink - check if it points to the right place
    target=$(readlink "$dst")
    if [ "$target" = "$src" ]; then
      echo "  ok   $d (symlink correct)"
      continue
    fi
    echo "  fix  $d (symlink wrong, re-pointing)"
    rm "$dst"
  elif [ -d "$dst" ]; then
    # A real directory exists locally - safer to leave alone
    echo "  WARN $d already exists locally (not a symlink) - leaving as-is."
    echo "       To replace with NAS symlink: rm -rf $dst && ln -s '$src' '$dst'"
    continue
  fi

  ln -s "$src" "$dst"
  echo "  link $d -> $src"
done

echo ""
echo "Done. Verify:"
echo "  ls -la $REPO | grep ^l"
echo ""
echo "If you ever lose the NAS mount, your symlinks will appear broken until you remount."
