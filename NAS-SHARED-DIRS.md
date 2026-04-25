# NAS-Shared Directories — blender-mcp

This repo's heavy directories (renders, models, assets, etc.) do **not** live in git. They live on the Synology NAS at `192.168.1.164` and are accessed locally through symlinks.

## Why

The blender-mcp pipeline produces large binary outputs — `.blend`, `.exr`, `.mp4`, baked textures — plus referenced 3D model assets. Putting all of those in git would blow past GitHub's file-size limits, balloon clone times, and pollute history. The NAS hosts them once; every machine symlinks the same path.

## Directories on NAS

NAS root for this repo: `/Volumes/home/blender-mcp-shared/`

| Symlink in repo | NAS location | What it holds |
|---|---|---|
| `renders/` | `…/blender-mcp-shared/renders` | rendered .blend / .png / .exr / .mp4 outputs |
| `exports/` | `…/blender-mcp-shared/exports` | exported .glb / .fbx / .obj |
| `models/` | `…/blender-mcp-shared/models` | source 3D model assets |
| `assets/` | `…/blender-mcp-shared/assets` | textures, references |
| `bridge_renders/` | `…/blender-mcp-shared/bridge_renders` | bridge pipeline render outputs |
| `portfolio_curated_best/` | `…/blender-mcp-shared/portfolio_curated_best` | curated portfolio outputs |
| `portfolio_forensic_v4/` | `…/blender-mcp-shared/portfolio_forensic_v4` | forensic portfolio v4 outputs |
| `data/` | `…/blender-mcp-shared/data` | datasets / config payloads |

## First-time setup on a new machine (e.g. M3 Max)

```bash
# 1. Clone the repo
cd ~/claw-repos
git clone https://github.com/jabbertones-cloud/blender-mcp.git
cd blender-mcp

# 2. Mount the NAS share (Finder → Go → Connect to Server → smb://192.168.1.164/home, login as SMAT)
#    or just run the setup script below — it'll prompt you to mount.

# 3. Run the setup script — it creates the symlinks
bash setup-blender-mcp-from-nas.sh
```

The script lives at the repo root once committed. It:

1. Verifies you're inside the blender-mcp repo
2. Mounts `smb://192.168.1.164/home` to `/Volumes/home` if not already mounted
3. Confirms `/Volumes/home/blender-mcp-shared/` exists
4. Creates symlinks for every NAS-hosted directory

## Day-to-day

The symlinks are transparent — Blender, Python scripts, and the MCP server see normal directory paths. The only requirement is that the NAS is mounted at `/Volumes/home` whenever you're working with the heavy assets. If the NAS isn't mounted, the symlinks dangle and code that touches them fails noisily — that's the desired behavior, not a silent bug.

## .gitignore

The directory names above are added to `.gitignore` so the symlinks themselves are NOT committed. Each developer creates them locally via `setup-blender-mcp-from-nas.sh`. This keeps the repo portable to anyone without NAS access.

## Adding more directories

If a new heavy directory shows up:

1. `mv my-new-dir /Volumes/home/blender-mcp-shared/`
2. `ln -s /Volumes/home/blender-mcp-shared/my-new-dir my-new-dir`
3. Add `my-new-dir/` to `.gitignore`
4. Add it to the `DIRS=(...)` array in `setup-blender-mcp-from-nas.sh`

## Recovery / disaster scenarios

- **NAS is down**: symlinks dangle. Bring NAS back up (`ssh SMAT@192.168.1.164`, see `nas-ops` runbook). Symlinks will resolve again automatically.
- **NAS is gone forever**: restore `/Volumes/home/blender-mcp-shared/` from your most recent backup (Synology Hyper Backup → external drive). Symlinks resume working once content is back at the same path.
- **Need to work offline**: copy whichever subdirectory you need to a temp local path and edit `setup-blender-mcp-from-nas.sh` to point there for that session.
