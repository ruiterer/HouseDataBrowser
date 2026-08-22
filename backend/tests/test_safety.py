import pytest

from app.influx.safety import UnsafeQueryError, validate


class TestAllowed:
    def test_simple_select(self):
        v = validate("SELECT mean(value) FROM temperature WHERE time > now() - 1d")
        assert v.sql.startswith("SELECT")
        assert "LIMIT 50000" in v.sql
        assert v.had_limit is False

    def test_select_with_existing_limit_is_unchanged(self):
        v = validate("SELECT * FROM temperature LIMIT 100")
        assert v.sql.endswith("LIMIT 100")
        assert v.had_limit is True
        assert v.sql.count("LIMIT") == 1

    def test_show_measurements(self):
        v = validate("SHOW MEASUREMENTS")
        assert v.sql == "SHOW MEASUREMENTS"

    def test_show_tag_keys(self):
        v = validate('SHOW TAG KEYS FROM "temperature"')
        assert "SHOW TAG KEYS" in v.sql

    def test_explain(self):
        v = validate("EXPLAIN SELECT * FROM temperature")
        assert v.sql.startswith("EXPLAIN")

    def test_select_lowercase(self):
        v = validate("select count(*) from doors")
        assert "LIMIT 50000" in v.sql

    def test_select_with_trailing_semicolon(self):
        v = validate("SELECT * FROM temperature;")
        assert ";" not in v.sql

    def test_select_with_newlines(self):
        v = validate("SELECT mean(value)\nFROM temperature\nWHERE time > now() - 1h")
        assert v.sql.startswith("SELECT")

    def test_custom_default_limit(self):
        v = validate("SELECT * FROM x", default_limit=10)
        assert v.sql.endswith("LIMIT 10")


class TestDenied:
    @pytest.mark.parametrize(
        "q",
        [
            "DROP MEASUREMENT temperature",
            "DROP DATABASE house",
            "DELETE FROM temperature WHERE time < now() - 30d",
            "INSERT INTO temperature value=1",
            'CREATE DATABASE "evil"',
            'ALTER RETENTION POLICY "default" ON "house" DURATION 1h DEFAULT',
            'GRANT ALL ON "house" TO "user"',
            'REVOKE ALL ON "house" FROM "user"',
            "KILL QUERY 1",
            "SET PASSWORD FOR \"user\" = 'x'",
        ],
    )
    def test_blocked_statements(self, q):
        with pytest.raises(UnsafeQueryError):
            validate(q)

    def test_two_statements_rejected(self):
        with pytest.raises(UnsafeQueryError):
            validate("SELECT * FROM temperature; DROP MEASUREMENT temperature")

    def test_select_then_delete_rejected(self):
        with pytest.raises(UnsafeQueryError):
            validate("SELECT 1; DELETE FROM x")

    def test_empty(self):
        with pytest.raises(UnsafeQueryError):
            validate("")

    def test_whitespace_only(self):
        with pytest.raises(UnsafeQueryError):
            validate("   \n\t ")

    def test_comment_only(self):
        with pytest.raises(UnsafeQueryError):
            validate("-- just a comment")

    def test_keyword_in_string_literal_is_allowed(self):
        # The word "drop" inside a string literal must NOT trigger the deny list.
        v = validate("SELECT * FROM events WHERE message = 'drop the bass'")
        assert "LIMIT" in v.sql

    def test_block_comment_with_drop_inside_select_still_safe(self):
        # Block comment is stripped from token stream — SELECT remains the leading kw.
        # Either accepted (and limited) or rejected — never executes the DROP.
        try:
            v = validate("SELECT /* DROP */ * FROM temperature")
            assert v.sql.startswith("SELECT")
        except UnsafeQueryError:
            pass


class TestEdgeCases:
    def test_unknown_lead_keyword_rejected(self):
        with pytest.raises(UnsafeQueryError):
            validate("WITH cte AS (SELECT 1) SELECT * FROM cte")

    def test_garbage_rejected(self):
        with pytest.raises(UnsafeQueryError):
            validate("not a query at all")
