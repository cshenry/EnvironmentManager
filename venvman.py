#!/usr/bin/env python3
import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


def venv_home() -> Path:
    """Get the virtual environment home directory from $VENV_HOME or default."""
    return Path(os.environ.get("VENV_HOME", str(Path.home() / "VirtualEnvironments")))


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    """Execute a subprocess command and return the result."""
    return subprocess.run(cmd, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def find_python(pyver: str | None) -> Path | None:
    """
    Find a suitable Python interpreter with priority-based resolution.

    Priority:
    1. pyenv (if available and version specified)
    2. System python<version> (if version specified)
    3. Fallback to python3

    Args:
        pyver: Python version string (e.g., "3.12") or None

    Returns:
        Path to Python interpreter or None if not found
    """
    # Try pyenv first if version specified
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
    """
    Extract MAJOR.MINOR version from a Python interpreter.

    Args:
        python_bin: Path to Python interpreter

    Returns:
        Version string in format "MAJOR.MINOR" (e.g., "3.12")

    Raises:
        SystemExit: If unable to determine Python version
    """
    r = run([str(python_bin), "-c", "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"])
    if r.returncode != 0:
        print("Error reading python version", file=sys.stderr)
        sys.exit(1)
    return r.stdout.strip()


def list_envs(args):
    """List all virtual environments in $VENV_HOME."""
    root = venv_home()
    if not root.exists():
        return
    for p in sorted([d for d in root.iterdir() if d.is_dir()]):
        print(p.name)


def ensure_symlink(link: Path, target: Path, force: bool):
    """
    Create a symlink, handling existing links and --force flag.

    Args:
        link: Path where symlink should be created
        target: Path the symlink should point to
        force: If True, remove existing link/directory before creating

    Raises:
        SystemExit: If .venv exists but is not a symlink and force=False
    """
    if link.exists() or link.is_symlink():
        if link.is_symlink():
            if link.resolve() == target.resolve():
                return
        if not force:
            # Check if it's a regular directory/file (not a symlink)
            if link.exists() and not link.is_symlink():
                print(f"Error: {link} exists but is not a symlink.", file=sys.stderr)
                print(f"Use --force to replace it.", file=sys.stderr)
                sys.exit(1)
            # Replace symlink by default (safe behavior)
            link.unlink(missing_ok=True)
        else:
            link.unlink(missing_ok=True)
    link.symlink_to(target)


def write_activate_sh(repo_dir: Path):
    """
    Generate activate.sh script in the project directory.

    Args:
        repo_dir: Path to the project directory
    """
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
    """
    Create a virtual environment and link it into a project directory.

    Args:
        args: Parsed command-line arguments
    """
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

    # Create venv if missing
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


def delete_env(args):
    """
    Delete a virtual environment from $VENV_HOME.

    Args:
        args: Parsed command-line arguments
    """
    root = venv_home()

    # Determine which environment to delete
    if args.env:
        env_dir = root / args.env
    elif args.project:
        # Search for matching environments
        pattern = f"{args.project}-py*"
        matches = list(root.glob(pattern)) if root.exists() else []

        if len(matches) == 0:
            print(f"No environments found for project: {args.project}", file=sys.stderr)
            sys.exit(1)
        elif len(matches) > 1:
            print(f"Multiple environments found for project '{args.project}':", file=sys.stderr)
            for m in matches:
                print(f"  - {m.name}", file=sys.stderr)
            print("Please specify --env with the exact environment name.", file=sys.stderr)
            sys.exit(1)
        else:
            env_dir = matches[0]
    else:
        print("Error: Must specify either --project or --env", file=sys.stderr)
        sys.exit(1)

    # Validate environment exists
    if not env_dir.exists():
        print(f"Environment does not exist: {env_dir}", file=sys.stderr)
        sys.exit(1)

    # Warn and confirm
    print(f"WARNING: About to delete: {env_dir}")
    print("Note: Symlinks in project directories will NOT be automatically removed.")
    response = input("Continue? (y/n): ").strip().lower()

    if response != 'y' and response != 'yes':
        print("Deletion cancelled.")
        sys.exit(0)

    # Delete the environment
    try:
        shutil.rmtree(env_dir)
        print(f"Successfully deleted: {env_dir}")
    except PermissionError as e:
        print(f"Permission error while deleting environment: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error deleting environment: {e}", file=sys.stderr)
        sys.exit(1)


def get_dir_size(path: Path) -> int:
    """
    Calculate total size of a directory recursively.

    Args:
        path: Path to directory

    Returns:
        Total size in bytes
    """
    total = 0
    try:
        for entry in path.rglob('*'):
            if entry.is_file():
                total += entry.stat().st_size
    except Exception:
        pass
    return total


def format_size(size_bytes: int) -> str:
    """
    Format size in bytes to human-readable string.

    Args:
        size_bytes: Size in bytes

    Returns:
        Formatted string (e.g., "1.5 MB")
    """
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"


def info_env(args):
    """
    Display information about a virtual environment.

    Args:
        args: Parsed command-line arguments
    """
    root = venv_home()

    # Resolve environment path (similar to delete)
    if args.env:
        env_dir = root / args.env
    elif args.project:
        pattern = f"{args.project}-py*"
        matches = list(root.glob(pattern)) if root.exists() else []

        if len(matches) == 0:
            print(f"No environments found for project: {args.project}", file=sys.stderr)
            sys.exit(1)
        elif len(matches) > 1:
            print(f"Multiple environments found for project '{args.project}':", file=sys.stderr)
            for m in matches:
                print(f"  - {m.name}", file=sys.stderr)
            print("Please specify --env with the exact environment name.", file=sys.stderr)
            sys.exit(1)
        else:
            env_dir = matches[0]
    else:
        print("Error: Must specify either --project or --env", file=sys.stderr)
        sys.exit(1)

    # Validate environment exists
    if not env_dir.exists():
        print(f"Environment does not exist: {env_dir}", file=sys.stderr)
        sys.exit(1)

    # Display information
    print(f"Environment: {env_dir.name}")
    print(f"Path:        {env_dir}")

    # Extract Python version from name
    import re
    match = re.search(r'py(\d+\.\d+)', env_dir.name)
    if match:
        print(f"Python:      {match.group(1)}")

    # Try to read interpreter path from pyvenv.cfg
    pyvenv_cfg = env_dir / "pyvenv.cfg"
    if pyvenv_cfg.exists():
        try:
            content = pyvenv_cfg.read_text()
            for line in content.split('\n'):
                if line.startswith('home = '):
                    home = line.split('=', 1)[1].strip()
                    print(f"Interpreter: {home}")
                    break
        except Exception:
            pass

    # Calculate size
    size_bytes = get_dir_size(env_dir)
    print(f"Size:        {format_size(size_bytes)}")

    # Get creation date
    try:
        import time
        ctime = env_dir.stat().st_ctime
        created = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(ctime))
        print(f"Created:     {created}")
    except Exception:
        pass


