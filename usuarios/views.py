from django.contrib.auth.models import User
from django.contrib import messages
from django.shortcuts import render, get_object_or_404, redirect
from django import forms


INPUT_CLASS = 'w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent'


class UsuarioForm(forms.Form):
    username = forms.CharField(
        label='Login', max_length=150,
        widget=forms.TextInput(attrs={'class': INPUT_CLASS, 'placeholder': 'Nome de usuário para login'})
    )
    first_name = forms.CharField(
        label='Nome completo', max_length=150, required=False,
        widget=forms.TextInput(attrs={'class': INPUT_CLASS, 'placeholder': 'Nome (opcional)'})
    )
    email = forms.EmailField(
        label='E-mail', required=False,
        widget=forms.EmailInput(attrs={'class': INPUT_CLASS, 'placeholder': 'email@exemplo.com'})
    )
    password = forms.CharField(
        label='Senha', required=False,
        widget=forms.PasswordInput(attrs={'class': INPUT_CLASS, 'placeholder': 'Mínimo 6 caracteres'}),
    )
    is_active = forms.BooleanField(
        label='Usuário ativo', required=False, initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'w-4 h-4 text-blue-600 rounded'})
    )

    def __init__(self, *args, instance=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._instance = instance
        if instance:
            self.fields['username'].initial = instance.username
            self.fields['first_name'].initial = instance.first_name
            self.fields['email'].initial = instance.email
            self.fields['is_active'].initial = instance.is_active
            self.fields['password'].help_text = 'Deixe em branco para não alterar a senha.'

    def clean_username(self):
        username = self.cleaned_data['username']
        qs = User.objects.filter(username=username)
        if self._instance:
            qs = qs.exclude(pk=self._instance.pk)
        if qs.exists():
            raise forms.ValidationError('Este login já está em uso.')
        return username

    def clean_password(self):
        pwd = self.cleaned_data.get('password', '')
        if not self._instance and not pwd:
            raise forms.ValidationError('A senha é obrigatória para novos usuários.')
        if pwd and len(pwd) < 6:
            raise forms.ValidationError('A senha deve ter pelo menos 6 caracteres.')
        return pwd


def _superuser_required(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        if not request.user.is_superuser:
            messages.error(request, 'Acesso restrito a administradores.')
            return redirect('dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper


@_superuser_required
def usuario_lista(request):
    usuarios = User.objects.all().order_by('username')
    return render(request, 'usuarios/lista.html', {'usuarios': usuarios})


@_superuser_required
def usuario_criar(request):
    if request.method == 'POST':
        form = UsuarioForm(request.POST)
        if form.is_valid():
            u = User.objects.create_user(
                username=form.cleaned_data['username'],
                password=form.cleaned_data['password'],
                first_name=form.cleaned_data.get('first_name', ''),
                email=form.cleaned_data.get('email', ''),
            )
            u.is_active = form.cleaned_data.get('is_active', True)
            u.save()
            messages.success(request, f'Usuário {u.username} criado com sucesso!')
            return redirect('usuarios:lista')
    else:
        form = UsuarioForm()
    return render(request, 'usuarios/form.html', {
        'form': form, 'titulo': 'Novo Usuário', 'btn_label': 'Criar Usuário',
    })


@_superuser_required
def usuario_editar(request, pk):
    usuario = get_object_or_404(User, pk=pk)
    if request.method == 'POST':
        form = UsuarioForm(request.POST, instance=usuario)
        if form.is_valid():
            usuario.username = form.cleaned_data['username']
            usuario.first_name = form.cleaned_data.get('first_name', '')
            usuario.email = form.cleaned_data.get('email', '')
            usuario.is_active = form.cleaned_data.get('is_active', True)
            if form.cleaned_data.get('password'):
                usuario.set_password(form.cleaned_data['password'])
            usuario.save()
            messages.success(request, f'Usuário {usuario.username} atualizado!')
            return redirect('usuarios:lista')
    else:
        form = UsuarioForm(instance=usuario)
    return render(request, 'usuarios/form.html', {
        'form': form,
        'titulo': f'Editar: {usuario.username}',
        'btn_label': 'Salvar Alterações',
        'usuario': usuario,
    })


@_superuser_required
def usuario_toggle_ativo(request, pk):
    usuario = get_object_or_404(User, pk=pk)
    if usuario == request.user:
        messages.error(request, 'Você não pode desativar sua própria conta.')
        return redirect('usuarios:lista')
    if request.method == 'POST':
        usuario.is_active = not usuario.is_active
        usuario.save()
        status = 'ativado' if usuario.is_active else 'desativado'
        messages.success(request, f'Usuário {usuario.username} {status}.')
    return redirect('usuarios:lista')
