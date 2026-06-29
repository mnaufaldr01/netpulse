from datetime import timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.sensors.external_task import ExternalTaskSensor

from common import DEFAULT_ARGS, PIPELINE_START_DATE

with DAG(
    dag_id="netpulse_staging",
    default_args=DEFAULT_ARGS,
    description="Clean raw data and write to staging zone",
    schedule_interval="0 2 * * *",
    start_date=PIPELINE_START_DATE,
    catchup=True,
    tags=["netpulse", "staging"],
) as dag:

    wait_for_acquisition = ExternalTaskSensor(
        task_id="wait_for_acquisition",
        external_dag_id="netpulse_acquisition",
        external_task_id="end",
        execution_delta=timedelta(hours=1),
        mode="reschedule",
        poke_interval=60,
        timeout=3600,
    )

    def _clean_telemetry(**context):
        from transforms.clean_tower_telemetry import run
        return run(context["logical_date"].date())

    def _clean_sessions(**context):
        from transforms.clean_subscriber_sessions import run
        return run(context["logical_date"].date())

    read_raw_tower_telemetry = PythonOperator(
        task_id="read_raw_tower_telemetry",
        python_callable=lambda **ctx: None,
    )
    clean_tower_telemetry = PythonOperator(
        task_id="clean_tower_telemetry",
        python_callable=_clean_telemetry,
    )
    write_staging_tower_telemetry = PythonOperator(
        task_id="write_staging_tower_telemetry",
        python_callable=lambda **ctx: None,
    )

    read_raw_subscriber_sessions = PythonOperator(
        task_id="read_raw_subscriber_sessions",
        python_callable=lambda **ctx: None,
    )
    clean_subscriber_sessions = PythonOperator(
        task_id="clean_subscriber_sessions",
        python_callable=_clean_sessions,
    )
    write_staging_subscriber_sessions = PythonOperator(
        task_id="write_staging_subscriber_sessions",
        python_callable=lambda **ctx: None,
    )

    wait_for_acquisition >> [read_raw_tower_telemetry, read_raw_subscriber_sessions]
    read_raw_tower_telemetry >> clean_tower_telemetry >> write_staging_tower_telemetry
    read_raw_subscriber_sessions >> clean_subscriber_sessions >> write_staging_subscriber_sessions
