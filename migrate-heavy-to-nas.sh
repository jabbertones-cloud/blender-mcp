#!/bin/bash
# migrate-heavy-to-nas.sh
# One-time migration: copy this repo's 8 heavy directories up to the NAS, verify
# they made it intact, then offer to delete the local copies so setup-blender-mcp-from-nas.sh
# can replace them with symlinks.
#
# Pairs with setup-blender-mcp-from-nas.sh — run THIS first, that one second.
#
# Reads ~/claw-architect/.env for NAS_SMB_* / NAS_MOUNT_POINT — same as the setup script.

set -u

# -- Load NAS_* from ~/claw-architect/.env ------------------------------------
ENV_FILE="$HOME/claw-architect/.env"
if [ -f "$ENV_FILE" ]; then
  while IFS= read -r line; do
    case "$line" in
      NAS_SMB_*=*|NAS_MOUNT_POINT=*|NAS_PATH_REDIRECT=*)
        export "${line%%=*}"="$(printf '%s' "${line#*=}" | sed -E 's/^"(.*)"$/\1/')"
        ;;
    esac
  done < <(grep -E '^(NAS_SMB_|NAS_MOUNT_POINT|NAS_PATH_REDIRECT)' "$ENV_FILE")
fi

NAS_HOST="${NAS_SMB_HOST:-192.168.1.164}"
NAS_MOUNT="${NAS_MOUNT_POINT:-/Volumes/homes}"
NAS_PATH="$NAS_MOUNT/blender-mcp-shared"
FALLBACK_MOUNT="$HOME/.claw-architect/nas-smb-home"

REPO=$(cd "$(dirname "$0")" && pwd)
DIRS=(renders exports models assets bridge_renders portfolio_curated_best portfolio_forensic_v4 data)

# -- Check mount; if neither path is mounted, ask user to run nas:mount:home --
if ! mount | grep -q "$NAS_HOST.*on $NAS_MOUNT"; then
  if mount | grep -q "$NAS_HOST.*on $FALLBACK_MOUNT"; then
    NAS_MOUNT="$FALLBACK_MOUNT"; NAS_PATH="$NAS_MOUNT/blender-mcp-shared"
  else
    echo "NAS not mounted. Run first:"
    echo "  cd ~/claw-architect && npm run nas:mount:home"
    echo "  (or: bash setup-blender-mcp-from-nas.sh — it auto-mounts then exits)"
    exit 1
  fi
fi
echo "NAS mounted at $NAS_MOUNT"

mkdir -p "$NAS_PATH" || { echo "ERROR: cannot mkdir $NAS_PATH"; exit 1; }

# -- Plan ---------------------------------------------------------------------
echo ""
echo "Migration plan — $REPO -> $NAS_PATH/"
total=0
declare -a plan
for d in "${DIRS[@]}"; do
  src="$REPO/$d"
  if [ -L "$src" ]; then
    echo "  skip $d (already a symlink)"
    continue
  fi
  if [ ! -d "$src" ]; then
    echo "  skip $d (no local dir)"
    continue
  fi
  sz_kb=$(du -sk "$src" 2>/dev/null | awk '{print $1}')
  sz_h=$(du -sh "$src" 2>/dev/null | awk '{print $1}')
  total=$((total + sz_kb))
  plan+=("$d")
  echo "  copy $d  ($sz_h)"
done
total_h=$(awk -v t="$total" 'BEGIN{ if(t>1048576) printf "%.1f GB",t/1048576; else printf "%.0f MB",t/1024 }')
echo "  ---"
echo "  total to copy: $total_h"

if [ "${#plan[@]}" -eq 0 ]; then
  echo "Nothing to migrate — all dirs are already symlinks or missing."
  exit 0
fi

read -r -p "Proceed with rsync to NAS? [y/N] " ans
case "$ans" in y|Y|yes|YES) ;; *) echo "Aborted."; exit 1 ;; esac

# -- Copy ---------------------------------------------------------------------
for d in "${plan[@]}"; do
  src="$REPO/$d"
  dst="$NAS_PATH/$d"
  echo ""
  echo "==> rsync $d"
  # -a archive, -h human, -P partial+progress, --info=progress2 single-line summary,
  # --no-perms because SMB doesn't preserve macOS perms cleanly
  rsync -a --no-perms --info=progress2 "$src/" "$dst/"
done

# -- Verify (file counts must match) ------------------------------------------
echo ""
echo "Verifying (file count parity)..."
fail=0
for d in "${plan[@]}"; do
  s=$(find "$REPO/$d" -type f 2>/dev/null | wc -l | tr -d ' ')
  t=$(find "$NAS_PATH/$d" -type f 2>/dev/null | wc -l | tr -d ' ')
  if [ "$s" = "$t" ]; then
    echo "  ok   $d ($s files)"
  else
    echo "  MISMATCH $d (local=$s, nas=$t)"
    fail=1
  fi
done

if [ "$fail" -ne 0 ]; then
  echo ""
  echo "Some dirs didn't transfer cleanly. NOT deleting local copies. Re-run rsync manually:"
  for d in "${plan[@]}"; do echo "  rsync -aP $REPO/$d/ $NAS_PATH/$d/"; done
  exit 1
fi

# -- Offer to delete local copies --------------------------------------------
echo ""
read -r -p "Verified clean. Delete local $total_h so symlinks can take over? [y/N] " ans
case "$ans" in y|Y|yes|YES) ;; *) echo "Kept locals. Run setup-blender-mcp-from-nas.sh later — it'll WARN until locals are gone."; exit 0 ;; esac

for d in "${plan[@]}"; do
  echo "  rm -rf $REPO/$d"
  rm -rf "$REPO/$d"
done

echo ""
echo "Done. Now run:"
echo "  bash setup-blender-mcp-from-nas.sh"
echo "to create the symlinks."
