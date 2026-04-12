---
name: sonarqube-cli
description: |
  Use this skill whenever the user wants to interact with SonarQube via the `sonar` CLI tool.
  This covers all SonarQube CLI workflows including: scanning code for issues and secrets,
  authenticating with SonarQube Cloud or Server, listing issues and projects, making
  authenticated API requests, integrating with Claude Code or Git hooks, running server-side
  analysis (SQAA), verifying files, and managing CLI configuration. Trigger when the user
  mentions "sonar", "sonarqube", "sonar cli", "sonarqube cli", "sonar analyze", "sonar verify",
  "sonar scan", "sonar secrets", code quality scanning, secrets scanning, or wants to integrate
  SonarQube into their workflow. Also trigger when the user asks about detecting hardcoded secrets,
  preventing secret leaks in commits, or setting up pre-commit/pre-push hooks for security scanning.
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

## Decision Guide

When a user asks to "scan" or "check" code, choose the right command:

| Need | Command |
|---|---|
| Check a single file for all issues | `sonar verify --file <path>` |
| Find hardcoded secrets in files | `sonar analyze secrets <paths...>` |
| Deep server-side analysis (Cloud only) | `sonar analyze sqaa --file <path>` |
| View existing issues in a project | `sonar list issues -p <project>` |
| Browse available projects | `sonar list projects` |
| Call any SonarQube API | `sonar api <method> <endpoint>` |
| Stop secrets from leaking via Git | `sonar integrate git` |
| Protect AI coding sessions | `sonar integrate claude` |
