#!/bin/bash
# Railway Deployment Optimization Script
# This script helps optimize Railway deployments by only deploying when necessary

set -e

echo "🚂 Railway Deployment Optimizer"
echo "================================="

# Function to check if only ignored files changed
check_relevant_changes() {
    echo "📋 Checking for relevant file changes..."

    # Get list of changed files (you can modify this based on your git workflow)
    if [ -n "$GITHUB_SHA" ]; then
        # GitHub Actions context
        CHANGED_FILES=$(git diff --name-only HEAD~1)
    else
        # Local context - compare with origin/main
        CHANGED_FILES=$(git diff --name-only origin/main)
    fi

    echo "Changed files:"
    echo "$CHANGED_FILES"
    echo "---"

    # Check if any relevant files changed
    RELEVANT_CHANGED=false

    while IFS= read -r file; do
        if [ -n "$file" ]; then
            # Check if file is NOT in .railwayignore patterns
            if ! grep -q "^${file}$" .railwayignore 2>/dev/null && \
               ! grep -q "^${file}/" .railwayignore 2>/dev/null && \
               ! grep -q "^${file%.md}.md$" .railwayignore 2>/dev/null; then
                echo "✅ Relevant change detected: $file"
                RELEVANT_CHANGED=true
            else
                echo "⏭️  Ignored change: $file"
            fi
        fi
    done <<< "$CHANGED_FILES"

    if [ "$RELEVANT_CHANGED" = true ]; then
        echo "🔄 Deployment needed - relevant files changed"
        return 0
    else
        echo "⏹️  Skipping deployment - only ignored files changed"
        return 1
    fi
}

# Function to optimize requirements for Railway
optimize_requirements() {
    echo "📦 Optimizing requirements.txt for Railway..."

    if [ ! -f "requirements.txt" ]; then
        echo "❌ requirements.txt not found"
        return 1
    fi

    # Create a Railway-optimized version
    cp requirements.txt requirements_railway.txt

    echo "✅ Created requirements_railway.txt"
}

# Function to clean up before deployment
cleanup_for_deployment() {
    echo "🧹 Cleaning up for deployment..."

    # Remove cache files
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find . -name "*.pyc" -delete 2>/dev/null || true
    find . -name "*.pyo" -delete 2>/dev/null || true

    # Remove logs and temporary files
    rm -f *.log 2>/dev/null || true
    rm -rf temp/ tmp/ 2>/dev/null || true

    echo "✅ Cleanup completed"
}

# Main deployment check
main() {
    case "$1" in
        "check")
            if check_relevant_changes; then
                echo "🎯 DEPLOY=true"
                exit 0
            else
                echo "🎯 DEPLOY=false"
                exit 1
            fi
            ;;
        "optimize")
            optimize_requirements
            cleanup_for_deployment
            ;;
        "cleanup")
            cleanup_for_deployment
            ;;
        *)
            echo "Usage: $0 {check|optimize|cleanup}"
            echo ""
            echo "Commands:"
            echo "  check    - Check if deployment is needed"
            echo "  optimize - Optimize files for Railway deployment"
            echo "  cleanup  - Clean up temporary files"
            exit 1
            ;;
    esac
}

main "$@"
