class TenantHeaderMiddleware:
    """Stores tenant headers for later validation inside DRF permissions."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.tenant_id = request.headers.get("X-Organization-ID")
        request.tenant_nif = request.headers.get("X-Organization-NIF")
        request.empresa = None
        return self.get_response(request)
