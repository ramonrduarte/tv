from django.urls import path
from . import views

app_name = 'api'

urlpatterns = [
    # Consultas por WhatsApp do cliente
    path('cliente/', views.ClientePorWhatsAppView.as_view(), name='cliente'),
    path('listas/', views.ListasPorWhatsAppView.as_view(), name='listas'),
    path('status/', views.StatusMensalidadesView.as_view(), name='status'),

    # Pagamento por lista específica (endpoint antigo, mantido para compatibilidade)
    path('pagamento/', views.RegistrarPagamentoView.as_view(), name='pagamento'),

    # Novos: pagamento por valor (cobre múltiplas listas/meses automaticamente)
    path('pendencias/', views.PendenciasView.as_view(), name='pendencias'),
    path('pagamento-avulso/', views.PagamentoAvulsoView.as_view(), name='pagamento_avulso'),
]
