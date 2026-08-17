import os
import sys
import traceback

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'jameya_masjid.settings')

_startup_error = None
try:
    from django.core.wsgi import get_wsgi_application
    _django_app = get_wsgi_application()
except Exception as e:
    _django_app = None
    _startup_error = traceback.format_exc()

_migration_attempted = False

def _ensure_migrations():
    global _migration_attempted
    if not _migration_attempted:
        _migration_attempted = True
        try:
            from django.core.management import call_command
            from django.contrib.auth import get_user_model

            call_command('migrate', interactive=False)

            User = get_user_model()
            if not User.objects.filter(is_superuser=True).exists():
                User.objects.create_superuser('admin', 'admin@masjid.com', 'admin12345')
        except Exception as e:
            print("Auto-migration exception:", e)

def handler(environ, start_response):
    if _django_app is None:
        status = '500 Internal Server Error'
        headers = [('Content-Type', 'text/html; charset=utf-8')]
        start_response(status, headers)
        html = f"""
        <html>
        <head><title>Masjid App Startup Error</title></head>
        <body style="font-family: sans-serif; padding: 20px; background: #fff0f0; color: #c00;">
            <h1>⚠️ Django WSGI Startup Error</h1>
            <pre style="background: #222; color: #fff; padding: 15px; border-radius: 6px; overflow-x: auto;">{_startup_error}</pre>
        </body>
        </html>
        """
        return [html.encode('utf-8')]

    _ensure_migrations()

    try:
        return _django_app(environ, start_response)
    except Exception:
        err_detail = traceback.format_exc()
        status = '500 Internal Server Error'
        headers = [('Content-Type', 'text/html; charset=utf-8')]
        start_response(status, headers)
        html = f"""
        <html>
        <head><title>Database Diagnostic Info</title></head>
        <body style="font-family: system-ui, sans-serif; padding: 30px; background: #0f172a; color: #f8fafc;">
            <div style="max-width: 900px; margin: 0 auto; background: #1e293b; padding: 24px; border-radius: 12px; border: 1px solid #ef4444;">
                <h2 style="color: #ef4444; margin-top: 0;">⚠️ Live Application Error Diagnostic</h2>
                <p>Detailed error trace captured below:</p>
                <pre style="background: #090d16; color: #fca5a5; padding: 16px; border-radius: 8px; overflow-x: auto; font-size: 13px; line-height: 1.5;">{err_detail}</pre>
            </div>
        </body>
        </html>
        """
        return [html.encode('utf-8')]

app = handler
application = handler
