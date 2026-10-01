import pytest

from backend.curriculum import TASKS
from backend.sql_engine import equal_results, grade, run_query, validate_sql

SQL_TASKS = [t for t in TASKS if t["kind"] == "sql"]


@pytest.mark.parametrize("task", SQL_TASKS, ids=lambda t: t["id"])
def test_reference_on_all_variants(task):
    assert grade(task["answer"], task["answer"], task["ordered"])["passed"]


@pytest.mark.parametrize("task", SQL_TASKS, ids=lambda t: t["id"])
def test_equivalent_wrapped_query(task):
    query = "WITH solution AS (" + task["answer"] + ") SELECT * FROM solution"
    assert grade(query, task["answer"], task["ordered"])["passed"]


BAD = [
    "DROP TABLE orders",
    "SELECT * FROM read_csv('/etc/passwd')",
    "SELECT * FROM read_parquet('https://example.com/a.parquet')",
    "SELECT * FROM sqlite_master",
    "SELECT * FROM duckdb_settings()",
    "SELECT 1; SELECT 2",
    "COPY orders TO '/tmp/export.csv'",
    "ATTACH '/tmp/test.db'",
    "SELECT getenv('HOME')",
    "SELECT * FROM information_schema.tables",
]


@pytest.mark.parametrize("sql", BAD)
def test_forbidden_queries(sql):
    with pytest.raises(ValueError):
        validate_sql(sql)


def test_quality_hand_checked_values():
    data = run_query(SQL_TASKS[0]["answer"])
    assert data["rows"] == [[243, 12]]


def test_constant_answer_fails_hidden_data():
    task = SQL_TASKS[0]
    result = grade("SELECT 243 AS total_orders,12 AS missing_customer_orders", task["answer"])
    assert result["public_passed"] and not result["passed"]


def test_wrong_order_count_fails():
    task = SQL_TASKS[1]
    assert not grade(
        task["answer"].replace("COUNT(DISTINCT o.order_id)", "COUNT(*)"), task["answer"]
    )["passed"]


def test_result_order_null_and_tolerance():
    a = {"columns": ["x"], "rows": [[None], [1.00000001]]}
    b = {"columns": ["x"], "rows": [[1.0], [None]]}
    assert equal_results(a, b, False)
    assert not equal_results(a, b, True)


def test_cpu_exhaustion_terminated():
    with pytest.raises(ValueError):
        run_query(
            "SELECT COUNT(*) FROM order_items a CROSS JOIN order_items b CROSS JOIN order_items c CROSS JOIN order_items d WHERE a.unit_price+b.unit_price+c.unit_price+d.unit_price>0",
            timeout=1,
        )
