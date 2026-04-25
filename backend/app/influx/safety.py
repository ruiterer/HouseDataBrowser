"""Read-only InfluxQL gate.

Every query that goes to InfluxDB passes through `validate()` first, regardless of
whether it came from the LLM, a debug tool, or a future user-typed input. The gate is
a token-level whitelist:

  - exactly one statement
  - the first significant keyword is SELECT, SHOW, or EXPLAIN
  - no token in the deny list appears anywhere
  - a LIMIT is appended to SELECTs that lack one

The InfluxDB account the app uses should also be read-only (defence in depth).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import sqlparse
from sqlparse.sql import Statement
from sqlparse.tokens import Comment, Keyword, Punctuation, Whitespace

ALLOWED_LEAD_KEYWORDS = frozenset({"SELECT", "SHOW", "EXPLAIN"})

DENY_KEYWORDS = frozenset(
    {
        "INSERT",
        "DELETE",
        "DROP",
        "CREATE",
        "ALTER",
        "GRANT",
        "REVOKE",
        "KILL",
        "SET",
        "UPDATE",
        "TRUNCATE",
    }
)

_LIMIT_RE = re.compile(r"\blimit\s+\d+", re.IGNORECASE)


class UnsafeQueryError(ValueError):
    """Raised when a query fails the read-only gate."""


@dataclass(frozen=True)
class ValidatedQuery:
    sql: str
    had_limit: bool


def validate(query: str, *, default_limit: int = 50_000) -> ValidatedQuery:
    """Validate a single InfluxQL statement and return the (possibly limit-augmented) form.

    Raises UnsafeQueryError on any policy violation.
    """
    if not query or not query.strip():
        raise UnsafeQueryError("empty query")

    parsed = sqlparse.parse(query)
    statements = [s for s in parsed if _has_meaningful_tokens(s)]
    if len(statements) == 0:
        raise UnsafeQueryError("empty query")
    if len(statements) > 1:
        raise UnsafeQueryError("multiple statements not allowed")

    stmt = statements[0]
    lead = _first_significant_keyword(stmt)
    if lead is None:
        raise UnsafeQueryError("could not identify statement type")
    if lead not in ALLOWED_LEAD_KEYWORDS:
        raise UnsafeQueryError(f"statement type {lead!r} is not allowed (read-only)")

    for token in stmt.flatten():
        if token.ttype in (Keyword, Keyword.DDL, Keyword.DML):
            up = token.value.upper()
            if up in DENY_KEYWORDS:
                raise UnsafeQueryError(f"keyword {up!r} is not allowed")

    sql = str(stmt).rstrip().rstrip(";").rstrip()
    had_limit = bool(_LIMIT_RE.search(sql))

    if lead == "SELECT" and not had_limit:
        sql = f"{sql} LIMIT {default_limit}"

    return ValidatedQuery(sql=sql, had_limit=had_limit)


def _has_meaningful_tokens(stmt: Statement) -> bool:
    for token in stmt.flatten():
        if token.ttype in (Whitespace, Comment, Comment.Single, Comment.Multiline):
            continue
        if token.ttype is Punctuation and token.value == ";":
            continue
        if token.value.strip() == "":
            continue
        return True
    return False


def _first_significant_keyword(stmt: Statement) -> str | None:
    for token in stmt.flatten():
        if token.ttype in (Whitespace, Comment, Comment.Single, Comment.Multiline):
            continue
        if token.ttype is Punctuation:
            continue
        if token.value.strip() == "":
            continue
        if token.ttype in (Keyword, Keyword.DDL, Keyword.DML):
            return token.value.upper()
        return None
    return None
