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

import fnmatch
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any

from datalens.profiling.naming import name_tokens


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
    method: str = "name"
    """What triggered the detection: "name", "value", "name+value" or "config"."""


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

# Field-name hints, matched against whole *tokens* of the field name (snake_case,
# camelCase and kebab-case are split, and adjacent tokens are also joined, so
# "first_name" / "firstName" give "firstname"). Token matching avoids substring
# false positives like "pan" in "company", "tel" in "hotel", "state" in "statement".
#
# Each hint carries the confidence a name alone deserves. Names that clearly
# describe a person's data (email, ssn, first_name…) are strong; generic words
# that often label non-person entities ("name" of a team, "author" of a record)
# are weak and only reported as *possible* PII. Location words on their own
# (city, state, country) are not PII and are not flagged.
_NAME_HINTS: dict[PIIType, tuple[set[str], float]] = {
    PIIType.EMAIL: ({"email", "emailaddress", "emailid", "mail"}, 0.8),
    PIIType.PHONE: ({"phone", "phonenumber", "mobile", "telephone", "tel", "cell", "cellphone", "fax", "msisdn"}, 0.75),
    PIIType.SSN: ({"ssn", "socialsecurity", "socialsecuritynumber", "taxid", "nationalid", "nino"}, 0.85),
    PIIType.CREDIT_CARD: ({"cardnumber", "cardnum", "creditcard", "ccnum", "ccnumber", "pan"}, 0.8),
    PIIType.IP_ADDRESS: ({"ip", "ipaddr", "ipaddress", "clientip", "remoteip"}, 0.6),
    PIIType.NAME: ({"firstname", "lastname", "fullname", "surname", "givenname", "familyname",
                    "middlename", "customername", "username", "displayname"}, 0.75),
    PIIType.ADDRESS: ({"address", "streetaddress", "street", "addressline", "zip", "zipcode",
                       "postal", "postalcode", "postcode"}, 0.6),
    PIIType.DATE_OF_BIRTH: ({"dob", "birthdate", "dateofbirth", "birthday"}, 0.8),
    PIIType.PASSPORT: ({"passport", "passportnumber", "passportno"}, 0.85),
    PIIType.DRIVER_LICENSE: ({"driverlicense", "driverslicense", "licensenumber", "dlnum", "dlnumber"}, 0.85),
}

# Generic words that *may* hold a person's name, reported at low confidence.
_WEAK_NAME_HINTS: dict[str, float] = {"name": 0.4, "author": 0.45, "owner": 0.4, "contact": 0.4}

# Share of observed values that must match a value pattern before it counts.
MIN_VALUE_MATCH_RATIO = 0.3

# Detections at or above this confidence are "high risk" (and masked in reports).
HIGH_RISK_CONFIDENCE = 0.8


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
        examples: Observed values from the field (examples and/or top values).

    Returns:
        List of PII detections with confidence scores. Each detection's
        ``method`` says what triggered it: "name", "value" or "name+value".
    """
    detections: list[PIIDetection] = []
    field_name = field_path.split(".")[-1].replace("[]", "")
    tokens = name_tokens(field_name)

    for pii_type, (hints, confidence) in _NAME_HINTS.items():
        if tokens & hints:
            detections.append(PIIDetection(pii_type, confidence, field_path, method="name"))

    # Value patterns (string-like fields only)
    values = [v for v in examples if isinstance(v, str)]
    if field_type in ("string", "email", "phone") and values:
        for pii_type, pattern in _PATTERNS.items():
            matches = sum(1 for v in values if pattern.match(v))
            ratio = matches / len(values)
            if not matches or ratio < MIN_VALUE_MATCH_RATIO:
                continue
            confidence = min(0.95, 0.5 + ratio * 0.45)
            existing = next((d for d in detections if d.pii_type == pii_type), None)
            if existing:
                existing.confidence = min(0.99, max(existing.confidence, confidence) + 0.05)
                existing.method = "name+value"
            else:
                detections.append(PIIDetection(pii_type, confidence, field_path, method="value"))

    # Generic words ("name", "contact") only count when nothing more specific matched.
    if not detections:
        weak = max((c for word, c in _WEAK_NAME_HINTS.items() if word in tokens), default=0.0)
        if weak:
            detections.append(PIIDetection(PIIType.NAME, weak, field_path, method="name"))

    return detections


def _matches_any(obj_name: str, path: str, patterns: list[str] | dict[str, Any]) -> str | None:
    """Return the first pattern matching "object.path" (fnmatch wildcards), if any."""
    target = f"{obj_name}.{path}"
    for pattern in patterns:
        if fnmatch.fnmatchcase(target, pattern) or fnmatch.fnmatchcase(path, pattern):
            return pattern
    return None


def detect_pii_in_schema(
    schema_json: dict[str, Any],
    *,
    ignore: list[str] | None = None,
    force: dict[str, str] | None = None,
) -> dict[str, list[PIIDetection]]:
    """
    Scan entire schema for PII fields.

    Args:
        schema_json: Schema analysis JSON from profiling.
        ignore: "object.path" patterns never treated as PII (config ``pii_ignore``).
        force: "object.path" pattern → PII type, always treated as PII (config ``pii_force``).

    Returns:
        Dict mapping object names to lists of PII detections.
    """
    results: dict[str, list[PIIDetection]] = {}
    ignore = ignore or []
    force = force or {}

    for obj in schema_json.get("objects", []):
        obj_name = obj.get("object", "unknown")
        obj_detections: list[PIIDetection] = []

        for field in obj.get("fields", []):
            path = field.get("path", "")
            if _matches_any(obj_name, path, ignore):
                continue
            forced = _matches_any(obj_name, path, force)
            if forced:
                try:
                    pii_type = PIIType(force[forced])
                except ValueError:
                    pii_type = PIIType.NAME
                obj_detections.append(PIIDetection(pii_type, 1.0, path, method="config"))
                continue

            types = field.get("types", {})
            non_null = {t: c for t, c in types.items() if t != "null"} or types
            primary_type = max(non_null, key=non_null.get) if non_null else "string"
            values = list(field.get("examples", []))
            values += [v for v in (field.get("value_counts") or {}) if v not in values]

            obj_detections.extend(detect_pii_in_field(path, primary_type, values))

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
    fields: list[dict[str, Any]] = []

    for obj_name, obj_detections in detections.items():
        for detection in obj_detections:
            total_fields += 1
            pii_type = detection.pii_type.value
            by_type[pii_type] = by_type.get(pii_type, 0) + 1

            entry = {
                "object": obj_name,
                "field": detection.field_path,
                "type": pii_type,
                "confidence": round(detection.confidence, 2),
                "method": getattr(detection, "method", "name"),
                "high_risk": detection.confidence >= HIGH_RISK_CONFIDENCE,
            }
            fields.append(entry)
            if entry["high_risk"]:
                high_risk.append(entry)

    return {
        "total_pii_fields": total_fields,
        "fields": fields,
        "by_type": by_type,
        "high_risk_fields": sorted(
            high_risk, key=lambda x: x["confidence"], reverse=True
        ),
    }
