#!/usr/bin/env python3
"""Build local git repository fixtures and optionally publish GitHub PR fixtures."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote, urlencode, urlparse

DEFAULT_FIXTURE_DIR = "example"
OUTPUT_REPO = "repo"

MESSAGE_FILE = ".message"
MERGE_FILE = ".merge"
PULL_REQUESTS_FILE = ".pullrequests.json"
REMOTE_FILE = ".remote"
ENV_FILE = ".env"

GITHUB_TOKEN_ENV = "GITHUB_TOKEN"
GITHUB_API_URL = "https://api.github.com"
GITHUB_API_VERSION = "2022-11-28"


@dataclass(frozen=True)
class PullRequestSpec:
    """A pull request that should exist in the generated remote test repo."""

    title: str
    head: str
    base: str
    body: str = ""
    merge: bool = False

    @classmethod
    def from_json(cls, item: dict, index: int) -> "PullRequestSpec":
        for field in ("title", "head", "base"):
            if not item.get(field):
                raise ValueError(f"{PULL_REQUESTS_FILE} entry {index} is missing '{field}'.")
        return cls(
            title=item["title"],
            head=item["head"],
            base=item["base"],
            body=item.get("body", ""),
            merge=item.get("merge", False),
        )


@dataclass(frozen=True)
class MergeEvent:
    """Local history point needed to create and merge a GitHub PR in order."""

    base: str
    head: str
    base_sha: str
    head_sha: str


@dataclass(frozen=True)
class GeneratedRepository:
    git: "GitRepository"
    branches: set[str]
    merge_events: list[MergeEvent]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a git repository from a sequence of commit folders.")
    parser.add_argument(
        "root_dir",
        nargs="?",
        default=DEFAULT_FIXTURE_DIR,
        help="Directory containing c* commit folders.",
    )
    return parser.parse_args()


def run(command: list[str], check: bool = True, **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(command, check=check, **kwargs)


def load_env_file(path: Path) -> None:
    """Load simple KEY=VALUE entries without replacing existing environment values."""
    if not path.exists():
        return

    with path.open() as env_file:
        for line in env_file:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            if line.startswith("export "):
                line = line[len("export ") :].strip()
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def load_environment(script_dir: Path, fixture_dir: Path) -> None:
    load_env_file(script_dir / ENV_FILE)
    load_env_file(fixture_dir / ENV_FILE)


def read_optional_text(path: Path) -> str | None:
    if not path.exists():
        return None
    return path.read_text().strip()


def commit_directories(fixture_dir: Path) -> list[Path]:
    return sorted(path for path in fixture_dir.glob("c*") if path.is_dir())


def branch_name_for(directory: Path) -> str:
    if "--" not in directory.name:
        return "main"
    return directory.name.split("--", 1)[1]


def read_message(directory: Path) -> str:
    return (directory / MESSAGE_FILE).read_text().strip()


def read_merge_branch(directory: Path) -> str | None:
    return read_optional_text(directory / MERGE_FILE)


def copy_commit_contents(commit_dir: Path, output_dir: Path) -> None:
    for entry in commit_dir.iterdir():
        if entry.name in (MESSAGE_FILE, MERGE_FILE):
            continue

        destination = output_dir / entry.name
        if entry.is_dir():
            shutil.copytree(entry, destination, dirs_exist_ok=True)
        else:
            shutil.copy2(entry, destination)


class GitRepository:
    """Small wrapper around git commands scoped to one repository."""

    def __init__(self, path: Path):
        self.path = path

    def init(self) -> None:
        if self.path.exists():
            shutil.rmtree(self.path)
        run(["git", "init", "-b", "main", str(self.path)])

    def git(self, args: list[str], check: bool = True, **kwargs) -> subprocess.CompletedProcess:
        return run(["git", "-C", str(self.path), *args], check=check, **kwargs)

    def switch_or_create(self, branch_name: str) -> None:
        switch = self.git(
            ["switch", branch_name],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if switch.returncode != 0:
            self.git(["switch", "-c", branch_name])

    def add_all(self) -> None:
        self.git(["add", "."])

    def commit(self, message: str) -> None:
        self.git(["commit", "-m", message])

    def has_staged_changes(self) -> bool:
        return self.git(["diff", "--cached", "--quiet"], check=False).returncode != 0

    def merge_no_ff(self, branch_name: str, message: str) -> None:
        self.git(["merge", "--no-ff", branch_name, "-m", message])

    def rev_parse(self, ref: str) -> str:
        result = self.git(["rev-parse", ref], capture_output=True, text=True)
        return result.stdout.strip()

    def add_remote(self, name: str, url: str) -> None:
        self.git(["remote", "add", name, url])

    def push_all_force(self) -> None:
        self.git(["push", "--all", "--force"])

    def push_ref_force(self, sha: str, branch_name: str) -> None:
        self.git(["push", "--force", "origin", f"{sha}:refs/heads/{branch_name}"])

    def show_branches(self) -> None:
        self.git(["show-branch", "--all"])


class RepositoryGenerator:
    """Apply ordered fixture folders to a freshly generated repository."""

    def __init__(self, fixture_dir: Path, output_dir: Path):
        self.fixture_dir = fixture_dir
        self.repository = GitRepository(output_dir)
        self.branches: set[str] = set()
        self.branch_heads: dict[str, str] = {}
        self.merge_events: list[MergeEvent] = []

    def generate(self) -> GeneratedRepository:
        """Build the local fixture repo and record branch merge points for publishing."""
        self.repository.init()
        for commit_dir in commit_directories(self.fixture_dir):
            self.apply_commit_directory(commit_dir)
        return GeneratedRepository(self.repository, self.branches, self.merge_events)

    def apply_commit_directory(self, commit_dir: Path) -> None:
        branch_name = branch_name_for(commit_dir)
        message = read_message(commit_dir)
        self.branches.add(branch_name)
        self.repository.switch_or_create(branch_name)

        merge_branch = read_merge_branch(commit_dir)
        if merge_branch:
            self.apply_merge(commit_dir.name, branch_name, merge_branch, message)

        copy_commit_contents(commit_dir, self.repository.path)
        self.repository.add_all()
        if self.repository.has_staged_changes():
            self.repository.commit(message)
        self.branch_heads[branch_name] = self.repository.rev_parse(branch_name)

    def apply_merge(self, directory_name: str, base_branch: str, head_branch: str, message: str) -> None:
        if head_branch not in self.branch_heads:
            raise ValueError(f"{directory_name} merges unknown branch '{head_branch}'.")

        base_sha = self.repository.rev_parse(base_branch)
        head_sha = self.branch_heads[head_branch]
        self.repository.merge_no_ff(head_branch, message)
        self.merge_events.append(MergeEvent(base_branch, head_branch, base_sha, head_sha))


def load_pull_requests(fixture_dir: Path, script_dir: Path) -> list[PullRequestSpec]:
    fixture_path = fixture_dir / PULL_REQUESTS_FILE
    script_path = script_dir / PULL_REQUESTS_FILE
    path = fixture_path if fixture_path.exists() else script_path
    if not path.exists():
        return []
    return read_pull_requests(path)


def read_pull_requests(path: Path) -> list[PullRequestSpec]:
    data = json.loads(path.read_text())
    if not isinstance(data, list):
        raise ValueError(f"{PULL_REQUESTS_FILE} must contain a JSON array.")
    return [PullRequestSpec.from_json(item, index) for index, item in enumerate(data, start=1)]


def validate_pull_requests(pull_requests: list[PullRequestSpec], branches: set[str]) -> None:
    for pull_request in pull_requests:
        for field, branch_name in (("head", pull_request.head), ("base", pull_request.base)):
            if ":" not in branch_name and branch_name not in branches:
                raise ValueError(
                    f"Pull request '{pull_request.title}' references unknown {field} branch '{branch_name}'."
                )


def find_merge_event(merge_events: list[MergeEvent], pull_request: PullRequestSpec) -> MergeEvent:
    for merge_event in merge_events:
        if merge_event.base == pull_request.base and merge_event.head == pull_request.head:
            return merge_event
    raise ValueError(
        f"Pull request '{pull_request.title}' is marked for merge, "
        f"but no {MERGE_FILE} step merges '{pull_request.head}' into '{pull_request.base}'."
    )


def parse_github_repo(remote_url: str) -> tuple[str, str]:
    if remote_url.startswith("git@"):
        _, path = remote_url.split(":", 1)
    else:
        path = urlparse(remote_url).path

    path = path.strip("/")
    if path.endswith(".git"):
        path = path[:-4]

    parts = path.split("/")
    if len(parts) != 2:
        raise ValueError(f"Could not determine GitHub owner/repo from remote URL: {remote_url}")
    return parts[0], parts[1]


def next_link(link_header: str | None) -> str | None:
    if not link_header:
        return None
    for link in link_header.split(","):
        url, rel = link.split(";", 1)
        if 'rel="next"' in rel:
            return url.strip()[1:-1]
    return None


class GitHubClient:
    """Minimal GitHub REST client for the test-repo publishing workflow."""

    def __init__(self, token: str):
        self.token = token

    def headers(self, has_body: bool = False) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self.token}",
            "User-Agent": "reprogit",
            "X-GitHub-Api-Version": GITHUB_API_VERSION,
        }
        if has_body:
            headers["Content-Type"] = "application/json"
        return headers

    def request(self, method: str, url: str, payload: dict | None = None):
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = urllib.request.Request(
            url,
            data=data,
            headers=self.headers(payload is not None),
            method=method,
        )
        try:
            with urllib.request.urlopen(request) as response:
                body = response.read().decode("utf-8")
                return json.loads(body) if body else None
        except urllib.error.HTTPError as error:
            if method == "DELETE" and error.code == 404:
                return None
            details = error.read().decode("utf-8")
            raise RuntimeError(f"GitHub {method} {url} returned {error.code}: {details}") from error

    def paginated_request(self, url: str, results_key: str | None = None) -> list:
        results = []
        while url:
            request = urllib.request.Request(url, headers=self.headers(), method="GET")
            try:
                with urllib.request.urlopen(request) as response:
                    page = json.loads(response.read().decode("utf-8"))
                    results.extend(page[results_key] if results_key else page)
                    url = next_link(response.headers.get("Link"))
            except urllib.error.HTTPError as error:
                details = error.read().decode("utf-8")
                raise RuntimeError(f"GitHub GET {url} returned {error.code}: {details}") from error
        return results

    def repo_url(self, remote_url: str) -> str:
        owner, repo = parse_github_repo(remote_url)
        return f"{GITHUB_API_URL}/repos/{owner}/{repo}"

    def clean_repository(self, remote_url: str) -> None:
        """Clean disposable GitHub state while preserving the default branch ref."""
        repo_url = self.repo_url(remote_url)
        default_branch = self.request("GET", repo_url)["default_branch"]
        self.close_open_pull_requests(repo_url)
        self.delete_workflow_runs(repo_url)
        self.delete_non_default_branches(repo_url, default_branch)

    def close_open_pull_requests(self, repo_url: str) -> None:
        pulls = self.paginated_request(
            f"{repo_url}/pulls?{urlencode({'state': 'open', 'per_page': 100})}"
        )
        for pull_request in pulls:
            closed = self.request("PATCH", pull_request["url"], {"state": "closed"})
            print(f"Pull request closed: {closed['html_url']}")

    def delete_workflow_runs(self, repo_url: str) -> None:
        runs_url = f"{repo_url}/actions/runs?{urlencode({'per_page': 100})}"
        for run_data in self.paginated_request(runs_url, "workflow_runs"):
            self.request("DELETE", f"{repo_url}/actions/runs/{run_data['id']}")
            print(f"Workflow run deleted: {run_data['id']}")

    def delete_non_default_branches(self, repo_url: str, default_branch: str) -> None:
        branches = self.paginated_request(f"{repo_url}/branches?{urlencode({'per_page': 100})}")
        for branch in branches:
            branch_name = branch["name"]
            if branch_name == default_branch:
                continue
            encoded_branch = quote(branch_name, safe="")
            self.request("DELETE", f"{repo_url}/git/refs/heads/{encoded_branch}")
            print(f"Branch deleted: {branch_name}")

    def create_or_update_pull_request(self, remote_url: str, pull_request: PullRequestSpec) -> dict:
        owner, _ = parse_github_repo(remote_url)
        api_url = f"{self.repo_url(remote_url)}/pulls"
        query_head = pull_request.head if ":" in pull_request.head else f"{owner}:{pull_request.head}"
        query = urlencode({"state": "open", "head": query_head, "base": pull_request.base})
        existing_pull_requests = self.request("GET", f"{api_url}?{query}")

        payload = {
            "title": pull_request.title,
            "body": pull_request.body,
            "base": pull_request.base,
        }

        if existing_pull_requests:
            updated = self.request("PATCH", existing_pull_requests[0]["url"], payload)
            print(f"Pull request updated: {updated['html_url']}")
            return updated

        payload["head"] = pull_request.head
        created = self.request("POST", api_url, payload)
        print(f"Pull request created: {created['html_url']}")
        return created

    def merge_pull_request(self, pull_request: PullRequestSpec, github_pull_request: dict) -> None:
        merged = self.request(
            "PUT",
            f"{github_pull_request['url']}/merge",
            {
                "commit_title": pull_request.title,
                "merge_method": "merge",
            },
        )
        if merged and merged.get("merged"):
            print(f"Pull request merged: {github_pull_request['html_url']}")


def confirm_remote_write(remote_url: str) -> bool:
    print(f"The resulting repository will be configured with a remote to {remote_url}.")
    print(
        "WARNING: This may close pull requests, delete workflow runs, delete branches, "
        "and force-push generated branches."
    )
    response = input("Enter `yes` to continue, anything else to abort: ").strip().lower()
    return response == "yes"


def publish_repository(
    generated: GeneratedRepository,
    remote_url: str,
    pull_requests: list[PullRequestSpec],
    token: str | None,
) -> None:
    """Push generated history and replay configured GitHub pull requests."""
    print(f"Setting up remote {remote_url}...")
    generated.git.add_remote("origin", remote_url)

    if not pull_requests:
        print("All ready. Now you can push the resulting repository to the remote with the following command:")
        print(f"git -C {generated.git.path} push --all --force")
        return

    if not token:
        raise ValueError(f"Cannot create pull requests: {GITHUB_TOKEN_ENV} is not set.")

    github = GitHubClient(token)
    print("Cleaning remote repository...")
    github.clean_repository(remote_url)

    for pull_request in (pull_request for pull_request in pull_requests if pull_request.merge):
        merge_event = find_merge_event(generated.merge_events, pull_request)
        generated.git.push_ref_force(merge_event.base_sha, merge_event.base)
        generated.git.push_ref_force(merge_event.head_sha, merge_event.head)
        github_pull_request = github.create_or_update_pull_request(remote_url, pull_request)
        github.merge_pull_request(pull_request, github_pull_request)

    print("Pushing all generated branches...")
    generated.git.push_all_force()

    for pull_request in (pull_request for pull_request in pull_requests if not pull_request.merge):
        github.create_or_update_pull_request(remote_url, pull_request)


def main() -> int:
    args = parse_args()
    script_dir = Path(__file__).resolve().parent
    fixture_dir = Path(args.root_dir)

    load_environment(script_dir, fixture_dir)
    pull_requests = load_pull_requests(fixture_dir, script_dir)

    generated = RepositoryGenerator(fixture_dir, Path(OUTPUT_REPO)).generate()
    validate_pull_requests(pull_requests, generated.branches)

    print()
    print("Branches and commits in the resulting repository:", flush=True)
    generated.git.show_branches()
    print()

    remote_url = read_optional_text(fixture_dir / REMOTE_FILE)
    if not remote_url:
        if pull_requests:
            print(f"Cannot create pull requests from {PULL_REQUESTS_FILE}: no {REMOTE_FILE} file was found.")
            return 1
        return 0

    token = os.getenv(GITHUB_TOKEN_ENV)
    if pull_requests and not token:
        print(f"Cannot create pull requests: {GITHUB_TOKEN_ENV} is not set.")
        return 1

    if not confirm_remote_write(remote_url):
        print("Aborting.")
        return 0

    try:
        publish_repository(generated, remote_url, pull_requests, token)
    except ValueError as error:
        print(error)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
