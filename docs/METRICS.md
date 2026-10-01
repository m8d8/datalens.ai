# How Datalens scores your data

Every number in the report is explained here: what it means, when it is computed, and exactly how.
This file is generated from `src/datalens/glossary.py` (`datalens glossary --markdown > docs/METRICS.md`),
which reads the same constants the code uses — so it always matches the implementation.

## Health score

One number for 'can I trust this data today?': DQI minus penalties for PII, drift, expected-schema failures and mixed types. ≥80 healthy, ≥60 needs attention, below is at risk.

**When:** Every run.

**How:**

- start from the overall DQI (70 if quality could not be scored)
- − PII: 3 per high-risk PII field, max 15
- − drift vs the reference run: 0 none · 3 info only · 10 warnings · 20 any breach
- − expected schema (BYOS): 3 per failed check, max 15
- − mixed types: 1.5 per field holding more than one non-null type, max 10
- status: ≥80 🟢 healthy · ≥60 🟡 attention · else 🔴 risk; a drift breach caps the status at 'attention'

## Data Quality Index (DQI)

0–100 weighted mean of the quality dimensions (completeness, consistency, uniqueness, validity, timeliness, granularity, accuracy) per object; the overall DQI is the mean over objects.

**When:** Every run, per object and overall.

**How:**

- object DQI = Σ(dimension score × weight) / Σ(weights of the dimensions that could be scored)
- weights: completeness 0.30, consistency 0.25, uniqueness 0.20, validity 0.25, timeliness 0.10, granularity 0.10, accuracy 0.15
- a dimension that can't be scored (e.g. no date fields → no timeliness) is left out, and the remaining weights are re-normalised
- overall DQI = mean of object DQIs

## Completeness

Average share of rows where each field is present and not null/empty.

**When:** Every object. Weight 0.30 in the DQI.

**How:**

