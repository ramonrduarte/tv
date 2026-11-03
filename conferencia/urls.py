from django.urls import path
from . import views

app_name = 'conferencia'

urlpatterns = [
    path('', views.painel, name='painel'),
    path('frequencia/', views.salvar_frequencia, name='salvar_frequencia'),
    path('renovar/', views.renovar, name='renovar'),
    path('renovar/conferir/', views.renovar_conferir, name='renovar_conferir'),
    path('renovar/enviar/', views.renovar_executar, name='renovar_executar'),
    path('lista/<int:pk>/acesso/', views.acesso_editar, name='acesso_editar'),
    path('<str:painel>/atualizar/', views.atualizar, name='atualizar'),
    path('vincular/', views.vincular, name='vincular'),
    path('vinculos/<int:pk>/remover/', views.desvincular, name='desvincular'),
    path('ignorar/', views.ignorar, name='ignorar'),
    path('ignoradas/<int:pk>/restaurar/', views.restaurar, name='restaurar'),
]
