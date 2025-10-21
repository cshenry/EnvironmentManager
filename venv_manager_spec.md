# Centralized Python Virtual Environment Manager

**Goal:** maintain all project venvs in a single directory (e.g., `~/VirtualEnvironments/`), keep each repo clean, and preserve tool compatibility via a `.venv` **symlink** in the project root. Also generate a repo-local `activate.sh` that you can `source` to activate the right env.

## High-level design

- **Central store:** `$VENV_HOME` (default `~/VirtualEnvironments`).
- **Naming:** `<project-name>-py<MAJOR.MINOR>`, e.g. `orchestrator-py3.12`.
- **Repo integration:** a **symlink** `./.venv -> $VENV_HOME/<project>-py<ver>` in each repo root.
- **Activation:** `source activate.sh` (generated per project) which sources `./.venv/bin/activate`.

## Components

1. **Python CLI:** `venvman.py`
   - `list`: list available envs under `$VENV_HOME`
   - `create`: create env for a project with Python version and link it into a repo  
     Inputs: `--project`, `--python`, `--dir`  
     Actions:
       - Resolve interpreter
       - `python -m venv $VENV_HOME/<project>-py<ver>`
       - symlink `.venv` into repo
       - write `activate.sh`

2. **Repo script:** `activate.sh`
   - `source activate.sh` activates the env via `./.venv/bin/activate`.

## Usage

```bash
python venvman.py list

python venvman.py create \
  --project orchestrator \
  --python 3.12 \
  --dir ~/repos/orchestrator

cd ~/repos/orchestrator
source activate.sh
```

## Reference Implementation (`venvman.py`)

```#!/usr/bin/env python3
import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

def venv_home() -> Path:
    return Path(os.environ.get("VENV_HOME", str(Path.home() / "VirtualEnvironments")))

def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

def find_python(pyver: str | None) -> Path | None:
    # Try pyenv first
    if pyver:
        if shutil.which("pyenv"):
            r = run(["pyenv", "which", f"python{pyver}"])
            if r.returncode == 0:
                p = Path(r.stdout.strip())
                if p.exists():
                    return p
        # Then system python<ver>
        cand = shutil.which(f"python{pyver}")
        if cand:
            return Path(cand)
    # Fallback to python3
    cand = shutil.which("python3")
    return Path(cand) if cand else None

def python_version_str(python_bin: Path) -> str:
    r = run([str(python_bin), "-c", "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"])
    if r.returncode != 0:
        print("Error reading python version", file=sys.stderr)
        sys.exit(1)
    return r.stdout.strip()

def list_envs(args):
    root = venv_home()
    if not root.exists():
        return
    for p in sorted([d for d in root.iterdir() if d.is_dir()]):
        print(p.name)

def ensure_symlink(link: Path, target: Path, force: bool):
    if link.exists() or link.is_symlink():
        if link.is_symlink():
            if link.resolve() == target.resolve():
                return
        if not force:
            # Replace safely by default (acts like -snf). If you prefer strict, flip logic.
            link.unlink(missing_ok=True)
        else:
            link.unlink(missing_ok=True)
    link.symlink_to(target)

def write_activate_sh(repo_dir: Path):
    script = repo_dir / "activate.sh"
    script.write_text("""#!/usr/bin/env bash
# Source this file to activate the project environment.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ ! -L "$HERE/.venv" ]; then
  echo "Error: $HERE/.venv is not a symlink. Did you run venvman.py create?" >&2
  return 1 2>/dev/null || exit 1
fi

if [ ! -f "$HERE/.venv/bin/activate" ]; then
  echo "Error: $HERE/.venv/bin/activate not found. Was the venv created successfully?" >&2
  return 1 2>/dev/null || exit 1
fi

# shellcheck disable=SC1090
source "$HERE/.venv/bin/activate"
echo "Activated $(readlink "$HERE/.venv")"
""")
    script.chmod(0o755)

def create_env(args):
    root = venv_home()
    root.mkdir(parents=True, exist_ok=True)

    repo_dir = Path(args.dir).expanduser().resolve()
    if not repo_dir.exists():
        print(f"Project directory does not exist: {repo_dir}", file=sys.stderr)
        sys.exit(1)

    py = find_python(args.python)
    if not py:
        print("No suitable python interpreter found.", file=sys.stderr)
        sys.exit(1)

    ver = python_version_str(py)
    env_dir = root / f"{args.project}-py{ver}"

    # Create venv if missing (or if force and you want to recreate—default: don't destroy existing)
    if env_dir.exists():
        print(f"Env exists: {env_dir}")
    else:
        print(f"Creating venv: {env_dir} using {py}")
        r = run([str(py), "-m", "venv", str(env_dir)])
        if r.returncode != 0:
            print(r.stderr, file=sys.stderr)
            sys.exit(1)

    # Symlink .venv in repo
    link = repo_dir / ".venv"
    ensure_symlink(link, env_dir, force=args.force)
    print(f"Linked {link} -> {env_dir}")

    # Write/refresh activate.sh
    write_activate_sh(repo_dir)
    print(f"Wrote {repo_dir/'activate.sh'} (source this to activate)")

def main():
    parser = argparse.ArgumentParser(description="Centralized venv manager with per-repo .venv symlink.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list", help="List available environments under $VENV_HOME")
    p_list.set_defaults(func=list_envs)

    p_create = sub.add_parser("create", help="Create env and link it into a repo")
    p_create.add_argument("--project", required=True, help="Project name (used in env folder)")
    p_create.add_argument("--python", help="Python version, e.g., 3.12")
    p_create.add_argument("--dir", required=True, help="Project directory where .venv and activate.sh are placed")
    p_create.add_argument("--force", action="store_true", help="Replace existing .venv symlink / rewrite activate.sh")
    p_create.set_defaults(func=create_env)

    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
```

(Add entire code block into the file as appropriate.)
