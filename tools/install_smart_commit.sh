#!/bin/bash
# Install smart commit functionality
# This makes pre-commit hooks automatically re-stage formatted files

set -e

echo "Installing smart commit functionality..."

# Create a simple wrapper that handles file modifications
cat > .git/hooks/pre-commit << 'EOF'
#!/bin/bash
# Auto-restage files modified by pre-commit hooks
# Simple and robust - just run pre-commit twice if needed

# First run
pre-commit run
EXIT_CODE=$?

# If it failed, check if files were modified
if [ $EXIT_CODE -ne 0 ]; then
    # Check for any unstaged changes
    if ! git diff --quiet; then
        echo ""
        echo "Re-staging files modified by hooks..."
        git add -u  # Stage all modified files that were already tracked

        echo "Running hooks again..."
        pre-commit run
        EXIT_CODE=$?
    fi
fi

exit $EXIT_CODE
EOF

chmod +x .git/hooks/pre-commit

echo "✅ Smart commit installed!"
echo ""
echo "How it works:"
echo "  1. Runs pre-commit hooks"
echo "  2. If files are modified by hooks (formatting, etc), stages them"
echo "  3. Runs hooks again to verify"
echo ""
echo "Just use 'git commit' normally - it will handle the rest!"
