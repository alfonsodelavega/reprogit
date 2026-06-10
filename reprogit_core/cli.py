import argparse
import os
from pathlib import Path

from .config import DEFAULT_FIXTURE_DIR, GITHUB_TOKEN_ENV, OUTPUT_REPO, PULL_REQUESTS_FILE, REMOTE_FILE
from .env import load_environment
from .fixtures import load_pull_requests, read_optional_text, validate_pull_requests
from .generator import RepositoryGenerator
from .publish import confirm_remote_write, publish_repository


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a git repository from a sequence of commit folders.")
    parser.add_argument(
        "root_dir",
        nargs="?",
        default=DEFAULT_FIXTURE_DIR,
        help="Directory containing c* commit folders.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_dir = Path(__file__).resolve().parent.parent
    fixture_dir = Path(args.root_dir)

    load_environment(project_dir)
    pull_requests = load_pull_requests(fixture_dir)

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
    except (RuntimeError, TimeoutError, ValueError) as error:
        print(error)
        return 1
    return 0
