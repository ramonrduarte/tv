from django.conf import settings
from django.core.management.base import BaseCommand

from conferencia.leitura import LeituraInvalida, ler_knewcms


class Command(BaseCommand):
    help = 'Lê o knewcms pela API. Só consulta: não altera nada no painel.'

    def handle(self, *args, **options):
        if not settings.WWPANEL_API_TOKEN:
            self.stdout.write('WWPANEL_API_TOKEN não configurado; leitura do knewcms ignorada.')
            return
        try:
            leitura = ler_knewcms()
        except LeituraInvalida as e:
            self.stderr.write(f'Falha ao ler o knewcms: {e}')
            return
        self.stdout.write(f'knewcms lido: {leitura.total} acessos.')
