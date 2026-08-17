import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'jameya_masjid.settings')

from django.core.wsgi import get_wsgi_application

application = get_wsgi_application()

# Run database migrations and guarantee admin superuser
try:
    from django.core.management import call_command
    from django.contrib.auth import get_user_model

    call_command('migrate', interactive=False)

    User = get_user_model()
    user, created = User.objects.get_or_create(
        username='admin',
        defaults={'email': 'admin@masjid.com'}
    )
    user.set_password('admin12345')
    user.is_staff = True
    user.is_superuser = True
    user.is_active = True
    user.save()
    print("Guaranteed admin superuser (admin / admin12345)")
except Exception as e:
    print("Vercel Auto-Migration Info:", e)

app = application
handler = application
