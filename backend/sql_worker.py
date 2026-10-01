import json
import resource
import sys
from datetime import date, datetime
from decimal import Decimal

import duckdb

from backend.data import populate
from backend.sql_engine import validate_sql


def execute(payload):
    resource.setrlimit(resource.RLIMIT_CPU, (3, 3))
    resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
    con = duckdb.connect(
        ":memory:",
        config={
            "threads": 1,
            "memory_limit": "96MB",
            "enable_external_access": False,
            "autoload_known_extensions": False,
            "autoinstall_known_extensions": False,
            "allow_unsigned_extensions": False,
            "temp_directory": "",
        },
    )
    populate(con, payload["seed"])
    con.execute("SET lock_configuration = true")
    validate_sql(payload["sql"])
    cursor = con.execute(payload["sql"])
    rows = cursor.fetchmany(501)

    def plain(v):
        if isinstance(v, Decimal):
            return float(v)
        if isinstance(v, (date, datetime)):
            return v.isoformat()
        return v

    return {
        "columns": [d[0] for d in cursor.description],
        "rows": [[plain(v) for v in r] for r in rows[:500]],
        "truncated": len(rows) > 500,
    }


if __name__ == "__main__":
    try:
        print(json.dumps(execute(json.load(sys.stdin)), ensure_ascii=False))
    except Exception as exc:
        print(json.dumps({"error": str(exc)[:400]}, ensure_ascii=False))
