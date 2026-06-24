from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender='financeiro.Mensalidade')
def gerar_proxima_apos_pagamento(sender, instance, **kwargs):
    if instance.status != 'pago':
        return
    _gerar_proxima_mensalidade_lista(instance.lista)


def _gerar_proxima_mensalidade_lista(lista):
    from listas.models import add_one_month
    from .models import Mensalidade

    if not lista.ativa or not lista.data_ativacao:
        return
    ultima = lista.mensalidades.order_by('-vencimento').first()
    if ultima and ultima.status == 'pago':
        proxima = add_one_month(ultima.vencimento)
        if not lista.mensalidades.filter(vencimento=proxima).exists():
            Mensalidade.objects.create(
                lista=lista,
                valor=lista.valor_mensalidade,
                vencimento=proxima,
                referencia=proxima.strftime('%Y-%m'),
                status='pendente',
            )
