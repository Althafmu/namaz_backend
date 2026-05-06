# Mutation Semantics

## Pragmatic Tradeoff: `ensure_*_exists()` in GET Endpoints

Currently, some GET endpoints (e.g., `streak_view`) call `ensure_streak_exists()` which writes to DB if streak missing.

This is technically impure REST semantics, but pragmatic for simplicity.

## Why We Do It

- Avoids extra initialization step after user registration.
- Keeps API simple: first GET creates the resource.
- Common pattern in Django monoliths.

## Future Alternatives

1. **Post-registration signal**: Create streak/settings via signal when user is created.
2. **Explicit initialization endpoint**: Client calls POST `/api/v1/streak/init` on first login.
3. **Lazy creation in service**: Service layer handles missing resources.

## Naming Convention

We use `ensure_*_exists()` to communicate side effects:

- `ensure_streak_exists(user)` – mutation: creates if not exists.
- `ensure_user_settings_exist(user)` – mutation: creates if not exists.

This naming makes the side effect explicit, unlike `get_or_create_*` which sounds read-only.

## Documentation

When using `ensure_*_exists()` in views, add a comment:

```python
# Mutation: ensures streak exists (pragmatic tradeoff for simplicity)
streak = ensure_streak_exists(request.user)
```

## Enforcement

- Use `ensure_*` prefix for any function that may create DB records.
- Avoid `get_or_create` in views; move to service layer.
- Document the tradeoff in ADRs (this file).
