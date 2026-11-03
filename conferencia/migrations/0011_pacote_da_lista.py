from django.db import migrations, models
import django.db.models.deletion


def plano_do_knewcms_vira_pacote(apps, schema_editor):
    # No knewcms o que a API chama de plano é o pacote mostrado no painel.
    Acesso = apps.get_model('conferencia', 'AcessoPainel')
    for acesso in Acesso.objects.filter(painel='knewcms').exclude(plano=''):
        acesso.pacote = acesso.plano
        acesso.save(update_fields=['pacote'])


class Migration(migrations.Migration):

    dependencies = [
        ('listas', '0012_formato_lista_app'),
        ('conferencia', '0010_plano_no_painel'),
    ]

    operations = [
        migrations.RunPython(plano_do_knewcms_vira_pacote, migrations.RunPython.noop),
        migrations.RemoveField(model_name='acessopainel', name='plano'),
        migrations.CreateModel(
            name='PacoteLista',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('painel', models.CharField(choices=[('bit', 'BIT'), ('knewcms', 'knewcms')], max_length=20, verbose_name='Painel')),
                ('pacote_id', models.CharField(blank=True, max_length=60, verbose_name='ID do pacote no painel')),
                ('nome', models.CharField(max_length=200, verbose_name='Pacote')),
                ('atualizado_em', models.DateTimeField(auto_now=True)),
                ('lista', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='pacote_painel', to='listas.listacanais', verbose_name='Lista')),
            ],
            options={'verbose_name': 'Pacote da lista', 'verbose_name_plural': 'Pacotes das listas'},
        ),
    ]
