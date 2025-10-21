# Centralized Python Virtual Environment Manager

A command-line tool that manages Python virtual environments in a centralized location while keeping your project repositories clean. Instead of creating `.venv` directories scattered throughout your projects, `venvman` stores all environments in one place and uses symlinks to maintain tool compatibility.

## Why Use This?

**Problems this tool solves:**
- Virtual environment directories cluttering project repositories
- Difficulty locating and managing multiple environments
- Inconsistent activation patterns across projects
- Wasted disk space from redundant environment files

**Benefits:**
- All virtual environments in one centralized location (`~/VirtualEnvironments/` by default)
- Clean project repositories (only a symlink, not the full venv)
- Compatible with VSCode, PyCharm, and other tools that expect `.venv`
- Simple, consistent activation with `source activate.sh`
- Easy discovery of all environments with `venvman.py list`

## Requirements

- Python 3.10 or later
- Linux or macOS (bash shell required)
- Filesystem with symlink support

## Installation

1. Clone or download this repository:
```bash
git clone <repository-url>
cd EnvironmentManager
```

2. Make the script executable:
```bash
chmod +x venvman.py
```

3. (Optional) Add to your PATH or create an alias:
```bash
# Add to ~/.bashrc or ~/.zshrc
alias venvman='/path/to/EnvironmentManager/venvman.py'

# Or copy to a directory in your PATH
cp venvman.py ~/.local/bin/venvman
```

## Quick Start

Create a new environment for a project:
```bash
./venvman.py create --project myapp --python 3.12 --dir ~/projects/myapp
cd ~/projects/myapp
source activate.sh
```

That's it! Your environment is created, symlinked, and ready to use.

## Commands

### `list` - List All Environments

List all virtual environments managed by venvman:

```bash
./venvman.py list
```

**Example output:**
```
myapp-py3.12
webapp-py3.11
webapp-py3.12
```

### `create` - Create New Environment

Create a virtual environment and link it into a project directory:

```bash
./venvman.py create --project <name> --dir <path> [--python <version>] [--force] [--install-deps]
```

**Arguments:**
- `--project` (required): Project name (used in environment folder name)
- `--dir` (required): Path to project directory where `.venv` and `activate.sh` will be created
- `--python` (optional): Python version (e.g., `3.12`). Uses pyenv if available, then system python, then fallback to python3
- `--force` (optional): Replace existing `.venv` symlink/directory
- `--install-deps` (optional): Automatically install dependencies from `requirements.txt` or `pyproject.toml`

**Examples:**
```bash
# Basic usage
./venvman.py create --project myapp --dir ~/projects/myapp

# Specify Python version
./venvman.py create --project myapp --python 3.12 --dir ~/projects/myapp

# Create and install dependencies
./venvman.py create --project myapp --dir ~/projects/myapp --install-deps

# Force replacement of existing .venv
./venvman.py create --project myapp --dir ~/projects/myapp --force
```

**What it does:**
1. Resolves the Python interpreter (pyenv → system → python3)
2. Creates virtual environment at `$VENV_HOME/<project>-py<version>`
3. Creates `.venv` symlink in your project directory
4. Generates `activate.sh` script for easy activation
5. Optionally installs dependencies if `--install-deps` is provided

### `delete` - Delete Environment

Delete a virtual environment from the centralized storage:

```bash
./venvman.py delete --project <name>
# OR
./venvman.py delete --env <exact-name>
```

**Arguments:**
- `--project`: Project name (will prompt if multiple versions exist)
- `--env`: Exact environment name (e.g., `myapp-py3.12`)

**Examples:**
```bash
# Delete by project name (if only one version exists)
./venvman.py delete --project myapp

# Delete specific environment
./venvman.py delete --env myapp-py3.12
```

**Note:** This command will prompt for confirmation before deletion. Symlinks in project directories are NOT automatically removed.

### `info` - Display Environment Information

Show detailed information about a virtual environment:

```bash
./venvman.py info --project <name>
# OR
./venvman.py info --env <exact-name>
```

