from django.contrib import admin
from django.urls import path
from django.contrib.auth import views as auth_views
from core import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('hola-django/', views.index, name='pagina_inicial'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('entrar-admin/', views.enter_as_admin, name='enter_as_admin'),
    path('', views.dashboard, name='dashboard'),
    path('predios/', views.predios, name='predios'),
    path('predios/nuevo/', views.predio_form, name='predio_create'),
    path('predios/<int:pk>/', views.predio_detail, name='predio_detail'),
    path('predios/<int:pk>/editar/', views.predio_form, name='predio_edit'),
    path('predios/<int:predio_pk>/potreros/nuevo/', views.potrero_form, name='potrero_create'),
    path('predios/<int:predio_pk>/potreros/<int:pk>/editar/', views.potrero_form, name='potrero_edit'),
    path('cuenta/recuperar/', auth_views.PasswordResetView.as_view(template_name='registration/access_form.html', email_template_name='registration/password_reset_email.txt', subject_template_name='registration/password_reset_subject.txt'), name='password_reset'),
    path('cuenta/enviado/', auth_views.PasswordResetDoneView.as_view(template_name='registration/reset_done.html'), name='password_reset_done'),
    path('cuenta/restablecer/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(template_name='registration/access_form.html'), name='password_reset_confirm'),
    path('cuenta/restablecida/', auth_views.PasswordResetCompleteView.as_view(template_name='registration/reset_complete.html'), name='password_reset_complete'),
    path('decisiones/', views.decisiones, name='decisiones'),
    path('calculos/ejecutar/', views.calculate, name='calculate'),
    path('asesor/', views.asesor, name='asesor'),
    path('calculadora/', views.calculadora, name='calculadora'),
    path('cobertura/', views.cobertura, name='cobertura'),
    path('predictor/', views.predictor, name='predictor'),
    path('calendario/', views.calendario, name='calendario'),
    path('actividades/', views.activity_list, name='actividad_list'),
    path('actividades/nueva/', views.activity_create, name='actividad_create'),
    path('actividades/<int:pk>/', views.activity_detail, name='actividad_detail'),
    path('actividades/<int:pk>/editar/', views.activity_edit, name='actividad_edit'),
    path('actividades/<int:pk>/estado/', views.activity_change_status, name='actividad_estado'),
    path('actividades/<int:pk>/eliminar/', views.activity_delete, name='actividad_delete'),
    path('busqueda/', views.busqueda, name='busqueda'),
    path('reportes/', views.reportes, name='reportes'),
    path('panel-admin/', views.admin_panel, name='admin_panel'),
]
