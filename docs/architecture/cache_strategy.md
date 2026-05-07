# Cache Strategy for Group Selectors

## Current State (G2 Prep)

### Query Patterns
1. **Group List** (`get_group_queryset`)
   - Annotations: `member_count`, `user_is_member`
   - Filters: privacy_level, user membership
   - Current queries: 1 (verified by assertNumQueries)

2. **User Groups** (`get_user_groups_queryset`)
   - Annotations: `member_count`
   - Filters: user memberships (status=active)
   - Current queries: 1 (verified by assertNumQueries)

3. **Group Detail** (future)
   - Additional annotations: member list, recent activity
   - Expected queries: 1-3 (with proper select_related/prefetch_related)

---

## Cache Strategy for G2

### 1. Cache Layers

#### L1: QuerySet Cache (Short TTL: 60s)
```python
from django.core.cache import cache

def get_cached_group_queryset(user=None, privacy_filter=None, timeout=60):
    """Cached version for read-heavy endpoints."""
    cache_key = f"group_qs:{user.id if user else 'anon'}:{privacy_filter}"
    
    # Try cache first
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    
    # Compute and cache
    qs = get_group_queryset(user, privacy_filter)
    # Force evaluation and store
    result = list(qs)
    cache.set(cache_key, result, timeout)
    return result
```

#### L2: Object Cache (Medium TTL: 300s)
```python
def get_cached_group_detail(group_id, user=None, timeout=300):
    """Cache individual group with annotations."""
    cache_key = f"group_detail:{group_id}:{user.id if user else 'anon'}"
    
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    
    group = Group.objects.get(id=group_id)
    # Add annotations
    # ...
    
    cache.set(cache_key, group, timeout)
    return group
```

---

### 2. Invalidation Strategy

#### Triggers for Invalidation:
1. **Membership changes** (join/leave/remove/ban)
   ```python
   def invalidate_group_cache_on_membership_change(sender, instance, **kwargs):
       """Invalidate when membership status changes."""
       group = instance.group
       # Invalidate group list (user count changed)
       cache.delete_pattern(f"group_qs:*")
       # Invalidate specific group detail
       cache.delete(f"group_detail:{group.id}:*")
   ```

2. **Group updates** (name, description, privacy)
   ```python
   def invalidate_group_cache_on_update(sender, instance, **kwargs):
       """Invalidate when group metadata changes."""
       cache.delete_pattern(f"group_qs:*")
       cache.delete_pattern(f"group_detail:{instance.id}:*")
   ```

3. **Invite consumption** (member count changes)
   ```python
   # Already handled by membership signal
   ```

---

### 3. Implementation Plan (G2 Proper)

#### Phase 1: Add Signals (Week 1)
- Create `prayers/signals.py`
- Connect `post_save`/`post_delete` for `GroupMembership`
- Connect `post_save` for `Group`

#### Phase 2: Add Cache Layer (Week 2)
- Implement `get_cached_group_queryset()`
- Implement `get_cached_group_detail()`
- Add cache keys to `group_selectors.py`

#### Phase 3: Add Prefetch Optimization (Week 3)
- Use `select_related('created_by')` for Group
- Use `prefetch_related('memberships', 'memberships__user')` for member lists

#### Phase 4: Monitor & Tune (Week 4)
- Add Django Debug Toolbar for query analysis
- Monitor cache hit/miss ratios
- Adjust TTL based on usage patterns

---

## Cache Backend Recommendation

### Development:
```python
# settings/dev.py
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    }
}
```

### Production:
```python
# settings/prod.py
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/1',
        'OPTIONS': {
            'CLIENT_CLASS': 'django.core.cache.backends.redis.RedisClient',
            'SOCKET_CONNECT_TIMEOUT': 5,
            'SOCKET_TIMEOUT': 5,
            'CONNECTION_POOL_KWARGS': {
                'max_connections': 100,
            },
        }
    }
}
```

---

## Query Governance with Cache

### Assertions (from test_group_baseline.py)
```python
# Stable selectors: exact assertions
with self.assertNumQueries(1):
    groups = list(get_group_queryset(user=self.user))

# Cache-enabled endpoints: bounded assertions
with self.assertLessEqual(len(connection.queries), 3):
    groups = list(get_cached_group_queryset(user=self.user))
```

---

## Next Steps (G2 Proper)

1. ☐ Create `prayers/signals.py` with invalidation handlers
2. ☐ Update `group_selectors.py` to use cache layer
3. ☐ Add `select_related`/`prefetch_related` optimizations
4. ☐ Create cache invalidation tests
5. ☐ Monitor query counts with Django Debug Toolbar
6. ☐ Tune cache TTL based on usage patterns

---

**Status:** Plan complete. Ready for G2 proper implementation.
