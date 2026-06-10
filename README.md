# `reprogit`: reproducible generation of git repositories

`reprogit` can be used to generate a repository whose commits are created from the contents of an ordered list of folders (each folder represents a commit). This is useful to configure repositories for testing tools that work against local or remote repositories.

## Setup

1. Create an empty GitHub repository to use as the generated test repository.

    This repository is disposable: when pull requests are configured, `reprogit` closes open pull requests, deletes workflow runs, deletes non-default branches, and force-pushes generated branches.

2. In the fixture directory, set `.remote` to the SSH or HTTPS URL of that GitHub repository:

    ```bash
    # example/.remote
    git@github.com:YOUR_USER/YOUR_TEST_REPO.git
    ```

3. Create a fine-grained personal access token in GitHub under `Settings > Developer settings > Personal access tokens > Fine-grained tokens`. Limit the token to the generated test repository and grant these repository permissions:

    - `Contents`: Read and write
    - `Pull requests`: Read and write
    - `Actions`: Read and write
    - `Metadata`: Read-only

4. Expose the token as `GITHUB_TOKEN` before running `reprogit`:

    ```bash
    export GITHUB_TOKEN=github_pat_...
    ```

5. Alternatively, create a local `.env` file in the project root. `reprogit` loads it automatically:

    ```bash
    # .env
    GITHUB_TOKEN=github_pat_...
    ```

    Do not commit `.env` or any token value. The project `.gitignore` ignores `.env`.

## Usage (with the provided example)

From the root of this repository, run:

```bash
python3 reprogit.py
```

The previous command generates a new git repository in a `repo` folder. By default, the fixture directory is `example`; another fixture directory can be passed as the first argument. The generated repository has one commit for each one of the folders present in the fixture directory, organized as follows:

- The name of each folder follows the pattern `<commit_number>--<branch_name>`. The `commit_number` orders commits in time, independently of the branch they are placed on, and all commit numbers must start with a "c" (e.g. `c010`).
- Commits will be placed in branches according to `branch_name`, in the order imposed by their `commit_number`. When a feature branch is first seen, it is created from the current `main` branch; later folders with the same `branch_name` add commits to that existing branch.
- If no `branch_name` is present, it is assumed that the commit belongs to the `main` default branch.
- Each folder contains the updated files that have changed with respect to the previous commit, as well as a `.message` file that contains the commit message. Files can be placed directly in the commit folder or inside nested directories such as `library/library.ecore`.
- If a folder contains a `.merge` file, the current branch merges the branch named in `.merge` before any files in that folder are committed. Do not use `.merge` for branches that should remain open as pull requests.
- If a `.remote` file with a repo url is present at the root folder, then branches will be associated with remote branches.
- If a `.pullrequests.json` file is present in the fixture directory, publishing replays the generated branch snapshots in fixture order. A pull request is created as soon as its head and base branches have been pushed; later pushes to that head branch trigger GitHub's `pull_request` `synchronize` action automatically.
- If a configured pull request branch has more than one fixture commit, publishing waits for the GitHub Actions run for each branch state to complete before moving to the next state. This keeps workflows such as RAMA from reading the final pull request head in every run.

To create the same pull requests on every run, configure them in `.pullrequests.json`:

```json
[
  {
    "title": "Add metamodel",
    "head": "add-metamodel",
    "base": "main",
    "body": "Adds the library metamodel fixture."
  }
]
```

Pull request creation uses the GitHub repository from `.remote` and a token from `GITHUB_TOKEN`:

```bash
export GITHUB_TOKEN=...
python3 reprogit.py
```

The token must have permission to write repository contents, pull requests, and GitHub Actions runs in the target repository. On each publishing run, `reprogit` first closes open pull requests, deletes workflow runs, deletes non-default branches, and then pushes generated branch snapshots in fixture order. For repeated pull request branches, `reprogit` polls GitHub Actions and waits up to 30 minutes for each pull request workflow run before pushing the next branch state. The resulting remote is one `main` branch with the base files plus one branch per feature, each with an open pull request into its configured base branch. GitHub does not permanently delete pull request records; closed pull requests remain visible in repository history.

## Note on commit hashes

Commit hashes not only depend on the contents of each commit, but also on the date and time when the commit was generated. As such, these hashes do not remain the same between repository generations.
