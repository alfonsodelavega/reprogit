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

# Find all directories starting with 'c' in the current directory
directories = [d for d in glob.glob(os.path.join(root_dir, 'c*/')) if os.path.isdir(d)]
directories.sort()

# create a commit for each directory
for directory in directories:
    # Copy the contents of the directory to the output repo
    os.system(f"cp -r {directory}/* {output_repo}/")
    # Add the files to the git index
    os.system(f"git -C {output_repo} add .")

    # Commit the changes with the content of .message file in directory
    with open(directory + ".message", "r") as f:
        message = f.read().strip()
        os.system(f"git -C {output_repo} commit -m '{message}'")
