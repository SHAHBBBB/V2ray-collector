#!/bin/bash
# run.sh — One command to pull, scan, and push

cd ~/V2ray-collector

echo "=== [1/3] Pulling latest configs ==="
git pull

echo ""
echo "=== [2/3] Scanning configs ==="
python3 local_scan.py --no-pull

echo ""
echo "=== [3/3] Pushing results to GitHub ==="
git add output/
git diff --staged --quiet && echo "No changes to push." || {
    git commit -m "filtered configs [$(date '+%Y-%m-%d %H:%M')]"
    git push
}

echo ""
echo "=== Done! ==="
