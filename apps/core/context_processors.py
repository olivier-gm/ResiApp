from django.conf import settings


def site(request):
    return {
        "local_demo": settings.LOCAL_DEMO,
        "site_url": settings.PUBLIC_BASE_URL,
        "google_oauth_enabled": bool(settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET),
    }
