# `reprogit`: reproducible generation of git repositories

`reprogit` can be used to generate a repository whose commits are created from the contents of an ordered list of folders (each folder represents a commit). This is useful to configure repositories for testing tools that work agains local or remote repositories.

## Usage (with the provided example)

From the root of this repository, run:

```python
python reprogit.py example
```

The previous command generates a new git repository in a `repo` folder. This repository has one commit for each one of the folders present in the `example` directory, organized as follows:

- The name of each folder follows the pattern `<commit_number>--<branch_name>`. The `commit_number` orders commits in time, independently of the branch they are placed on, and all commit numbers must start with a "c" (e.g. `c010`).
- Commits will be placed in branches according to `branch_name`, in the order imposed by their `commit_number`. This is useful to create conflicts between branches, for instance.
- If no `branch_name` is present, it is assumed that the commit belongs to the `main` default branch.
- Each folder contains the updated files that have changed with respect to the previous commit, as well as a `.message` file that contains the commit message.
- If a `.remote` file with a repo url is present at the root folder, then branches will be associated with remote branches, and (WARNING!!) force-pushed.


## Note on commit hashes

Commit hashes not only depend on the contents of each commit, but also on the date and time when the commit was generated. As such, these hashes do not remain the same between repository generations.
