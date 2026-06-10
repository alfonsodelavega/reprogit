from pathlib import Path

from .fixtures import branch_name_for, commit_directories, copy_commit_contents, read_merge_branch, read_message
from .git import GitRepository
from .models import CommitSnapshot, GeneratedRepository


class RepositoryGenerator:
    """Apply ordered fixture folders to a freshly generated repository."""

    def __init__(self, fixture_dir: Path, output_dir: Path):
        self.fixture_dir = fixture_dir
        self.repository = GitRepository(output_dir)
        self.branches: set[str] = set()
        self.branch_heads: dict[str, str] = {}
        self.commit_snapshots: list[CommitSnapshot] = []

    def generate(self) -> GeneratedRepository:
        """Build the local fixture repo."""
        self.repository.init()
        for commit_dir in commit_directories(self.fixture_dir):
            self.apply_commit_directory(commit_dir)
        return GeneratedRepository(
            self.repository,
            self.branches,
            list(self.commit_snapshots),
        )

    def apply_commit_directory(self, commit_dir: Path) -> None:
        branch_name = branch_name_for(commit_dir)
        message = read_message(commit_dir)
        self.branches.add(branch_name)
        previous_head = self.branch_heads.get(branch_name)
        start_point = "main" if branch_name != "main" and "main" in self.branch_heads else None
        self.repository.switch_or_create(branch_name, start_point)

        merge_branch = read_merge_branch(commit_dir)
        if merge_branch:
            self.apply_merge(commit_dir.name, branch_name, merge_branch, message)

        copy_commit_contents(commit_dir, self.repository.path)
        self.repository.add_all()
        if self.repository.has_staged_changes():
            self.repository.commit(message)
        current_head = self.repository.rev_parse(branch_name)
        self.branch_heads[branch_name] = current_head
        if current_head != previous_head:
            self.commit_snapshots.append(CommitSnapshot(commit_dir.name, branch_name, current_head))

    def apply_merge(self, directory_name: str, base_branch: str, head_branch: str, message: str) -> None:
        if head_branch not in self.branch_heads:
            raise ValueError(f"{directory_name} merges unknown branch '{head_branch}'.")

        self.repository.merge_no_ff(head_branch, message)
