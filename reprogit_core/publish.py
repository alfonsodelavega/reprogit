from .config import GITHUB_TOKEN_ENV
from .github import GitHubClient
from .models import GeneratedRepository, PullRequestSpec


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

    print("Pushing all generated branches...")
    generated.git.push_all_force()

    for pull_request in pull_requests:
        github.create_or_update_pull_request(remote_url, pull_request)
