from rest_framework.response import Response


ERROR_MESSAGES = {
    "INVALID_MANUAL_OFFSETS": "manual_offsets must be a JSON object",
    "INVALID_OFFSET_KEY": "Invalid offset key.",
    "INVALID_OFFSET_VALUE": "Offset value must be an integer.",
    "INVALID_INTENT_LEVEL": "Invalid intent_level.",
    "MISSING_INTENT_LEVEL": "intent_level is required",
    "VALIDATION_ERROR": "Validation error.",
    "INVALID_DAYS": "days parameter must be a valid integer",
    "INVALID_DAYS_RANGE": "days parameter must be between 1 and 365",
    "INVALID_PRAYER_NAME": "Invalid prayer name.",
    "INVALID_DATE_FORMAT": "Invalid date format. Expected YYYY-MM-DD.",
    "FUTURE_DATE_NOT_ALLOWED": "Cannot use future dates.",
    "EDIT_WINDOW_EXCEEDED": "Cannot edit prayers more than 2 days in the past.",
    "INVALID_STATUS_CLASSIFICATION_INPUT": "Invalid status.",
    "INVALID_YEAR": "year parameter must be a valid integer",
    "INVALID_MONTH": "month parameter must be a valid integer",
    "INVALID_MONTH_RANGE": "month must be between 1 and 12",
    "MISSING_DATE": "date is required. Format: YYYY-MM-DD",
    "EXCUSED_FUTURE_LIMIT": "Cannot set excused more than 7 days in the future.",
    "EXCUSED_PAST_LIMIT": "Cannot set excused more than 30 days in the past.",
    "TOKEN_NOT_ALLOWED": "Token consumption is not allowed right now.",
    "NO_TOKENS_AVAILABLE": "No protector tokens available. Tokens reset every Sunday.",
    "TOKEN_WINDOW_EXCEEDED": "Can only consume token for today or yesterday (Qada must be within 24 hours).",
    "DATE_ALREADY_VALID": "Date is already valid for streak. No token needed.",
    "UNDO_NOT_AVAILABLE": "No completed prayer found to undo for the selected date.",
    "LOG_NOT_FOUND": "No prayer log found for the requested date.",
    "SUNNAH_GROWTH_REQUIRED": "Sunna tracking is only available for Growth intent level.",
}


def error_response(code, detail, status_code, field_errors=None):
    safe_detail = ERROR_MESSAGES.get(code, "Request failed.")
    payload = {
        "code": code,
        "detail": safe_detail,
        "field_errors": field_errors or {},
        # Backward-compatible alias during transition
        "error": safe_detail,
    }
    return Response(payload, status=status_code)
