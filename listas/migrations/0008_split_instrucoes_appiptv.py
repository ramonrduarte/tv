from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('listas', '0007_add_instrucoes_appiptv'),
    ]

    operations = [
        migrations.RenameField(
            model_name='appiptv',
            old_name='instrucoes',
            new_name='instrucoes_cadastro',
        ),
        migrations.AlterField(
            model_name='appiptv',
            name='instrucoes_cadastro',
            field=models.TextField(
                blank=True,
                help_text='Texto para orientar o cliente no primeiro cadastro do app.',
                verbose_name='Instruções de Cadastro',
            ),
        ),
        migrations.AddField(
            model_name='appiptv',
            name='instrucoes_edicao',
            field=models.TextField(
                blank=True,
                help_text='Texto para orientar o cliente ao editar/atualizar o app.',
                verbose_name='Instruções de Edição',
            ),
        ),
    ]
