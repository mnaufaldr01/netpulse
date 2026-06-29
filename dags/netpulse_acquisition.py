from airflow import DAG
from airflow.operators.dummy import DummyOperator
from airflow.operators.python import PythonOperator

from common import DEFAULT_ARGS, PIPELINE_START_DATE

with DAG(
    dag_id="netpulse_acquisition",
    default_args=DEFAULT_ARGS,
    description="Generate synthetic telemetry and sessions to raw zone",
    schedule_interval="0 1 * * *",
    start_date=PIPELINE_START_DATE,
    catchup=True,
    tags=["netpulse", "acquisition"],
) as dag:

    def _generate_telemetry(**context):
        from generators.generate_tower_telemetry import run
        partition_date = context["logical_date"].date()
        key = run(partition_date)
        return key

    def _generate_sessions(**context):
        from generators.generate_subscriber_sessions import run
        partition_date = context["logical_date"].date()
        key = run(partition_date)
        return key

    def _validate_raw(**context):
        from generators.generate_tower_telemetry import validate as validate_telemetry
        from generators.generate_subscriber_sessions import validate as validate_sessions
        partition_date = context["logical_date"].date()
        validate_telemetry(partition_date)
        validate_sessions(partition_date)

    start = DummyOperator(task_id="start")
    end = DummyOperator(task_id="end")

    generate_tower_telemetry = PythonOperator(
        task_id="generate_tower_telemetry",
        python_callable=_generate_telemetry,
    )
    generate_subscriber_sessions = PythonOperator(
        task_id="generate_subscriber_sessions",
        python_callable=_generate_sessions,
    )
    validate_raw_landing = PythonOperator(
        task_id="validate_raw_landing",
        python_callable=_validate_raw,
    )

    start >> [generate_tower_telemetry, generate_subscriber_sessions] >> validate_raw_landing >> end
