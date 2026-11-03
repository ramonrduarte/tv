from django.db import migrations


def remover_vinculos_bit(apps, schema_editor):
    # A API do BIT só identifica acessos pelo usuário; os IDs do favorito antigo não valem mais.
    apps.get_model('conferencia', 'VinculoPainel').objects.filter(painel='bit').delete()
    apps.get_model('conferencia', 'AcessoPainel').objects.filter(painel='bit').update(painel_id='')


class Migration(migrations.Migration):

    dependencies = [
        ('conferencia', '0004_ordem_leituras'),
    ]

    operations = [
        migrations.RunPython(remover_vinculos_bit, migrations.RunPython.noop),
    ]
