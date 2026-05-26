# IPTV Manager

Sistema web para gerenciamento de clientes IPTV — controle de listas, servidores, mensalidades e integração com agente WhatsApp.

## Funcionalidades

- Cadastro de clientes, pagadores e listas IPTV
- Controle financeiro com geração automática de mensalidades
- Gerenciamento de servidores, aplicativos e planos
- Dashboard com alertas de atraso e vencimento próximo
- API REST para integração com agente WhatsApp

## Stack

Python 3.11 · Django 4.2 · Django REST Framework · PostgreSQL · Docker · Gunicorn

## Documentação completa

Instalação, uso do sistema e guia detalhado da API:

**[DOCUMENTACAO.md](DOCUMENTACAO.md)**

## Início rápido

```bash
# Configure as variáveis de ambiente
cp .env.example .env  # edite com seus dados

# Suba com Docker
docker compose up -d --build

# Crie o superusuário (primeira vez)
docker exec -it iptv-manager python manage.py createsuperuser
```

Acesse em `http://localhost:8080`

## API — autenticação

Todos os endpoints da API exigem o header:

```
X-Api-Token: seu-token-aqui
```

O token é definido na variável de ambiente `API_TOKEN_WHATSAPP`.

| Endpoint | Descrição |
|----------|-----------|
| `GET /api/v1/cliente/` | Dados do cliente pelo WhatsApp |
| `GET /api/v1/pendencias/` | Total pendente do pagador |
| `POST /api/v1/pagamento-avulso/` | Registra pagamento por valor |

Veja todos os endpoints e exemplos completos em [DOCUMENTACAO.md](DOCUMENTACAO.md).
