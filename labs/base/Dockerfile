FROM python:3.13-slim

# System deps + Docker CLI + JRE
# gnupg/ca-certificates: required to verify and trust the Docker apt repo signing key
# curl: used to download the Docker GPG key
# git, build-essential, nodejs, npm: toolchain for MyST and native Python extensions
# openjdk-21-jre-headless: required by any JVM-backed Python package (pyspark, etc.)
#                          — used by the streaming lab; harmless overhead (~250MB) elsewhere.
#                          21 is the current LTS and what Trixie's main repo ships
#                          (17 was dropped). Spark 4 supports Java 17 / 21.
#
# Docker CLI setup (docker-ce-cli only — no daemon, no containerd):
#   install -m 0755 -d /etc/apt/keyrings   — creates the keyrings dir with correct permissions
#   curl ... | gpg --dearmor               — downloads and converts Docker's GPG key to binary format
#   echo "deb ..."                         — registers the official Docker apt repo for this arch/distro
#   apt-get install docker-ce-cli          — installs only the CLI; the actual daemon runs on the host
#                                            and is reached via the /var/run/docker.sock volume mount,
#                                            allowing `docker exec` into other lab containers from workspace
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    build-essential \
    nodejs \
    npm \
    gnupg \
    ca-certificates \
    openjdk-21-jre-headless \
    && install -m 0755 -d /etc/apt/keyrings \
    && curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor \
        -o /etc/apt/keyrings/docker.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
        https://download.docker.com/linux/debian bookworm stable" \
        > /etc/apt/sources.list.d/docker.list \
    && apt-get update \
    && apt-get install -y docker-ce-cli \
    && rm -rf /var/lib/apt/lists/*

# Install MyST CLI (Node-based)
RUN npm install -g mystmd

# Install uv for fast Python package management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /workspace

# Install base Python deps (Jupyter) from labs/base/pyproject.toml
COPY labs/base/pyproject.toml /tmp/base-deps/pyproject.toml
RUN uv pip install --system /tmp/base-deps/

# Install per-lab Python dependencies from labs/<LAB>/pyproject.toml.
# LAB is set by the lab's compose.yml (workspace.build.args.LAB).
# Defaults to "base" — the COPY is a no-op since base/pyproject.toml was already installed.
ARG LAB=base
COPY labs/${LAB}/pyproject.toml /tmp/lab-deps/pyproject.toml
RUN uv pip install --system /tmp/lab-deps/ 2>/dev/null || true

# Register Jupyter kernel
RUN python -m ipykernel install --sys-prefix --name python3 --display-name "Python 3"
