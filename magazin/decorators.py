from django.core.exceptions import PermissionDenied
from functools import wraps


def role_required(*roles):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                from django.shortcuts import redirect
                return redirect('login')
            try:
                if request.user.profile.role in roles:
                    return view_func(request, *args, **kwargs)
            except Exception:
                pass
            raise PermissionDenied
        return wrapper
    return decorator