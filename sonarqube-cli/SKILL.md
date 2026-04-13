---
name: sonarqube-cli
description: |
  Use this skill whenever the user wants to interact with SonarQube via the `sonar` CLI tool or
  `sonar-scanner`. This covers all SonarQube CLI workflows including: scanning code for issues and
  secrets, authenticating with SonarQube Cloud or Server, listing issues and projects, making
  authenticated API requests, integrating with Claude Code or Git hooks, running server-side
  analysis (SQAA), verifying files, and managing CLI configuration. Also covers full project
  analysis with sonar-scanner, branch-based scanning, quality gate checks, and the scan_branch.py
  orchestration script. Trigger when the user mentions "sonar", "sonarqube", "sonar cli",
  "sonarqube cli", "sonar analyze", "sonar verify", "sonar scan", "sonar secrets", "sonar-scanner",
  "sonar scanner", code quality scanning, secrets scanning, quality gate, branch analysis, or wants
  to integrate SonarQube into their workflow. Also trigger when the user asks about detecting
  hardcoded secrets, preventing secret leaks in commits, setting up pre-commit/pre-push hooks for
  security scanning, or running a full SonarQube analysis on a specific branch.
---

# SonarQube CLI Skill

The SonarQube CLI (`sonar`, version 0.9.0) detects security vulnerabilities and code quality issues directly from the terminal. It connects to SonarQube Cloud or SonarQube Server and supports local secrets scanning, server-side code analysis, issue management, and integrations with AI coding agents and Git.

**Note:** This product is in Beta — breaking changes may occur.

## Quick Reference

Before doing anything else, verify the CLI is installed and authenticated:

```bash
sonar --version
sonar auth status
```

If not authenticated, see the Authentication section below.

For the full command reference, read `references/commands.md`.

## Authentication

All SonarQube CLI commands require authentication. The CLI stores tokens in the system keychain.

### Login

```bash
# Interactive login for SonarQube Cloud (opens browser)
sonar auth login

# Non-interactive with organization and token
sonar auth login -o my-org -t squ_abc123

# For a self-hosted SonarQube Server
sonar auth login -s https://my-sonarqube.io --with-token squ_def456
```

**Important:** Only *user tokens* work for authentication. Project tokens, global tokens, and scoped organization tokens are not supported.

### Check and manage connections

```bash
sonar auth status    # Show active connection and verify token
sonar auth logout    # Remove active token
sonar auth purge     # Remove ALL saved tokens
```

## Code Analysis

### Verify a single file (`sonar verify`)

Run a comprehensive scan on a single file. This is the fastest way to check a file for issues:

```bash
sonar verify --file src/app.ts
sonar verify --file src/app.ts --branch main
sonar verify --file src/app.ts -p my-project
```

### Scan for secrets (`sonar analyze secrets`)

Scan files or stdin for hardcoded secrets (API keys, tokens, passwords, etc.):

```bash
# Scan specific files or directories
sonar analyze secrets src/config.ts
sonar analyze secrets src/config.ts src/secrets/

# Scan from stdin (useful in pipelines)
cat .env | sonar analyze secrets --stdin
```

The command exits with a non-zero code when secrets are found, making it suitable for CI pipelines and scripts.

### Server-side analysis — SQAA (`sonar analyze sqaa`)

Run SonarQube Agentic Analysis on a file. This sends the file to SonarQube Cloud for deep server-side analysis (SonarQube Cloud only):

```bash
sonar analyze sqaa --file src/app.ts
sonar analyze sqaa --file src/app.ts --branch main
sonar analyze sqaa --file src/app.ts -p my-project
```

## Listing Resources

### List issues

```bash
sonar list issues -p my-project
sonar list issues -p my-project --severity CRITICAL
sonar list issues -p my-project --format toon
sonar list issues -p my-project --branch main
sonar list issues -p my-project --page 2 --page-size 50
```

The `--format toon` output format is designed for consumption by AI agents.

### List projects

```bash
sonar list projects
sonar list projects -q my-project
sonar list projects --page 2 --page-size 50
```

## API Access

The `sonar api` command lets you make authenticated requests to any SonarQube API endpoint. The CLI automatically handles authentication and routes between V1/V2 APIs based on the endpoint path.

```bash
# GET requests
sonar api get "/api/favorites/search"
sonar api get "/api/rules/search?organization=org-name"

# POST requests with JSON body
sonar api post "/api/user_tokens/generate" --data '{"name":"my-new-token"}'
sonar api post "/api/issues/do_transition" --data '{"issue":"issue-id","transition":"accept"}'

# Debug with verbose output
sonar api get "/api/favorites/search" --verbose
```

Supported HTTP methods: `get`, `post`, `patch`, `put`, `delete`.

