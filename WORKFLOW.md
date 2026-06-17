# reprogit Flow

`reprogit.py` is the entry point. It delegates to `reprogit_core.cli.main()`; the rest of the implementation lives in `reprogit_core`.

## 1. Parse input

`cli.parse_args()` reads one optional positional argument:

```bash
python3 reprogit.py
python3 reprogit.py other-fixture
```

If no fixture directory is passed, it uses `example`.

## 2. Load environment

`cli.main()` computes the project root and selected fixture directory:

```python
project_dir = Path(__file__).resolve().parent.parent
fixture_dir = Path(args.root_dir)
```

Then it loads the project-root `.env` file:

```python
load_environment(project_dir)
```

This lets `GITHUB_TOKEN` come from `.env` without manually exporting it in the shell.

## 3. Load pull request fixtures

Pull request definitions are read from:

```text
<fixture_dir>/.pullrequests.json
```

Only the selected fixture directory is used for pull request config.

## 4. Generate the local repository

`RepositoryGenerator` creates a fresh local repository at:

```text
repo/
```

It processes fixture folders in sorted order:

```text
c001/
c002/
c003--add-metamodel/
c005--update-metamodel/
```

Folder names control the target branch:

```text
c001                  -> main
c003--add-metamodel  -> add-metamodel
```

For each folder, the generator:

1. Switches to or creates the target branch. New feature branches are created from `main`.
2. Reads `.message`.
3. If `.merge` exists, merges the branch named inside it.
4. If `.delete` exists, removes each listed relative path from the generated repository before copying new files.
5. Recursively copies all fixture files except root `.message`, `.merge`, and `.delete`.
6. Stages and commits copied file changes, if any.

## 5. Optional local merges

`.merge` only affects the generated local branch history. The publisher no longer uses `.merge` to replay or merge GitHub pull requests. Leave `.merge` out of feature branches that should stay open as pull requests.

## 6. Validate pull requests

After generation, the script checks that each pull request in `.pullrequests.json` references generated branches:

```json
{
  "head": "add-metamodel",
  "base": "main"
}
```

## 7. Show the local result

The script prints the generated branch structure:

```bash
git -C repo show-branch --all
```

## 8. Publish to a remote repository

If the fixture has no `.remote`, the script stops after local generation.

If `.remote` exists, the script reads the target GitHub repository URL from:

```text
<fixture_dir>/.remote
```

If pull requests are configured, `GITHUB_TOKEN` is required. The script asks for confirmation before remote publishing because the remote workflow is destructive.

## 9. Clean the GitHub repository

When confirmed, the GitHub client:

1. Closes open pull requests.
2. Deletes workflow runs.
3. Deletes non-default branches.
4. Keeps the default branch ref.

This cleanup happens before new branches are pushed or new pull requests are created. GitHub does not permanently delete pull request records. It only allows them to be closed.

## 10. Push branches and create pull requests

If no pull requests are configured, the script tells you how to force-push the generated local branches:

```bash
git -C repo push --all --force
```

If pull requests are configured, the publisher pushes generated branch snapshots in fixture order. For branches with a single fixture snapshot, pull requests are created after all generated snapshots have been pushed.

When a configured pull request head branch has more than one fixture snapshot, the publisher creates the pull request as soon as its head and base branches are available on the remote. It waits for the GitHub Actions run associated with each non-final pull request state before pushing the next state. Later pushes to that already-open pull request head branch are left to GitHub, which reports them as `synchronize` pull request events. The publisher does not wait for the final branch state before finishing.

The expected remote shape is one base branch, usually `main`, plus feature branches with open pull requests into that base branch.

## Module map

- `reprogit.py`: entry point.
- `reprogit_core/cli.py`: orchestration.
- `reprogit_core/generator.py`: local repository generation.
- `reprogit_core/git.py`: git command wrapper.
- `reprogit_core/fixtures.py`: fixture parsing and validation.
- `reprogit_core/github.py`: GitHub API client.
- `reprogit_core/publish.py`: remote publishing workflow.
- `reprogit_core/env.py`: root `.env` loading.
- `reprogit_core/models.py`: data structures.
