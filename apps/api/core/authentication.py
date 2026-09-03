from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
import os
class FirebaseAuthentication(BaseAuthentication):
    def authenticate(self, request):
        h = request.headers.get("Authorization","")
        if not h.startswith("Bearer "): return None
        token = h[7:]
        if os.getenv("FIREBASE_BYPASS_FOR_TEST") == "1" and token == "test-token":
            from django.contrib.auth.models import AnonymousUser
            u = AnonymousUser(); u.is_authenticated = True; u.uid = "test-user"; return (u, None)
        try:
            import firebase_admin, firebase_admin.auth
            if not firebase_admin._apps:
                import firebase_admin.credentials, json
                cred = os.getenv("FIREBASE_CREDENTIALS")
                if cred: firebase_admin.initialize_app(firebase_admin.credentials.Certificate(json.loads(cred)))
                else: firebase_admin.initialize_app()
            decoded = firebase_admin.auth.verify_id_token(token)
            from django.contrib.auth.models import AnonymousUser
            u = AnonymousUser(); u.is_authenticated = True; u.uid = decoded.get("uid"); u.claims = decoded; return (u, None)
        except Exception as e:
            raise AuthenticationFailed(str(e))
