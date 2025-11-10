#!/bin/bash
# Deploy HappyTube web player to GitHub Pages
# This script exports videos to static JSON and optionally commits/pushes

set -e  # Exit on error

echo "🎬 HappyTube Web Deployment Script"
echo "===================================="

# Check if we're in the project root
if [ ! -f "pyproject.toml" ]; then
    echo "❌ Error: Please run this script from the project root directory"
    exit 1
fi

# Step 1: Export videos to static JSON
echo ""
echo "📊 Step 1: Exporting videos to static JSON..."
poetry run python -m happytube.web.export

if [ $? -ne 0 ]; then
    echo "❌ Export failed. Make sure you've run 'poetry run python -m happytube.main' first."
    exit 1
fi

# Check if videos.json was created
if [ ! -f "happytube/web/static/videos.json" ]; then
    echo "❌ Error: videos.json was not created"
    exit 1
fi

# Count videos
VIDEO_COUNT=$(python -c "import json; print(len(json.load(open('happytube/web/static/videos.json'))))")
echo "✅ Exported $VIDEO_COUNT videos"

# Step 2: Test locally (optional)
echo ""
echo "🧪 Step 2: Test locally? (optional)"
echo "You can test the static build by running:"
echo "  cd happytube/web/static && python -m http.server 8000"
echo ""
read -p "Start local test server now? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Starting local server at http://localhost:8000"
    echo "Press Ctrl+C to stop and continue with deployment"
    cd happytube/web/static
    python -m http.server 8000
    cd ../../..
fi

# Step 3: Commit and push (optional)
echo ""
echo "🚀 Step 3: Commit and push to GitHub?"
echo ""
git status happytube/web/static/videos.json
echo ""
read -p "Commit and push changes? (y/N) " -n 1 -r
echo

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Committing changes..."
    git add happytube/web/static/videos.json

    # Create commit message with video count
    COMMIT_MSG="Update video list ($VIDEO_COUNT videos)"
    git commit -m "$COMMIT_MSG" || echo "No changes to commit"

    echo "Pushing to GitHub..."
    git push

    echo ""
    echo "✅ Deployment complete!"
    echo ""
    echo "Your site will be updated on GitHub Pages in a few minutes."
    echo "Check your repository's Actions tab for deployment status."
else
    echo ""
    echo "ℹ️  Skipped git commit. To deploy manually:"
    echo "  git add happytube/web/static/videos.json"
    echo "  git commit -m 'Update video list'"
    echo "  git push"
fi

echo ""
echo "📝 Next steps:"
echo "  1. Verify deployment on GitHub Pages"
echo "  2. If not configured, see happytube/web/DEPLOYMENT.md"
echo ""
