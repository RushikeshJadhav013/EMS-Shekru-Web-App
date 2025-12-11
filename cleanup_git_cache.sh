#!/bin/bash

# Git Cache Cleanup Script
# This script removes cached files from Git tracking based on the updated .gitignore

set -e  # Exit on error

echo "=========================================="
echo "Git Cache Cleanup Script"
echo "=========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if we're in a git repository
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    echo -e "${RED}Error: Not a git repository${NC}"
    exit 1
fi

echo -e "${YELLOW}Step 1: Checking current status...${NC}"
git status --short

echo ""
echo -e "${YELLOW}Step 2: Removing all cached files from Git index...${NC}"
echo "This will NOT delete files from your disk, only from Git tracking."
read -p "Continue? (y/n) " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 1
fi

# Remove all files from Git index
git rm -r --cached . 2>/dev/null || echo "Some files were already untracked"

echo ""
echo -e "${YELLOW}Step 3: Re-adding files based on new .gitignore...${NC}"
git add .

echo ""
echo -e "${YELLOW}Step 4: Checking what will be committed...${NC}"
echo ""
echo "Files to be deleted (removed from tracking):"
git status --short | grep "^D" | head -20
echo ""
echo "Modified files:"
git status --short | grep "^M" | head -10
echo ""

echo -e "${GREEN}Summary:${NC}"
git status --short | wc -l | xargs echo "Total changes:"

echo ""
echo -e "${YELLOW}Step 5: Ready to commit${NC}"
echo "Suggested commit message:"
echo "  chore: update .gitignore and remove cached files from tracking"
echo ""
read -p "Commit these changes? (y/n) " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    git commit -m "chore: update .gitignore and remove cached files from tracking"
    echo ""
    echo -e "${GREEN}✓ Changes committed successfully!${NC}"
    echo ""
    echo -e "${YELLOW}Step 6: Push to remote?${NC}"
    read -p "Push to origin? (y/n) " -n 1 -r
    echo ""
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        BRANCH=$(git rev-parse --abbrev-ref HEAD)
        echo "Pushing to origin/$BRANCH..."
        git push origin "$BRANCH"
        echo ""
        echo -e "${GREEN}✓ Changes pushed successfully!${NC}"
    else
        echo "Skipped push. You can push later with: git push origin $(git rev-parse --abbrev-ref HEAD)"
    fi
else
    echo "Commit skipped. Changes are staged. You can commit later with:"
    echo "  git commit -m \"chore: update .gitignore and remove cached files\""
fi

echo ""
echo -e "${GREEN}=========================================="
echo "Cleanup Complete!"
echo "==========================================${NC}"
echo ""
echo "Verification commands:"
echo "  git check-ignore Frontend/node_modules"
echo "  git check-ignore Backend/__pycache__"
echo "  git ls-files | grep node_modules"
echo ""
