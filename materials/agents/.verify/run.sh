#!/bin/bash
# Convert all lesson .md to ipynb, execute, and save outputs for audit.
set -e
cd /workspace
OUT=/tmp/lesson-verify
mkdir -p "$OUT"

for md in $(find materials/agents -name "*.md" -type f | grep -v README.md | sort); do
    rel="${md#materials/agents/}"
    flat=$(echo "$rel" | tr '/' '__')
    base="${flat%.md}"
    if grep -q '{code-cell}' "$md"; then
        echo ">>> $rel"
        jupytext --to ipynb "$md" -o "$OUT/$base.ipynb" 2>&1 | tail -1
    fi
done
