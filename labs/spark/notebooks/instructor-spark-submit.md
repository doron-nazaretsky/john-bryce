---
jupytext:
  text_representation:
    extension: .md
    format_name: myst
    format_version: 0.13
    jupytext_version: 1.19.1
kernelspec:
  display_name: Python 3
  language: python
  name: python3
---

# Instructor — `spark-submit` walkthrough

Show students the production face of Spark. Take Exercise B's logic, packaged as `jobs/exercise_b_job.py`, and submit it to the same standalone cluster — no notebook driver, no JupyterLab, just a job sent to the master.

Talking points:

- The notebook driver and a `spark-submit` driver are the same thing — both connect to `spark://spark-master:7077` and ship work to the workers.
- In CI/cron/airflow you almost always use `spark-submit` (or its containerized cousin `spark-on-k8s-operator`), not a notebook.
- The job appears in the **Master UI** (<http://localhost:8080>) under "Completed Applications" once it finishes.

```{code-cell}
import subprocess

result = subprocess.run(
    [
        "spark-submit",
        "--master", "spark://spark-master:7077",
        "--executor-memory", "800m",
        "--total-executor-cores", "2",
        "/home/jovyan/work/jobs/exercise_b_job.py",
    ],
    capture_output=True, text=True,
)
print("--- STDOUT ---")
print(result.stdout[-2000:])
print("--- STDERR (tail) ---")
print(result.stderr[-2000:])
print("exit:", result.returncode)
```

Open <http://localhost:8080> and find the application by name (`exercise-b-submit`).
