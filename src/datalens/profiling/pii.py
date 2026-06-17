"""
PII Detection — identify and optionally mask personally identifiable information.

Detects common PII patterns:
- Email addresses
- Phone numbers
- Social Security Numbers (SSN)
- Credit card numbers
- IP addresses
- Names (heuristic based on field names)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any


class PIIType(str, Enum):
    """Types of PII that can be detected."""

    EMAIL = "email"
    PHONE = "phone"
    SSN = "ssn"
    CREDIT_CARD = "credit_card"
    IP_ADDRESS = "ip_address"
    NAME = "name"
    ADDRESS = "address"
    DATE_OF_BIRTH = "date_of_birth"
    PASSPORT = "passport"
    DRIVER_LICENSE = "driver_license"


@dataclass
class PIIDetection:
    """Represents a PII detection result."""

    pii_type: PIIType
    confidence: float  # 0.0 to 1.0
    field_path: str
    sample_masked: str | None = None


# Regex patterns for PII detection
_PATTERNS = {
    PIIType.EMAIL: re.compile(
        r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    ),
    PIIType.PHONE: re.compile(
        r"^(\+\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}$"
    ),
    PIIType.SSN: re.compile(r"^\d{3}[-\s]?\d{2}[-\s]?\d{4}$"),
    PIIType.CREDIT_CARD: re.compile(r"^\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}$"),
    PIIType.IP_ADDRESS: re.compile(
        r"^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}"
        r"(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$"
    ),
    PIIType.PASSPORT: re.compile(r"^[A-Z]{1,2}\d{6,9}$"),
}

# Field name patterns that suggest PII
_NAME_PATTERNS = {
    PIIType.EMAIL: re.compile(r"(email|e[-_]?mail)", re.IGNORECASE),
    PIIType.PHONE: re.compile(
        r"(phone|mobile|cell|tel|telephone|fax)", re.IGNORECASE
    ),
    PIIType.SSN: re.compile(r"(ssn|social[-_]?security|tax[-_]?id)", re.IGNORECASE),
    PIIType.CREDIT_CARD: re.compile(
        r"(card[-_]?num|credit[-_]?card|cc[-_]?num|pan)", re.IGNORECASE
    ),
    PIIType.IP_ADDRESS: re.compile(r"(ip[-_]?addr|ip[-_]?address|client[-_]?ip)", re.IGNORECASE),
    PIIType.NAME: re.compile(
        r"(^name$|first[-_]?name|last[-_]?name|full[-_]?name|"
        r"user[-_]?name|author|customer[-_]?name)", re.IGNORECASE
    ),
    PIIType.ADDRESS: re.compile(
        r"(address|street|city|zip|postal|state|country)", re.IGNORECASE
    ),
    PIIType.DATE_OF_BIRTH: re.compile(
        r"(dob|birth[-_]?date|date[-_]?of[-_]?birth|birthday)", re.IGNORECASE
    ),
    PIIType.PASSPORT: re.compile(r"(passport)", re.IGNORECASE),
    PIIType.DRIVER_LICENSE: re.compile(
        r"(driver[-_]?lic|license[-_]?num|dl[-_]?num)", re.IGNORECASE
    ),
}


def detect_pii_in_field(
    field_path: str,
    field_type: str,
    examples: list[Any],
) -> list[PIIDetection]:
    """
    Detect potential PII in a field based on name and values.

    Args:
        field_path: Dot-notation path to the field.
        field_type: Inferred type of the field.
        examples: Sample values from the field.

    Returns:
        List of PII detections with confidence scores.
    """
    detections: list[PIIDetection] = []
    field_name = field_path.split(".")[-1].replace("[]", "")

    # Check field name patterns
    for pii_type, pattern in _NAME_PATTERNS.items():
        if pattern.search(field_name):
            confidence = 0.7  # Base confidence from field name
            detections.append(
                PIIDetection(
                    pii_type=pii_type,
                    confidence=confidence,
                    field_path=field_path,
                )
            )

    # Check value patterns for string types
    if field_type in ("string", "email", "phone") and examples:
        for pii_type, pattern in _PATTERNS.items():
            matches = sum(
                1
                for ex in examples
                if isinstance(ex, str) and pattern.match(ex)
            )
            if matches > 0:
                confidence = min(0.95, 0.5 + (matches / len(examples)) * 0.45)

                # Check if we already have this detection from field name
                existing = next(
                    (d for d in detections if d.pii_type == pii_type),
                    None,
                )
                if existing:
                    existing.confidence = max(existing.confidence, confidence)
                else:
                    detections.append(
                        PIIDetection(
                            pii_type=pii_type,
                            confidence=confidence,
                            field_path=field_path,
                        )
                    )

    return detections


def detect_pii_in_schema(schema_json: dict[str, Any]) -> dict[str, list[PIIDetection]]:
    """
    Scan entire schema for PII fields.

    Args:
        schema_json: Schema analysis JSON from profiling.

    Returns:
        Dict mapping object names to lists of PII detections.
    """
    results: dict[str, list[PIIDetection]] = {}

    for obj in schema_json.get("objects", []):
        obj_name = obj.get("object", "unknown")
        obj_detections: list[PIIDetection] = []

        for field in obj.get("fields", []):
            path = field.get("path", "")
            types = field.get("types", {})
            examples = field.get("examples", [])

            # Get primary type
            primary_type = max(types, key=types.get) if types else "string"

            field_detections = detect_pii_in_field(path, primary_type, examples)
            obj_detections.extend(field_detections)

        if obj_detections:
            results[obj_name] = obj_detections

    return results


def mask_value(value: Any, pii_type: PIIType) -> str:
    """
    Mask a PII value for safe display.

    Args:
        value: Original value to mask.
        pii_type: Type of PII detected.

    Returns:
        Masked string representation.
    """
    if value is None:
        return "***"

    val_str = str(value)
    length = len(val_str)

    if pii_type == PIIType.EMAIL:
        # Show first char and domain
        if "@" in val_str:
            local, domain = val_str.split("@", 1)
            return f"{local[0]}***@{domain}"
        return "***@***.***"

    if pii_type == PIIType.PHONE:
        # Show last 4 digits
        digits = "".join(c for c in val_str if c.isdigit())
        return f"***-***-{digits[-4:]}" if len(digits) >= 4 else "***-***-****"

    if pii_type == PIIType.SSN:
        return "***-**-****"

    if pii_type == PIIType.CREDIT_CARD:
        # Show last 4 digits
        digits = "".join(c for c in val_str if c.isdigit())
        return f"****-****-****-{digits[-4:]}" if len(digits) >= 4 else "****-****-****-****"

    if pii_type == PIIType.IP_ADDRESS:
        # Show first octet
        parts = val_str.split(".")
        return f"{parts[0]}.***.***.**" if parts else "***.***.***.***"

    if pii_type == PIIType.NAME:
        # Show first initial
        words = val_str.split()
        if words:
            return " ".join(w[0] + "***" for w in words if w)
        return "***"

    # Generic masking: show first and last char
    if length > 2:
        return f"{val_str[0]}{'*' * (length - 2)}{val_str[-1]}"
    return "*" * length


def mask_examples(
    examples: list[Any],
    detections: list[PIIDetection],
) -> list[str]:
    """
    Mask all examples based on detected PII types.

    Uses the highest-confidence detection to determine masking strategy.
    """
    if not detections:
        return [str(ex) for ex in examples]

    # Use highest confidence detection
    best = max(detections, key=lambda d: d.confidence)
    return [mask_value(ex, best.pii_type) for ex in examples]


def get_pii_summary(detections: dict[str, list[PIIDetection]]) -> dict[str, Any]:
    """
    Generate a summary of PII detections across all objects.

    Returns:
        Summary dict with counts and high-risk fields.
    """
    total_fields = 0
    by_type: dict[str, int] = {}
    high_risk: list[dict[str, Any]] = []

    for obj_name, obj_detections in detections.items():
        for detection in obj_detections:
            total_fields += 1
            pii_type = detection.pii_type.value
            by_type[pii_type] = by_type.get(pii_type, 0) + 1

            if detection.confidence >= 0.8:
                high_risk.append({
                    "object": obj_name,
                    "field": detection.field_path,
                    "type": pii_type,
                    "confidence": detection.confidence,
                })

    return {
        "total_pii_fields": total_fields,
        "by_type": by_type,
        "high_risk_fields": sorted(
            high_risk, key=lambda x: x["confidence"], reverse=True
        ),
    }
