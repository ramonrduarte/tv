from django.urls import path
from . import views

app_name = 'financeiro'

urlpatterns = [
    path('', views.MensalidadeListView.as_view(), name='lista'),
    path('nova/', views.MensalidadeCreateView.as_view(), name='nova'),
    path('<int:pk>/editar/', views.MensalidadeUpdateView.as_view(), name='editar'),
    path('<int:pk>/pagar/', views.mensalidade_pagar, name='pagar'),
    path('<int:pk>/excluir/', views.mensalidade_excluir, name='excluir'),
    path('pagar-lote/', views.pagar_lote, name='pagar_lote'),
    path('exportar/', views.exportar_csv, name='exportar_csv'),
]
