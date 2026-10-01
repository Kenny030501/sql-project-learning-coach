import json
import math
import subprocess
import sys
from pathlib import Path

import sqlglot
from sqlglot import exp

ROOT = Path(__file__).resolve().parents[1]
TABLES = {"orders", "order_items", "products", "customers"}
FUNCTIONS = {
    "COUNT",
    "SUM",
    "AVG",
    "MIN",
    "MAX",
    "COALESCE",
    "CAST",
    "TRY_CAST",
    "DATE_TRUNC",
    "TIMESTAMP_TRUNC",
    "EXTRACT",
    "ROUND",
    "NULLIF",
    "ROW_NUMBER",
    "DENSE_RANK",
    "RANK",
    "LAG",
    "LEAD",
    "ABS",
    "LOWER",
    "UPPER",
    "LENGTH",
    "CONCAT",
    "TIME_TO_STR",
    "STRFTIME",
    "IF",
    "CASE",
    "PAREN",
    "TO_CHAR",
    "AND",
    "OR",
}


def validate_sql(sql):
    if not isinstance(sql, str) or not sql.strip() or len(sql) > 12000:
        raise ValueError("SQL不能为空，最多12,000字符")
    try:
        nodes = sqlglot.parse(sql, read="duckdb")
    except sqlglot.errors.ParseError:
        raise ValueError("SQL语法无法解析") from None
    if len(nodes) != 1 or not isinstance(nodes[0], (exp.Select, exp.Union)):
        raise ValueError("只允许一条SELECT/CTE只读查询")
    tree = nodes[0]
    ctes = {c.alias for c in tree.find_all(exp.CTE)}
    for table in tree.find_all(exp.Table):
        if (
            not isinstance(table.this, exp.Identifier)
            or table.db
            or table.catalog
            or table.name not in TABLES | ctes
        ):
            raise ValueError("只能查询教学表或本查询的CTE，禁止文件、网络和系统表")
    for node in tree.walk():
        if isinstance(
            node, (exp.Insert, exp.Delete, exp.Update, exp.Create, exp.Drop, exp.Command, exp.Into)
        ):
            raise ValueError("禁止修改或导出数据")
        if isinstance(node, exp.Func):
            name = node.name.upper() if isinstance(node, exp.Anonymous) else node.sql_name().upper()
            if name not in FUNCTIONS:
                raise ValueError(f"教学沙箱暂不支持函数：{name}")
    return sql


def run_query(sql, seed=42, timeout=5):
    validate_sql(sql)
    try:
        result = subprocess.run(
            [sys.executable, "-m", "backend.sql_worker"],
            input=json.dumps({"sql": sql, "seed": seed}),
            text=True,
            capture_output=True,
            cwd=ROOT,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise ValueError("查询超过5秒，已终止隔离进程") from None
    if result.returncode != 0:
        raise ValueError("查询超过资源限制或执行失败")
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        raise ValueError("查询进程没有返回有效结果") from None
    if "error" in data:
        raise ValueError(data["error"])
    return data


def equal_results(got, expected, ordered=False):
    if got["columns"] != expected["columns"] or got.get("truncated"):
        return False
    a, b = got["rows"], expected["rows"]
    if len(a) != len(b):
        return False

    def eq(x, y):
        if isinstance(x, (int, float)) and isinstance(y, (int, float)):
            return math.isclose(x, y, rel_tol=1e-6, abs_tol=1e-6)
        return x == y

    if not ordered:
        a = sorted(a, key=lambda r: json.dumps(r, ensure_ascii=False, sort_keys=True))
        b = sorted(b, key=lambda r: json.dumps(r, ensure_ascii=False, sort_keys=True))
    return all(all(eq(x, y) for x, y in zip(r, s)) for r, s in zip(a, b))


def grade(sql, answer, ordered=False):
    displayed = run_query(sql)
    expected = run_query(answer)
    passed = equal_results(displayed, expected, ordered)
    hidden_passed = False
    if passed:
        hidden_passed = all(
            equal_results(run_query(sql, seed), run_query(answer, seed), ordered)
            for seed in (73, 119)
        )
    return {
        **displayed,
        "passed": passed and hidden_passed,
        "public_passed": passed,
        "feedback": "主数据与隐藏变体均通过。"
        if passed and hidden_passed
        else "尚未通过：检查口径、列名、粒度、排序和空值处理。",
    }
