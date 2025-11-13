#!/usr/bin/env python3
import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


def venv_home() -> Path:
    """Get the virtual environment home directory from $VENVMAN_DIRECTORY or default."""
    return Path(os.environ.get("VENVMAN_DIRECTORY", str(Path.home() / "VirtualEnvironments")))


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    """Execute a subprocess command and return the result."""
    return subprocess.run(cmd, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def find_python(pyver: str | None) -> Path | None:
    """
    Find a suitable Python interpreter with priority-based resolution.

    Priority:
    1. pyenv (if available and version specified)
    2. System python<version> (if version specified)
    3. Fallback to python3 (only if no specific version requested)

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
        # If a specific version was requested but not found, return None
        # Don't fallback to python3 as that would ignore the user's version requirement
        return None

    # Fallback to python3 only when no specific version was requested
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
    """List all virtual environments in $VENVMAN_DIRECTORY."""
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


def write_activate_sh(repo_dir: Path, env_dir: Path):
    """
    Generate activate.sh script in the project directory.

    Args:
        repo_dir: Path to the project directory
        env_dir: Path to the virtual environment directory
    """
    script = repo_dir / "activate.sh"
    script_content = f"""#!/usr/bin/env bash
# Source this file to activate the project environment.
set -euo pipefail

VENV_PATH="{env_dir}"

if [ ! -f "$VENV_PATH/bin/activate" ]; then
  echo "Error: $VENV_PATH/bin/activate not found. Was the venv created successfully?" >&2
  return 1 2>/dev/null || exit 1
fi

# shellcheck disable=SC1090
source "$VENV_PATH/bin/activate"
echo "Activated $VENV_PATH"
"""
    script.write_text(script_content)
    script.chmod(0o755)


def install_dependencies(env_dir: Path, repo_dir: Path):
    """
    Install dependencies from requirements.txt or pyproject.toml.

    Args:
        env_dir: Path to virtual environment
        repo_dir: Path to project directory
    """
    pip_bin = env_dir / "bin" / "pip"
    requirements_file = repo_dir / "requirements.txt"
    pyproject_file = repo_dir / "pyproject.toml"

    installed_any = False

    # Install from requirements.txt
    if requirements_file.exists():
        print(f"\nInstalling dependencies from {requirements_file}...")
        r = run([str(pip_bin), "install", "-r", str(requirements_file)])
        if r.returncode == 0:
            print("Successfully installed dependencies from requirements.txt")
            installed_any = True
        else:
            print(f"WARNING: Failed to install from requirements.txt", file=sys.stderr)
            print(r.stderr, file=sys.stderr)

    # Install from pyproject.toml (editable install)
    if pyproject_file.exists():
        print(f"\nInstalling project from {pyproject_file} (editable mode)...")
        r = run([str(pip_bin), "install", "-e", str(repo_dir)])
        if r.returncode == 0:
            print("Successfully installed project in editable mode")
            installed_any = True
        else:
            print(f"WARNING: Failed to install from pyproject.toml", file=sys.stderr)
            print(r.stderr, file=sys.stderr)

    if not installed_any:
        print("\nNo dependency files found (requirements.txt or pyproject.toml)")


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
        if args.python:
            print(f"Error: Python {args.python} not found.", file=sys.stderr)
            print(f"Searched for: pyenv python{args.python}, python{args.python} in PATH", file=sys.stderr)
            print(f"Tip: Install Python {args.python} via pyenv or ensure python{args.python} is in your PATH", file=sys.stderr)
        else:
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
    write_activate_sh(repo_dir, env_dir)
    print(f"Wrote {repo_dir/'activate.sh'} (source this to activate)")

    # Install dependencies if requested
    if args.install_deps:
        install_dependencies(env_dir, repo_dir)


def delete_env(args):
    """
    Delete a virtual environment from $VENVMAN_DIRECTORY.

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


def update_shell_rc(new_directory: str) -> bool:
    """
    Update shell RC file (.bash_profile or .bashrc) with VENVMAN_DIRECTORY.

    Args:
        new_directory: Path to set as VENVMAN_DIRECTORY

    Returns:
        True if successful, False otherwise
    """
    home = Path.home()
    rc_files = [home / ".bash_profile", home / ".bashrc"]

    # Find the first existing RC file, or default to .bash_profile
    target_rc = None
    for rc_file in rc_files:
        if rc_file.exists():
            target_rc = rc_file
            break

    if target_rc is None:
        target_rc = rc_files[0]  # Default to .bash_profile

    # Read existing content
    if target_rc.exists():
        content = target_rc.read_text()
        lines = content.split('\n')
    else:
        lines = []

    # Check if VENVMAN_DIRECTORY is already set and update/add it
    export_line = f'export VENVMAN_DIRECTORY="{new_directory}"'
    found = False

    for i, line in enumerate(lines):
        if line.strip().startswith('export VENVMAN_DIRECTORY='):
            lines[i] = export_line
            found = True
            break

    if not found:
        # Add it at the end
        if lines and lines[-1] != '':
            lines.append('')
        lines.append('# venvman: Virtual environment home directory')
        lines.append(export_line)

    # Write back
    try:
        target_rc.write_text('\n'.join(lines))
        print(f"Updated {target_rc}")
        return True
    except Exception as e:
        print(f"Error updating {target_rc}: {e}", file=sys.stderr)
        return False


def set_home(args):
    """
    Set the VENVMAN_DIRECTORY environment variable and migrate existing environments.

    Args:
        args: Parsed command-line arguments
    """
    new_dir = Path(args.directory).expanduser().resolve()
    current_dir = venv_home()

    print(f"Current directory: {current_dir}")
    print(f"New directory:     {new_dir}")

    # Check if new directory is the same as current
    if new_dir == current_dir:
        print("\nNew directory is the same as the current directory. No changes needed.")
        sys.exit(0)

    # Check if there are environments in the current location
    environments_to_migrate = []
    if current_dir.exists() and current_dir.is_dir():
        environments_to_migrate = [d for d in current_dir.iterdir() if d.is_dir()]

    if environments_to_migrate:
        print(f"\nFound {len(environments_to_migrate)} environment(s) in current location:")
        for env in environments_to_migrate:
            print(f"  - {env.name}")

        response = input("\nMigrate these environments to the new location? (y/n): ").strip().lower()
        if response == 'y' or response == 'yes':
            # Create new directory if it doesn't exist
            new_dir.mkdir(parents=True, exist_ok=True)

            # Migrate each environment
            print("\nMigrating environments...")
            for env in environments_to_migrate:
                dest = new_dir / env.name
                if dest.exists():
                    print(f"  Skipping {env.name} (already exists in destination)")
                else:
                    try:
                        shutil.copytree(env, dest)
                        print(f"  Copied {env.name}")
                    except Exception as e:
                        print(f"  Error copying {env.name}: {e}", file=sys.stderr)

            print("\nMigration complete.")
            response = input("Delete old environments? (y/n): ").strip().lower()
            if response == 'y' or response == 'yes':
                for env in environments_to_migrate:
                    try:
                        shutil.rmtree(env)
                        print(f"  Deleted {env.name}")
                    except Exception as e:
                        print(f"  Error deleting {env.name}: {e}", file=sys.stderr)
        else:
            print("Migration skipped.")
    else:
        # No environments to migrate, just create the directory
        new_dir.mkdir(parents=True, exist_ok=True)
        print(f"\nCreated directory: {new_dir}")

    # Update shell RC file
    print("\nUpdating shell configuration...")
    if update_shell_rc(str(new_dir)):
        print(f"\nVENVMAN_DIRECTORY has been set to: {new_dir}")
        print("Please restart your shell or run: source ~/.bash_profile (or ~/.bashrc)")
    else:
        print("\nFailed to update shell configuration.", file=sys.stderr)
        sys.exit(1)


def help_cmd(args):
    """Display the full README documentation."""
    # Get the directory where this script is located
    script_dir = Path(__file__).parent.resolve()
    readme_path = script_dir / "README.md"

    if not readme_path.exists():
        print("Error: README.md not found.", file=sys.stderr)
        print(f"Expected location: {readme_path}", file=sys.stderr)
        sys.exit(1)

    try:
        content = readme_path.read_text()
        print(content)
    except Exception as e:
        print(f"Error reading README.md: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    """Main entry point for the venvman CLI."""
    parser = argparse.ArgumentParser(
        description="Centralized venv manager with per-repo .venv symlink."
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    # List command
    p_list = sub.add_parser("list", help="List available environments under $VENVMAN_DIRECTORY")
    p_list.set_defaults(func=list_envs)

    # Create command
    p_create = sub.add_parser("create", help="Create env and link it into a repo")
    p_create.add_argument("--project", required=True, help="Project name (used in env folder)")
    p_create.add_argument("--python", help="Python version, e.g., 3.12")
    p_create.add_argument("--dir", required=True, help="Project directory where .venv and activate.sh are placed")
    p_create.add_argument("--force", action="store_true", help="Replace existing .venv symlink / rewrite activate.sh")
    p_create.add_argument("--install-deps", action="store_true", help="Install dependencies from requirements.txt or pyproject.toml")
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

    # Set home command
    p_set_home = sub.add_parser("set_home", help="Set the VENVMAN_DIRECTORY and migrate environments")
    p_set_home.add_argument("directory", help="New directory path for virtual environments")
    p_set_home.set_defaults(func=set_home)

    # Help command
    p_help = sub.add_parser("help", help="Display full README documentation")
    p_help.set_defaults(func=help_cmd)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
