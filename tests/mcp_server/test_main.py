import pytest

from mcp_server.main import enforce_read_only, parse_table_ref


@pytest.mark.parametrize(
    ("table", "expected"),
    [
        ("events", ("public", "events")),
        ("analytics.events_2026", ("analytics", "events_2026")),
    ],
)
def test_parse_table_ref_accepts_simple_identifiers(table, expected):
    assert parse_table_ref(table) == expected


@pytest.mark.parametrize(
    "table",
    [
        "events; DROP TABLE users",
        "analytics.events.extra",
        "pg_catalog.pg_user",
        "information_schema.tables",
        'public."events"',
    ],
)
def test_parse_table_ref_rejects_unsafe_or_system_identifiers(table):
    with pytest.raises(ValueError):
        parse_table_ref(table)


def test_enforce_read_only_accepts_select():
    enforce_read_only("SELECT id FROM events")


@pytest.mark.parametrize(
    "statement",
    [
        "DELETE FROM events",
        "SELECT * FROM events; DROP TABLE events",
        "WITH deleted AS (DELETE FROM events RETURNING *) SELECT * FROM deleted",
    ],
)
def test_enforce_read_only_rejects_write_or_multiple_statements(statement):
    with pytest.raises(ValueError):
        enforce_read_only(statement)
