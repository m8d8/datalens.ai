"""
Field-name tokenisation shared by PII detection, quality and drift.

Names are split into lower-case tokens across snake_case, camelCase and
kebab-case ("customerId" → {"customer", "id"}), and neighbouring tokens are also
joined ("first_name" → "firstname"), so hints match whole words instead of
substrings ("id" must not match "video", "pan" must not match "company").
"""

from __future__ import annotations

import re

_TOKEN_RE = re.compile(r"[A-Z]?[a-z]+|[A-Z]+(?![a-z])|\d+")

IDENTIFIER_TOKENS = frozenset({"id", "uuid", "guid", "key", "code", "pk", "sku", "ref", "slug"})


def leaf_name(path: str) -> str:
    return path.rsplit(".", 1)[-1].replace("[]", "")


def name_tokens(name: str) -> set[str]:
    """Lower-case tokens of a field name plus joined neighbours."""
    tokens = [t.lower() for t in _TOKEN_RE.findall(name)]
    out = set(tokens)
    for i in range(len(tokens) - 1):
        out.add(tokens[i] + tokens[i + 1])
    if len(tokens) > 2:
        out.add("".join(tokens))
    return out


def is_identifier_name(path: str) -> bool:
    """True for identifier-shaped field names: id, user_id, orderId, sku, uuid, match_key…"""
    leaf = leaf_name(path)
    return leaf.lower() in {"id", "_id", "uuid", "guid"} or bool(name_tokens(leaf) & IDENTIFIER_TOKENS)


_PLACEHOLDER_RE = re.compile(r"^(col(umn)?[_ ]?\d+|unnamed.*|field[_ ]?\d+|_\d+)$", re.IGNORECASE)


def is_placeholder_name(name: object) -> bool:
    """True for a blank or tool-generated column name: "", None, col_6, Column1, Unnamed: 3, Field2."""
    return name is None or not str(name).strip() or bool(_PLACEHOLDER_RE.match(str(name).strip()))
