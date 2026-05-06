# Validation Ownership

## Layers and Responsibilities

| Layer      | Responsibility             | Example |
| ---------- | -------------------------- | ------- |
| Serializer | Transport/input validation | DRF serializers validate incoming request data types, required fields. |
| Service    | Business rules             | `log_prayer` validates prayer_name against allowed values, status allowed. |
| Model      | Invariant constraints      | `full_clean()` validates model fields, uniqueness, etc. |

## Service Validation Guidelines

1. Services should NOT use DRF serializers for validation (transport leakage).
2. Services should perform targeted validation (e.g., validate prayer_name, status) using helper functions.
3. Avoid `full_clean()` on every write - use targeted validation or model validation only when needed.
4. If complex validation is needed, create explicit validation helper functions in services or domain.

## Example

```python
# Service validation helper
def _validate_prayer_name(prayer_name: str) -> str:
    valid_names = {'fajr', 'dhuhr', 'asr', 'maghrib', 'isha'}
    normalized = str(prayer_name).strip().lower()
    if normalized not in valid_names:
        raise ValueError(f"Invalid prayer name: {prayer_name}")
    return normalized

# In log_prayer service:
prayer_name = _validate_prayer_name(prayer_name)
```

## Enforcement

- No DRF serializer imports in service modules.
- No `request` object in services.
- Each service function should have clear validation comments.
