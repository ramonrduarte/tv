from django.conf import settings
from django.core.management.base import BaseCommand

from conferencia.leitura import LeituraInvalida, knewcms_na_hora, ler_knewcms


class Command(BaseCommand):
    help = 'Lê o knewcms pela API, conforme a frequência configurada. Só consulta: não altera nada no painel.'

    def add_arguments(self, parser):
        parser.add_argument('--agora', action='store_true', help='Lê mesmo fora do horário configurado.')

    def handle(self, *args, **options):
        if not settings.WWPANEL_API_TOKEN:
            self.stdout.write('WWPANEL_API_TOKEN não configurado; leitura do knewcms ignorada.')
            return
        if not options['agora'] and not knewcms_na_hora():
            return
        try:
            leitura = ler_knewcms()
        except LeituraInvalida as e:
            self.stderr.write(f'Falha ao ler o knewcms: {e}')
            return
        self.stdout.write(f'knewcms lido: {leitura.total} acessos.')
