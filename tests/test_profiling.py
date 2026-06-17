"""Tests for the profiling module."""

import pytest
from datalens.profiling.types import infer_type, is_empty_value, get_primitive_value


class TestInferType:
    """Tests for type inference."""

    def test_null(self):
        assert infer_type(None) == "null"

    def test_bool(self):
        assert infer_type(True) == "bool"
        assert infer_type(False) == "bool"

    def test_int(self):
        assert infer_type(42) == "int"
        assert infer_type(0) == "int"
        assert infer_type(-100) == "int"

    def test_float(self):
        assert infer_type(3.14) == "float"
        assert infer_type(0.0) == "float"

    def test_string(self):
        assert infer_type("hello") == "string"
        assert infer_type("") == "string"

    def test_url(self):
        assert infer_type("http://example.com") == "url"
        assert infer_type("https://example.com/path") == "url"
        assert infer_type("HTTP://EXAMPLE.COM") == "url"

    def test_uri(self):
        assert infer_type("uri:abc:123") == "uri"
        assert infer_type("custom://resource") == "uri"

    def test_email(self):
        assert infer_type("user@example.com") == "email"
        assert infer_type("test.user+tag@domain.co.uk") == "email"

    def test_uuid(self):
        assert infer_type("550e8400-e29b-41d4-a716-446655440000") == "uuid"

    def test_date(self):
        assert infer_type("2024-01-15") == "date"
        assert infer_type("2024-01-15T10:30:00") == "date"

    def test_object(self):
        assert infer_type({"key": "value"}) == "object"
        assert infer_type({}) == "object"

    def test_array(self):
        assert infer_type([1, 2, 3]) == "array"
        assert infer_type([]) == "array"


class TestIsEmptyValue:
    """Tests for empty value detection."""

    def test_none_is_empty(self):
        assert is_empty_value(None) is True

    def test_empty_string_is_empty(self):
        assert is_empty_value("") is True

    def test_empty_list_is_empty(self):
        assert is_empty_value([]) is True

    def test_empty_dict_is_empty(self):
        assert is_empty_value({}) is True

    def test_non_empty_values(self):
        assert is_empty_value("hello") is False
        assert is_empty_value(0) is False
        assert is_empty_value(False) is False
        assert is_empty_value([1]) is False
        assert is_empty_value({"a": 1}) is False


class TestGetPrimitiveValue:
    """Tests for primitive value extraction."""

    def test_primitives_unchanged(self):
        assert get_primitive_value("hello") == "hello"
        assert get_primitive_value(42) == 42
        assert get_primitive_value(3.14) == 3.14
        assert get_primitive_value(True) is True
        assert get_primitive_value(None) is None

    def test_complex_returns_none(self):
        assert get_primitive_value([1, 2, 3]) is None
        assert get_primitive_value({"a": 1}) is None
