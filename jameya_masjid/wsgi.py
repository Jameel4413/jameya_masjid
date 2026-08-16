"""
WSGI config for jameya_masjid project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'jameya_masjid.settings')

application = get_wsgi_application()
app = application

# Automatic migration & initial superuser creation for cloud database (Vercel / Supabase)
try:
    from django.core.management import call_command
    from django.contrib.auth import get_user_model

    call_command('migrate', interactive=False)

    User = get_user_model()
    if not User.objects.filter(is_superuser=True).exists():
        User.objects.create_superuser('admin', 'admin@masjid.com', 'admin12345')
        print("Auto Superuser created: admin / admin12345")
except Exception as e:
    print("Auto migration info:", e)

