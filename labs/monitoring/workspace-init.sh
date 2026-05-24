#!/usr/bin/env bash
# Monitoring-lab workspace entrypoint.
#
# Boots the docs + notebook services only. The producer daemon AND the batch
# loop are on-demand: students start them from MyST {code-cell}s via the
#   producer start / producer stop
#   spark batch start / spark batch stop
# CLIs. This keeps idle CPU near zero outside of an active demo.
#
# Installs two thin CLI shims onto PATH:
#   /usr/local/bin/producer  -> python -m producer.cli
#   /usr/local/bin/spark     -> python -m spark_cli.cli
set -e

WORKSPACE_ROOT=/workspace/labs/monitoring

cat > /usr/local/bin/producer <<EOF
#!/usr/bin/env bash
export PYTHONPATH=$WORKSPACE_ROOT:\${PYTHONPATH:-}
exec python3 -m producer.cli "\$@"
EOF
chmod +x /usr/local/bin/producer

cat > /usr/local/bin/spark <<EOF
#!/usr/bin/env bash
export PYTHONPATH=$WORKSPACE_ROOT:\${PYTHONPATH:-}
exec python3 -m spark_cli.cli "\$@"
EOF
chmod +x /usr/local/bin/spark

# ── Jupyter (background) ─────────────────────────────────────────────────
nohup jupyter server --no-browser --ip=0.0.0.0 --port=8888 \
  --IdentityProvider.token="${JUPYTER_TOKEN:-local-dev}" \
  --ServerApp.allow_origin="http://localhost:3000" \
  --allow-root \
  > /proc/1/fd/1 2>&1 &

# ── MyST docs (foreground, PID 1) ────────────────────────────────────────
myst clean --all --yes
HOST=0.0.0.0 exec myst start --keep-host --port 3000 --server-port 3100
