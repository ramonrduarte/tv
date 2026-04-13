from django.urls import path
from . import views

app_name = 'listas'

urlpatterns = [
    # Listas de canais
    path('', views.ListaCanaisListView.as_view(), name='lista'),
    path('nova/', views.ListaCanaisCreateView.as_view(), name='nova'),
    path('<int:pk>/', views.lista_detalhe, name='detalhe'),
    path('<int:pk>/editar/', views.ListaCanaisUpdateView.as_view(), name='editar'),
    path('<int:pk>/excluir/', views.lista_excluir, name='excluir'),

    # Apps por lista
    path('<int:lista_pk>/apps/adicionar/', views.lista_app_adicionar, name='app_adicionar'),
    path('<int:lista_pk>/apps/<int:app_pk>/editar/', views.lista_app_editar, name='app_editar'),
    path('<int:lista_pk>/apps/<int:app_pk>/excluir/', views.lista_app_excluir, name='app_excluir'),

    # Servidores
    path('servidores/', views.ServidorListView.as_view(), name='servidores'),
    path('servidores/novo/', views.ServidorCreateView.as_view(), name='servidor_novo'),
    path('servidores/<int:pk>/editar/', views.ServidorUpdateView.as_view(), name='servidor_editar'),
    path('servidores/<int:pk>/excluir/', views.servidor_excluir, name='servidor_excluir'),

    # Aplicativos IPTV
    path('aplicativos/', views.AppIPTVListView.as_view(), name='aplicativos'),
    path('aplicativos/novo/', views.AppIPTVCreateView.as_view(), name='app_iptv_novo'),
    path('aplicativos/<int:pk>/editar/', views.AppIPTVUpdateView.as_view(), name='app_iptv_editar'),
    path('aplicativos/<int:pk>/excluir/', views.app_iptv_excluir, name='app_iptv_excluir'),

    # Health check servidores
    path('servidores/<int:pk>/ping/', views.servidor_ping, name='servidor_ping'),
    path('servidores/dns-health/', views.dns_health_check, name='dns_health'),

    # Filtros
    path('filtro/app/', views.filtrar_por_app, name='filtro_app'),
    path('filtro/servidor/', views.filtrar_por_servidor, name='filtro_servidor'),

    # Planos
    path('planos/', views.PlanoListView.as_view(), name='planos'),
    path('planos/novo/', views.PlanoCreateView.as_view(), name='plano_novo'),
    path('planos/<int:pk>/editar/', views.PlanoUpdateView.as_view(), name='plano_editar'),
    path('planos/<int:pk>/excluir/', views.plano_excluir, name='plano_excluir'),
]
