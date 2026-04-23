web: gunicorn nestova.wsgi:application --bind 0.0.0.0:$PORT
worker: celery -A nestova worker --loglevel=info --pool=solo
beat: celery -A nestova beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler