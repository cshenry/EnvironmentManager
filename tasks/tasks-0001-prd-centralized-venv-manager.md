# Task List: Centralized Python Virtual Environment Manager

## Relevant Files

- `venvman.py` - Main CLI tool implementation containing all commands and core logic
- `README.md` - User-facing documentation with installation instructions, usage examples, and troubleshooting guide
- `.gitignore` - Git ignore patterns to exclude generated files and virtual environments (optional but recommended)

### Notes

- The `activate.sh` script is generated dynamically by the tool in each project directory, so it's not a source file in this repository
- This project has no automated tests per the PRD requirements (manual testing only)
- The tool requires Python 3.10+ to run (uses modern type hint syntax like `list[str]`)

## Tasks

- [x] 1.0 Set up project structure and core utilities
  - [x] 1.1 Create `venvman.py` file with proper shebang (`#!/usr/bin/env python3`)
  - [x] 1.2 Import required standard library modules (argparse, os, pathlib, subprocess, shutil, sys)
  - [x] 1.3 Implement `venv_home()` function to get/resolve `$VENV_HOME` path (default: `~/VirtualEnvironments`)
  - [x] 1.4 Implement `run()` helper function to execute subprocess commands and capture output
  - [x] 1.5 Set up main argparse parser with program description
  - [x] 1.6 Create subparsers structure for commands (list, create, delete, info)
  - [x] 1.7 Add main() function with argument parsing and command dispatch
  - [x] 1.8 Make venvman.py executable (chmod +x)

- [x] 2.0 Implement Python interpreter resolution and environment path management
  - [x] 2.1 Implement `find_python(pyver: str | None)` function with priority-based resolution
  - [x] 2.2 Add pyenv resolution logic (check if pyenv exists, run `pyenv which python<ver>`)
  - [x] 2.3 Add system python resolution (check for `python<ver>` using shutil.which)
  - [x] 2.4 Add fallback to `python3` if no version specified or version not found
  - [x] 2.5 Implement `python_version_str(python_bin: Path)` to extract MAJOR.MINOR version from interpreter
  - [x] 2.6 Add error handling for invalid/non-executable Python interpreters
  - [x] 2.7 Implement environment naming convention: `<project>-py<MAJOR.MINOR>`

- [x] 3.0 Implement the `list` command
  - [x] 3.1 Create `list_envs(args)` function
  - [x] 3.2 Check if `$VENV_HOME` directory exists (return silently if not)
  - [x] 3.3 Iterate through directories in `$VENV_HOME` and filter for valid environment directories
  - [x] 3.4 Sort environment names alphabetically
  - [x] 3.5 Print each environment name (one per line)
  - [x] 3.6 Add subparser for `list` command with help text
  - [x] 3.7 Set command handler function (set_defaults)

- [x] 4.0 Implement the `create` command with symlink and activation script generation
  - [x] 4.1 Create `create_env(args)` function
  - [x] 4.2 Add subparser for `create` command with all required/optional arguments (--project, --dir, --python, --force)
  - [x] 4.3 Validate that project directory (--dir) exists, exit with error if not (FR8)
  - [x] 4.4 Create `$VENV_HOME` directory if it doesn't exist (mkdir with parents=True, exist_ok=True)
  - [x] 4.5 Resolve Python interpreter using `find_python()`, exit with error if not found (FR8)
  - [x] 4.6 Get actual Python version using `python_version_str()`
  - [x] 4.7 Construct environment directory path: `$VENV_HOME/<project>-py<ver>`
  - [x] 4.8 Check if environment already exists; if yes, print message and skip creation
  - [x] 4.9 Create virtual environment using `python -m venv <env_dir>`, handle creation errors (FR8)
  - [x] 4.10 Implement `ensure_symlink(link: Path, target: Path, force: bool)` function
  - [x] 4.11 In `ensure_symlink()`, check if link exists and is symlink pointing to correct target (skip if match)
  - [x] 4.12 Handle case where .venv exists but is not a symlink (error unless --force, suggest --force in message)
  - [x] 4.13 Handle --force flag: remove existing .venv (symlink or directory) before creating new symlink
  - [x] 4.14 Create symlink from `<project-dir>/.venv` to environment directory
  - [x] 4.15 Implement `write_activate_sh(repo_dir: Path)` function
  - [x] 4.16 Generate activate.sh content with proper validation (check .venv is symlink, check activate exists)
  - [x] 4.17 Write activate.sh to project directory
  - [x] 4.18 Make activate.sh executable (chmod 0o755)
  - [x] 4.19 Print success messages showing environment path, symlink, and activate.sh location
  - [x] 4.20 Add comprehensive help text for create command

