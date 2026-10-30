from .regras import contar_divergencias


def divergencias(request):
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return {}
    return {'conferencia_total': contar_divergencias()}
