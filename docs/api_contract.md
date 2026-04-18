# API Contract

## Error schema (standardized)

All handled validation errors return:

```json
{
  "code": "STRING_CODE",
  "detail": "Human-readable message",
  "field_errors": {},
  "error": "Human-readable message"
}
```

`error` is a temporary backward-compatible alias for `detail`.

## Core endpoints

### POST `/api/prayers/log/`
- Request fields:
  - `prayer` (required): `fajr|dhuhr|asr|maghrib|isha`
  - `completed` (optional, default `true`)
  - `in_jamaat` (optional)
  - `location` (optional)
  - `reason` (optional)
  - `date` (optional, `YYYY-MM-DD`)
  - `logged_at` (optional, ISO datetime)
  - `prayer_time_windows` (optional, classifier input)
  - `config` (optional, classifier input)
- Response fields:
  - Full `DailyPrayerLogSerializer` payload
- Notes:
  - Status is classified server-side using canonical logic.
  - Compatibility fallback accepts explicit `status` temporarily.
  - Isha cutoff policy: if `qada_end` is absent, Isha qada cutoff defaults to next local day `03:00`.

### GET/PUT `/api/prayers/today/`
- Request (PUT): partial `DailyPrayerLog` update
- Response: full `DailyPrayerLogSerializer` payload

### GET `/api/prayers/history/`
- Query: `days`, `page`
- Response:
  - `results`, `count`, `page`, `total_pages`, `page_size`

### GET `/api/prayers/history/detailed/`
- Query: `year`, `month`, `page`
- Response:
  - `results`, `count`, `page`, `total_pages`, `page_size`

### GET `/api/streak/`
- Response: `current_streak`, `longest_streak`, `last_completed_date`, `display_streak`

### POST `/api/streak/consume-token/`
- Request: optional `date` (`YYYY-MM-DD`)
- Response:
  - `message`, `tokens_remaining`, `weekly_tokens_remaining`, `streak`

### POST `/api/prayers/excused/`
- Request: `date` (`YYYY-MM-DD`), optional `reason`
- Response: full `DailyPrayerLogSerializer` payload

### POST `/api/prayers/log/undo/`
- Request: `prayer`, `date`
- Response: full `DailyPrayerLogSerializer` payload

### GET `/api/sync/status/`
- Response:
  - `pending_count`

### POST `/api/user/pause-notifications-today/`
- Response:
  - `paused_until` (`YYYY-MM-DD`)

