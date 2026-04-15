from django.contrib.postgres.operations import UnaccentExtension
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('clientes', '0003_add_template_mensagem'),
    ]

    operations = [
        UnaccentExtension(),
    ]
