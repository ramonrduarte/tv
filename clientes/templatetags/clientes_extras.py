from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    return dictionary.get(key, '')


@register.simple_tag(takes_context=True)
def sort_url(context, field):
    """Retorna query string com sort/dir para o campo dado, invertendo se já ativo."""
    request = context['request']
    params = request.GET.copy()
    current_sort = params.get('sort', '')
    current_dir = params.get('dir', 'asc')
    new_dir = 'desc' if current_sort == field and current_dir == 'asc' else 'asc'
    params['sort'] = field
    params['dir'] = new_dir
    params.pop('page', None)
    return '?' + params.urlencode()


@register.simple_tag(takes_context=True)
def sort_icon(context, field):
    """Retorna ▲ ou ▼ se a coluna estiver ativa, ou vazio caso contrário."""
    request = context['request']
    if request.GET.get('sort', '') == field:
        return '▼' if request.GET.get('dir', 'asc') == 'desc' else '▲'
    return ''
