from django import forms
from .models import ListaCanais, ListaApp, Servidor, AppIPTV, Plano

INPUT_CLASS = 'w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent'
SELECT_CLASS = 'w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white'
TEXTAREA_CLASS = 'w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent'


class PlanoForm(forms.ModelForm):
    class Meta:
        model = Plano
        fields = ['nome', 'preco_por_tela', 'custo_por_tela', 'descricao', 'ativo']
        widgets = {
            'nome': forms.TextInput(attrs={'class': INPUT_CLASS, 'placeholder': 'Ex: Plano Básico, Plano Premium'}),
            'preco_por_tela': forms.NumberInput(attrs={'class': INPUT_CLASS, 'step': '0.01', 'min': '0'}),
            'custo_por_tela': forms.NumberInput(attrs={'class': INPUT_CLASS, 'step': '0.01', 'min': '0'}),
            'descricao': forms.Textarea(attrs={'class': TEXTAREA_CLASS, 'rows': 2}),
            'ativo': forms.CheckboxInput(attrs={'class': 'w-4 h-4 text-blue-600 rounded'}),
        }


class ListaCanaisForm(forms.ModelForm):
    class Meta:
        model = ListaCanais
        fields = [
            'cliente', 'pagador', 'plano', 'servidor', 'nome', 'usuario', 'senha',
            'num_telas', 'dns_customizado', 'aparelho',
            'data_ativacao', 'ultima_atualizacao', 'controle_desde', 'ativa', 'em_teste', 'data_inicio_teste', 'notas'
        ]
        widgets = {
            'cliente': forms.Select(attrs={'class': SELECT_CLASS}),
            'pagador': forms.Select(attrs={'class': SELECT_CLASS}),
            'plano': forms.Select(attrs={
                'class': SELECT_CLASS,
                'id': 'id_plano',
                '@change': 'atualizar()',
            }),
            'servidor': forms.Select(attrs={'class': SELECT_CLASS}),
            'nome': forms.TextInput(attrs={'class': INPUT_CLASS, 'placeholder': 'Nome da lista'}),
            'usuario': forms.TextInput(attrs={'class': INPUT_CLASS, 'placeholder': 'Usuário IPTV'}),
            'senha': forms.TextInput(attrs={'class': INPUT_CLASS, 'placeholder': 'Senha IPTV'}),
            'num_telas': forms.NumberInput(attrs={
                'class': INPUT_CLASS, 'min': 1,
                'id': 'id_num_telas',
                '@input': 'atualizar()',
            }),
            'dns_customizado': forms.TextInput(attrs={'class': INPUT_CLASS, 'placeholder': 'ex: iptv.servidor.com:8080'}),
            'aparelho': forms.TextInput(attrs={'class': INPUT_CLASS, 'placeholder': 'Ex: Fire Stick, Samsung Smart TV, Celular Android'}),
            'data_ativacao': forms.DateInput(attrs={'class': INPUT_CLASS, 'type': 'date'},
                                             format='%Y-%m-%d'),
            'ultima_atualizacao': forms.DateInput(attrs={'class': INPUT_CLASS, 'type': 'date'},
                                                  format='%Y-%m-%d'),
            'controle_desde': forms.DateInput(attrs={'class': INPUT_CLASS, 'type': 'date'},
                                              format='%Y-%m-%d'),
            'ativa': forms.CheckboxInput(attrs={'class': 'w-4 h-4 text-blue-600 rounded'}),
            'em_teste': forms.CheckboxInput(attrs={'class': 'w-4 h-4 text-yellow-500 rounded'}),
            'data_inicio_teste': forms.DateInput(attrs={'class': INPUT_CLASS, 'type': 'date'},
                                                 format='%Y-%m-%d'),
            'notas': forms.Textarea(attrs={'class': TEXTAREA_CLASS, 'rows': 3}),
        }


class ListaAppForm(forms.ModelForm):
    """Filtra apps compatíveis com o servidor da lista."""

    def __init__(self, *args, lista=None, **kwargs):
        super().__init__(*args, **kwargs)
        if lista and lista.servidor:
            apps_servidor = lista.servidor.apps.all()
            if apps_servidor.exists():
                self.fields['app'].queryset = apps_servidor
                self.fields['app'].help_text = f'Apps vinculados a {lista.servidor.nome}'

    class Meta:
        model = ListaApp
        fields = ['app', 'usuario_app', 'senha_app', 'device_id', 'notas']
        widgets = {
            'app': forms.Select(attrs={'class': SELECT_CLASS}),
            'usuario_app': forms.TextInput(attrs={'class': INPUT_CLASS, 'placeholder': 'Usuário no aplicativo'}),
            'senha_app': forms.TextInput(attrs={'class': INPUT_CLASS, 'placeholder': 'Senha no aplicativo'}),
            'device_id': forms.TextInput(attrs={'class': INPUT_CLASS, 'placeholder': 'Device ID ou MAC Address'}),
            'notas': forms.Textarea(attrs={'class': TEXTAREA_CLASS, 'rows': 2}),
        }


class ServidorForm(forms.ModelForm):
    class Meta:
        model = Servidor
        fields = ['nome', 'dns', 'porta', 'ativo', 'notas']
        widgets = {
            'nome': forms.TextInput(attrs={'class': INPUT_CLASS, 'placeholder': 'Nome do servidor'}),
            'dns': forms.TextInput(attrs={'class': INPUT_CLASS, 'placeholder': 'ex: iptv.exemplo.com'}),
            'porta': forms.NumberInput(attrs={'class': INPUT_CLASS}),
            'ativo': forms.CheckboxInput(attrs={'class': 'w-4 h-4 text-blue-600 rounded'}),
            'notas': forms.Textarea(attrs={'class': TEXTAREA_CLASS, 'rows': 3}),
        }


class AppIPTVForm(forms.ModelForm):
    class Meta:
        model = AppIPTV
        fields = ['nome', 'servidores', 'instrucoes', 'notas']
        widgets = {
            'nome': forms.TextInput(attrs={'class': INPUT_CLASS, 'placeholder': 'ex: TiviMate, IPTV Smarters'}),
            'servidores': forms.CheckboxSelectMultiple(),
            'instrucoes': forms.Textarea(attrs={
                'class': TEXTAREA_CLASS, 'rows': 6,
                'placeholder': 'Ex: Para cadastrar no CLOUDDY:\n1. Abra o app\n2. Clique em "Adicionar lista"\n3. Informe o servidor: {servidor}\n4. Usuário: {usuario}\n5. Senha: {senha}',
            }),
            'notas': forms.Textarea(attrs={'class': TEXTAREA_CLASS, 'rows': 2}),
        }
