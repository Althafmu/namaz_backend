from rest_framework.response import Response


def error_response(code, detail, status_code, field_errors=None, extra=None):
    payload = {
        "code": code,
        "detail": detail,
        "field_errors": field_errors or {},
        # Backward-compatible alias during transition
        "error": detail,
    }
    if extra:
        payload.update(extra)
    return Response(payload, status=status_code)

