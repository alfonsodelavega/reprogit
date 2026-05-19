import os
from pathlib import Path

from .config import ENV_FILE


def load_environment(project_dir: Path) -> None:
    """Load simple KEY=VALUE entries without replacing existing environment values."""
    path = project_dir / ENV_FILE
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
