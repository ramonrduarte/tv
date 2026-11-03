from django.db import migrations, models


def limpar_dns_ficticio(apps, schema_editor):
    """Um DNS sem ponto (ex.: "Warez") não é endereço de verdade e só aparecia como "Warez:80"."""
    Servidor = apps.get_model('listas', 'Servidor')
    for servidor in Servidor.objects.all():
        if servidor.dns and '.' not in servidor.dns:
            servidor.dns = ''
            servidor.porta = None
            servidor.save(update_fields=['dns', 'porta'])


class Migration(migrations.Migration):

    dependencies = [
        ('listas', '0012_formato_lista_app'),
    ]

    operations = [
        migrations.AlterField(
            model_name='servidor',
            name='dns',
            field=models.CharField(blank=True, help_text='Só para servidor sem painel. No BIT o endereço vem da API; no knewcms fica no aplicativo.', max_length=500, verbose_name='DNS / URL'),
        ),
        migrations.AlterField(
            model_name='servidor',
            name='porta',
            field=models.IntegerField(blank=True, null=True, verbose_name='Porta'),
        ),
        migrations.RunPython(limpar_dns_ficticio, migrations.RunPython.noop),
    ]
