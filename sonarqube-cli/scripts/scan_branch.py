#!/usr/bin/env python3
"""SonarQube branch scanner with quality gate checking.

Orchestrates a full sonar-scanner analysis on a given branch, waits for
completion, then reports the quality gate result. If the gate fails it
prints the list of issues found by the analysis.

This script works with SonarQube Community Edition by default: it checks
out the git ref you provide and runs the scan against the single project
context (no branch parameter). If you have Developer Edition or above,
use --use-branch to enable true branch analysis.

Requirements:
  - sonar-scanner must be on PATH
  - git must be on PATH
  - Environment variables SONAR_HOST_URL and SONAR_TOKEN must be set
  - sonar-scanner must have write access to .scannerwork/ in the project

Environment variables:
  SONAR_HOST_URL  - SonarQube server URL (e.g. https://sonarqube.example.com)
  SONAR_TOKEN     - SonarQube authentication token (stored in $SONAR_TOKEN)
  SONAR_PROJECT_KEY - (optional) Default project key, overridden by --project-key

Usage:
  export SONAR_HOST_URL="https://your-sonarqube.example.com"
  export SONAR_TOKEN="squ_your_token_here"
  python scan_branch.py --branch feature/my-branch --project-key my-project
  python scan_branch.py --branch develop --project-key my-project --project-dir ./src
  python scan_branch.py --branch main --project-key my-project --use-branch --timeout 900
"""

import argparse
import base64
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


def log(msg: str) -> None:
    print(f"[scan_branch] {msg}", flush=True)


def die(msg: str, code: int = 1) -> None:
    print(f"[scan_branch] ERROR: {msg}", file=sys.stderr, flush=True)
    sys.exit(code)


def make_auth_header(token: str) -> str:
    encoded = base64.b64encode(f"{token}:".encode()).decode()
    return f"Basic {encoded}"


def api_get(url: str, token: str) -> dict:
    req = urllib.request.Request(url)
    req.add_header("Authorization", make_auth_header(token))
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        die(f"API request failed ({e.code}): {body}")
    except urllib.error.URLError as e:
        die(f"Connection error: {e.reason}")


def run_scanner(project_key: str, project_name: str, project_dir: str, branch_name: str | None, extra_args: list[str]) -> str:
    cmd = [
        "sonar-scanner",
        f"-Dsonar.projectKey={project_key}",
        f"-Dsonar.projectName={project_name}",
    ]
    if branch_name:
        cmd.append(f"-Dsonar.branch.name={branch_name}")
    if project_dir:
        cmd.append(f"-Dsonar.projectBaseDir={project_dir}")
    cmd.extend(extra_args)

    log(f"Running: {' '.join(cmd)}")
    try:
        subprocess.run(cmd, check=True)
    except FileNotFoundError:
        die("sonar-scanner not found on PATH. Install it from https://docs.sonarsource.com/sonarqube/latest/analyzing-source-code/scanners/sonarscanner/")
    except subprocess.CalledProcessError as e:
        die(f"sonar-scanner exited with code {e.returncode}")

    report_path = Path(project_dir or ".") / ".scannerwork" / "report-task.txt"
    if not report_path.exists():
        die(f"Report file not found at {report_path}")
    return report_path.read_text()


def parse_report(content: str) -> dict[str, str]:
    result = {}
    for line in content.strip().splitlines():
        if "=" in line:
            key, _, value = line.partition("=")
            result[key.strip()] = value.strip()
    return result


def wait_for_analysis(host_url: str, token: str, task_id: str, timeout: int, poll_interval: int = 5) -> dict:
    url = f"{host_url.rstrip('/')}/api/ce/task?id={task_id}"
    deadline = time.time() + timeout

    log(f"Waiting for analysis task {task_id} (timeout: {timeout}s)...")
    while time.time() < deadline:
        data = api_get(url, token)
        task = data.get("task", {})
        status = task.get("status", "UNKNOWN")
        log(f"  Task status: {status}")

        if status in ("SUCCESS",):
            return task
        if status in ("FAILED", "CANCELED"):
            die(f"Analysis task {status}: {task.get('errorMessage', 'no details')}")

        time.sleep(poll_interval)

    die(f"Timed out waiting for analysis after {timeout}s")


def check_quality_gate(host_url: str, token: str, project_key: str, branch: str | None = None) -> dict:
    params = {"projectKey": project_key}
    if branch:
        params["branch"] = branch
    url = f"{host_url.rstrip('/')}/api/qualitygates/project_status?{urllib.parse.urlencode(params)}"
    data = api_get(url, token)
    return data.get("projectStatus", {})


def fetch_issues(host_url: str, token: str, project_key: str, branch: str | None = None, page_size: int = 500) -> list[dict]:
    all_issues = []
    page = 1
    while True:
        params = {
            "projectKeys": project_key,
            "ps": str(page_size),
            "p": str(page),
        }
        if branch:
            params["branch"] = branch
        url = f"{host_url.rstrip('/')}/api/issues/search?{urllib.parse.urlencode(params)}"
        data = api_get(url, token)
        issues = data.get("issues", [])
        all_issues.extend(issues)
        total = data.get("paging", {}).get("total", len(issues))
        if len(all_issues) >= total or not issues:
            break
        page += 1
    return all_issues