API documentation:
- SonarQube Cloud: https://docs.sonarsource.com/sonarqube-cloud/appendices/web-api
- SonarQube Server: https://docs.sonarsource.com/sonarqube-server/extension-guide/web-api

## Integrations

### Claude Code integration (`sonar integrate claude`)

Installs secrets-scanning hooks that automatically block Claude Code from reading or writing files containing secrets. Also configures the SonarQube MCP Server.

```bash
# Interactive setup for current project
sonar integrate claude -p my-project

# Global install (affects all projects)
sonar integrate claude -g -p my-project

# Non-interactive
sonar integrate claude -p my-project --non-interactive
```

After installation, restart Claude Code for hooks to take effect.

### Git hooks (`sonar integrate git`)

Installs native Git hooks that automatically scan for secrets before commits or pushes:

```bash
# Interactive — install pre-commit hook (scans staged files)
sonar integrate git

# Pre-push hook (scans committed files before push)
sonar integrate git --hook pre-push

# Global — applies to all repositories
sonar integrate git --global

# Force overwrite an existing hook
sonar integrate git --force

# Non-interactive global pre-push
sonar integrate git --hook pre-push --global --non-interactive
```

## Configuration and Maintenance

```bash
# Telemetry
sonar config telemetry --enabled
sonar config telemetry --disabled

# Self-update
sonar self-update              # Update to latest version
sonar self-update --status     # Check for newer version
sonar self-update --force      # Force reinstall latest
```

## Common Workflows

### First-time setup

1. Install the CLI (if not already installed):
   ```bash
   curl -o- https://raw.githubusercontent.com/SonarSource/sonarqube-cli/refs/heads/master/user-scripts/install.sh | bash
   ```
2. Authenticate: `sonar auth login`
3. Verify connection: `sonar auth status`
4. Scan a file: `sonar verify --file src/app.ts`

### Prevent secret leaks with Git hooks

1. Install the hook: `sonar integrate git`
2. Test it by staging a file with a fake API key — the commit should be blocked
3. The hook runs `sonar analyze secrets` automatically on every commit

### Review and triage issues

1. List issues: `sonar list issues -p my-project`
2. Filter by severity: `sonar list issues -p my-project --severity CRITICAL`
3. Triage via API: `sonar api post "/api/issues/do_transition" --data '{"issue":"<id>","transition":"accept"}'`

### CI/CD secrets scanning

```bash
sonar analyze secrets src/ || exit 1
```

The non-zero exit code on secret detection makes this a natural fit for pipeline gating.

## Full Project Analysis with sonar-scanner

The `sonar-scanner` binary performs a complete project analysis and sends results to SonarQube Server or Cloud. This is different from the `sonar` CLI's local scanning commands — `sonar-scanner` does a full server-side analysis with language-specific parsers, coverage integration, and quality gate evaluation.

### Prerequisites

- `sonar-scanner` must be installed and on PATH. Install from https://docs.sonarsource.com/sonarqube/latest/analyzing-source-code/scanners/sonarscanner/
- Environment variables `SONAR_HOST_URL` and `SONAR_TOKEN` must be set
- Branch analysis requires SonarQube Developer Edition or higher (Community Edition has no branch support)

### Basic usage

```bash
export SONAR_HOST_URL="https://your-sonarqube.example.com"
export SONAR_TOKEN="squ_your_token_here"

# Community Edition — no branch parameter
git checkout feature/my-branch
sonar-scanner \
  -Dsonar.projectKey=my-project \
  -Dsonar.projectName="My Project"

# Developer Edition+ — with branch analysis
sonar-scanner \
  -Dsonar.projectKey=my-project \
  -Dsonar.projectName="My Project" \
  -Dsonar.branch.name=feature/my-branch
```

The scanner writes a report to `.scannerwork/report-task.txt` containing the analysis task ID needed to track completion.

### Checking analysis status

After sonar-scanner completes, the analysis runs asynchronously on the server. Use the SonarQube API to poll for completion:

```bash
# Extract task ID from the report
TASK_ID=$(grep ceTaskId .scannerwork/report-task.txt | cut -d= -f2)

# Poll task status
sonar api get "/api/ce/task?id=$TASK_ID"
```

### Checking quality gate

```bash
sonar api get "/api/qualitygates/project_status?projectKey=my-project&branch=feature/my-branch"
```

### Fetching issues after a failed gate

```bash
sonar list issues -p my-project --branch feature/my-branch
```

## Branch Scan Orchestration Script

The skill bundles `scripts/scan_branch.py` — a self-contained Python script (no external dependencies) that automates the full workflow, matching the behavior of the `manual-sonarqube.yml` GitHub Actions workflow:

1. Checks out the specified git ref via `git checkout`
2. Runs `sonar-scanner` against the single project context (Community Edition compatible by default)
3. Waits for the server-side analysis to complete
4. Checks the quality gate result
5. If passed: prints a success message and exits 0
6. If failed: fetches and displays all issues, then exits 1

