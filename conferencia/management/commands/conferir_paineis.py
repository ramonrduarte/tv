from django.core.management.base import BaseCommand

from conferencia.leitura import PAINEIS_API, LeituraInvalida, ler_painel, na_hora, tem_token


class Command(BaseCommand):
    help = 'Lê os painéis pela API, conforme a frequência configurada. Só consulta: não altera nada nos painéis.'

    def add_arguments(self, parser):
        parser.add_argument('--agora', action='store_true', help='Lê mesmo fora do horário configurado.')

    def handle(self, *args, **options):
        for painel, (variavel, _) in PAINEIS_API.items():
            if not tem_token(painel):
                self.stdout.write(f'{variavel} não configurado; leitura do {painel} ignorada.')
                continue
            if not options['agora'] and not na_hora(painel):
                continue
            try:
                leitura = ler_painel(painel)
            except LeituraInvalida as e:
                self.stderr.write(f'Falha ao ler o {painel}: {e}')
                continue
            self.stdout.write(f'{painel} lido: {leitura.total} acessos.')
