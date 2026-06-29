import os
from datetime import timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.sensors.external_task import ExternalTaskSensor

from common import DEFAULT_ARGS, PIPELINE_START_DATE

DBT_PROJECT_DIR = "/opt/airflow/dbt"
DBT_PROFILES_DIR = "/opt/airflow/dbt"

with DAG(
    dag_id="netpulse_dbt",
    default_args=DEFAULT_ARGS,
    description="Run dbt seed, staging, marts, and tests",
    schedule_interval="0 3 * * *",
    start_date=PIPELINE_START_DATE,
    catchup=True,
    tags=["netpulse", "dbt"],
) as dag:

    wait_for_staging_telemetry = ExternalTaskSensor(
        task_id="wait_for_staging_telemetry",
        external_dag_id="netpulse_staging",
        external_task_id="write_staging_tower_telemetry",
        execution_delta=timedelta(hours=1),
        mode="reschedule",
        poke_interval=60,
        timeout=3600,
    )
    wait_for_staging_sessions = ExternalTaskSensor(
        task_id="wait_for_staging_sessions",
        external_dag_id="netpulse_staging",
        external_task_id="write_staging_subscriber_sessions",
        execution_delta=timedelta(hours=1),
        mode="reschedule",
        poke_interval=60,
        timeout=3600,
    )

    dbt_env = {
        "DBT_PROFILES_DIR": DBT_PROFILES_DIR,
        "POSTGRES_HOST": os.environ.get("POSTGRES_HOST", "postgres"),
        "POSTGRES_PORT": os.environ.get("POSTGRES_PORT", "5432"),
        "POSTGRES_DB": os.environ.get("POSTGRES_DB", "netpulse"),
        "POSTGRES_USER": os.environ.get("POSTGRES_USER", "netpulse"),
        "POSTGRES_PASSWORD": os.environ.get("POSTGRES_PASSWORD", "netpulse_dev"),
    }

    dbt_seed = BashOperator(
        task_id="dbt_seed",
        bash_command=f"cd {DBT_PROJECT_DIR} && dbt seed --profiles-dir {DBT_PROFILES_DIR}",
        env=dbt_env,
    )
    dbt_staging = BashOperator(
        task_id="dbt_staging",
        bash_command=f"cd {DBT_PROJECT_DIR} && dbt run --select staging.* --profiles-dir {DBT_PROFILES_DIR}",
        env=dbt_env,
    )
    dbt_marts = BashOperator(
        task_id="dbt_marts",
        bash_command=f"cd {DBT_PROJECT_DIR} && dbt run --select marts.* --profiles-dir {DBT_PROFILES_DIR}",
        env=dbt_env,
    )
    dbt_test = BashOperator(
        task_id="dbt_test",
        bash_command=f"cd {DBT_PROJECT_DIR} && dbt test --profiles-dir {DBT_PROFILES_DIR}",
        env=dbt_env,
    )

    [wait_for_staging_telemetry, wait_for_staging_sessions] >> dbt_seed >> dbt_staging >> dbt_marts >> dbt_test
