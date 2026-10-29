from django.utils.cache import patch_vary_headers


class PrivacyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        patch_vary_headers(response, ["Cookie", "HX-Request", "HX-History-Restore-Request"])
        if request.user.is_authenticated or request.path.startswith(("/panel/", "/cuenta/", "/media/")):
            response["Cache-Control"] = "private, no-store"
            response["X-Robots-Tag"] = "noindex, nofollow"
        response["Referrer-Policy"] = "same-origin"
        response["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        return response
