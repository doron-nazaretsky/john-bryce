# ─── streaming-clickstream scaffold ─────────────────────────────────────────
#
# Run from the scaffold root. The scaffold is self-contained: it brings up
# its own 3-broker Kafka cluster + Spark + Jupyter and does not merge with
# labs/base/compose.yml.
# ────────────────────────────────────────────────────────────────────────────

.PHONY: lab-streaming lab-streaming-down test-streaming \
        events-start events-stop events-status events-reset \
        run-ingest run-windowed help

JUPYTER := streaming-jupyter

help:
	@echo ""
	@echo "  make lab-streaming        Start Kafka × 3 + Spark + Jupyter"
	@echo "  make lab-streaming-down   Stop the cluster"
	@echo "  make test-streaming       Run stage pytest suite inside $(JUPYTER)"
	@echo "  make events-start         Start the synthetic pageview producer"
	@echo "  make events-stop          Stop the producer"
	@echo "  make events-status        Show producer status + topic counts"
	@echo "  make events-reset         Recreate topics from scratch"
	@echo "  make run-ingest           spark-submit pipeline.ingest_job"
	@echo "  make run-windowed         spark-submit pipeline.windowed_job"
	@echo ""

lab-streaming: lab-streaming-down
	docker compose up -d --build --remove-orphans --wait
	@echo ""
	@echo "=============================================================="
	@echo " streaming-clickstream lab is ready."
	@echo "   JupyterLab:        http://localhost:8888"
	@echo "   Spark Master UI:   http://localhost:8080"
	@echo "   Spark Driver UI:   http://localhost:4040  (after a query starts)"
	@echo "   Kafka brokers:     localhost:19092, localhost:19093, localhost:19094"
	@echo "   Producer:          make events-start / events-status / events-stop"
	@echo "=============================================================="

lab-streaming-down:
	docker compose down --remove-orphans

test-streaming:
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
	    --master spark://spark-master:7077 \
	    --packages org.apache.spark:spark-sql-kafka-0-10_2.13:4.0.0 \
	    /home/jovyan/work/jobs/run_ingest_job.py

run-windowed:
	docker exec $(JUPYTER) spark-submit \
	    --master spark://spark-master:7077 \
	    --packages org.apache.spark:spark-sql-kafka-0-10_2.13:4.0.0 \
	    /home/jovyan/work/jobs/run_windowed_job.py
