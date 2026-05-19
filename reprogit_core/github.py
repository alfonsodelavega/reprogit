import json
import urllib.error
import urllib.request
from urllib.parse import quote, urlencode, urlparse

from .config import GITHUB_API_URL, GITHUB_API_VERSION
from .models import PullRequestSpec


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