def main():
    """Main entry point for the venvman CLI."""
    parser = argparse.ArgumentParser(
        description="Centralized venv manager with per-repo .venv symlink."
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    # List command
    p_list = sub.add_parser("list", help="List available environments under $VENV_HOME")
    p_list.set_defaults(func=list_envs)

    # Create command
    p_create = sub.add_parser("create", help="Create env and link it into a repo")
    p_create.add_argument("--project", required=True, help="Project name (used in env folder)")
    p_create.add_argument("--python", help="Python version, e.g., 3.12")
    p_create.add_argument("--dir", required=True, help="Project directory where .venv and activate.sh are placed")
    p_create.add_argument("--force", action="store_true", help="Replace existing .venv symlink / rewrite activate.sh")
    p_create.set_defaults(func=create_env)

    # Delete command
    p_delete = sub.add_parser("delete", help="Delete a virtual environment")
    delete_group = p_delete.add_mutually_exclusive_group(required=True)
    delete_group.add_argument("--project", help="Project name (deletes matching environment)")
    delete_group.add_argument("--env", help="Exact environment name to delete")
    p_delete.set_defaults(func=delete_env)

    # Info command
    p_info = sub.add_parser("info", help="Display information about an environment")
    info_group = p_info.add_mutually_exclusive_group(required=True)
    info_group.add_argument("--project", help="Project name")
    info_group.add_argument("--env", help="Exact environment name")
    p_info.set_defaults(func=info_env)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
