#!/bin/bash
# Pre-launch hook for the Jupyter docker-stacks image.
# Runs before Jupyter starts as root; CHOWN_EXTRA fixes /home/jovyan/work/data
# and /checkpoints ownership so the producer/jobs can write as jovyan.
#
# Body runs in a subshell because docker-stacks sources *.sh hooks — without
# isolation, set -e/set -u would leak into start.sh.
(
    set -euo pipefail
    echo "[bootstrap] streaming-clickstream ready (no data prefetch needed)."
)
