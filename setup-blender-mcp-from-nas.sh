#!/bin/bash
# setup-blender-mcp-from-nas.sh  (patched for Scott's claw-architect layout)
# Run on the Mac AFTER cloning blender-mcp. Mounts the Synology NAS over SMB
# and creates symlinks for heavy dirs that live on NAS instead of in git.
#
# What's different from upstream:
#   - Reads NAS_SMB_* + NAS_MOUNT_POINT from ~/claw-architect/.env so you don't
#     have to hand-edit shares/credentials per machine.
#   - Defaults match Scott's setup: share=homes, mount=/Volumes/homes (Synology
#     DSM7's "homes" share, not the singular /Volumes/home which fails EACCES on
#     macOS Sequoia for non-admins).
#   - URL-encodes the SMB password before `open smb://...` so passwords
#     containing $, #, &, etc. don't break the shell.
#   - EACCES fallback: if macOS denies /Volumes/<share>, mounts under
#     ~/.claw-architect/nas-smb-home and the symlinks point there instead.
#
# Usage:
#   cd ~/claw-architect/openclaw-blender-mcp
#   bash setup-blender-mcp-from-nas.sh
#
# Prereqs:
#   - ~/claw-architect/.env contains NAS_SMB_USER, NAS_SMB_PASSWORD, NAS_SMB_HOST,
#     NAS_SMB_SHARE, NAS_MOUNT_POINT  (matches docs/NAS-SMB-MOUNT.md)
#   - SMAT account has read/write on the NAS share.

set -u

# -- 1. Load config from ~/claw-architect/.env (best-effort) ------------------
ENV_FILE="$HOME/claw-architect/.env"
if [ -f "$ENV_FILE" ]; then
  # Only export NAS_* keys; ignore the rest of .env to avoid surprises.
  while IFS= read -r line; do
    case "$line" in
      NAS_SMB_*=*|NAS_MOUNT_POINT=*|NAS_PATH_REDIRECT=*)
        # shellcheck disable=SC2163
        export "${line%%=*}"="$(printf '%s' "${line#*=}" | sed -E 's/^"(.*)"$/\1/')"
        ;;
    esac
  done < <(grep -E '^(NAS_SMB_|NAS_MOUNT_POINT|NAS_PATH_REDIRECT)' "$ENV_FILE")
fi

NAS_HOST="${NAS_SMB_HOST:-192.168.1.164}"
NAS_USER="${NAS_SMB_USER:-SMAT}"
NAS_PASS="${NAS_SMB_PASSWORD:-}"
NAS_SHARE="${NAS_SMB_SHARE:-homes}"
NAS_MOUNT="${NAS_MOUNT_POINT:-/Volumes/homes}"
NAS_PATH="$NAS_MOUNT/blender-mcp-shared"
FALLBACK_MOUNT="$HOME/.claw-architect/nas-smb-home"

# -- 2. Verify we're inside the blender-mcp repo ------------------------------
REPO=$(cd "$(dirname "$0")" && pwd)
if [ ! -f "$REPO/README.md" ] || ! grep -qi "blender" "$REPO/README.md" 2>/dev/null; then
  echo "ERROR: This doesn't look like the blender-mcp repo. Run from repo root."
  exit 1
fi

# -- 3. URL-encode the password so $ and friends survive `open smb://...` -----
urlencode() {
  local s="$1" out="" c
  for ((i=0;i<${#s};i++)); do
    c="${s:$i:1}"
    case "$c" in
      [a-zA-Z0-9.~_-]) out+="$c" ;;
      *) out+=$(printf '%%%02X' "'$c") ;;
    esac
  done
  printf '%s' "$out"
}

# -- 4. Try to mount NAS at primary mount; fall back on EACCES ----------------
mount_nas() {
  local target="$1"
  if mount | grep -q "$NAS_HOST.*on $target"; then return 0; fi
  mkdir -p "$target" 2>/dev/null || return 1
  local enc_pass=""
  [ -n "$NAS_PASS" ] && enc_pass=":$(urlencode "$NAS_PASS")"
  echo "  trying  smb://${NAS_USER}${enc_pass:+:***}@${NAS_HOST}/${NAS_SHARE} -> $target"
  open "smb://${NAS_USER}${enc_pass}@${NAS_HOST}/${NAS_SHARE}" 2>/dev/null
  for i in 1 2 3 4 5 6 7 8 9 10; do
    sleep 2
    if mount | grep -q "$NAS_HOST.*on $target"; then return 0; fi
    if mount | grep -q "$NAS_HOST.*on /Volumes/${NAS_SHARE}"; then
      NAS_MOUNT="/Volumes/${NAS_SHARE}"
      NAS_PATH="$NAS_MOUNT/blender-mcp-shared"
      return 0
    fi
  done
  return 1
}

if ! mount_nas "$NAS_MOUNT"; then
  echo "  primary mount failed — trying EACCES fallback at $FALLBACK_MOUNT"
  NAS_MOUNT="$FALLBACK_MOUNT"
  NAS_PATH="$NAS_MOUNT/blender-mcp-shared"
  if ! mount_nas "$NAS_MOUNT"; then
    echo "ERROR: NAS share never came up. Manual: Finder → Go → Connect to Server"
    echo "       smb://${NAS_USER}@${NAS_HOST}/${NAS_SHARE}"
    echo "       Then re-run this script."
    exit 1
  fi
fi
echo "NAS mounted at $NAS_MOUNT"

# -- 5. Verify the shared directory exists ------------------------------------
if [ ! -d "$NAS_PATH" ]; then
  echo "ERROR: $NAS_PATH does not exist on the NAS."
  echo "       Has the migration run from a source machine yet? See:"
  echo "       bash migrate-heavy-to-nas.sh"
  exit 1
fi

# -- 6. Create symlinks for every NAS-hosted directory ------------------------
DIRS=(renders exports models assets bridge_renders portfolio_curated_best portfolio_forensic_v4 data)

echo "Creating symlinks under $REPO ..."
for d in "${DIRS[@]}"; do
  src="$NAS_PATH/$d"
  dst="$REPO/$d"

  if [ ! -d "$src" ]; then
    echo "  skip $d (not on NAS yet)"
    continue
  fi

  if [ -L "$dst" ]; then
    target=$(readlink "$dst")
    if [ "$target" = "$src" ]; then
      echo "  ok   $d (symlink correct)"
      continue
    fi
    echo "  fix  $d (symlink wrong, re-pointing $target -> $src)"
    rm "$dst"
  elif [ -d "$dst" ]; then
    sz=$(du -sh "$dst" 2>/dev/null | cut -f1)
    echo "  WARN $d already exists locally ($sz) — leaving as-is."
    echo "       Migrate first: bash migrate-heavy-to-nas.sh"
    continue
  fi

  ln -s "$src" "$dst"
  echo "  link $d -> $src"
done

echo ""
echo "Done. Verify:"
echo "  ls -la $REPO | grep ^l"
echo ""
echo "If you ever lose the NAS mount, symlinks dangle until remount —"
echo "  npm run nas:mount:home    # from ~/claw-architect"
