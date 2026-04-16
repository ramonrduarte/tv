from django.db import migrations, models


def copiar_aparelho(apps, schema_editor):
    ListaCanais = apps.get_model('listas', 'ListaCanais')
    ListaApp = apps.get_model('listas', 'ListaApp')
    for lista in ListaCanais.objects.exclude(aparelho=''):
        ListaApp.objects.filter(lista=lista).update(aparelho=lista.aparelho)


class Migration(migrations.Migration):

    dependencies = [
        ('listas', '0008_split_instrucoes_appiptv'),
    ]

    operations = [
        migrations.AddField(
            model_name='listaapp',
            name='aparelho',
            field=models.CharField(
                blank=True,
                help_text='Ex: Fire Stick, Samsung Smart TV, Celular Android',
                max_length=200,
                verbose_name='Aparelho',
            ),
        ),
        migrations.RunPython(copiar_aparelho, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='listacanais',
            name='aparelho',
        ),
    ]
