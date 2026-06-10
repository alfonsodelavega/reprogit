from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from .config import GITHUB_TOKEN_ENV, WORKFLOW_EVENT_LOOKBACK_SECONDS
from .github import GitHubClient
from .models import GeneratedRepository, PullRequestSpec


@dataclass(frozen=True)
class PendingWorkflowWait:
    pull_request: dict
    head_branch: str
    head_sha: str
    triggered_after: datetime


def local_branch_name(branch_name: str) -> str | None:
    if ":" in branch_name:
        return None
    return branch_name


def workflow_event_started_at() -> datetime:
    return datetime.now(timezone.utc) - timedelta(seconds=WORKFLOW_EVENT_LOOKBACK_SECONDS)


def pull_request_can_be_created(
    pull_request: PullRequestSpec,
    pushed_branches: set[str],
) -> bool:
    head = local_branch_name(pull_request.head)
    base = local_branch_name(pull_request.base)
    return (head is None or head in pushed_branches) and (base is None or base in pushed_branches)


def wait_for_pending_workflow(
    github: GitHubClient,
    remote_url: str,
    pending_waits: dict[str, PendingWorkflowWait],
    branch_name: str,
) -> None:
    pending = pending_waits.pop(branch_name, None)
    if not pending:
        return

    github.wait_for_pull_request_workflows(
        remote_url,
        pending.pull_request,
        pending.head_branch,
        pending.head_sha,
        pending.triggered_after,
    )


def publish_pull_request_timeline(
    generated: GeneratedRepository,
    github: GitHubClient,
    remote_url: str,
    pull_requests: list[PullRequestSpec],
) -> None:
    snapshot_counts = Counter(snapshot.branch for snapshot in generated.commit_snapshots)
    workflow_wait_branches = {branch for branch, count in snapshot_counts.items() if count > 1}
    remaining_snapshots = snapshot_counts.copy()
    pushed_branches: set[str] = set()
    pushed_heads: dict[str, str] = {}
    created_pull_requests: set[int] = set()
    open_pull_requests_by_head: dict[str, dict] = {}
    pending_waits: dict[str, PendingWorkflowWait] = {}

    print("Pushing generated branch snapshots...")
    for snapshot in generated.commit_snapshots:
        wait_for_pending_workflow(github, remote_url, pending_waits, snapshot.branch)

        triggered_after = workflow_event_started_at()
        generated.git.push_ref_force(snapshot.sha, snapshot.branch)
        pushed_branches.add(snapshot.branch)
        pushed_heads[snapshot.branch] = snapshot.sha
        remaining_snapshots[snapshot.branch] -= 1

        if snapshot.branch in open_pull_requests_by_head and snapshot.branch in workflow_wait_branches:
            pending_waits[snapshot.branch] = PendingWorkflowWait(
                open_pull_requests_by_head[snapshot.branch],
                snapshot.branch,
                snapshot.sha,
                triggered_after,
            )

        for index, pull_request in enumerate(pull_requests):
            if index in created_pull_requests:
                continue
            if not pull_request_can_be_created(pull_request, pushed_branches):
                continue
            triggered_after = workflow_event_started_at()
            github_pull_request, action = github.create_or_update_pull_request_with_action(
                remote_url,
                pull_request,
            )
            created_pull_requests.add(index)

            head = local_branch_name(pull_request.head)
            if not head:
                continue

            open_pull_requests_by_head[head] = github_pull_request
            if action == "created" and head in workflow_wait_branches:
                pending_waits[head] = PendingWorkflowWait(
                    github_pull_request,
                    head,
                    pushed_heads[head],
                    triggered_after,
                )

    for index, pull_request in enumerate(pull_requests):
        if index in created_pull_requests:
            continue
        if pull_request_can_be_created(pull_request, pushed_branches):
            github.create_or_update_pull_request_with_action(remote_url, pull_request)
            created_pull_requests.add(index)

    for branch_name in sorted(pending_waits):
        wait_for_pending_workflow(github, remote_url, pending_waits, branch_name)

    if len(created_pull_requests) != len(pull_requests):
        missing_titles = [
            pull_request.title
            for index, pull_request in enumerate(pull_requests)
            if index not in created_pull_requests
        ]
        raise ValueError(f"Could not create pull requests after publishing branches: {', '.join(missing_titles)}")


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
    """Push generated history and create configured GitHub pull requests."""
    print()
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

    publish_pull_request_timeline(generated, github, remote_url, pull_requests)
