"""Validate LLM-generated SQL: single read-only SELECT over the analytics schema, row-capped."""

import sqlglot
from sqlglot import exp
from sqlglot.errors import SqlglotError

ANALYTICS_TABLES = frozenset(
    {"sites", "lines", "equipment", "procedures", "procedure_steps", "ppe_requirements", "pm_tasks", "quality_specs"}
)

# any of these anywhere in the tree => reject (covers CTE-wrapped writes, SELECT INTO, locking reads)
_FORBIDDEN = (
    exp.Insert, exp.Update, exp.Delete, exp.Merge, exp.Create, exp.Drop, exp.Alter, exp.Command,
    exp.Copy, exp.Set, exp.Use, exp.Transaction, exp.Commit, exp.Rollback, exp.Grant,
    exp.TruncateTable, exp.Into, exp.Lock, exp.Pragma, exp.Describe,
)

# Functions we allow; everything else (pg_sleep, pg_read_file, dblink, lo_import, ...) is rejected.
_ALLOWED_FUNC_NAMES = {
    "COUNT", "SUM", "AVG", "MIN", "MAX", "ROUND", "COALESCE", "NULLIF", "LOWER", "UPPER", "LENGTH",
    "ABS", "CEIL", "CEILING", "FLOOR", "TRIM", "SUBSTRING", "CONCAT", "DATE_TRUNC", "EXTRACT",
    "STDDEV", "VARIANCE", "ARRAY_AGG", "STRING_AGG", "GREATEST", "LEAST", "IF", "NOW",
    "CURRENT_DATE", "CURRENT_TIMESTAMP", "REPLACE", "SPLIT_PART", "TO_CHAR", "MEDIAN",
    "ROW_NUMBER", "RANK", "DENSE_RANK", "COUNT_IF", "ANY_VALUE",
}


class UnsafeSQL(ValueError):
    pass


def _func_ok(node: exp.Expression) -> bool:
    if isinstance(node, exp.Anonymous):
        return False
    if isinstance(node, (exp.Cast, exp.TryCast)):
        return True
    return node.sql_name().upper() in _ALLOWED_FUNC_NAMES


def validate_select(sql: str, allowed_schema: str = "analytics", max_rows: int = 200) -> str:
    if not isinstance(sql, str) or not sql.strip():
        raise UnsafeSQL("empty SQL")
    if "--" in sql or "/*" in sql or "\x00" in sql:
        raise UnsafeSQL("comments are not allowed")
    try:
        stmts = [s for s in sqlglot.parse(sql, read="postgres") if s is not None]
    except SqlglotError as e:
        raise UnsafeSQL(f"unparseable SQL: {e}") from e
    if len(stmts) != 1:
        raise UnsafeSQL("exactly one statement is allowed")
    tree = stmts[0]
    if not isinstance(tree, exp.Select):
        raise UnsafeSQL("only plain SELECT is allowed")
    if tree.args.get("locks"):
        raise UnsafeSQL("locking reads are not allowed")

    for node in tree.walk():
        if isinstance(node, _FORBIDDEN):
            raise UnsafeSQL(f"{type(node).__name__} is not allowed")
        if isinstance(node, exp.Func) and not _func_ok(node):
            raise UnsafeSQL(f"function not allowed: {getattr(node, 'name', '') or node.sql_name()}")
        if isinstance(node, (exp.Parameter, exp.Placeholder, exp.SessionParameter)):
            raise UnsafeSQL("parameters / session variables are not allowed")

    cte_names = {c.alias_or_name.lower() for c in tree.find_all(exp.CTE)}
    for t in tree.find_all(exp.Table):
        if not isinstance(t.this, exp.Identifier):
            raise UnsafeSQL("table functions are not allowed")
        if t.catalog:
            raise UnsafeSQL("cross-database references are not allowed")
        name, schema = t.name.lower(), t.db.lower()
        if not schema and name in cte_names:
            continue
        if schema and schema != allowed_schema.lower():
            raise UnsafeSQL(f"schema '{t.db}' is not allowed")
        if name not in ANALYTICS_TABLES:
            raise UnsafeSQL(f"table '{t.name}' is not in the {allowed_schema} schema")
        if not schema:
            t.set("db", exp.to_identifier(allowed_schema))  # pin unqualified names to the schema

    _cap_limit(tree, max_rows)
    return tree.sql(dialect="postgres")


def _cap_limit(tree: exp.Select, max_rows: int) -> None:
    lim = tree.args.get("limit")
    if lim is not None:
        e = lim.expression
        if isinstance(e, exp.Literal) and e.is_int and int(e.this) <= max_rows:
            return
    tree.set("limit", exp.Limit(expression=exp.Literal.number(max_rows)))
