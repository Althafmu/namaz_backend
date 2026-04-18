from rest_framework.views import exception_handler as drf_exception_handler


def api_exception_handler(exc, context):
    response = drf_exception_handler(exc, context)
    if response is None:
        return response

    detail = response.data.get("detail") if isinstance(response.data, dict) else str(response.data)
    field_errors = {}
    if isinstance(response.data, dict):
        for key, value in response.data.items():
            if key != "detail":
                field_errors[key] = value

    response.data = {
        "code": "API_ERROR",
        "detail": str(detail),
        "field_errors": field_errors,
        "error": str(detail),
    }
    return response

