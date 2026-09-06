from django.urls import path

from .password_reset_views import ChangePasswordView, ForgotPasswordView, ResetPasswordView
from .token_views import NewshubTokenObtainPairView, NewshubTokenRefreshView
from .views import LogoutView, MeView, RegisterAuthorView, RegisterReaderView, SubscriberRegisterView

urlpatterns = [
    path("register/", RegisterReaderView.as_view(), name="register-reader"),
    path("register-subscriber/", SubscriberRegisterView.as_view(), name="register-subscriber"),
    path("register-author/", RegisterAuthorView.as_view(), name="register-author"),
    path("login/", NewshubTokenObtainPairView.as_view(), name="token-obtain-pair"),
    path("refresh/", NewshubTokenRefreshView.as_view(), name="token-refresh"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("me/", MeView.as_view(), name="me"),
    path("forgot-password/", ForgotPasswordView.as_view(), name="forgot-password"),
    path("reset-password/", ResetPasswordView.as_view(), name="reset-password"),
    path("change-password/", ChangePasswordView.as_view(), name="change-password"),
]