**Arguments:**
- `--project`: Project name
- `--env`: Exact environment name

**Example:**
```bash
./venvman.py info --project myapp
```

**Example output:**
```
Environment: myapp-py3.12
Path:        /home/user/VirtualEnvironments/myapp-py3.12
Python:      3.12
Interpreter: /usr/bin/python3.12
Size:        45.2 MB
Created:     2025-10-21 14:30:00
```

## Configuration

### Environment Variables

**`$VENV_HOME`** - Override the default location for centralized environments

Default: `~/VirtualEnvironments`

Example:
```bash
export VENV_HOME=~/.venvs
./venvman.py create --project myapp --dir ~/projects/myapp
```

## How It Works

### Architecture

```
~/VirtualEnvironments/           # $VENV_HOME (centralized storage)
├── myapp-py3.11/               # Virtual environment
├── myapp-py3.12/               # Same project, different Python version
├── webapp-py3.12/              # Another project
└── ...

~/projects/myapp/                # Your project repository
├── .venv -> ~/VirtualEnvironments/myapp-py3.12  # Symlink
├── activate.sh                  # Generated activation script
├── requirements.txt
├── main.py
└── ...
```

### Environment Naming

Environments are named using the pattern: `<project-name>-py<MAJOR.MINOR>`

Examples:
- `myapp-py3.12`
- `webapp-py3.11`

This allows you to have multiple environments for the same project with different Python versions.

### Activation Script

The generated `activate.sh` script:
- Validates that `.venv` is a symlink
- Validates that the environment exists
- Sources the environment's `activate` script
- Prints confirmation message

Usage:
```bash
source activate.sh
```

### Python Interpreter Resolution

When creating an environment, `venvman` finds Python in this order:

1. **pyenv** (if installed and version specified): `pyenv which python<version>`
2. **System python** (if version specified): `which python<version>`
3. **Fallback**: `which python3`

## Troubleshooting

### "Project directory does not exist"
Make sure the directory specified with `--dir` exists before running `create`.

### "No suitable python interpreter found"
Ensure Python is installed and accessible. Try specifying a version with `--python` or install pyenv.

### ".venv exists but is not a symlink"
You have an existing `.venv` directory or file. Use `--force` to replace it, or remove it manually first.

### "Environment does not exist" (when using `info` or `delete`)
Check available environments with `./venvman.py list` and use the exact name with `--env`.

### Tools don't recognize the environment
The `.venv` symlink should work with most tools (VSCode, PyCharm, etc.). If not, try:
1. Reload your IDE
2. Manually point the IDE to the environment in `$VENV_HOME`

### Activation script fails
Ensure:
1. `.venv` is a valid symlink: `ls -l .venv`
2. The target environment exists: `ls -ld $(readlink .venv)`
3. You're sourcing the script: `source activate.sh` (not `./activate.sh`)

## Example Workflow

Setting up a new Python project:

```bash
# 1. Create project directory
mkdir ~/projects/myapp
cd ~/projects/myapp

# 2. Create virtual environment with dependencies
~/EnvironmentManager/venvman.py create \
  --project myapp \
  --python 3.12 \
  --dir . \
  --install-deps

# 3. Activate the environment
source activate.sh

# 4. Start working!
python --version
pip list
```

## .gitignore Recommendations

Add these entries to your `.gitignore`:

```gitignore
# Virtual environment symlink
.venv

# Activation script
activate.sh
```

This keeps your repository clean while allowing `venvman` to manage environments locally.

## Additional Notes

- **Multiple Python versions**: You can create multiple environments for the same project with different Python versions. Just specify different `--python` versions.
- **Environment persistence**: Environments remain in `$VENV_HOME` even if you delete the project directory or symlink.
- **Disk space**: To free up space, use the `delete` command to remove unused environments.
- **Sharing environments**: Not recommended. Each developer should create their own environments.
- **Dependencies**: The `--install-deps` flag looks for `requirements.txt` and `pyproject.toml` in the project directory.

## License

[Specify your license here]

## Contributing

[Specify contribution guidelines here]
