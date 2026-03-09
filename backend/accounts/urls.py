from django.urls import path, include
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from rest_framework.routers import DefaultRouter
from .views import UserDetailView, UserViewSet
from .google_auth import GoogleLoginView
from django.http import JsonResponse

router = DefaultRouter()
router.register(r'users', UserViewSet, basename='user')

def test_server_view(request):
    return JsonResponse({"status": "running", "canary": "V3_FIXED"})

urlpatterns = [
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('me/', UserDetailView.as_view(), name='user_detail'),
    path('google-login/', GoogleLoginView.as_view(), name='google_login'),
    path('test-server/', test_server_view, name='test_server'),
    path('', include(router.urls)),
]
