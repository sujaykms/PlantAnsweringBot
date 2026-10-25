import pytest

from app.guards.sql import UnsafeSQL, validate_select


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT count(*) FROM equipment",
        "SELECT e.name, l.name FROM analytics.equipment e JOIN lines l ON l.id = e.line_id WHERE e.status = 'down'",
        "WITH x AS (SELECT * FROM pm_tasks) SELECT count(*) FROM x",
        "SELECT line_id, round(avg(x), 2) FROM quality_specs GROUP BY 1 ORDER BY 2 DESC LIMIT 10",
        "SELECT * FROM sites WHERE name = 'a;b'",
        "SELECT * FROM equipment WHERE id IN (SELECT equipment_id FROM pm_tasks)",
    ],
)
def test_allowed(sql):
    out = validate_select(sql)
    assert out.upper().startswith(("SELECT", "WITH")) and "LIMIT" in out.upper()


def test_unqualified_tables_pinned_to_schema():
    assert "analytics.equipment" in validate_select("SELECT * FROM equipment")


@pytest.mark.parametrize(
    "sql",
    [
        "",
        "   ",
        "DROP TABLE equipment",
        "INSERT INTO equipment VALUES (1)",
        "UPDATE equipment SET name='x'",
        "DELETE FROM equipment",
        "TRUNCATE equipment",
        "COPY equipment TO '/tmp/x'",
        "CALL do_thing()",
        "SET search_path = public",
        "SELECT 1; DROP TABLE equipment",
        "SELECT * FROM equipment; SELECT * FROM sites",
        "WITH d AS (DELETE FROM equipment RETURNING *) SELECT * FROM d",
        "WITH i AS (INSERT INTO sites VALUES (1) RETURNING *) SELECT * FROM i",
        "SELECT pg_sleep(10)",
        "SELECT pg_read_file('/etc/passwd')",
        "SELECT * FROM dblink('host=x', 'select 1') AS t(a int)",
        "SELECT lo_import('/etc/passwd')",
        "SELECT current_setting('x')",
        "SELECT * FROM generate_series(1, 1000000)",
        "SELECT * FROM pg_user",
        "SELECT * FROM pg_catalog.pg_tables",
        "SELECT * FROM information_schema.tables",
        "SELECT * FROM public.sites",
        "SELECT * FROM otherdb.analytics.sites",
        "SELECT * FROM users",
        "SELECT * INTO newt FROM equipment",
        "SELECT * FROM equipment FOR UPDATE",
        "SELECT * FROM equipment -- ; DROP TABLE x",
        "SELECT * FROM equipment /* hi */",
        "SELECT * FROM equipment WHERE id = $1",
        "EXPLAIN ANALYZE SELECT * FROM equipment",
        "SELECT * FROM equipment UNION SELECT * FROM pg_shadow",
        "SELECT (SELECT pg_sleep(1)) FROM equipment",
        "SELECT * FROM equipment WHERE id = (SELECT 1 FROM pg_authid LIMIT 1)",
        "VACUUM equipment",
        "GRANT ALL ON equipment TO public",
    ],
)
def test_rejected(sql):
    with pytest.raises(UnsafeSQL):
        validate_select(sql)


@pytest.mark.parametrize(
    "sql,expected",
    [
        ("SELECT * FROM sites", "LIMIT 200"),
        ("SELECT * FROM sites LIMIT 5000", "LIMIT 200"),
        ("SELECT * FROM sites LIMIT 50", "LIMIT 50"),
        ("SELECT * FROM sites LIMIT ALL", "LIMIT 200"),
    ],
)
def test_limit_capped(sql, expected):
    assert expected in validate_select(sql)


def test_custom_max_rows():
    assert "LIMIT 10" in validate_select("SELECT * FROM sites", max_rows=10)
