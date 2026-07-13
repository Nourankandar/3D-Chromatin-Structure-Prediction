from django.db import models

# This app intentionally has no custom models — authentication is built
# directly on top of Django's built-in `django.contrib.auth.models.User`.
# See services.py for the AuthService and views.py for the REST endpoints.
