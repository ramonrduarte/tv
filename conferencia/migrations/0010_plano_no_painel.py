from django.db import migrations, models


def mover_plano_do_knewcms(apps, schema_editor):
    # No knewcms o que estava em "pacote" é o plano da lista.
    Acesso = apps.get_model('conferencia', 'AcessoPainel')
    for acesso in Acesso.objects.filter(painel='knewcms').exclude(pacote=''):
        acesso.plano, acesso.pacote = acesso.pacote, ''
        acesso.save(update_fields=['plano', 'pacote'])


class Migration(migrations.Migration):

    dependencies = [
        ('conferencia', '0009_ip_saida_leitura'),
    ]

    operations = [
        migrations.AddField(
            model_name='acessopainel',
            name='plano',
            field=models.CharField(blank=True, max_length=200, verbose_name='Plano no painel'),
        ),
        migrations.RunPython(mover_plano_do_knewcms, migrations.RunPython.noop),
    ]
