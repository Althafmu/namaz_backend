from django.http import JsonResponse
from django.db import connection

def health_check(request):
    """
    Simple health check endpoint.
    """
    try:
        # Test database connection
        connection.ensure_connection()
        db_status = "ok"
    except Exception as e:
        db_status = f"error: {str(e)}"

    return JsonResponse({
        "status": "ok",
        "database": db_status,
    }, status=200 if db_status == "ok" else 500)
