# PRD: Centralized Python Virtual Environment Manager

## Introduction/Overview

The Centralized Python Virtual Environment Manager (`venvman`) is a command-line tool that helps individual developers manage Python virtual environments across multiple projects. Instead of creating isolated virtual environments scattered throughout different project directories, this tool maintains all virtual environments in a single centralized location (`~/VirtualEnvironments/` by default) while using symlinks in project repositories to maintain tool compatibility.

**Problem Statement:** Developers working on multiple Python projects often face:
- Virtual environment directories cluttering project repositories
- Difficulty locating and managing multiple environments
- Inconsistent activation patterns across projects
- Wasted disk space from redundant environment files

**Solution:** A centralized management system that stores all environments in one location, creates symlinks in project directories for tool compatibility, and provides simple activation scripts.

## Goals

1. Centralize all Python virtual environments in a single, configurable directory (`$VENV_HOME`)
2. Keep project repositories clean by using symlinks instead of full environment directories
3. Maintain compatibility with tools that expect `.venv` in the project root
4. Provide a simple, consistent activation mechanism across all projects
5. Enable easy discovery and management of all virtual environments
6. Reduce developer time spent on environment setup and management

## User Stories

1. **As a developer**, I want to list all my virtual environments in one command, so that I can quickly see what environments I have available.

2. **As a developer**, I want to create a new virtual environment for my project with a specific Python version, so that I can start working without cluttering my repository.

3. **As a developer**, I want to activate my project's environment with a simple `source activate.sh` command, so that I don't need to remember complex paths.

4. **As a developer**, I want to delete environments I no longer need, so that I can free up disk space and keep my environment directory organized.

5. **As a developer**, I want to view detailed information about an environment (Python version, location, linked projects), so that I can verify my setup is correct.

6. **As a developer**, I want to optionally install dependencies during environment creation, so that I can set up a complete working environment in one step.

7. **As a developer**, I want clear error messages when something goes wrong, so that I can quickly understand and fix the issue.

## Functional Requirements

### FR1: List Command
The system must provide a `list` command that:
- Lists all virtual environments in `$VENV_HOME`
- Displays environment names in sorted order
- Shows environment naming format: `<project-name>-py<MAJOR.MINOR>` (e.g., `orchestrator-py3.12`)
- Handles cases where `$VENV_HOME` doesn't exist gracefully (no error, no output)

### FR2: Create Command
The system must provide a `create` command that:
- Accepts required arguments: `--project` (project name), `--dir` (project directory path)
- Accepts optional arguments: `--python` (Python version, e.g., "3.12"), `--force` (replace existing symlink), `--install-deps` (install dependencies)
- Resolves the Python interpreter in this order:
  1. pyenv (if available and version specified)
  2. System `python<version>` (if version specified)
  3. Fallback to `python3`
- Creates virtual environment at `$VENV_HOME/<project>-py<MAJOR.MINOR>`
- Skips creation if environment already exists (prints message)
- Creates `.venv` symlink in project directory pointing to the centralized environment
- Generates `activate.sh` script in project directory
- Makes `activate.sh` executable (chmod 755)
- Fails with clear error if project directory doesn't exist
- Fails with clear error if no suitable Python interpreter found
- Fails with clear error if `.venv` exists and is not a symlink (unless `--force` is used)

### FR3: Delete Command
The system must provide a `delete` command that:
- Accepts required argument: `--project` (project name) OR `--env` (full environment name)
- Lists matching environments if project name is ambiguous (multiple Python versions)
- Removes the virtual environment directory from `$VENV_HOME`
- Warns the user before deletion
- Fails with clear error if environment doesn't exist
- Does NOT automatically remove symlinks from project directories (user maintains repos)

### FR4: Info Command
The system must provide an `info` command that:
- Accepts required argument: `--project` (project name) OR `--env` (full environment name)
- Displays:
  - Environment name
  - Full path to environment directory
  - Python version
  - Python interpreter path used to create it (if determinable)
  - Environment size on disk
  - Creation date (if determinable)
- Fails with clear error if environment doesn't exist

### FR5: Activation Script
The system must generate an `activate.sh` script that:
- Can be sourced from bash/zsh shells: `source activate.sh`
- Validates that `.venv` is a symlink (fails if not)
- Validates that `.venv/bin/activate` exists (fails if not)
- Sources `.venv/bin/activate`
- Prints confirmation message showing which environment was activated
- Uses proper error handling for both interactive and non-interactive shells

### FR6: Dependency Installation
When the `--install-deps` flag is provided to the `create` command, the system must:
- Check for `requirements.txt` in the project directory
- Check for `pyproject.toml` in the project directory (PEP 621 dependencies)
- Install dependencies using pip after environment creation
- Report success or failure of installation
- Continue with symlink/script creation even if installation fails (with warning)

