from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from . import google, views

app_name = "accounts"
urlpatterns = [
    path("google/", google.start, name="google_start"),
    path("google/callback/", google.callback, name="google_callback"),
    path("registro/", views.register, name="register"),
    path("acceso/", views.AccountLoginView.as_view(), name="login"),
    path("salir/", auth_views.LogoutView.as_view(next_page=reverse_lazy("accounts:login")), name="logout"),
    path("verificacion-enviada/", views.verification_sent, name="verification_sent"),
    path("verificar/<str:token>/", views.verify, name="verify"),
    path("reenviar-verificacion/", views.resend_verification, name="resend_verification"),
    path("perfil/", views.profile, name="profile"),
    path("eliminar/", views.request_deletion, name="request_deletion"),
    path("recuperar/", views.AccountPasswordResetView.as_view(), name="password_reset"),
    path("recuperar/enviado/", auth_views.PasswordResetDoneView.as_view(), name="password_reset_done"),
    path(
        "restablecer/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            success_url=reverse_lazy("accounts:password_reset_complete")
        ),
        name="password_reset_confirm",
    ),
    path(
        "restablecer/completo/",
        auth_views.PasswordResetCompleteView.as_view(),
        name="password_reset_complete",
    ),
    path(
        "contrasena/",
        auth_views.PasswordChangeView.as_view(success_url=reverse_lazy("accounts:password_change_done")),
        name="password_change",
    ),
    path("contrasena/actualizada/", auth_views.PasswordChangeDoneView.as_view(), name="password_change_done"),
]
