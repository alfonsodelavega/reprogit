import json
import shutil
from pathlib import Path

from .config import MERGE_FILE, MESSAGE_FILE, PULL_REQUESTS_FILE
from .models import PullRequestSpec


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
    for source in commit_dir.rglob("*"):
        if not source.is_file():
            continue

        relative_path = source.relative_to(commit_dir)
        if relative_path.parts == (MESSAGE_FILE,) or relative_path.parts == (MERGE_FILE,):
            continue

        destination = output_dir / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def load_pull_requests(fixture_dir: Path) -> list[PullRequestSpec]:
    path = fixture_dir / PULL_REQUESTS_FILE
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