- per field: (rows with the key present − null/empty values) / rows sampled × 100
- nested fields are measured against their parent: extras.wides counts only rows that have an `extras` object (optional sub-objects aren't penalised for being optional)
- object score: mean over all fields (nested fields included)
- fields below 50% are listed as problem fields

## Consistency

How reliably each field keeps one type: share of non-null values that have the field's main type.

**When:** Every object. Weight 0.25 in the DQI.

**How:**

- per field: count of the dominant type / all non-null values × 100 (nulls don't count — they are a completeness matter)
- object score: mean over fields
- e.g. 950 ints + 50 strings → 95

## Uniqueness

Does each object have a unique identifier? Score = distinct ratio of its most unique id-like field.

**When:** Objects with at least one top-level identifier-shaped field (id, *_id, uuid, key, code…). Weight 0.20.

**How:**

- candidates: top-level fields whose name has an identifier token (so 'video' ≠ 'id')
- score = 100 if the best candidate is ≥99% distinct, else distinct ratio × 100
- references to other objects (customer_id in orders) are expected to repeat and are not penalised
- no identifier field → 100 (nothing to check)

## Validity

Penalises suspicious values: a text field with one repeated value, or fields mostly null/empty.

**When:** Every object. Weight 0.25 in the DQI.

**How:**

- per field start at 100
- −20 if a text field has exactly one distinct value over >10 rows (placeholder/default?)
- −30 if more than half of the present values are null/empty
- object score: mean over fields

## Timeliness

How fresh the data is: age of the newest record in date fields (100 = today).

**When:** Objects with date fields (by value type or name). Weight 0.10.

**How:**

- age = today − newest date found (ISO dates, tracked across every row read)
- score = 100 − 25·log10(age in days + 1): same day ≈100, a week ≈77, a month ≈63, a year ≈36
- − 5 per future-dated example, max −40
- dates that can't be parsed → neutral 70

## Granularity

Share of scalar fields whose cardinality is useful: not constant, and not unique-per-row unless an id.

**When:** Objects with ≥20 rows (fewer rows make every field look constant or unique). Weight 0.10.

**How:**

- constant field (≤1 distinct value) → not healthy
- non-identifier field distinct on ≥99% of rows (free text / noise) → not healthy
- score = healthy fields / scalar fields × 100

## Accuracy (pattern conformance)

How consistently values follow their field's dominant shape (UUID, email, date, code…).

**When:** Objects where value patterns were detected. Weight 0.15.

**How:**

- per field: share of values matching the dominant detected pattern
- object score: mean over pattern-bearing fields × 100

## Field quality score

Per-field score used in the field explorer.

**When:** Every field.

**How:**

- 0.4·completeness + 0.3·consistency + 0.3·validity

## Coverage

True coverage: share of rows where the field holds a real value. Rows where it is missing, null or empty all count against it — the same number everywhere in the report and its exports.

**When:** Every field, every run; tracked across runs for drift.

**How:**

- (rows with a real value) / rows profiled × 100 — a missing key, null, "", [] or {} is not a value
- drift rule (default): a decrease of ≥ 25% or an increase of ≥ 50%, relative to the earlier coverage (100% → 70% is −30%; 40% → 63% is +58%); moves under 1 point are ignored
- override globally (--coverage-drop / --coverage-increase), per object, or per field (--field-coverage-rule, a drift: config section, or x-datalens in an expected schema); the most specific rule wins
- changes within 3 standard errors of sampling noise (√(p(1−p)/n)) are ignored

## Row count (volume)

Rows in the object. True count when the whole source was read, otherwise the sample size.

**When:** Every run; drift compares it with the reference or the learned band.

**How:**

- default rule: warn at −10%, fail at −25%; warn at +50%, fail at +200%

## Distribution shift (PSI)

Population Stability Index: how much a field's value mix moved. <0.10 stable, 0.10–0.25 moderate, >0.25 major.

**When:** Category-like and numeric fields present in both runs with enough rows (ids, references, dates excluded).

**How:**

- PSI = Σ (new% − old%) · ln(new% / old%) over value bins
- categories: one bin per value; numbers: the reference run's deciles (+ below-min / above-max bins)
- noise floor: two samples of the same data give PSI ≈ (bins−1)·(1/n₁+1/n₂); shifts below 3× that are not reported
- default thresholds: warn ≥0.1, fail ≥0.25

## Rolling baseline (learned normal range)

Each metric learns its own normal range from recent runs: median ± 3 robust sigmas, widened to include every non-breached value seen. Alerts only when today falls outside.

**When:** --compare-to rolling (or drift.compare_to: rolling), once a metric has ≥3 earlier runs.

**How:**

- M = median of the last N values (default N = 14)
- MAD = median(|xᵢ − M|); σ̂ = 1.4826·MAD (robust: one bad run can't inflate it)
- σ̂ₑ = max(σ̂, 5%·|M|, sampling noise for percentages, 1 for counts)
- band = [min(M − 3σ̂ₑ, min seen·0.95), max(M + 3σ̂ₑ, max seen·1.05)]
- outside the band → warn; also |x − M| > 3σ̂ₑ → fail
- runs that breached are left out of later baselines (a bad day can't become 'normal')
- fewer than 3 earlier values → cold start: the fixed rules apply and the report says so

## Orphan rate (referential integrity)

Share of a foreign key's values that point to a row that doesn't exist in the parent object.

**When:** Fields whose values mostly (≥50%) resolve to another object's unique key.

**How:**

- orphans = child occurrences whose value is not among the parent key's values
- orphan % = orphans / child occurrences × 100 (exact, from value hashes kept in memory only)

## PII exposure score & risk

Share of fields holding PII, weighted by sensitivity. A confirmed direct identifier raises the risk floor (email/phone → at least medium; SSN/card/passport → high).

**When:** Every run.

**How:**

- sensitivity: ssn 3, credit_card 3, passport 3, driver_license 3, date_of_birth 3, email 2, phone 2, ip_address 2, address 2, name 1
- exposure = min(100, Σ(sensitivity × PII fields) / all fields × 50)
- risk: 0 none · <25 low · <60 medium · else high, then the direct-identifier floor
- high-risk = detection confidence ≥ 80% (value match, strong field name, or pii_force); these are masked in every output

## Fitness for use

Per-object readiness badges for reporting and ML, derived from DQI, completeness, consistency, PII and drift.

**When:** Every object.

**How:**

- Ready for reporting: DQI ≥ 75 and completeness ≥ 70
- Ready for ML/AI: DQI ≥ 80, consistency ≥ 90, no high-risk PII
- Needs cleanup: DQI < 70 or ≥5 problem fields
- Recently changed: this object has drift vs the reference run

## Expected-schema conformance (BYOS)

Share of checks against your expected JSON Schema that pass (required, type, enum, range, pattern…).

**When:** When --schema / expected_schema is given.

**How:**

- checks per declared field: required (coverage ≥ x-datalens.min_coverage, default 99%), type, format, enum, minimum/maximum, pattern
- undeclared fields: warn when additionalProperties is false, info otherwise
- conformance = passed / judged checks × 100 (info checks aren't judged)

## Default drift rules

Override any of these per dataset, object or field (see `docs/USAGE.md` → Drift rules).

```yaml
drift:
  defaults:
    row_count: {drop_pct: {warn: 10, fail: 25}, increase_pct: {warn: 50, fail: 200}}
    coverage: {drop_pct: 25, increase_pct: 50, min_delta: 1.0}
    distinct: {change_pct: {warn: 25}, min_delta: 3}
    orphan_pct: {increase_pts: {warn: 0.5, fail: 2}}
    dqi: {drop_pts: {warn: 3, fail: 8}}
    health: {drop_pts: {warn: 5, fail: 15}}
    distribution: {psi_warn: 0.1, psi_fail: 0.25}
    categories: {new: warn, vanished: warn}
    schema: {field_removed: fail, field_added: info, field_renamed: warn, type_changed: fail, object_removed: fail, object_added: info}
```

