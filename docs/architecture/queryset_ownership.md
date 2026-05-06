# QuerySet Ownership

## Principle

Selectors return lazy QuerySets. They do NOT evaluate querysets, do NOT slice for pagination, and do NOT add pagination metadata.

## Rules

1. Selectors return `QuerySet` (or `None`/`dict` for special cases like `get_today_log`).
2. Views are responsible for:
   - Pagination slicing
   - Counting total results
   - Serialization
3. Services should not evaluate querysets unless necessary for business logic.
4. Avoid double-evaluation: if a queryset is iterated in a service, do not iterate again in view.

## Examples

```python
# Selector: returns QuerySet
def get_prayer_history_queryset(user, days=7):
    today = timezone.localdate()
    start_date = today - timedelta(days=days-1)
    return DailyPrayerLog.objects.filter(
        user=user,
        date__gte=start_date,
        date__lte=today,
    ).order_by('-date')

# View: handles pagination
def prayer_history(request):
    queryset = get_prayer_history_queryset(request.user, days=days)
    total_count = queryset.count()
    # slice
    logs_page = queryset[offset:offset+page_size]
    # serialize
    serializer = DailyPrayerLogSerializer(logs_page, many=True)
```

## Enforcement

- Use `assertNumQueries` tests to detect N+1 queries.
- Avoid serializer evaluation of large querysets.
- Use `select_related`/`prefetch_related` in selectors when needed.
