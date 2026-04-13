from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender='listas.ListaCanais')
def criar_primeira_mensalidade(sender, instance, created, **kwargs):
    """Ao criar uma lista com data de ativação, gera a primeira mensalidade automaticamente."""
    if not created or not instance.data_ativacao:
        return

    from financeiro.models import Mensalidade

    # Não cria duplicata
    if instance.mensalidades.exists():
        return

    Mensalidade.objects.create(
        lista=instance,
        valor=instance.valor_mensalidade,
        vencimento=instance.data_ativacao,
        referencia=instance.data_ativacao.strftime('%Y-%m'),
        status='pendente',
    )
