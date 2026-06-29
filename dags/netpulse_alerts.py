from datetime import timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.sensors.external_task import ExternalTaskSensor

from common import DEFAULT_ARGS, PIPELINE_START_DATE

with DAG(
    dag_id="netpulse_alerts",
    default_args=DEFAULT_ARGS,
    description="Evaluate alert rules and write to PostgreSQL alerts table",
    schedule_interval="30 4 * * *",
    start_date=PIPELINE_START_DATE,
    catchup=True,
    tags=["netpulse", "alerts"],
) as dag:

    wait_for_dbt = ExternalTaskSensor(
        task_id="wait_for_dbt",
        external_dag_id="netpulse_dbt",
        external_task_id="dbt_test",
        execution_delta=timedelta(hours=1, minutes=30),
        mode="reschedule",
        poke_interval=60,
        timeout=3600,
    )

    def _hotspot(**_):
        from netpulse.alerts import evaluate_hotspot_alerts
        return evaluate_hotspot_alerts()

    def _peak_hour(**_):
        from netpulse.alerts import evaluate_peak_hour_alerts
        return evaluate_peak_hour_alerts()

    def _neighbour(**_):
        from netpulse.alerts import evaluate_neighbour_alerts
        return evaluate_neighbour_alerts()

    def _expire(**_):
        from netpulse.alerts import expire_resolved_alerts
        return expire_resolved_alerts()

    evaluate_hotspot_alerts = PythonOperator(
        task_id="evaluate_hotspot_alerts",
        python_callable=_hotspot,
    )
    evaluate_peak_hour_alerts = PythonOperator(
        task_id="evaluate_peak_hour_alerts",
        python_callable=_peak_hour,
    )
    evaluate_neighbour_alerts = PythonOperator(
        task_id="evaluate_neighbour_alerts",
        python_callable=_neighbour,
    )
    expire_resolved_alerts = PythonOperator(
        task_id="expire_resolved_alerts",
        python_callable=_expire,
    )

    wait_for_dbt >> evaluate_hotspot_alerts >> evaluate_peak_hour_alerts >> evaluate_neighbour_alerts >> expire_resolved_alerts
