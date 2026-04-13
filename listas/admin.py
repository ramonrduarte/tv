from django.contrib import admin
from .models import Servidor, AppIPTV, ListaCanais, ListaApp, Plano


@admin.register(Plano)
class PlanoAdmin(admin.ModelAdmin):
    list_display = ['nome', 'preco_por_tela', 'custo_por_tela', 'ativo']
    list_filter = ['ativo']


@admin.register(Servidor)
class ServidorAdmin(admin.ModelAdmin):
    list_display = ['nome', 'dns', 'porta', 'ativo']
    list_filter = ['ativo']


@admin.register(AppIPTV)
class AppIPTVAdmin(admin.ModelAdmin):
    list_display = ['nome', 'criado_em']


class ListaAppInline(admin.TabularInline):
    model = ListaApp
    extra = 0


@admin.register(ListaCanais)
class ListaCanaisAdmin(admin.ModelAdmin):
    list_display = ['nome', 'cliente', 'servidor', 'usuario', 'ativa', 'ultima_atualizacao']
    list_filter = ['ativa', 'servidor']
    search_fields = ['nome', 'cliente__nome', 'usuario']
    inlines = [ListaAppInline]


@admin.register(ListaApp)
class ListaAppAdmin(admin.ModelAdmin):
    list_display = ['lista', 'app', 'usuario_app', 'device_id']
    search_fields = ['lista__nome', 'app__nome']
