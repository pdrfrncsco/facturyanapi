from rest_framework.views import exception_handler


def enveloped_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is not None:
        response.data = {"success": False, "data": None, "errors": response.data}
    return response
