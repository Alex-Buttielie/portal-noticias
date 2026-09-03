import os
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-secret")
DEBUG = os.getenv("DEBUG", "0") == "1"
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "*").split(",")
INSTALLED_APPS = ["django.contrib.contenttypes","django.contrib.auth","rest_framework","corsheaders","core","payments"]
MIDDLEWARE = ["corsheaders.middleware.CorsMiddleware","django.middleware.common.CommonMiddleware"]
ROOT_URLCONF = "config.urls"
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3","NAME": "/tmp/db.sqlite3"}}
REST_FRAMEWORK = {"DEFAULT_AUTHENTICATION_CLASSES": ["core.authentication.FirebaseAuthentication"],"DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticatedOrReadOnly"]}
CORS_ALLOW_ALL_ORIGINS = True
PAYMENT_PROVIDER = os.getenv("PAYMENT_PROVIDER","fake")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY","")
FIREBASE_CREDENTIALS = os.getenv("FIREBASE_CREDENTIALS","")
