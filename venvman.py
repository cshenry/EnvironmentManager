#!/usr/bin/env python3
import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional


def script_dir() -> Path:
    """Get the directory where this script is located."""
    return Path(__file__).parent.resolve()


def data_dir() -> Path:
    """Get the data directory for venvman."""
    d = script_dir() / "data"
    d.mkdir(exist_ok=True)
    return d


def projects_file() -> Path:
    """Get the path to the projects tracking JSON file."""
    return data_dir() / "projects.json"


def load_projects() -> Dict[str, dict]:
    """Load projects from JSON file.

    Returns:
        Dict mapping project name to project info dict containing:
        - path: project directory path
        - venv_subdir: virtual environment subdirectory name
        - last_deps_install: ISO timestamp of last dependency installation (or null)
    """
    pf = projects_file()
    if not pf.exists():
        return {}
    try:
        with open(pf, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError:
        print(f"Error: {pf} contains invalid JSON", file=sys.stderr)
        sys.exit(1)


def save_projects(projects: Dict[str, dict]) -> None:
    """Save projects to JSON file."""
    with open(projects_file(), 'w') as f:
        json.dump(projects, f, indent=2, sort_keys=True)


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


def write_activate_sh(repo_dir: Path, venv_subdir: str):
    """
    Generate activate.sh script in the project directory.

    The script uses VIRTUAL_ENVIRONMENT_DIRECTORY env var to find the venv root,
    and handles dependencies.yaml for adding paths to PYTHONPATH.

    Args:
        repo_dir: Path to the project directory
        venv_subdir: Name of the virtual environment subdirectory (e.g., "myproject-py3.12")
    """
    script = repo_dir / "activate.sh"
    script_content = f'''#!/usr/bin/env bash
# Source this file to activate the project environment.
# Generated by venvman - https://github.com/cshenry/EnvironmentManager

# Get the directory containing this script
SCRIPT_DIR="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)"

# Check for VIRTUAL_ENVIRONMENT_DIRECTORY
if [ -z "${{VIRTUAL_ENVIRONMENT_DIRECTORY:-}}" ]; then
  echo "Error: VIRTUAL_ENVIRONMENT_DIRECTORY is not set." >&2
  echo "" >&2
  echo "This environment variable must point to your virtual environments root directory." >&2
  echo "Use venvman to set it:" >&2
  echo "  venvman setenv /path/to/your/VirtualEnvironments" >&2
  echo "" >&2
  echo "Then restart your shell or run: source ~/.bash_profile (or ~/.bashrc)" >&2
  return 1 2>/dev/null || exit 1
fi

VENV_SUBDIR="{venv_subdir}"
VENV_PATH="${{VIRTUAL_ENVIRONMENT_DIRECTORY}}/${{VENV_SUBDIR}}"

if [ ! -f "$VENV_PATH/bin/activate" ]; then
  echo "Error: $VENV_PATH/bin/activate not found." >&2
  echo "Was the virtual environment created? Check that VIRTUAL_ENVIRONMENT_DIRECTORY is correct." >&2
  return 1 2>/dev/null || exit 1
fi

# shellcheck disable=SC1090
source "$VENV_PATH/bin/activate"
echo "Activated $VENV_PATH"

# Handle dependencies.yaml if present
DEPS_FILE="${{SCRIPT_DIR}}/dependencies.yaml"
if [ -f "$DEPS_FILE" ]; then
  # Extract paths from dependencies.yaml and add to PYTHONPATH
  # Parse YAML path: lines using grep and sed
  grep -E '^[[:space:]]*path:' "$DEPS_FILE" | while IFS= read -r line; do
    # Extract the value after "path:"
    dep_path=$(echo "$line" | sed 's/^[[:space:]]*path:[[:space:]]*//' | sed 's/^["'"'"']//' | sed 's/["'"'"']$//' | sed 's/[[:space:]]*$//')

    if [ -n "$dep_path" ]; then
      # If path is relative (doesn't start with /), prepend SCRIPT_DIR
      if [[ "$dep_path" != /* ]]; then
        dep_path="${{SCRIPT_DIR}}/${{dep_path}}"
      fi
      # Resolve to absolute path
      if [ -d "$dep_path" ]; then
        dep_path="$(cd "$dep_path" && pwd)"
        export PYTHONPATH="${{PYTHONPATH:+$PYTHONPATH:}}$dep_path"
        echo "Added to PYTHONPATH: $dep_path"
      else
        echo "Warning: Dependency path not found: $dep_path" >&2
      fi
    fi
  done
fi
'''
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
    Create a virtual environment and set up activate.sh in a project directory.

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
    venv_subdir = f"{args.project}-py{ver}"
    env_dir = root / venv_subdir

    # Create venv if missing
    if env_dir.exists():
        print(f"Env exists: {env_dir}")
    else:
        print(f"Creating venv: {env_dir} using {py}")
        r = run([str(py), "-m", "venv", str(env_dir)])
        if r.returncode != 0:
            print(r.stderr, file=sys.stderr)
            sys.exit(1)

    # Write/refresh activate.sh (uses env var for portability)
    write_activate_sh(repo_dir, venv_subdir)
    print(f"Wrote {repo_dir / 'activate.sh'} (source this to activate)")

    # Track last_deps_install timestamp
    last_deps_install: Optional[str] = None

    # Install dependencies if requested
    if args.install_deps:
        install_dependencies(env_dir, repo_dir)
        last_deps_install = datetime.now().isoformat()

    # Track this project
    projects = load_projects()
    projects[args.project] = {
        "path": str(repo_dir),
        "venv_subdir": venv_subdir,
        "last_deps_install": last_deps_install
    }
    save_projects(projects)
    print(f"Tracking project '{args.project}'")


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


def update_shell_rc(var_name: str, new_directory: str) -> bool:
    """
    Update shell RC file (.bash_profile or .bashrc) with an environment variable.

    Args:
        var_name: Name of the environment variable to set
        new_directory: Path to set as the variable value

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

    # Check if the variable is already set and update/add it
    export_line = f'export {var_name}="{new_directory}"'
    found = False

    for i, line in enumerate(lines):
        if line.strip().startswith(f'export {var_name}='):
            lines[i] = export_line
            found = True
            break

    if not found:
        # Add it at the end
        if lines and lines[-1] != '':
            lines.append('')
        lines.append(f'# venvman: {var_name}')
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

    # Update shell RC file for both variables
    print("\nUpdating shell configuration...")
    success = True
    if not update_shell_rc("VENVMAN_DIRECTORY", str(new_dir)):
        success = False
    if not update_shell_rc("VIRTUAL_ENVIRONMENT_DIRECTORY", str(new_dir)):
        success = False

    if success:
        print(f"\nVENVMAN_DIRECTORY and VIRTUAL_ENVIRONMENT_DIRECTORY have been set to: {new_dir}")
        print("Please restart your shell or run: source ~/.bash_profile (or ~/.bashrc)")
    else:
        print("\nFailed to update shell configuration.", file=sys.stderr)
        sys.exit(1)


def setenv(args):
    """
    Set the VIRTUAL_ENVIRONMENT_DIRECTORY environment variable.

    This is a simpler alternative to set_home that doesn't migrate environments.

    Args:
        args: Parsed command-line arguments
    """
    new_dir = Path(args.directory).expanduser().resolve()

    if not new_dir.exists():
        print(f"Directory does not exist: {new_dir}", file=sys.stderr)
        response = input("Create it? (y/n): ").strip().lower()
        if response == 'y' or response == 'yes':
            new_dir.mkdir(parents=True, exist_ok=True)
            print(f"Created directory: {new_dir}")
        else:
            sys.exit(1)

    print(f"Setting VIRTUAL_ENVIRONMENT_DIRECTORY to: {new_dir}")

    # Update shell RC file
    success = True
    if not update_shell_rc("VIRTUAL_ENVIRONMENT_DIRECTORY", str(new_dir)):
        success = False
    # Also set VENVMAN_DIRECTORY for backward compatibility
    if not update_shell_rc("VENVMAN_DIRECTORY", str(new_dir)):
        success = False

    if success:
        print(f"\nVIRTUAL_ENVIRONMENT_DIRECTORY has been set to: {new_dir}")
        print("Please restart your shell or run: source ~/.bash_profile (or ~/.bashrc)")
    else:
        print("\nFailed to update shell configuration.", file=sys.stderr)
        sys.exit(1)


def bootstrap(args):
    """
    Bootstrap the project list from existing virtual environment subdirectories.

    Scans the VENVMAN_DIRECTORY for existing environments and adds them to tracking.
    Since we don't know the project paths, they are left as null and can be updated later.

    Args:
        args: Parsed command-line arguments
    """
    import re

    root = venv_home()
    if not root.exists():
        print(f"Virtual environment directory does not exist: {root}", file=sys.stderr)
        sys.exit(1)

    # Find all environment directories
    env_dirs = [d for d in root.iterdir() if d.is_dir()]
    if not env_dirs:
        print(f"No environments found in {root}")
        return

    projects = load_projects()
    added_count = 0
    skipped_count = 0

    print(f"Scanning {root} for environments...\n")

    for env_dir in sorted(env_dirs):
        # Parse environment name to extract project name
        # Expected format: <project>-py<version>
        match = re.match(r'^(.+)-py(\d+\.\d+)$', env_dir.name)
        if match:
            project_name = match.group(1)
            venv_subdir = env_dir.name

            if project_name in projects:
                print(f"  Skipped {env_dir.name} (project '{project_name}' already tracked)")
                skipped_count += 1
            else:
                projects[project_name] = {
                    "path": None,  # Unknown - user needs to add project path
                    "venv_subdir": venv_subdir,
                    "last_deps_install": None
                }
                print(f"  Added {env_dir.name} as project '{project_name}'")
                added_count += 1
        else:
            print(f"  Skipped {env_dir.name} (doesn't match pattern <project>-py<version>)")
            skipped_count += 1

    save_projects(projects)
    print(f"\nBootstrap complete: {added_count} added, {skipped_count} skipped")
    if added_count > 0:
        print("\nNote: Bootstrapped projects have no project path set.")
        print("Use 'venvman addproject <directory>' to set the path for each project,")
        print("or manually edit the projects.json file.")


def update_projects(args):
    """
    Update activate.sh scripts in all tracked projects.

    This regenerates activate.sh files to use the new VIRTUAL_ENVIRONMENT_DIRECTORY
    approach and removes any .venv symlinks.

    Args:
        args: Parsed command-line arguments
    """
    projects = load_projects()

    if not projects:
        print("No projects are currently tracked.")
        print("Use 'venvman create' or 'venvman addproject' to add projects.")
        return

    print(f"Updating {len(projects)} project(s)...\n")

    updated_count = 0
    missing_count = 0
    no_path_count = 0

    for project_name, info in sorted(projects.items()):
        project_path_str = info.get("path")
        venv_subdir = info.get("venv_subdir")

        if not project_path_str:
            print(f"  Skipped '{project_name}' (no project path set)")
            no_path_count += 1
            continue

        project_path = Path(project_path_str)

        if not project_path.exists():
            print(f"  Warning: '{project_name}' not found at {project_path}")
            missing_count += 1
            continue

        print(f"Updating '{project_name}':")
        print(f"  Path: {project_path}")

        # Remove .venv symlink if it exists
        venv_link = project_path / ".venv"
        if venv_link.is_symlink():
            venv_link.unlink()
            print(f"  Removed .venv symlink")
        elif venv_link.exists():
            print(f"  Warning: .venv exists but is not a symlink (not removed)")

        # Regenerate activate.sh
        if venv_subdir:
            write_activate_sh(project_path, venv_subdir)
            print(f"  Updated activate.sh")
        else:
            print(f"  Warning: No venv_subdir set, skipping activate.sh")

        print()
        updated_count += 1

    print(f"Updated {updated_count} project(s)")
    if missing_count > 0:
        print(f"  {missing_count} project(s) not found (consider removing them)")
    if no_path_count > 0:
        print(f"  {no_path_count} project(s) have no path set (use addproject to set)")


def addproject(args):
    """
    Add a project directory to tracking.

    If the project already exists (matched by venv_subdir), updates its path.
    Otherwise, creates a new tracking entry.

    Args:
        args: Parsed command-line arguments
    """
    project_path = Path(args.directory).expanduser().resolve()

    if not project_path.exists():
        print(f"Error: Directory does not exist: {args.directory}", file=sys.stderr)
        sys.exit(1)

    if not project_path.is_dir():
        print(f"Error: Not a directory: {args.directory}", file=sys.stderr)
        sys.exit(1)

    # Use directory name as project name if not specified
    project_name = args.project if args.project else project_path.name

    projects = load_projects()

    # Check if project already exists
    if project_name in projects:
        existing = projects[project_name]
        existing_path = existing.get("path")
        if existing_path and existing_path != str(project_path):
            print(f"Warning: Project '{project_name}' already exists with different path:")
            print(f"  Existing: {existing_path}")
            print(f"  New:      {project_path}")
            response = input("Update path? (y/n): ").strip().lower()
            if response != 'y' and response != 'yes':
                print("Cancelled.")
                sys.exit(0)
        # Update the path
        projects[project_name]["path"] = str(project_path)
        print(f"Updated project '{project_name}' path to: {project_path}")
    else:
        # New project - need to determine venv_subdir
        venv_subdir = args.venv if args.venv else None

        if not venv_subdir:
            # Try to find an existing environment for this project
            root = venv_home()
            if root.exists():
                pattern = f"{project_name}-py*"
                matches = list(root.glob(pattern))
                if len(matches) == 1:
                    venv_subdir = matches[0].name
                    print(f"Found existing environment: {venv_subdir}")
                elif len(matches) > 1:
                    print(f"Multiple environments found for '{project_name}':")
                    for m in matches:
                        print(f"  - {m.name}")
                    print("Please specify --venv with the exact environment name.")
                    sys.exit(1)

        projects[project_name] = {
            "path": str(project_path),
            "venv_subdir": venv_subdir,
            "last_deps_install": None
        }
        print(f"Added project '{project_name}'")

    save_projects(projects)

    # Regenerate activate.sh if we have venv_subdir
    venv_subdir = projects[project_name].get("venv_subdir")
    if venv_subdir:
        write_activate_sh(project_path, venv_subdir)
        print(f"Wrote {project_path / 'activate.sh'}")

        # Remove .venv symlink if it exists
        venv_link = project_path / ".venv"
        if venv_link.is_symlink():
            venv_link.unlink()
            print(f"Removed .venv symlink")
    else:
        print("Note: No virtual environment associated. Use 'venvman create' to create one.")


def removeproject(args):
    """
    Remove a project from tracking.

    Does not delete the virtual environment or project files.

    Args:
        args: Parsed command-line arguments
    """
    projects = load_projects()

    if args.project not in projects:
        print(f"Error: Project '{args.project}' is not tracked.", file=sys.stderr)
        print("\nCurrently tracked projects:")
        if projects:
            for name in sorted(projects.keys()):
                print(f"  - {name}")
        else:
            print("  (none)")
        sys.exit(1)

    project_info = projects[args.project]
    project_path = project_info.get("path", "(no path)")
    venv_subdir = project_info.get("venv_subdir", "(no venv)")

    del projects[args.project]
    save_projects(projects)

    print(f"Removed project '{args.project}' from tracking")
    print(f"  Path was: {project_path}")
    print(f"  Venv was: {venv_subdir}")
    print("\nNote: The virtual environment and project files were NOT deleted.")


def listprojects(args):
    """
    List all tracked projects.

    Args:
        args: Parsed command-line arguments
    """
    projects = load_projects()

    if not projects:
        print("No projects are currently tracked.")
        print("Use 'venvman create' or 'venvman addproject' to add projects.")
        return

    print(f"Tracked projects ({len(projects)}):\n")

    root = venv_home()

    for project_name in sorted(projects.keys()):
        info = projects[project_name]
        project_path = info.get("path")
        venv_subdir = info.get("venv_subdir")
        last_deps = info.get("last_deps_install")

        # Check status
        path_exists = project_path and Path(project_path).exists()
        venv_exists = venv_subdir and (root / venv_subdir).exists()

        status = "ok" if (path_exists and venv_exists) else "!"

        print(f"  [{status}] {project_name}")
        print(f"      Path: {project_path or '(not set)'}")
        print(f"      Venv: {venv_subdir or '(not set)'}")
        if last_deps:
            print(f"      Deps: {last_deps}")
        if not path_exists and project_path:
            print(f"      Warning: Project path not found")
        if not venv_exists and venv_subdir:
            print(f"      Warning: Virtual environment not found")
        print()


def installdeps(args):
    """
    Install dependencies for a tracked project.

    Activates the project's environment and runs pip install -r requirements.txt.

    Args:
        args: Parsed command-line arguments
    """
    projects = load_projects()

    if args.project not in projects:
        print(f"Error: Project '{args.project}' is not tracked.", file=sys.stderr)
        print("\nUse 'venvman listprojects' to see tracked projects,", file=sys.stderr)
        print("or 'venvman addproject <directory>' to add a project.", file=sys.stderr)
        sys.exit(1)

    project_info = projects[args.project]
    project_path = project_info.get("path")
    venv_subdir = project_info.get("venv_subdir")

    if not project_path:
        print(f"Error: Project '{args.project}' has no path set.", file=sys.stderr)
        print("Use 'venvman addproject <directory>' to set the path.", file=sys.stderr)
        sys.exit(1)

    project_dir = Path(project_path)
    if not project_dir.exists():
        print(f"Error: Project directory not found: {project_dir}", file=sys.stderr)
        sys.exit(1)

    if not venv_subdir:
        print(f"Error: Project '{args.project}' has no virtual environment.", file=sys.stderr)
        print("Use 'venvman create' to create one.", file=sys.stderr)
        sys.exit(1)

    # Check for requirements.txt
    requirements_file = project_dir / "requirements.txt"
    if not requirements_file.exists():
        print(f"Error: requirements.txt not found in {project_dir}", file=sys.stderr)
        sys.exit(1)

    # Check that VIRTUAL_ENVIRONMENT_DIRECTORY is set
    venv_root = os.environ.get("VIRTUAL_ENVIRONMENT_DIRECTORY")
    if not venv_root:
        print("Error: VIRTUAL_ENVIRONMENT_DIRECTORY is not set.", file=sys.stderr)
        print("Use 'venvman setenv' to set it, then restart your shell.", file=sys.stderr)
        sys.exit(1)

    venv_path = Path(venv_root) / venv_subdir
    pip_bin = venv_path / "bin" / "pip"

    if not pip_bin.exists():
        print(f"Error: Virtual environment not found at {venv_path}", file=sys.stderr)
        print("The environment may have been deleted or moved.", file=sys.stderr)
        sys.exit(1)

    print(f"Installing dependencies for '{args.project}'...")
    print(f"  Project: {project_dir}")
    print(f"  Venv:    {venv_path}")
    print(f"  Using:   {requirements_file}")
    print()

    # Run pip install
    r = run([str(pip_bin), "install", "-r", str(requirements_file)])

    if r.returncode == 0:
        print("\nSuccessfully installed dependencies")

        # Update last_deps_install timestamp
        projects[args.project]["last_deps_install"] = datetime.now().isoformat()
        save_projects(projects)
        print(f"Updated tracking for '{args.project}'")
    else:
        print("\nFailed to install dependencies:", file=sys.stderr)
        print(r.stderr, file=sys.stderr)
        sys.exit(1)


def help_cmd(args):
    """Display the full README documentation."""
    # Get the directory where this script is located
    readme_path = script_dir() / "README.md"

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
        description="Centralized venv manager with portable activate.sh scripts."
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    # List environments command
    p_list = sub.add_parser("list", help="List available environments under $VENVMAN_DIRECTORY")
    p_list.set_defaults(func=list_envs)

    # Create command
    p_create = sub.add_parser("create", help="Create env and set up activate.sh in a project")
    p_create.add_argument("--project", required=True, help="Project name (used in env folder)")
    p_create.add_argument("--python", help="Python version, e.g., 3.12")
    p_create.add_argument("--dir", required=True, help="Project directory where activate.sh is placed")
    p_create.add_argument("--force", action="store_true", help="Force overwrite of activate.sh")
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

    # Set home command (legacy, with migration)
    p_set_home = sub.add_parser("set_home", help="Set the VENVMAN_DIRECTORY and migrate environments")
    p_set_home.add_argument("directory", help="New directory path for virtual environments")
    p_set_home.set_defaults(func=set_home)

    # Setenv command (simple, just sets the env var)
    p_setenv = sub.add_parser("setenv", help="Set VIRTUAL_ENVIRONMENT_DIRECTORY in shell config")
    p_setenv.add_argument("directory", help="Directory path for virtual environments")
    p_setenv.set_defaults(func=setenv)

    # Bootstrap command
    p_bootstrap = sub.add_parser("bootstrap", help="Bootstrap project list from existing venv subdirectories")
    p_bootstrap.set_defaults(func=bootstrap)

    # Update command
    p_update = sub.add_parser("update", help="Update activate.sh in all tracked projects")
    p_update.set_defaults(func=update_projects)

    # Add project command
    p_addproject = sub.add_parser("addproject", help="Add a project directory to tracking")
    p_addproject.add_argument("directory", help="Path to project directory")
    p_addproject.add_argument("--project", help="Project name (defaults to directory name)")
    p_addproject.add_argument("--venv", help="Virtual environment subdirectory name")
    p_addproject.set_defaults(func=addproject)

    # Remove project command
    p_removeproject = sub.add_parser("removeproject", help="Remove a project from tracking")
    p_removeproject.add_argument("project", help="Project name to remove")
    p_removeproject.set_defaults(func=removeproject)

    # List projects command
    p_listprojects = sub.add_parser("listprojects", help="List all tracked projects")
    p_listprojects.set_defaults(func=listprojects)

    # Install dependencies command
    p_installdeps = sub.add_parser("installdeps", help="Install dependencies from requirements.txt")
    p_installdeps.add_argument("--project", required=True, help="Project name")
    p_installdeps.set_defaults(func=installdeps)

    # Help command
    p_help = sub.add_parser("help", help="Display full README documentation")
    p_help.set_defaults(func=help_cmd)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
