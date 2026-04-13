from django import forms
from .models import Mensalidade

INPUT_CLASS = 'w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent'
SELECT_CLASS = 'w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white'
TEXTAREA_CLASS = 'w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent'


class MensalidadeForm(forms.ModelForm):
    class Meta:
        model = Mensalidade
        fields = ['lista', 'valor', 'vencimento', 'data_pagamento', 'status', 'referencia', 'notas']
        widgets = {
            'lista': forms.Select(attrs={'class': SELECT_CLASS}),
            'valor': forms.NumberInput(attrs={'class': INPUT_CLASS, 'step': '0.01', 'min': '0'}),
            'vencimento': forms.DateInput(attrs={'class': INPUT_CLASS, 'type': 'date'}, format='%Y-%m-%d'),
            'data_pagamento': forms.DateInput(attrs={'class': INPUT_CLASS, 'type': 'date'}, format='%Y-%m-%d'),
            'status': forms.Select(attrs={'class': SELECT_CLASS}),
            'referencia': forms.TextInput(attrs={'class': INPUT_CLASS, 'placeholder': 'Ex: 2024-03'}),
            'notas': forms.Textarea(attrs={'class': TEXTAREA_CLASS, 'rows': 2}),
        }
