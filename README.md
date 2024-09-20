# `reprogit`: reproducible generation of git repositories

`reprogit` can be used to generate a repository whose commits are created from the contents of an ordered list of folders (each folder represents a commit). This is useful to configure repositories for testing tools that work agains local or remote repositories.

## Usage (with the provided example)

From the root of this repository, run:

```python
python reprogit.py example
```

The previous command generates a new git repository in a `repo` folder. This repository has one commit for each one of the `c*` folders present in the `example` directory. Each folder contains the updated files that have changed with respect to the previous commit, as well as a `.message` file that contains the commit message.

## Note on commit hashes

Commit hashes not only depend on the contents of each commit, but also on the date and time when the commit was generated. As such, these hashes do not remain the same between repository generations.
