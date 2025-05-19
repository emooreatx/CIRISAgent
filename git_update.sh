#!/bin/bash

# Navigate to the local clone of your forked repository
cd ~/CIRISAgent/

# Add the original repository as a remote if it's not already added
git remote add upstream https://github.com/CIRISAI/CIRISAgent.git

# Fetch the latest changes from the original repository
git fetch upstream

# Check out your fork's main branch
git checkout main

# Merge the changes from the original repository
git merge upstream/main

# Push the changes to your fork on GitHub
git push origin main
