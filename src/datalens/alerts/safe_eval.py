"""
Safe expression evaluator for alert rule conditions.

Replaces ``eval()`` for evaluating user/config-supplied boolean rule strings
(e.g. ``"quality_score < 70 and pii_count > 0"``) against a context dict.

Only a small, audited subset of Python expression syntax is permitted:
  • literals: numbers, strings, True/False/None
  • names: resolved ONLY from the supplied context dict
  • boolean ops: and / or / not
  • comparisons: < <= > >= == != in / not in
  • arithmetic: + - * / // % ** and unary +/-
  • containers: list / tuple / set literals (for ``x in [...]``)

Anything else — function calls, attribute access, subscripting, comprehensions,
lambdas, dunder access, imports — raises ``UnsafeExpressionError``. There is no
path to ``__import__``, ``os``, attribute traversal, or arbitrary callables.
"""

from __future__ import annotations

import ast
import operator
from typing import Any


class UnsafeExpressionError(ValueError):
    """Raised when an expression uses syntax outside the permitted subset."""


_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

_UNARY_OPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
    ast.Not: operator.not_,
}

_CMP_OPS = {
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.In: lambda a, b: a in b,
    ast.NotIn: lambda a, b: a not in b,
}


def _eval_node(node: ast.AST, context: dict[str, Any]) -> Any:
    if isinstance(node, ast.Expression):
        return _eval_node(node.body, context)

    # Literals
    if isinstance(node, ast.Constant):
        return node.value

    # Names → context only
    if isinstance(node, ast.Name):
        if node.id in context:
            return context[node.id]
        raise UnsafeExpressionError(f"Unknown name in expression: {node.id!r}")

    # Boolean ops (and / or)
    if isinstance(node, ast.BoolOp):
        values = [_eval_node(v, context) for v in node.values]
        if isinstance(node.op, ast.And):
            result: Any = True
            for v in values:
                result = result and v
            return result
        result = False
        for v in values:
            result = result or v
        return result

    # Unary (not / -x / +x)
    if isinstance(node, ast.UnaryOp):
        op = _UNARY_OPS.get(type(node.op))
        if op is None:
            raise UnsafeExpressionError(f"Operator not allowed: {type(node.op).__name__}")
        return op(_eval_node(node.operand, context))

    # Binary arithmetic
    if isinstance(node, ast.BinOp):
        op = _BIN_OPS.get(type(node.op))
        if op is None:
            raise UnsafeExpressionError(f"Operator not allowed: {type(node.op).__name__}")
        return op(_eval_node(node.left, context), _eval_node(node.right, context))

    # Comparisons (chained supported)
    if isinstance(node, ast.Compare):
        left = _eval_node(node.left, context)
        for op_node, comparator in zip(node.ops, node.comparators):
            op = _CMP_OPS.get(type(op_node))
            if op is None:
                raise UnsafeExpressionError(f"Comparison not allowed: {type(op_node).__name__}")
            right = _eval_node(comparator, context)
            if not op(left, right):
                return False
            left = right
        return True

    # Container literals (only safe for membership tests)
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        items = [_eval_node(e, context) for e in node.elts]
        if isinstance(node, ast.Tuple):
            return tuple(items)
        if isinstance(node, ast.Set):
            return set(items)
        return items

    raise UnsafeExpressionError(
        f"Disallowed expression element: {type(node).__name__}"
    )


def safe_eval(expression: str, context: dict[str, Any]) -> Any:
    """
    Safely evaluate ``expression`` against ``context``.

    Raises ``UnsafeExpressionError`` on disallowed syntax or unknown names,
    and ``SyntaxError`` on malformed input.
    """
    tree = ast.parse(expression, mode="eval")
    return _eval_node(tree, context)


def safe_eval_bool(expression: str, context: dict[str, Any]) -> bool:
    """Evaluate and coerce to bool. Returns False on any error (fail-safe)."""
    try:
        return bool(safe_eval(expression, context))
    except (UnsafeExpressionError, SyntaxError, TypeError, ZeroDivisionError, KeyError):
        return False
