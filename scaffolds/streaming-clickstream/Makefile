# ─── streaming-clickstream project ──────────────────────────────────────────
#
# Run from the project root. The project is self-contained: it brings up its
# own 3-broker Kafka cluster + Spark + Jupyter and does not merge with
# labs/base/compose.yml. Container names are prefixed `project-` and host
# ports are shifted so this can run side-by-side with the main
# `labs/streaming/` lab in the course repo.
# ────────────────────────────────────────────────────────────────────────────

.PHONY: run stop test \
        events-start events-stop events-status events-reset \
        run-ingest run-windowed help

JUPYTER := project-streaming-jupyter

help:
	@echo ""
	@echo "  make run                  Start Kafka × 3 + Spark + Jupyter"
	@echo "  make stop                 Stop the cluster"
	@echo "  make test                 Run stage pytest suite inside $(JUPYTER)"
	@echo "  make events-start         Start the synthetic pageview producer"
	@echo "  make events-stop          Stop the producer"
	@echo "  make events-status        Show producer status + topic counts"
	@echo "  make events-reset         Recreate topics from scratch"
	@echo "  make run-ingest           spark-submit pipeline.ingest_job"
	@echo "  make run-windowed         spark-submit pipeline.windowed_job"
	@echo ""

run: stop
	docker compose up -d --build --remove-orphans --wait
	@echo ""
	@echo "=============================================================="
	@echo " streaming-clickstream project is ready."
	@echo "   JupyterLab:        http://localhost:18888  (token: devtoken)"
	@echo "   Spark Driver UI:   http://localhost:14040  (after a query starts)"
	@echo "   Kafka UI (Kafbat): http://localhost:28080  (topics, partitions, consumer-group lag)"
	@echo "   Kafka brokers:     localhost:29092, localhost:29093, localhost:29094"
	@echo "   Producer:          make events-start / events-status / events-stop"
	@echo "=============================================================="

stop:
	docker compose down --remove-orphans

test:
	docker exec $(JUPYTER) pytest /home/jovyan/work/tests -v

events-start:
	docker exec $(JUPYTER) python /home/jovyan/work/scripts/event_generator.py start

events-stop:
	docker exec $(JUPYTER) python /home/jovyan/work/scripts/event_generator.py stop

events-status:
	docker exec $(JUPYTER) python /home/jovyan/work/scripts/event_generator.py status

events-reset:
	docker exec $(JUPYTER) python /home/jovyan/work/scripts/event_generator.py reset

run-ingest:
	docker exec $(JUPYTER) spark-submit \
	    --master 'local[*]' \
	    --packages org.apache.spark:spark-sql-kafka-0-10_2.13:4.0.0 \
	    /home/jovyan/work/jobs/run_ingest_job.py

run-windowed:
	docker exec $(JUPYTER) spark-submit \
	    --master 'local[*]' \
	    --packages org.apache.spark:spark-sql-kafka-0-10_2.13:4.0.0 \
	    /home/jovyan/work/jobs/run_windowed_job.py
