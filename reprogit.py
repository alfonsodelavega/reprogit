#!/usr/bin/env python
import os
import glob
import shutil
import sys

# Determine the root directory
root_dir = sys.argv[1] if len(sys.argv) > 1 else "."

output_repo = "repo" # must not start with "c"

# Remove the output directory if it exists
if os.path.exists(output_repo):
    shutil.rmtree(output_repo)

# init a git repository in the output directory
os.system(f"git init {output_repo}")

# Find all directories starting with 'c' in the root directory
directories = [d for d in glob.glob(os.path.join(root_dir, 'c*/')) if os.path.isdir(d)]
directories.sort()

# create a commit for each directory
branches = set()
for directory in directories:
    directory_name = os.path.basename(directory[:-1]) # remove the trailing slash
    branch_name = directory_name.split("--")[1] if "--" in directory_name else "main"

    # Create the branch if it does not exist
    os.system(f"git -C {output_repo} switch {branch_name} 2>/dev/null || git -C {output_repo} switch -c {branch_name}")

    # Copy the contents of the directory to the output repo
    os.system(f"cp -r {directory}/* {output_repo}/")

    # Add the files to the git index
    os.system(f"git -C {output_repo} add .")

    # Commit the changes with the content of .message file in directory
    with open(directory + ".message", "r") as f:
        message = f.read().strip()
        os.system(f"git -C {output_repo} commit -m '{message}'")
print()

# execute show-branches to show the resulting branches and commits
print("Branches and commits in the resulting repository:")
os.system(f"git -C {output_repo} show-branch --all")

print()
# If a .remote file is present at the root folder, then branches will be associated with remote branches, and (WARNING!!) force-pushed.
if os.path.exists(os.path.join(root_dir, ".remote")):
    with open(os.path.join(root_dir, ".remote"), "r") as f:
        remote_url = f.read().strip()
        # WARNING!! force-push the resulting repository to the remote url
        # Show a warning message before pushing
        print(f"The resulting repository will be configured with a remote to {remote_url}.")
        print("WARNING: Any force-push to this remote may overwrite existing branches and commits. Make sure you have a backup of any important data before proceeding.")
        response = input("Enter `yes` to continue, anything else to abort: ").strip().lower()
        if response != "yes":
            print("Aborting.")
            sys.exit(0)
        print(f"Setting up remote {remote_url}...")
        os.system(f"git -C {output_repo} remote add origin {remote_url}")
        print(f"All ready. Now you can push the resulting repository to the remote with the following command: ")
        print(f"git -C {output_repo} push --all --force")
