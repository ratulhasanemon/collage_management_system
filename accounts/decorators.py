from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def role_required(*roles):
    """Restrict a view to the given UserProfile.role values.

    Usage:
        @role_required('admin', 'accountant')
        def add_fee(request): ...

    This is used on the *new* accounts views for defense-in-depth. Existing
    views in your app are protected centrally instead, via
    accounts/middleware.py, so their code never has to be touched.
    """

    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def _wrapped(request, *args, **kwargs):
            profile = getattr(request.user, "profile", None)
            if request.user.is_superuser and profile is None:
                return view_func(request, *args, **kwargs)
            if profile is None or profile.role not in roles:
                raise PermissionDenied("You do not have permission to access this page.")
            return view_func(request, *args, **kwargs)

        return _wrapped

    return decorator
