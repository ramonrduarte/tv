from django import forms
from .models import Cliente, Pagador

INPUT_CLASS = 'w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent'
TEXTAREA_CLASS = 'w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent'


class ClienteForm(forms.ModelForm):
    # Campos opcionais para criar pagador junto com o cliente
    tem_pagador_diferente = forms.BooleanField(
        required=False,
        label='Possui pagador diferente do cliente?',
        widget=forms.CheckboxInput(attrs={
            'class': 'w-4 h-4 text-blue-600 rounded cursor-pointer',
            'x-model': 'temPagador',
        })
    )
    pagador_nome = forms.CharField(
        required=False, max_length=200, label='Nome do Pagador',
        widget=forms.TextInput(attrs={'class': INPUT_CLASS, 'placeholder': 'Nome completo do pagador'})
    )
    pagador_whatsapp = forms.CharField(
        required=False, max_length=20, label='WhatsApp do Pagador',
        widget=forms.TextInput(attrs={'class': INPUT_CLASS, 'placeholder': '(11) 99999-9999'})
    )

    class Meta:
        model = Cliente
        fields = ['nome', 'apelido', 'whatsapp', 'ativo', 'notas']
        widgets = {
            'nome': forms.TextInput(attrs={'class': INPUT_CLASS, 'placeholder': 'Nome completo'}),
            'apelido': forms.TextInput(attrs={'class': INPUT_CLASS, 'placeholder': 'Ex: Rafa, Dona Maria, Zé...'}),
            'whatsapp': forms.TextInput(attrs={'class': INPUT_CLASS, 'placeholder': '(11) 99999-9999'}),
            'ativo': forms.CheckboxInput(attrs={'class': 'w-4 h-4 text-blue-600 rounded'}),
            'notas': forms.Textarea(attrs={'class': TEXTAREA_CLASS, 'rows': 3, 'placeholder': 'Observações...'}),
        }

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('tem_pagador_diferente') and not cleaned.get('pagador_nome'):
            self.add_error('pagador_nome', 'Informe o nome do pagador.')
        return cleaned


class PagadorForm(forms.ModelForm):
    class Meta:
        model = Pagador
        fields = ['nome', 'whatsapp', 'notas']
        widgets = {
            'nome': forms.TextInput(attrs={'class': INPUT_CLASS, 'placeholder': 'Nome do pagador'}),
            'whatsapp': forms.TextInput(attrs={'class': INPUT_CLASS, 'placeholder': '(11) 99999-9999'}),
            'notas': forms.Textarea(attrs={'class': TEXTAREA_CLASS, 'rows': 3}),
        }