SEVERITY_ORDER = {"BLOCKER": 0, "CRITICAL": 1, "MAJOR": 2, "MINOR": 3, "INFO": 4}


def format_issues(issues: list[dict]) -> str:
    if not issues:
        return "No issues found."

    sorted_issues = sorted(
        issues,
        key=lambda i: SEVERITY_ORDER.get(i.get("severity", "INFO"), 99),
    )

    lines = [f"{'SEVERITY':<10} {'TYPE':<15} {'COMPONENT':<40} MESSAGE"]
    lines.append("-" * len(lines[0]) + "-" * 60)
    for issue in sorted_issues:
        severity = issue.get("severity", "?")
        issue_type = issue.get("type", "?")
        component = issue.get("component", "?")
        message = issue.get("message", "").replace("\n", " ")
        line_num = issue.get("line", "")
        location = f"{component}:{line_num}" if line_num else component
        lines.append(f"{severity:<10} {issue_type:<15} {location:<40} {message}")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run sonar-scanner on a branch and report quality gate results.",
    )
    parser.add_argument("--branch", required=True, help="Git branch or ref to checkout before scanning")
    parser.add_argument("--project-key", help="SonarQube project key (default: SONAR_PROJECT_KEY env var)")
    parser.add_argument("--project-name", help="SonarQube project display name (default: project key)")
    parser.add_argument("--project-dir", default="", help="Project base directory (passed to sonar.projectBaseDir)")
    parser.add_argument("--timeout", type=int, default=600, help="Max seconds to wait for analysis (default: 600)")
    parser.add_argument("--poll-interval", type=int, default=5, help="Seconds between status polls (default: 5)")
    parser.add_argument("--use-branch", action="store_true", help="Pass sonar.branch.name to scanner (requires Developer Edition+). Default: off, for Community Edition compatibility.")
    parser.add_argument("extra", nargs="*", help="Additional arguments passed to sonar-scanner")
    args = parser.parse_args()

    host_url = os.environ.get("SONAR_HOST_URL", "")
    token = os.environ.get("SONAR_TOKEN", "")
    project_key = args.project_key or os.environ.get("SONAR_PROJECT_KEY", "")

    if not host_url:
        die("SONAR_HOST_URL environment variable is not set")
    if not token:
        die("SONAR_TOKEN environment variable is not set")
    if not project_key:
        die("--project-key or SONAR_PROJECT_KEY environment variable is required")

    project_name = args.project_name or project_key
    scanner_branch = args.branch if args.use_branch else None

    log(f"SonarQube: {host_url}")
    log(f"Project:   {project_key}")
    log(f"Ref:       {args.branch}")
    if args.use_branch:
        log(f"Branch analysis: enabled (sonar.branch.name={args.branch})")
    else:
        log("Branch analysis: disabled (Community Edition mode — results update the main project context)")

    log(f"Checking out {args.branch}...")
    try:
        subprocess.run(["git", "fetch", "--unshallow"], check=False, capture_output=True)
        subprocess.run(["git", "checkout", args.branch], check=True, capture_output=True)
    except FileNotFoundError:
        die("git not found on PATH. This script requires git to checkout the target branch.")
    except subprocess.CalledProcessError as e:
        die(f"Failed to checkout {args.branch}: {e.stderr.decode(errors='replace').strip() if e.stderr else 'unknown error'}")

    report_content = run_scanner(project_key, project_name, args.project_dir, scanner_branch, args.extra)
    report = parse_report(report_content)

    task_id = report.get("ceTaskId", "")
    if not task_id:
        die("Could not extract ceTaskId from scanner report")

    task = wait_for_analysis(host_url, token, task_id, args.timeout, args.poll_interval)
    log(f"Analysis completed: {task.get('status')}")

    log("Checking quality gate...")
    gate = check_quality_gate(host_url, token, project_key, branch=scanner_branch)
    status = gate.get("status", "UNKNOWN")
    log(f"Quality gate status: {status}")

    if status == "OK":
        print()
        print("=" * 60)
        print("  QUALITY GATE PASSED - Everything looks good!")
        print("=" * 60)
        sys.exit(0)

    print()
    print("=" * 60)
    print(f"  QUALITY GATE FAILED ({status})")
    print("=" * 60)
    print()

    conditions = gate.get("conditions", [])
    if conditions:
        print("Failed conditions:")
        for cond in conditions:
            metric = cond.get("metricKey", "?")
            op = cond.get("operator", "?")
            val = cond.get("actualValue", "?")
            threshold = cond.get("errorThreshold", "?")
            print(f"  - {metric} {val} {op} {threshold}")
        print()

    log("Fetching issues...")
    issues = fetch_issues(host_url, token, project_key, branch=scanner_branch)
    print(f"Issues found: {len(issues)}")
    print()
    print(format_issues(issues))
    sys.exit(1)


if __name__ == "__main__":
    main()
