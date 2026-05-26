# IPTV Manager — Documentação Completa

## Índice

1. [O que é o sistema](#o-que-é-o-sistema)
2. [Como foi feito](#como-foi-feito)
3. [Estrutura do projeto](#estrutura-do-projeto)
4. [Como instalar e rodar](#como-instalar-e-rodar)
5. [Como usar o sistema](#como-usar-o-sistema)
6. [API REST — Guia Completo](#api-rest--guia-completo)

---

## O que é o sistema

O **IPTV Manager** é um sistema web para gerenciar clientes de IPTV. Ele centraliza:

- Cadastro de clientes e de quem paga por eles (pagadores)
- Listas de canais IPTV (usuário, senha, servidor, apps instalados)
- Controle financeiro de mensalidades (geração automática, registro de pagamentos)
- Planos com cálculo automático de margem
- Servidores e aplicativos IPTV
- API REST para integração com agente de WhatsApp (consultas e registros de pagamento)

---

## Como foi feito

### Stack tecnológica

| Camada | Tecnologia |
|--------|-----------|
| Backend | Python 3.11 + Django 4.2 |
| API REST | Django REST Framework 3.15 |
| Banco de dados | PostgreSQL (produção) / SQLite (desenvolvimento) |
| Servidor web | Gunicorn + WhiteNoise |
| Container | Docker + Docker Compose |
| Autenticação web | Django Sessions |
| Autenticação API | Token fixo via header `X-Api-Token` |

### Aplicações Django (apps)

O projeto é dividido em cinco apps independentes:

```
clientes/     → Clientes, Pagadores, Templates de mensagem, Dashboard
listas/       → Listas IPTV, Servidores, Aplicativos, Planos
financeiro/   → Mensalidades
api/          → API REST para integração WhatsApp
usuarios/     → Gerenciamento de usuários do sistema
```

### Banco de dados — modelo simplificado

```
Cliente ──< ListaCanais >── Servidor
               │                │
               │            AppIPTV (via ListaApp)
               │
Pagador ──< ListaCanais
               │
           Mensalidade
```

- Um **Cliente** pode ter várias **ListaCanais**
- Cada lista pode ter um **Pagador** separado (pessoa que paga, diferente de quem usa)
- Cada lista pertence a um **Servidor** e pode ter vários **AppIPTV** instalados (via `ListaApp`)
- Cada lista gera **Mensalidades** mensais automaticamente

---

## Estrutura do projeto

```
iptv/
├── config/               # Configurações Django (settings, urls raiz, wsgi)
├── clientes/             # App: clientes, dashboard, relatórios
├── listas/               # App: listas IPTV, servidores, apps, planos
├── financeiro/           # App: mensalidades
├── api/                  # App: API REST
├── usuarios/             # App: usuários do sistema
├── templates/            # HTML (Bootstrap)
├── manage.py
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── entrypoint.sh
```

---

## Como instalar e rodar

### Opção 1 — Docker (recomendado para produção)

**Pré-requisitos:** Docker instalado, PostgreSQL externo acessível.

**1. Crie o arquivo `.env`** na raiz do projeto:

```env
SECRET_KEY=uma-chave-secreta-longa-e-aleatoria
DEBUG=False
ALLOWED_HOSTS=seu-dominio.com,192.168.1.100
CSRF_TRUSTED_ORIGINS=https://seu-dominio.com

DB_NAME=iptv
DB_USER=postgres
DB_PASSWORD=sua-senha
DB_HOST=192.168.1.10
DB_PORT=5432

API_TOKEN_WHATSAPP=token-secreto-para-o-agente-whatsapp
```

**2. Suba o container:**

```bash
docker compose up -d --build
```

O sistema ficará disponível na porta `8080`.

**3. Crie o superusuário** (apenas na primeira vez):

```bash
docker exec -it iptv-manager python manage.py createsuperuser
```

### Opção 2 — Desenvolvimento local

**1. Crie o ambiente virtual e instale dependências:**

```bash
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

pip install -r requirements.txt
```

**2. Configure variáveis de ambiente** (ou use SQLite sem configurar nada):

```bash
# Para usar SQLite (mais simples para desenvolvimento):
set USE_SQLITE=True      # Windows
export USE_SQLITE=True   # Linux/Mac
```

**3. Aplique as migrations e suba:**

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

O sistema estará em `http://localhost:8000`.

---

## Como usar o sistema

### Acesso inicial

Acesse `/login/` e entre com o usuário criado no passo anterior.

A tela principal é o **Dashboard**, que mostra:
- Total de clientes e listas ativas
- Mensalidades atrasadas e com vencimento próximo
- Resumo financeiro do mês

### Fluxo básico de cadastro

```
1. Cadastrar Servidor (listas > Servidores > Novo)
2. Cadastrar App IPTV (listas > Aplicativos > Novo)
3. Cadastrar Plano (listas > Planos > Novo)
4. Cadastrar Cliente (Clientes > Novo)
5. Cadastrar Lista IPTV para o cliente (dentro do detalhe do cliente)
```

### Mensalidades

As mensalidades são **geradas automaticamente** quando você acessa o dashboard ou o detalhe do cliente. O sistema garante que sempre existe ao menos uma mensalidade pendente futura para cada lista ativa.

Para registrar um pagamento manualmente: acesse **Mensalidades**, localize a mensalidade e clique em **Pagar**.

### Pagadores

Um **Pagador** é uma pessoa diferente do cliente que paga por uma ou mais listas. Exemplo: o pai paga pelo filho. Cadastre em `Clientes > Pagadores` e depois associe à lista desejada.

---

## API REST — Guia Completo

A API foi projetada para integração com agentes de WhatsApp, permitindo consultar informações de clientes e registrar pagamentos sem acessar o sistema web.

### Autenticação

**Todos os endpoints exigem o token no header:**

```
X-Api-Token: seu-token-aqui
```

O token é definido na variável de ambiente `API_TOKEN_WHATSAPP`. Se o token estiver ausente ou errado, a resposta será:

```json
HTTP 403 Forbidden
{"erro": "Token inválido"}
```

### URL base

```
https://seu-dominio.com/api/v1/
```

### Busca de número de WhatsApp

A API faz busca **flexível** de WhatsApp: ela compara apenas os dígitos, ignorando formatação, e aceita correspondência parcial (número com ou sem código do país). Ou seja, `5511999999999`, `11999999999` e `+55 (11) 99999-9999` identificam o mesmo cadastro.

---

### Endpoints

---

#### `GET /api/v1/cliente/`

Busca os dados de um cliente pelo WhatsApp.

**Parâmetros (query string):**

| Parâmetro | Tipo | Obrigatório | Descrição |
|-----------|------|-------------|-----------|
| `whatsapp` | string | sim | Número do cliente |

**Exemplo de requisição:**

```
GET /api/v1/cliente/?whatsapp=5511999999999
X-Api-Token: meu-token
```

**Resposta de sucesso (200):**

```json
{
  "id": 1,
  "nome": "João da Silva",
  "whatsapp": "11999999999",
  "ativo": true,
  "listas": [
    {
      "id": 3,
      "nome": "Lista João",
      "usuario": "joao123",
      "num_telas": 2,
      "dns": "servidor1.iptv.com:80",
      "valor_mensalidade": "40.00",
      "data_ativacao": "2025-01-10",
      "data_vencimento": "2026-06-10",
      "ultima_atualizacao": "2025-06-10",
      "ativa": true,
      "status_pagamento": "em_dia"
    }
  ]
}
```

**Possíveis valores de `status_pagamento`:**

| Valor | Significado |
|-------|------------|
| `em_dia` | Mensalidade mais recente paga |
| `atrasado` | Há mensalidade vencida não paga |
| `pendente` | Mensalidade próxima ainda não paga |
| `sem_registro` | Nenhuma mensalidade registrada |

**Erros:**

```json
HTTP 400 → {"erro": "Parâmetro whatsapp é obrigatório"}
HTTP 404 → {"erro": "Cliente não encontrado"}
```

---

#### `GET /api/v1/listas/`

Retorna todas as listas ativas de um cliente.

**Parâmetros (query string):**

| Parâmetro | Tipo | Obrigatório | Descrição |
|-----------|------|-------------|-----------|
| `whatsapp` | string | sim | Número do cliente |

**Exemplo de requisição:**

```
GET /api/v1/listas/?whatsapp=11999999999
X-Api-Token: meu-token
```

**Resposta de sucesso (200):**

```json
{
  "cliente": "João da Silva",
  "whatsapp": "11999999999",
  "listas": [
    {
      "id": 3,
      "nome": "Lista João",
      "usuario": "joao123",
      "num_telas": 2,
      "dns": "servidor1.iptv.com:80",
      "valor_mensalidade": "40.00",
      "data_ativacao": "2025-01-10",
      "data_vencimento": "2026-06-10",
      "ultima_atualizacao": "2025-06-10",
      "ativa": true,
      "status_pagamento": "em_dia"
    }
  ]
}
```

---

#### `GET /api/v1/status/`

Retorna o status de pagamento das mensalidades de um cliente.

**Parâmetros (query string):**

| Parâmetro | Tipo | Obrigatório | Descrição |
|-----------|------|-------------|-----------|
| `whatsapp` | string | sim | Número do cliente |

**Exemplo de requisição:**

```
GET /api/v1/status/?whatsapp=11999999999
X-Api-Token: meu-token
```

**Resposta de sucesso (200):**

```json
{
  "cliente": "João da Silva",
  "listas": [
    {
      "lista_id": 3,
      "lista_nome": "Lista João",
      "status": "atrasado",
      "ultima_mensalidade": {
        "id": 45,
        "lista": 3,
        "lista_nome": "Lista João",
        "cliente_nome": "João da Silva",
        "pagador_nome": "João da Silva",
        "valor": "40.00",
        "vencimento": "2026-05-10",
        "data_pagamento": null,
        "status": "atrasado",
        "notas": ""
      }
    }
  ]
}
```

---

#### `GET /api/v1/pendencias/`

Retorna todas as mensalidades pendentes ou atrasadas de um **pagador** (busca tanto em Pagadores quanto em Clientes). Use este endpoint antes de registrar um pagamento para saber o total devido.

**Parâmetros (query string) — informe pelo menos um:**

| Parâmetro | Tipo | Obrigatório | Descrição |
|-----------|------|-------------|-----------|
| `whatsapp` | string | um dos dois | WhatsApp do pagador |
| `nome` | string | um dos dois | Nome do pagador (busca parcial) |

**Exemplos:**

```
GET /api/v1/pendencias/?whatsapp=5511999999999
GET /api/v1/pendencias/?nome=Raquel
X-Api-Token: meu-token
```

**Resposta de sucesso (200):**

```json
{
  "pagador": "Maria Raquel",
  "total_pendente": "120.00",
  "quantidade": 3,
  "mensalidades": [
    {
      "id": 41,
      "lista": 5,
      "lista_nome": "Lista Raquel 1",
      "cliente_nome": "Carlos (filho)",
      "pagador_nome": "Maria Raquel",
      "valor": "40.00",
      "vencimento": "2026-03-15",
      "data_pagamento": null,
      "status": "atrasado",
      "notas": ""
    },
    {
      "id": 42,
      "lista": 5,
      "lista_nome": "Lista Raquel 1",
      "cliente_nome": "Carlos (filho)",
      "pagador_nome": "Maria Raquel",
      "valor": "40.00",
      "vencimento": "2026-04-15",
      "data_pagamento": null,
      "status": "atrasado",
      "notas": ""
    },
    {
      "id": 50,
      "lista": 8,
      "lista_nome": "Lista Raquel 2",
      "cliente_nome": "Ana (filha)",
      "pagador_nome": "Maria Raquel",
      "valor": "40.00",
      "vencimento": "2026-05-20",
      "data_pagamento": null,
      "status": "pendente",
      "notas": ""
    }
  ]
}
```

**Erros:**

```json
HTTP 400 → {"erro": "Informe whatsapp ou nome do pagador"}
HTTP 404 → {"erro": "Pagador não encontrado"}
```

---

#### `POST /api/v1/pagamento/`

Registra o pagamento da mensalidade mais antiga pendente de uma lista específica. Útil quando se sabe exatamente qual lista está sendo paga.

**Body (JSON):**

| Campo | Tipo | Obrigatório | Descrição |
|-------|------|-------------|-----------|
| `lista_id` | inteiro | sim | ID da lista (obtido em `/listas/` ou `/status/`) |
| `data_pagamento` | string (YYYY-MM-DD) | não | Data do pagamento (padrão: hoje) |
| `notas` | string | não | Observação livre |

**Exemplo de requisição:**

```
POST /api/v1/pagamento/
X-Api-Token: meu-token
Content-Type: application/json

{
  "lista_id": 3,
  "data_pagamento": "2026-05-26",
  "notas": "Pix confirmado"
}
```

**Resposta de sucesso (200):**

```json
{
  "sucesso": true,
  "mensagem": "Pagamento de 2026-05-10 registrado para João da Silva",
  "mensalidade": {
    "id": 45,
    "lista": 3,
    "lista_nome": "Lista João",
    "cliente_nome": "João da Silva",
    "pagador_nome": "João da Silva",
    "valor": "40.00",
    "vencimento": "2026-05-10",
    "data_pagamento": "2026-05-26",
    "status": "pago",
    "notas": "Pix confirmado"
  }
}
```

**Erros:**

```json
HTTP 404 → {"erro": "Lista não encontrada"}
HTTP 404 → {"erro": "Nenhuma mensalidade pendente encontrada para esta lista"}
```

---

#### `POST /api/v1/pagamento-avulso/`

**Endpoint principal para integração com WhatsApp.** Recebe um valor em reais e distribui automaticamente pelas mensalidades mais antigas do pagador, em todas as suas listas, cobrindo quantos meses o valor permitir.

- Se o valor cobre mensalidades existentes **e sobra**, ele avança e cria/paga mensalidades futuras automaticamente.
- Se o valor não é suficiente para cobrir a próxima mensalidade, ele informa o que ficou pendente.
- Se sobrar troco (valor maior que tudo que devia), é informado no retorno.

**Body (JSON) — informe `whatsapp` ou `nome`:**

| Campo | Tipo | Obrigatório | Descrição |
|-------|------|-------------|-----------|
| `whatsapp` | string | um dos dois | WhatsApp do pagador |
| `nome` | string | um dos dois | Nome do pagador (busca parcial) |
| `valor` | decimal | sim | Valor total enviado (ex: `120.00`) |
| `data_pagamento` | string (YYYY-MM-DD) | não | Data do pagamento (padrão: hoje) |
| `notas` | string | não | Observação (ex: "Pix recebido") |

**Exemplo de requisição:**

```
POST /api/v1/pagamento-avulso/
X-Api-Token: meu-token
Content-Type: application/json

{
  "whatsapp": "5511999999999",
  "valor": 120.00,
  "data_pagamento": "2026-05-26",
  "notas": "Pix via WhatsApp"
}
```

**Resposta — pagamento completo (200):**

```json
{
  "pagador": "Maria Raquel",
  "valor_enviado": "120.00",
  "total_pago": "120.00",
  "mensalidades_pagas": [
    {
      "id": 41,
      "lista_nome": "Lista Raquel 1",
      "valor": "40.00",
      "vencimento": "2026-03-15",
      "data_pagamento": "2026-05-26",
      "status": "pago",
      "notas": "Pix via WhatsApp"
    },
    {
      "id": 42,
      "lista_nome": "Lista Raquel 1",
      "valor": "40.00",
      "vencimento": "2026-04-15",
      "data_pagamento": "2026-05-26",
      "status": "pago",
      "notas": "Pix via WhatsApp"
    },
    {
      "id": 50,
      "lista_nome": "Lista Raquel 2",
      "valor": "40.00",
      "vencimento": "2026-05-20",
      "data_pagamento": "2026-05-26",
      "status": "pago",
      "notas": "Pix via WhatsApp"
    }
  ]
}
```

**Resposta — valor insuficiente (200):**

```json
{
  "pagador": "Maria Raquel",
  "valor_enviado": "80.00",
  "total_pago": "80.00",
  "mensalidades_pagas": [...],
  "pendente_restante": "40.00",
  "mensalidades_pendentes_restantes": [
    {
      "id": 50,
      "lista_nome": "Lista Raquel 2",
      "valor": "40.00",
      "vencimento": "2026-05-20",
      "status": "atrasado"
    }
  ]
}
```

**Resposta — troco (200):**

```json
{
  "pagador": "Maria Raquel",
  "valor_enviado": "200.00",
  "total_pago": "120.00",
  "mensalidades_pagas": [...],
  "troco": "80.00",
  "aviso": "Valor enviado excede o total. Troco: R$ 80.0"
}
```

**Resposta — nenhuma pendência (200):**

```json
{
  "pagador": "Maria Raquel",
  "aviso": "Nenhuma mensalidade pendente encontrada.",
  "valor_enviado": "120.00"
}
```

**Erros:**

```json
HTTP 400 → {"erro": "Informe whatsapp ou nome do pagador"}
HTTP 400 → {"valor": ["O valor deve ser maior que zero."]}
HTTP 404 → {"erro": "Pagador não encontrado"}
```

---

### Resumo dos endpoints

| Método | URL | Descrição |
|--------|-----|-----------|
| GET | `/api/v1/cliente/` | Dados do cliente pelo WhatsApp |
| GET | `/api/v1/listas/` | Listas ativas do cliente |
| GET | `/api/v1/status/` | Status das mensalidades do cliente |
| GET | `/api/v1/pendencias/` | Total pendente do pagador |
| POST | `/api/v1/pagamento/` | Paga mensalidade de uma lista específica |
| POST | `/api/v1/pagamento-avulso/` | Paga por valor, distribui automaticamente |

### Fluxo recomendado para o agente WhatsApp

```
1. Cliente manda mensagem → agente normaliza o número
2. GET /pendencias/?whatsapp=... → verifica se há débito e quanto
3. Cliente confirma pagamento e informa valor
4. POST /pagamento-avulso/ com o valor → sistema distribui automaticamente
5. Agente responde com o resumo do que foi pago
```

---

### Códigos de resposta HTTP

| Código | Significado |
|--------|------------|
| 200 | Sucesso |
| 400 | Dados inválidos ou parâmetro faltando |
| 403 | Token ausente ou inválido |
| 404 | Recurso não encontrado |
