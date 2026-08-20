import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'jameya_masjid.settings')

from django.core.wsgi import get_wsgi_application

application = get_wsgi_application()

# Automatically apply database migrations on Vercel startup (Supabase PostgreSQL schema sync)
try:
    from django.core.management import call_command
    call_command('migrate', interactive=False)
except Exception as e:
    print("Auto-migration on cold start:", e)

app = application
handler = application
