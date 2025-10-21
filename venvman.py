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


def main():
    """Main entry point for the venvman CLI."""
    parser = argparse.ArgumentParser(
        description="Centralized venv manager with per-repo .venv symlink."
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    # List command
    p_list = sub.add_parser("list", help="List available environments under $VENV_HOME")
    p_list.set_defaults(func=list_envs)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
