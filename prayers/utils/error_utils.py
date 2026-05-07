from rest_framework.response import Response
from rest_framework import status


def error_response(message, code=None, http_status=status.HTTP_400_BAD_REQUEST):
    return Response({
        'success': False,
        'error': {
            'message': message,
            'code': code or 'error',
        }
    }, status=http_status)


def not_found_response(message='Resource not found'):
    return error_response(message, 'not_found', status.HTTP_404_NOT_FOUND)


def unauthorized_response(message='Authentication required'):
    return error_response(message, 'unauthorized', status.HTTP_401_UNAUTHORIZED)


def forbidden_response(message='Access denied'):
    return error_response(message, 'forbidden', status.HTTP_403_FORBIDDEN)