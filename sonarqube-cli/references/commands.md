# SonarQube CLI — Full Command Reference

Complete reference for all `sonar` CLI commands, subcommands, options, and examples.

## Table of Contents

1. [sonar api](#sonar-api)
2. [sonar auth login](#sonar-auth-login)
3. [sonar auth logout](#sonar-auth-logout)
4. [sonar auth purge](#sonar-auth-purge)
5. [sonar auth status](#sonar-auth-status)
6. [sonar analyze secrets](#sonar-analyze-secrets)
7. [sonar analyze sqaa](#sonar-analyze-sqaa)
8. [sonar list issues](#sonar-list-issues)
9. [sonar list projects](#sonar-list-projects)
10. [sonar verify](#sonar-verify)
11. [sonar integrate claude](#sonar-integrate-claude)
12. [sonar integrate git](#sonar-integrate-git)
13. [sonar config telemetry](#sonar-config-telemetry)
14. [sonar self-update](#sonar-self-update)

---

## sonar api

Make authenticated API requests to SonarQube. Automatically handles authentication and routes between V1/V2 APIs based on the endpoint path.

**Arguments:**

| Argument     | Description                                                              |
| ------------ | ------------------------------------------------------------------------ |
| `<method>`   | HTTP method (`get`, `post`, `patch`, `put`, `delete`)                    |
| `<endpoint>` | API endpoint path. Must start with `/` and can contain query parameters. |

**Options:**

| Option            | Type    | Required | Description                                                                      | Default |
| ----------------- | ------- | -------- | -------------------------------------------------------------------------------- | ------- |
| `--data`, `-d`    | string  | No       | JSON string for request body. Automatically formatted as form data or JSON body. | -       |
| `--verbose`, `-v` | boolean | No       | Print request and response details for debugging.                                | -       |

**Examples:**

```bash
sonar api get "/api/favorites/search"
sonar api get "/api/rules/search?organization=org-name"
sonar api post "/api/user_tokens/generate" --data '{"name":"my-new-token"}'
sonar api post "/api/issues/do_transition" --data '{"issue":"issue-id","transition":"accept"}'
sonar api get "/analysis/engine"
```

**API docs:**
- Cloud: https://docs.sonarsource.com/sonarqube-cloud/appendices/web-api
- Server: https://docs.sonarsource.com/sonarqube-server/extension-guide/web-api

---

## sonar auth login

Save an authentication token to the system keychain.

**Options:**

| Option               | Type   | Required | Description                                                     | Default |
| -------------------- | ------ | -------- | --------------------------------------------------------------- | ------- |
| `--server`, `-s`     | string | No       | SonarQube server URL (default is SonarQube Cloud)               | -       |
| `--org`, `-o`        | string | No       | SonarQube Cloud organization key (required for SonarQube Cloud) | -       |
| `--with-token`, `-t` | string | No       | Token value (skips browser, non-interactive mode)               | -       |

**Examples:**

```bash
sonar auth login                                          # Interactive (opens browser)
sonar auth login -o my-org -t squ_abc123                  # Non-interactive, Cloud
sonar auth login -s https://my-sonarqube.io --with-token squ_def456  # Self-hosted
```

**Note:** Only user tokens are supported. Project tokens, global tokens, and scoped organization tokens will not work.

---

## sonar auth logout

Remove the active authentication token from the keychain.

```bash
sonar auth logout
```

---

## sonar auth purge

Remove all authentication tokens from the keychain (interactive).

```bash
sonar auth purge
```

---

## sonar auth status

Show the active authentication connection with token verification.

```bash
sonar auth status
```

---

## sonar analyze secrets

Scan files or stdin for hardcoded secrets (API keys, tokens, passwords, certificates, etc.).

**Arguments:**

| Argument   | Description                                 |
| ---------- | ------------------------------------------- |
| `[paths…]` | File or directory paths to scan for secrets |

**Options:**

| Option    | Type    | Required | Description                               | Default |
| --------- | ------- | -------- | ----------------------------------------- | ------- |
| `--stdin` | boolean | No       | Read from standard input instead of paths | -       |

**Examples:**

```bash
sonar analyze secrets src/config.ts           # Single file
sonar analyze secrets src/config.ts src/secrets/  # Multiple paths
cat .env | sonar analyze secrets --stdin       # Stdin / pipeline
```

**Exit codes:** Non-zero when secrets are found. Suitable for CI/CD gating.

---

## sonar analyze sqaa

Run SonarQube Agentic Analysis — server-side analysis on a file. **SonarQube Cloud only.**

**Options:**

| Option              | Type   | Required | Description                                                   | Default |
| ------------------- | ------ | -------- | ------------------------------------------------------------- | ------- |
| `--file`            | string | Yes      | File path to analyze                                          | -       |
| `--branch`          | string | No       | Branch name for analysis context                              | -       |
| `-p`, `--project`   | string | No       | SonarQube Cloud project key (overrides auto-detected project) | -       |

**Examples:**

```bash
sonar analyze sqaa --file src/app.ts
sonar analyze sqaa --file src/app.ts --branch main
sonar analyze sqaa --file src/app.ts -p my-project
```

---

## sonar list issues

Search for issues in SonarQube.

**Options:**

| Option            | Type   | Required | Description        | Default |
| ----------------- | ------ | -------- | ------------------ | ------- |
| `-p`, `--project` | string | Yes      | Project key        | -       |
| `--severity`      | string | No       | Filter by severity | -       |
| `--format`        | string | No       | Output format      | `json`  |
| `--branch`        | string | No       | Branch name        | -       |
| `--pull-request`  | string | No       | Pull request ID    | -       |
| `--page-size`     | number | No       | Page size (1-500)  | `500`   |
| `--page`          | number | No       | Page number        | `1`     |

**Examples:**

```bash
sonar list issues -p my-project
sonar list issues -p my-project --severity CRITICAL
sonar list issues -p my-project --format toon
sonar list issues -p my-project --branch main
sonar list issues -p my-project --page 2 --page-size 50
```

The `--format toon` output is optimized for AI agent consumption.

---

## sonar list projects

Search for projects in SonarQube.

**Options:**

| Option          | Type   | Required | Description                                    | Default |
| --------------- | ------ | -------- | ---------------------------------------------- | ------- |
| `-q`, `--query` | string | No       | Search query to filter projects by name or key | -       |
| `--page`        | number | No       | Page number                                    | `1`     |
| `--page-size`   | number | No       | Page size (1-500)                              | `500`   |

**Examples:**

```bash
sonar list projects
sonar list projects -q my-project
sonar list projects --page 2 --page-size 50
```

---

## sonar verify

Analyze a single file for issues (local + server-side combined).

**Options:**

| Option              | Type   | Required | Description                                                   | Default |
| ------------------- | ------ | -------- | ------------------------------------------------------------- | ------- |
| `--file`            | string | Yes      | File path to analyze                                          | -       |
| `--branch`          | string | No       | Branch name for analysis context                              | -       |
| `-p`, `--project`   | string | No       | SonarQube Cloud project key (overrides auto-detected project) | -       |

**Examples:**

```bash
sonar verify --file src/app.ts
sonar verify --file src/app.ts --branch main
sonar verify --file src/app.ts -p my-project
```

---

## sonar integrate claude

Set up SonarQube integration for Claude Code. Installs secrets scanning hooks and configures the SonarQube MCP Server.

**Options:**

| Option              | Type    | Required | Description                                                                  | Default |
| ------------------- | ------- | -------- | ---------------------------------------------------------------------------- | ------- |
| `-p`, `--project`   | string  | No       | Project key                                                                  | -       |
| `--non-interactive` | boolean | No       | Non-interactive mode (no prompts)                                            | -       |
| `-g`, `--global`    | boolean | No       | Install hooks and config globally to ~/.claude instead of project directory | -       |

**Examples:**

```bash
sonar integrate claude -p my-project                        # Interactive
sonar integrate claude -g -p my-project                     # Global
sonar integrate claude -p my-project --non-interactive      # Non-interactive
```

After installation, restart Claude Code for hooks to take effect.

---

## sonar integrate git

Install a Git hook that scans for secrets automatically.

**Options:**

| Option              | Type    | Required | Description                                                                                      | Default |
| ------------------- | ------- | -------- | ------------------------------------------------------------------------------------------------ | ------- |
| `--hook`            | string  | No       | Hook type: `pre-commit` (scan staged files) or `pre-push` (scan files in unpushed commits)       | -       |
| `--force`           | boolean | No       | Overwrite an existing hook if it is not from `sonar integrate git`                               | -       |
| `--non-interactive` | boolean | No       | Non-interactive mode (no prompts)                                                                | -       |
| `--global`          | boolean | No       | Install hook globally for all repositories (sets `git config --global core.hooksPath`)           | -       |

**Examples:**

```bash
sonar integrate git                                         # Interactive (pre-commit)
sonar integrate git --hook pre-push                         # Pre-push hook
sonar integrate git --global                                # Global
sonar integrate git --hook pre-push --global --non-interactive  # Full non-interactive
sonar integrate git --force                                 # Overwrite existing hook
```

---

## sonar config telemetry

Configure anonymous usage statistics collection.

**Options:**

| Option       | Type    | Required | Description                                      | Default |
| ------------ | ------- | -------- | ------------------------------------------------ | ------- |
| `--enabled`  | boolean | No       | Enable collection of anonymous usage statistics  | -       |
| `--disabled` | boolean | No       | Disable collection of anonymous usage statistics | -       |

```bash
sonar config telemetry --enabled
sonar config telemetry --disabled
```

---

## sonar self-update

Update the SonarQube CLI to the latest version.

**Options:**

| Option     | Type    | Required | Description                                           | Default |
| ---------- | ------- | -------- | ----------------------------------------------------- | ------- |
| `--status` | boolean | No       | Check for a newer version without installing          | -       |
| `--force`  | boolean | No       | Install the latest version even if already up to date | -       |

```bash
sonar self-update              # Update to latest
sonar self-update --status     # Check only
sonar self-update --force      # Force reinstall
```
