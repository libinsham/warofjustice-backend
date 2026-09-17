from django.urls import path

from .password_reset_views import (
    ChangePasswordView,
    ForgotPasswordView,
    ResetPasswordView,
)

from .token_views import (
    NewshubTokenObtainPairView,
    NewshubTokenRefreshView,
)

from .views import (
    LogoutView,
    MeView,
    MemberContributorApplicationApproveView,
    MemberContributorApplicationDocumentView,
    MemberContributorApplicationListView,
    MemberContributorApplicationRejectView,
    MemberContributorRegisterView,
    RegisterAuthorView,
    RegisterReaderView,
    SubscriberApplicationListView,
    SubscriberRegisterView,
)


urlpatterns = [
    # =====================================================
    # READER REGISTRATION
    # =====================================================

    path(
        "register/",
        RegisterReaderView.as_view(),
        name="register-reader",
    ),

    # =====================================================
    # SUBSCRIBER REGISTRATION
    # =====================================================

    path(
        "register-subscriber/",
        SubscriberRegisterView.as_view(),
        name="register-subscriber",
    ),

    # =====================================================
    # SUBSCRIBER APPLICATIONS
    # ADMIN LIST
    # =====================================================

    path(
        "subscriber-applications/",
        SubscriberApplicationListView.as_view(),
        name="subscriber-applications",
    ),

    # =====================================================
    # MEMBER & CONTRIBUTOR REGISTRATION
    # =====================================================

    path(
        "register-member-contributor/",
        MemberContributorRegisterView.as_view(),
        name="register-member-contributor",
    ),

    # =====================================================
    # MEMBER & CONTRIBUTOR APPLICATIONS
    # ADMIN LIST
    # =====================================================

    path(
        "member-contributor-applications/",
        MemberContributorApplicationListView.as_view(),
        name="member-contributor-applications",
    ),

    # =====================================================
    # APPROVE APPLICATION
    # =====================================================

    path(
        "member-contributor-applications/<int:pk>/approve/",
        MemberContributorApplicationApproveView.as_view(),
        name="member-contributor-application-approve",
    ),

    # =====================================================
    # REJECT APPLICATION
    # =====================================================

    path(
        "member-contributor-applications/<int:pk>/reject/",
        MemberContributorApplicationRejectView.as_view(),
        name="member-contributor-application-reject",
    ),

    # =====================================================
    # VIEW APPLICATION DOCUMENT
    # =====================================================

    path(
        "member-contributor-applications/<int:pk>/document/<str:document_type>/",
        MemberContributorApplicationDocumentView.as_view(),
        name="member-contributor-application-document",
    ),

    # =====================================================
    # AUTHOR REGISTRATION
    # =====================================================

    path(
        "register-author/",
        RegisterAuthorView.as_view(),
        name="register-author",
    ),

    # =====================================================
    # LOGIN
    # =====================================================

    path(
        "login/",
        NewshubTokenObtainPairView.as_view(),
        name="token-obtain-pair",
    ),

    # =====================================================
    # TOKEN REFRESH
    # =====================================================

    path(
        "refresh/",
        NewshubTokenRefreshView.as_view(),
        name="token-refresh",
    ),

    # =====================================================
    # LOGOUT
    # =====================================================

    path(
        "logout/",
        LogoutView.as_view(),
        name="logout",
    ),

    # =====================================================
    # CURRENT USER
    # =====================================================

    path(
        "me/",
        MeView.as_view(),
        name="me",
    ),

    # =====================================================
    # FORGOT PASSWORD
    # =====================================================

    path(
        "forgot-password/",
        ForgotPasswordView.as_view(),
        name="forgot-password",
    ),

    # =====================================================
    # RESET PASSWORD
    # =====================================================

    path(
        "reset-password/",
        ResetPasswordView.as_view(),
        name="reset-password",
    ),

    # =====================================================
    # CHANGE PASSWORD
    # =====================================================

    path(
        "change-password/",
        ChangePasswordView.as_view(),
        name="change-password",
    ),
]