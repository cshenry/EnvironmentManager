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


def main():
    """Main entry point for the venvman CLI."""
    parser = argparse.ArgumentParser(
        description="Centralized venv manager with per-repo .venv symlink."
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    # Subparsers will be added here for each command

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
