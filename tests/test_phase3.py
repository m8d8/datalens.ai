"""Tests for Phase 3 modules: PII, Quality, Statistics, Relationships."""

import pytest
from datalens.profiling.pii import (
    PIIType,
    detect_pii_in_field,
    detect_pii_in_schema,
    get_pii_summary,
    mask_value,
)
from datalens.profiling.quality import (
    compute_field_quality,
    compute_object_quality,
    compute_schema_quality,
    get_quality_grade,
    get_quality_color,
)
from datalens.profiling.statistics import (
    compute_numeric_stats,
    compute_temporal_stats,
    compute_percentile,
)
from datalens.profiling.relationships import (
    detect_relationships_by_naming,
    analyze_relationships,
)


class TestPIIDetection:
    """Tests for PII detection module."""

    def test_detect_email_by_field_name(self):
        detections = detect_pii_in_field("user_email", "string", [])
        assert any(d.pii_type == PIIType.EMAIL for d in detections)

    def test_detect_email_by_value(self):
        detections = detect_pii_in_field(
            "contact",
            "string",
            ["john@example.com", "jane@test.org"],
        )
        assert any(d.pii_type == PIIType.EMAIL for d in detections)

    def test_detect_phone_by_field_name(self):
        detections = detect_pii_in_field("phone_number", "string", [])
        assert any(d.pii_type == PIIType.PHONE for d in detections)

    def test_detect_ssn_by_field_name(self):
        detections = detect_pii_in_field("ssn", "string", [])
        assert any(d.pii_type == PIIType.SSN for d in detections)

    def test_detect_name_by_field_name(self):
        detections = detect_pii_in_field("first_name", "string", [])
        assert any(d.pii_type == PIIType.NAME for d in detections)

    def test_no_pii_in_normal_field(self):
        detections = detect_pii_in_field("status", "string", ["active", "pending"])
        assert len(detections) == 0

    def test_mask_email(self):
        masked = mask_value("john.doe@example.com", PIIType.EMAIL)
        assert masked.startswith("j***@")
        assert "example.com" in masked

    def test_mask_phone(self):
        masked = mask_value("555-123-4567", PIIType.PHONE)
        assert "4567" in masked
        assert "***" in masked

    def test_mask_ssn(self):
        masked = mask_value("123-45-6789", PIIType.SSN)
        assert masked == "***-**-****"

    def test_detect_pii_in_schema(self):
        schema = {
            "objects": [
                {
                    "object": "users",
                    "fields": [
                        {"path": "email", "types": {"email": 10}, "examples": ["a@b.com"]},
                        {"path": "name", "types": {"string": 10}, "examples": ["John"]},
                        {"path": "status", "types": {"string": 10}, "examples": ["active"]},
                    ],
                }
            ]
        }
        pii_data = detect_pii_in_schema(schema)
        assert "users" in pii_data
        assert len(pii_data["users"]) >= 1  # At least email detected

    def test_get_pii_summary(self):
        pii_data = {
            "users": [
                type("D", (), {"pii_type": PIIType.EMAIL, "confidence": 0.9, "field_path": "email"})(),
                type("D", (), {"pii_type": PIIType.NAME, "confidence": 0.7, "field_path": "name"})(),
            ]
        }
        summary = get_pii_summary(pii_data)
        assert summary["total_pii_fields"] == 2
        assert "email" in summary["by_type"]
        assert len(summary["high_risk_fields"]) >= 1


class TestDataQuality:
    """Tests for Data Quality Index module."""

    def test_get_quality_grade(self):
        assert get_quality_grade(95) == "A"
        assert get_quality_grade(85) == "B"
        assert get_quality_grade(75) == "C"
        assert get_quality_grade(65) == "D"
        assert get_quality_grade(50) == "F"

    def test_get_quality_color(self):
        assert "excellent" in get_quality_color(95)
        assert "good" in get_quality_color(85)
        assert "fair" in get_quality_color(75)
        assert "poor" in get_quality_color(65)
        assert "critical" in get_quality_color(50)

    def test_compute_field_quality_high_completeness(self):
        field_data = {
            "path": "name",
            "presence_count": 100,
            "null_empty_count": 5,
            "types": {"string": 100},
            "distinct_count_in_sample": 90,
        }
        quality = compute_field_quality(field_data, sampled=100)
        assert quality.completeness == 95.0  # 95/100 non-empty
        assert quality.consistency == 100.0  # Single type
        assert quality.path == "name"

    def test_compute_field_quality_mixed_types(self):
        field_data = {
            "path": "value",
            "presence_count": 100,
            "null_empty_count": 0,
            "types": {"string": 60, "int": 40},
            "distinct_count_in_sample": 50,
        }
        quality = compute_field_quality(field_data, sampled=100)
        assert quality.consistency == 60.0  # 60% dominant type
        assert len(quality.issues) > 0  # Should flag mixed types

    def test_compute_object_quality(self):
        obj_data = {
            "object": "users",
            "sampled": 100,
            "fields": [
                {"path": "id", "presence_count": 100, "null_empty_count": 0, "types": {"string": 100}, "distinct_count_in_sample": 100},
                {"path": "email", "presence_count": 95, "null_empty_count": 5, "types": {"email": 95}, "distinct_count_in_sample": 90},
            ],
        }
        quality = compute_object_quality(obj_data)
        assert quality.object_name == "users"
        assert quality.dqi > 0
        assert quality.completeness.score > 0

    def test_compute_schema_quality(self):
        schema = {
            "objects": [
                {
                    "object": "users",
                    "sampled": 100,
                    "fields": [
                        {"path": "id", "presence_count": 100, "null_empty_count": 0, "types": {"string": 100}, "distinct_count_in_sample": 100},
                    ],
                }
            ]
        }
        quality = compute_schema_quality(schema)
        assert quality.overall_dqi > 0
        assert len(quality.objects) == 1


