from django.urls import path
from . import views

app_name = 'conferencia'

urlpatterns = [
    path('', views.painel, name='painel'),
    path('knewcms/atualizar/', views.atualizar_knewcms, name='atualizar_knewcms'),
    path('knewcms/frequencia/', views.salvar_frequencia, name='salvar_frequencia'),
    path('bit/receber/', views.receber_bit, name='receber_bit'),
    path('bit/importar/', views.importar_bit_view, name='importar_bit'),
    path('vincular/', views.vincular, name='vincular'),
    path('vinculos/<int:pk>/remover/', views.desvincular, name='desvincular'),
    path('ignorar/', views.ignorar, name='ignorar'),
    path('ignoradas/<int:pk>/restaurar/', views.restaurar, name='restaurar'),
]
