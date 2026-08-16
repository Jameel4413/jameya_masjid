import os
import sys
import traceback

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'jameya_masjid.settings')

try:
    from django.core.wsgi import get_wsgi_application
    _django_app = get_wsgi_application()

    def app(environ, start_response):
        try:
            return _django_app(environ, start_response)
        except Exception as ex:
            status = '500 Internal Server Error'
            response_headers = [('Content-type', 'text/html; charset=utf-8')]
            start_response(status, response_headers)
            err_msg = traceback.format_exc()
            return [f"<html><body><h2>Django Request Exception</h2><pre>{err_msg}</pre></body></html>".encode('utf-8')]

except Exception as e:
    err_tb = traceback.format_exc()

    def app(environ, start_response):
        status = '500 Internal Server Error'
        response_headers = [('Content-type', 'text/html; charset=utf-8')]
        start_response(status, response_headers)
        return [f"<html><body><h2>Django Startup Exception</h2><pre>{err_tb}</pre></body></html>".encode('utf-8')]

handler = app
application = app
