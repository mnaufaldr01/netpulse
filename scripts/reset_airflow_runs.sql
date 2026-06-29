-- Reset stuck netpulse DAG runs (local dev only)
DELETE FROM task_instance WHERE dag_id LIKE 'netpulse_%';
DELETE FROM dag_run WHERE dag_id LIKE 'netpulse_%';
DELETE FROM xcom WHERE dag_id LIKE 'netpulse_%';
