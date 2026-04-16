from django.db import migrations, models


def copiar_dns(apps, schema_editor):
    ListaCanais = apps.get_model('listas', 'ListaCanais')
    ListaApp = apps.get_model('listas', 'ListaApp')
    for lista in ListaCanais.objects.exclude(dns_customizado=''):
        ListaApp.objects.filter(lista=lista).update(dns_customizado=lista.dns_customizado)


class Migration(migrations.Migration):

    dependencies = [
        ('listas', '0009_move_aparelho_to_listaapp'),
    ]

    operations = [
        migrations.AddField(
            model_name='listaapp',
            name='dns_customizado',
            field=models.CharField(
                blank=True,
                help_text='Preencha apenas se diferente do servidor da lista',
                max_length=500,
                verbose_name='DNS Customizado',
            ),
        ),
        migrations.RunPython(copiar_dns, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='listacanais',
            name='dns_customizado',
        ),
    ]
