import shutil
import subprocess
from pathlib import Path


def run(command: list[str], check: bool = True, **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(command, check=check, **kwargs)


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

    def switch_or_create(self, branch_name: str, start_point: str | None = None) -> None:
        switch = self.git(
            ["switch", branch_name],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if switch.returncode != 0:
            args = ["switch", "-c", branch_name]
            if start_point:
                args.append(start_point)
            self.git(args)

    def add_all(self) -> None:
        self.git(["add", "."])
        # Fixture files are copied with their metadata preserved. Re-normalizing
        # makes Git re-hash tracked files instead of relying on its stat cache,
        # which can otherwise miss a same-size replacement with a close mtime.
        self.git(["add", "--renormalize", "."])

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