class TestStatistics:
    """Tests for numeric and temporal statistics module."""

    def test_compute_percentile(self):
        values = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        assert compute_percentile(values, 50) == 5.5
        assert compute_percentile(values, 0) == 1
        assert compute_percentile(values, 100) == 10

    def test_compute_numeric_stats(self):
        values = [10, 20, 30, 40, 50]
        stats = compute_numeric_stats("score", values)
        assert stats is not None
        assert stats.count == 5
        assert stats.min_value == 10
        assert stats.max_value == 50
        assert stats.mean == 30
        assert stats.zero_count == 0
        assert stats.negative_count == 0
        assert stats.positive_count == 5

    def test_compute_numeric_stats_with_zeros_and_negatives(self):
        values = [-10, -5, 0, 5, 10]
        stats = compute_numeric_stats("balance", values)
        assert stats.zero_count == 1
        assert stats.negative_count == 2
        assert stats.positive_count == 2

    def test_compute_temporal_stats(self):
        values = ["2024-01-15", "2024-02-20", "2024-03-10"]
        stats = compute_temporal_stats("created_at", values)
        assert stats is not None
        assert stats.count == 3
        assert "2024-01-15" in stats.min_date
        assert "2024-03-10" in stats.max_date
        assert stats.span_days > 0

    def test_compute_numeric_stats_no_numeric_values(self):
        values = ["hello", "world", None]
        stats = compute_numeric_stats("text_field", values)
        assert stats is None

    def test_compute_temporal_stats_no_dates(self):
        values = ["not a date", "also not a date"]
        stats = compute_temporal_stats("random_field", values)
        assert stats is None


class TestRelationships:
    """Tests for relationship detection module."""

    def test_detect_foreign_key_by_naming(self):
        schema = {
            "objects": [
                {
                    "object": "orders",
                    "fields": [
                        {"path": "id", "types": {"string": 100}},
                        {"path": "user_id", "types": {"string": 100}},
                    ],
                },
                {
                    "object": "users",
                    "fields": [
                        {"path": "_id", "types": {"string": 100}},
                        {"path": "name", "types": {"string": 100}},
                    ],
                },
            ]
        }
        relationships = detect_relationships_by_naming(schema)
        assert len(relationships) >= 1
        fk_rel = next((r for r in relationships if r.relationship_type == "foreign_key"), None)
        assert fk_rel is not None
        assert fk_rel.source_object == "orders"
        assert fk_rel.target_object == "users"

    def test_analyze_relationships(self):
        schema = {
            "objects": [
                {
                    "object": "products",
                    "fields": [
                        {"path": "category_id", "types": {"string": 100}},
                    ],
                },
                {
                    "object": "categories",
                    "fields": [
                        {"path": "_id", "types": {"string": 100}},
                    ],
                },
            ]
        }
        result = analyze_relationships(schema)
        assert "total_relationships" in result
        assert "relationships" in result
        assert "by_object" in result


class TestIntegration:
    """Integration tests for Phase 3 features."""

    def test_full_schema_analysis(self):
        """Test that all Phase 3 modules work together."""
        schema = {
            "objects": [
                {
                    "object": "customers",
                    "sampled": 100,
                    "fields": [
                        {
                            "path": "id",
                            "presence_count": 100,
                            "null_empty_count": 0,
                            "types": {"string": 100},
                            "distinct_count_in_sample": 100,
                            "examples": ["c1", "c2", "c3"],
                        },
                        {
                            "path": "email",
                            "presence_count": 95,
                            "null_empty_count": 5,
                            "types": {"email": 95},
                            "distinct_count_in_sample": 90,
                            "examples": ["john@example.com", "jane@test.com"],
                        },
                        {
                            "path": "age",
                            "presence_count": 100,
                            "null_empty_count": 0,
                            "types": {"int": 100},
                            "distinct_count_in_sample": 50,
                            "examples": [25, 30, 35, 40, 45],
                        },
                        {
                            "path": "created_at",
                            "presence_count": 100,
                            "null_empty_count": 0,
                            "types": {"date": 100},
                            "distinct_count_in_sample": 80,
                            "examples": ["2024-01-15", "2024-02-20", "2024-03-10"],
                        },
                    ],
                }
            ]
        }

        # Test PII detection
        pii = detect_pii_in_schema(schema)
        assert "customers" in pii
        pii_summary = get_pii_summary(pii)
        assert pii_summary["total_pii_fields"] > 0

        # Test Quality
        quality = compute_schema_quality(schema)
        assert quality.overall_dqi > 50  # Should be decent quality

        # Test Relationships (no relationships expected with single object)
        rels = analyze_relationships(schema)
        assert "total_relationships" in rels
