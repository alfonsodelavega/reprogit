from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .config import PULL_REQUESTS_FILE

if TYPE_CHECKING:
    from .git import GitRepository


@dataclass(frozen=True)
class PullRequestSpec:
    """A pull request that should exist in the generated remote test repo."""

    title: str
    head: str
    base: str
    body: str = ""

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
        )


@dataclass(frozen=True)
class CommitSnapshot:
    """The HEAD of a branch after applying one fixture commit directory."""

    directory: str
    branch: str
    sha: str


@dataclass(frozen=True)
class GeneratedRepository:
    git: "GitRepository"
    branches: set[str]
    commit_snapshots: list[CommitSnapshot]
