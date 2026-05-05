# streaming-clickstream — Kafka + Spark Structured Streaming

A 3-stage scaffolded project: synthetic pageview events flow through a 3-broker
Kafka cluster and a Spark Structured Streaming pipeline.

**Start here:** [`00-introduction.md`](./00-introduction.md).

Stage lessons live under [`stages/`](./stages/). Student stubs live under
[`pipeline/`](./pipeline/). Tests live under [`tests/`](./tests/).

## Editing in VS Code — attach to the container

You'll get the best experience by running VS Code *inside* the
`project-streaming-jupyter` container. One Python interpreter powers
everything — cell execution, Pylance autocomplete, "Go to Definition",
debugging, the integrated terminal — so there's no host/container drift to
manage.

### One-time setup

1. Install the **Dev Containers** extension (`ms-vscode-remote.remote-containers`)
   in VS Code on your host.
2. Bring the project up: `make run`. Confirm `project-streaming-jupyter` is
   listed by `docker ps`.

### Attach

1. Command Palette (`Cmd/Ctrl+Shift+P`) → **Dev Containers: Attach to Running
   Container…** → pick `project-streaming-jupyter`.
2. A new VS Code window opens, attached to the container. In that window:
   **File → Open Folder…** → `/home/jovyan/work`.
3. The first attach takes ~30s — VS Code Server downloads itself and the
   extensions declared in `.devcontainer/devcontainer.json` (`ms-python.python`,
   `ms-toolsai.jupyter`, `ms-toolsai.jupyter-renderers`) install
   automatically. You don't have to pick anything.
4. The Python interpreter is pre-set to `/opt/conda/bin/python` (the Jupyter
   image's Python, where `kafka-python`, `pyspark`, and the rest of the lab's
   deps live) via `python.defaultInterpreterPath` in the devcontainer config.

The VS Code Server lives in a named docker volume (`vscode_server`), so every
attach after the first is instant — even across `make down` / `make run` /
`docker compose build` cycles. To force a fresh install, run
`docker volume rm streaming-clickstream_vscode_server`.

### Working there

- Open or create a notebook under `notebooks/`. The kernel picker shows
  **Python 3 (ipykernel)** from the in-container interpreter — pick it. Both
  *running* and *IntelliSense for* `from kafka import KafkaProducer` resolve
  to the same Python, so imports are no longer red-squiggled.
- Edit `pipeline/`, `helpers/`, `scripts/`, etc. in the same window. The
  container view of those directories is the host's `./pipeline`, `./helpers`,
  `./scripts` (bind-mounted in `compose.yml`), so your changes show up on the
  host filesystem and survive `make down` / `make run`.
- Use the integrated terminal for `pytest`, `spark-submit`, `kafka-topics.sh`
  — the shell runs in the container, so all the CLI tools and broker hostnames
  (`project-kafka-1:9092`, …) are available without any port-mapping
  gymnastics.

### Notes

- **Don't open the project folder from the host VS Code window.** That gives
  you a host-side interpreter that doesn't have the lab's packages and can't
  reach the brokers under their internal hostnames.
- The bind-mounted notebook directory means git also sees your `.ipynb` files
  on the host — commit from either side.
- After a `make stop` the attached window will disconnect. Run `make run`
  again, then re-attach via the same Command Palette flow.