**Community Edition mode (default):** The script does NOT pass `sonar.branch.name` — it checks out the ref and scans. Results update the single project analysis context, exactly like the GitHub Actions workflow. This avoids the Developer Edition requirement.

**Developer Edition+:** Pass `--use-branch` to enable true branch analysis via `sonar.branch.name`.

### Usage

```bash
# Set required environment variables
export SONAR_HOST_URL="https://your-sonarqube.example.com"
export SONAR_TOKEN="squ_your_token_here"

# Community Edition (default) — just checks out the ref and scans
python scripts/scan_branch.py --branch feature/my-branch --project-key my-project

# With a project subdirectory (like the GitHub Actions workflow)
python scripts/scan_branch.py --branch develop --project-key my-project --project-dir ./yodea-app

# Developer Edition+ — enable true branch analysis
python scripts/scan_branch.py --branch feature/my-branch --project-key my-project --use-branch

# With custom timeout and extra scanner args
python scripts/scan_branch.py \
  --branch main \
  --project-key my-project \
  --timeout 900 \
  -Dsonar.sources=src
```

### All options

| Option | Required | Description |
|---|---|---|
| `--branch` | Yes | Git branch or ref to checkout before scanning |
| `--project-key` | No* | SonarQube project key (falls back to `SONAR_PROJECT_KEY` env var) |
| `--project-name` | No | Display name (defaults to project key) |
| `--project-dir` | No | Base directory passed as `sonar.projectBaseDir` |
| `--timeout` | No | Max seconds to wait for analysis (default: 600) |
| `--poll-interval` | No | Seconds between status polls (default: 5) |
| `--use-branch` | No | Pass `sonar.branch.name` to scanner (requires Developer Edition+) |
| Extra positional args | No | Passed through to sonar-scanner (e.g. `-Dsonar.sources=src`) |

*Either `--project-key` or the `SONAR_PROJECT_KEY` environment variable is required.

### Environment variables

| Variable | Required | Description |
|---|---|---|
| `SONAR_HOST_URL` | Yes | SonarQube server URL |
| `SONAR_TOKEN` | Yes | SonarQube authentication token — stored in `$SONAR_TOKEN`, used by both `sonar-scanner` and the script |
| `SONAR_PROJECT_KEY` | No | Default project key (overridden by `--project-key`) |

The `SONAR_TOKEN` is the SonarQube user token used for authentication. It is stored in the `SONAR_TOKEN` environment variable and referenced as `$SONAR_TOKEN`. Both `sonar-scanner` and `scan_branch.py` read it automatically — no need to pass it as a flag. Make sure it is exported before running:

```bash
export SONAR_TOKEN="squ_your_token_here"
```

### Output examples

**Quality gate passed:**
```
============================================================
  QUALITY GATE PASSED - Everything looks good!
============================================================
```

**Quality gate failed:**
```
============================================================
  QUALITY GATE FAILED (FAILED)
============================================================

Failed conditions:
  - new_violations 3 > 0

Issues found: 12

SEVERITY   TYPE            COMPONENT                                 MESSAGE
--------------------------------------------------------------------
BLOCKER    BUG             src/app.ts:42                             Null pointer dereference
CRITICAL   VULNERABILITY   src/auth.ts:15                            Hardcoded credentials
MAJOR      CODE_SMELL      src/utils.ts:88                           Function has 42 parameters
```

This script replicates the `manual-sonarqube.yml` GitHub Actions workflow as a local CLI command.

## Decision Guide

When a user asks to "scan" or "check" code, choose the right command:

| Need | Command |
|---|---|
| Check a single file for all issues | `sonar verify --file <path>` |
| Find hardcoded secrets in files | `sonar analyze secrets <paths...>` |
| Deep server-side analysis (Cloud only) | `sonar analyze sqaa --file <path>` |
| Full project analysis on a branch (Community Edition) | `python scripts/scan_branch.py --branch <name> --project-key <key>` |
| Full project analysis with branch analysis (Developer+) | `python scripts/scan_branch.py --branch <name> --project-key <key> --use-branch` |
| Run sonar-scanner directly (Community Edition) | `git checkout <branch> && sonar-scanner -Dsonar.projectKey=<key>` |
| Run sonar-scanner directly (Developer+) | `sonar-scanner -Dsonar.projectKey=<key> -Dsonar.branch.name=<branch>` |
| View existing issues in a project | `sonar list issues -p <project>` |
| Browse available projects | `sonar list projects` |
| Call any SonarQube API | `sonar api <method> <endpoint>` |
| Stop secrets from leaking via Git | `sonar integrate git` |
| Protect AI coding sessions | `sonar integrate claude` |
