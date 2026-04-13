from django.urls import path
from . import views

app_name = 'usuarios'

urlpatterns = [
    path('', views.usuario_lista, name='lista'),
    path('novo/', views.usuario_criar, name='novo'),
    path('<int:pk>/editar/', views.usuario_editar, name='editar'),
    path('<int:pk>/toggle/', views.usuario_toggle_ativo, name='toggle'),
]
