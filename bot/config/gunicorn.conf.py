import os

workers = int(os.getenv("GUNICORN_WORKERS", "2"))
bind = os.getenv("GUNICORN_BIND", "0.0.0.0:8000")
accesslog = os.getenv("GUNICORN_ACCESS_LOG", "-")
errorlog = os.getenv("GUNICORN_ERROR_LOG", "-")
