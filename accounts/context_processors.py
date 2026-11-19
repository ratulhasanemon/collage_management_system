from django.apps import apps

from .middleware import CORE_APP


def site_branding(request):
    """Makes the college's name & logo — set by the admin from the main
    dashboard's "College Info" modal — available as `site_settings` in
    every template rendered with a request (login page, student/teacher
    dashboards, profile, class routine, etc.).

    Read-only, single DB query per request, and fails silently (falls
    back to the hardcoded "MPI" default already baked into the templates)
    if the SiteSettings row doesn't exist yet or the app isn't ready.
    """
    try:
        SiteSettings = apps.get_model(CORE_APP, "SiteSettings")
        site_settings = SiteSettings.objects.first()
    except Exception:
        site_settings = None
    return {"site_settings": site_settings}