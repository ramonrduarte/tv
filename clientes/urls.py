from django.urls import path
from . import views

app_name = 'clientes'

urlpatterns = [
    path('', views.ClienteListView.as_view(), name='lista'),
    path('novo/', views.ClienteCreateView.as_view(), name='novo'),
    path('<int:pk>/', views.cliente_detalhe, name='detalhe'),
    path('<int:pk>/editar/', views.ClienteUpdateView.as_view(), name='editar'),
    path('<int:pk>/excluir/', views.cliente_excluir, name='excluir'),

    # Ações
    path('dashboard/encerrar-teste/<int:lista_pk>/', views.encerrar_teste, name='encerrar_teste'),

    # Pagadores
    path('pagadores/', views.PagadorListView.as_view(), name='pagadores'),
    path('pagadores/novo/', views.PagadorCreateView.as_view(), name='pagador_novo'),
    path('pagadores/<int:pk>/editar/', views.PagadorUpdateView.as_view(), name='pagador_editar'),
    path('pagadores/<int:pk>/excluir/', views.pagador_excluir, name='pagador_excluir'),
]
