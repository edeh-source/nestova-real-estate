import sys
import logging
from django.shortcuts import render

logger = logging.getLogger('nestova')

def custom_404(request, exception):
    """Custom 404 error page"""
    return render(request, '404.html', status=404)

def custom_500(request):
    """Custom 500 error page that logs the active exception and traceback to production terminal"""
    exc_type, exc_value, exc_traceback = sys.exc_info()
    if exc_value:
        logger.error(
            "\n" + "=" * 70 + "\n"
            f"[PRODUCTION 500 ERROR] {request.method} {request.path}\n"
            f"User: {getattr(request, 'user', 'Anonymous')}\n"
            f"Exception: {exc_type.__name__ if exc_type else 'Unknown'}: {exc_value}\n"
            + "=" * 70,
            exc_info=(exc_type, exc_value, exc_traceback)
        )
    else:
        logger.error(f"[PRODUCTION 500 ERROR] 500 handler triggered for {request.method} {request.path} (no active exception)")

    return render(request, '500.html', status=500)