- [x] 5.0 Implement the `delete` command
  - [x] 5.1 Create `delete_env(args)` function
  - [x] 5.2 Add subparser for `delete` command with mutually exclusive arguments (--project OR --env)
  - [x] 5.3 If `--env` provided, construct full path to environment
  - [x] 5.4 If `--project` provided, search `$VENV_HOME` for matching environments (pattern: `<project>-py*`)
  - [x] 5.5 Handle ambiguous matches (multiple environments for same project): list them and ask user to specify --env
  - [x] 5.6 Validate that environment exists, exit with error if not found (FR8)
  - [x] 5.7 Print warning message showing what will be deleted
  - [x] 5.8 Prompt user for confirmation (y/n) before deletion
  - [x] 5.9 Remove environment directory using shutil.rmtree()
  - [x] 5.10 Handle permission errors during deletion (FR8)
  - [x] 5.11 Print success message confirming deletion
  - [x] 5.12 Add help text noting that symlinks in projects are NOT automatically removed

- [x] 6.0 Implement the `info` command
  - [x] 6.1 Create `info_env(args)` function
  - [x] 6.2 Add subparser for `info` command with mutually exclusive arguments (--project OR --env)
  - [x] 6.3 Resolve environment path (similar logic to delete command)
  - [x] 6.4 Validate that environment exists, exit with error if not found (FR8)
  - [x] 6.5 Display environment name
  - [x] 6.6 Display full path to environment directory
  - [x] 6.7 Extract and display Python version from environment name (parse `py<MAJOR.MINOR>`)
  - [x] 6.8 Attempt to read Python interpreter path from `pyvenv.cfg` file
  - [x] 6.9 Calculate environment size on disk (recursively sum all files)
  - [x] 6.10 Get creation date from directory metadata (os.path.getctime or stat)
  - [x] 6.11 Format output in readable way (consider using labels and alignment)
  - [x] 6.12 Add help text for info command

- [ ] 7.0 Add dependency installation support (`--install-deps` flag)
  - [ ] 7.1 Add `--install-deps` flag to create command subparser
  - [ ] 7.2 In `create_env()`, check if `--install-deps` flag is set
  - [ ] 7.3 After environment creation and symlink setup, check for `requirements.txt` in project directory
  - [ ] 7.4 If `requirements.txt` exists, install using `<env>/bin/pip install -r requirements.txt`
  - [ ] 7.5 Check for `pyproject.toml` in project directory
  - [ ] 7.6 If `pyproject.toml` exists, install using `<env>/bin/pip install -e .` (editable install)
  - [ ] 7.7 Handle case where both files exist (install both, requirements.txt first)
  - [ ] 7.8 Capture and display pip output
  - [ ] 7.9 If installation fails, print warning but continue with symlink/script creation (FR6)
  - [ ] 7.10 Print success/failure message for dependency installation

- [ ] 8.0 Create comprehensive documentation (README with examples)
  - [ ] 8.1 Create README.md file
  - [ ] 8.2 Add project title and brief description
  - [ ] 8.3 Add "Why use this?" section explaining benefits
  - [ ] 8.4 Add installation instructions (clone repo, make executable, add to PATH or create alias)
  - [ ] 8.5 Add "Quick Start" section with basic usage example
  - [ ] 8.6 Document the `list` command with example
  - [ ] 8.7 Document the `create` command with all options and examples
  - [ ] 8.8 Document the `delete` command with examples
  - [ ] 8.9 Document the `info` command with example output
  - [ ] 8.10 Add section on `$VENV_HOME` environment variable configuration
  - [ ] 8.11 Add "How It Works" section explaining the architecture (centralized storage, symlinks, activate.sh)
  - [ ] 8.12 Add "Troubleshooting" section with common issues and solutions
  - [ ] 8.13 Add example workflow for setting up a new project
  - [ ] 8.14 Add notes about .gitignore recommendations (ignore .venv and activate.sh)
  - [ ] 8.15 Add requirements section (Python 3.10+, Linux/macOS, bash shell)
