web: python manage.py migrate && python manage.py collectstatic --noinput && python seed_data.py && gunicorn scr.wsgi:application --bind 0.0.0.0:$PORT
