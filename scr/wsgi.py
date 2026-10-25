"""
WSGI config for scr project.
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'scr.settings')
django.setup()

# Staticfiles va Media papkalarini mavjudligini ta'minlash
try:
    from django.conf import settings
    if hasattr(settings, 'STATIC_ROOT') and settings.STATIC_ROOT:
        os.makedirs(settings.STATIC_ROOT, exist_ok=True)
    if hasattr(settings, 'MEDIA_ROOT') and settings.MEDIA_ROOT:
        os.makedirs(settings.MEDIA_ROOT, exist_ok=True)
except Exception:
    pass

# PostgreSQL bazasini tekshirish va agar jadvallar bo'lmasa darhol migratsiya qilish
try:
    from django.db import connection
    from django.core.management import call_command

    tables = connection.introspection.table_names()
    if 'app_book' not in tables or 'app_category' not in tables:
        print("[STARTUP] Baza jadvallari topilmadi. Avtomatik 'migrate' bajarilmoqda...")
        call_command('migrate', interactive=False)
        print("[STARTUP] Migratsiya muvaffaqiyatli bajarildi!")
        try:
            from seed_data import run_seed
            run_seed()
            print("[STARTUP] Boshlang'ich ma'lumotlar (seed) muvaffaqiyatli kiritildi!")
        except Exception as seed_err:
            print(f"[STARTUP] Seed xatosi: {seed_err}")
    else:
        print("[STARTUP] Baza jadvallari mavjud.")
except Exception as e:
    print(f"[STARTUP] Avtomatik migratsiyada xatolik: {e}")

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
