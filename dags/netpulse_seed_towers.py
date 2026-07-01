"""DAG 0 — cloud only: fetch OpenCelliD Indonesia slice, sample towers, load RDS."""

from datetime import datetime
from pathlib import Path

from airflow import DAG
from airflow.operators.python import PythonOperator

from common import DEFAULT_ARGS

with DAG(
    dag_id="netpulse_seed_towers",
    default_args=DEFAULT_ARGS,
    description="Fetch OpenCelliD Indonesia slice and seed tower_master in RDS",
    schedule_interval="@monthly",
    start_date=datetime(2025, 5, 25),
    catchup=False,
    tags=["netpulse", "seed"],
) as dag:

    def _fetch_opencellid(**context):
        from netpulse.opencellid_fetch import fetch_and_upload

        partition_date = context["logical_date"].date()
        return fetch_and_upload(partition_date)

    def _sample_and_classify(**context):
        import tempfile

        from netpulse.geo import filter_indonesia_slice, load_opencellid_csv, sample_towers
        from netpulse.storage import download_bytes

        key = context["ti"].xcom_pull(task_ids="fetch_opencellid_indonesia")
        raw_bytes = download_bytes(key)
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
            tmp.write(raw_bytes)
            tmp_path = tmp.name

        df = load_opencellid_csv(tmp_path)
        Path(tmp_path).unlink(missing_ok=True)
        filtered = filter_indonesia_slice(df)
        sampled = sample_towers(filtered)
        return sampled.to_json(orient="records")

    def _assign_provinces(**context):
        from pathlib import Path

        import pandas as pd

        from netpulse.config import settings
        from netpulse.geo import assign_provinces, build_tower_master_df

        records_json = context["ti"].xcom_pull(task_ids="sample_and_classify_towers")
        sampled = pd.read_json(records_json, orient="records")
        if sampled.empty:
            raise ValueError("No towers after sampling")

        boundaries_dir = Path(settings.boundaries_data_path)
        geojson_files = list(boundaries_dir.glob("*.geojson")) + list(boundaries_dir.glob("*.json"))
        if not geojson_files:
            raise FileNotFoundError(
                f"No province GeoJSON in {boundaries_dir}. Run scripts/download_boundaries.py on EC2."
            )

        with_provinces = assign_provinces(sampled, geojson_files[0])
        tower_df = build_tower_master_df(with_provinces)
        return tower_df.to_json(orient="records", date_format="iso")

    def _load_tower_master(**context):
        import pandas as pd

        from netpulse.tower_seed import seed_towers_from_dataframe

        records_json = context["ti"].xcom_pull(task_ids="assign_provinces")
        tower_df = pd.read_json(records_json, orient="records")
        return seed_towers_from_dataframe(tower_df)

    def _validate_tower_master(**context):
        from netpulse.config import settings
        from netpulse.tower_seed import validate_tower_master

        loaded = context["ti"].xcom_pull(task_ids="load_tower_master")
        expected = settings.tower_sample_limit if settings.tower_sample_limit else loaded
        return validate_tower_master(int(expected))

    fetch_opencellid_indonesia = PythonOperator(
        task_id="fetch_opencellid_indonesia",
        python_callable=_fetch_opencellid,
    )
    sample_and_classify_towers = PythonOperator(
        task_id="sample_and_classify_towers",
        python_callable=_sample_and_classify,
    )
    assign_provinces_task = PythonOperator(
        task_id="assign_provinces",
        python_callable=_assign_provinces,
    )
    load_tower_master = PythonOperator(
        task_id="load_tower_master",
        python_callable=_load_tower_master,
    )
    validate_tower_master_task = PythonOperator(
        task_id="validate_tower_master",
        python_callable=_validate_tower_master,
    )

    (
        fetch_opencellid_indonesia
        >> sample_and_classify_towers
        >> assign_provinces_task
        >> load_tower_master
        >> validate_tower_master_task
    )
