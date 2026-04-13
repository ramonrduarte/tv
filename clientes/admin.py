from django.contrib import admin
from .models import Cliente, Pagador


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ['nome', 'whatsapp', 'ativo', 'criado_em']
    list_filter = ['ativo']
    search_fields = ['nome', 'whatsapp']


@admin.register(Pagador)
class PagadorAdmin(admin.ModelAdmin):
    list_display = ['nome', 'whatsapp', 'criado_em']
    search_fields = ['nome', 'whatsapp']
