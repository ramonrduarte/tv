from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
import clientes.views as clientes_views

urlpatterns = [
    path('admin/', admin.site.urls),

    # Auth
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),

    # Dashboard
    path('', clientes_views.dashboard, name='dashboard'),

    # Relatórios
    path('relatorios/', clientes_views.relatorios, name='relatorios'),

    # Busca global
    path('busca/', clientes_views.busca_global, name='busca_global'),

    # Configurar mensagens WhatsApp
    path('configuracoes/mensagens/', clientes_views.configurar_mensagens, name='configurar_mensagens'),

    # Apps
    path('clientes/', include('clientes.urls', namespace='clientes')),
    path('listas/', include('listas.urls', namespace='listas')),
    path('mensalidades/', include('financeiro.urls', namespace='financeiro')),
    path('usuarios/', include('usuarios.urls', namespace='usuarios')),

    # API
    path('api/v1/', include('api.urls', namespace='api')),
]
