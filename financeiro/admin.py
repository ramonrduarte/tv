from django.contrib import admin
from .models import Mensalidade


@admin.register(Mensalidade)
class MensalidadeAdmin(admin.ModelAdmin):
    list_display = ['lista', 'referencia', 'valor', 'vencimento', 'data_pagamento', 'status']
    list_filter = ['status']
    search_fields = ['lista__nome', 'lista__cliente__nome']
    date_hierarchy = 'vencimento'