### FR7: Environment Variable Support
The system must:
- Support `$VENV_HOME` environment variable to override default location
- Default to `~/VirtualEnvironments` if `$VENV_HOME` is not set
- Create `$VENV_HOME` directory if it doesn't exist (during `create` command)

### FR8: Error Handling
The system must provide clear error messages for:
- Project directory doesn't exist
- No suitable Python interpreter found
- `.venv` exists but is not a symlink (suggest using `--force`)
- Permission errors when creating directories or symlinks
- Disk space issues (venv creation failure)
- `$VENV_HOME` permission issues
- Invalid arguments or missing required arguments

### FR9: Symlink Management
The system must:
- Create symlinks using relative or absolute paths as appropriate
- Replace existing symlinks if they point to a different target and `--force` is not set (safe default behavior)
- Fail if `.venv` exists as a regular directory or file (not a symlink) without `--force`
- When `--force` is provided, remove existing `.venv` (symlink or directory) and recreate

## Non-Goals (Out of Scope)

The following are explicitly NOT included in this version:

1. Configuration files (no `~/.venvmanrc` or per-project config files)
2. Additional environment variables beyond `$VENV_HOME`
3. Customizable naming patterns for environments
4. Team collaboration features or shared environment management
5. CI/CD pipeline integration or automation features
6. Automatic dependency detection without explicit `--install-deps` flag
7. Interactive prompts for user decisions (all behavior controlled by flags)
8. Automatic backup of existing `.venv` directories
9. Migration tools for existing virtual environments
10. GUI or web interface
11. Environment versioning or snapshots
12. Automatic environment activation (e.g., via shell integration like direnv)
13. Windows support (initial version targets Linux/macOS with bash)
14. Package management beyond basic pip install from requirements files
15. Virtual environment templates or presets

## Design Considerations

### Command-Line Interface
- Follow standard CLI conventions (GNU-style long options with `--`)
- Provide helpful `--help` output for main command and all subcommands
- Use argparse for argument parsing (as shown in reference implementation)
- Return appropriate exit codes (0 for success, non-zero for errors)

### File System Structure
```
~/VirtualEnvironments/           # $VENV_HOME
├── project-a-py3.11/
├── project-a-py3.12/
├── project-b-py3.12/
└── orchestrator-py3.12/

~/repos/project-a/               # Project repository
├── .venv -> ~/VirtualEnvironments/project-a-py3.12
├── activate.sh
└── [project files]
```

### Naming Convention
- Environment naming: `<project-name>-py<MAJOR.MINOR>`
- Project name comes from `--project` argument
- Python version comes from actual interpreter version (not just the `--python` argument)
- This allows multiple environments for the same project with different Python versions

## Technical Considerations

### Dependencies
- Standard library only (argparse, os, pathlib, subprocess, shutil, sys)
- No external dependencies required
- Python 3.10+ required to run the tool itself (uses modern syntax like `list[str]`)

### Python Interpreter Resolution
Priority order:
1. pyenv (if installed and version specified): `pyenv which python<version>`
2. System python: `which python<version>`
3. Fallback: `which python3`

### Compatibility
- Target platforms: Linux and macOS (bash shell required)
- Symlinks used (requires filesystem support)
- Scripts assume bash for activation

### Integration Points
- Respects existing venv module behavior
- Generated `.venv` symlink compatible with:
  - VSCode Python extension
  - PyCharm
  - Most Python tools that look for `.venv`

## Success Metrics

The primary success metric is **developer time saved in environment setup**. This can be measured by:

1. Time to create and activate a new project environment (target: < 30 seconds including dependency installation)
2. Reduction in "environment doesn't work" troubleshooting time
3. Developer satisfaction with environment management workflow

Qualitative indicators of success:
- Developers consistently use the tool for new projects
- Reduced questions about "which environment am I in?"
- Cleaner project repositories (no `.venv` directories checked into git)

## Open Questions

1. Should `delete` command require confirmation (y/n prompt) or use a `--force` flag to skip confirmation?
2. Should `info` command show which projects link to an environment (reverse lookup)?
3. How should the tool handle environments that have been manually modified or corrupted?
4. Should there be a `migrate` command to import existing local virtual environments into the centralized structure? (Currently out of scope but may be useful)
5. Should `create` command automatically add `.venv` and `activate.sh` to `.gitignore` if it exists?

## Acceptance Criteria

The feature will be considered complete when:

1. All four commands (`list`, `create`, `delete`, `info`) are implemented and functional
2. `create` command successfully creates centralized environments with correct naming
3. Symlinks are created correctly and work with common Python tools (VSCode, PyCharm)
4. `activate.sh` script works in bash and zsh shells
5. `--install-deps` flag correctly installs from `requirements.txt` or `pyproject.toml`
6. Error messages are clear and actionable for all specified error conditions
7. `--help` output is complete and accurate for all commands
8. README exists with installation instructions and usage examples
9. Manual testing confirms all user stories can be completed successfully
10. Tool works on both Linux and macOS systems
