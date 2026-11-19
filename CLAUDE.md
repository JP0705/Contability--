# Contability — contexto do projeto

MVP de assistente contábil com IA (pt-BR). Flask + PostgreSQL + Groq (API compatível com OpenAI).

## Como rodar

```bash
py -m pip install -r requirements.txt
cp .env.example .env                  # preencher GROQ_API_KEY e SECRET_KEY
docker compose up -d                  # sobe o Postgres já com contability/schema.sql aplicado
py app.py                             # http://127.0.0.1:5000 (cria/atualiza as tabelas ao iniciar)
py scripts/seed_demo.py               # dados de demonstração
py -m unittest discover -s tests -v   # NF-e (sem banco) + chat/consultoria/menu (banco real; pulados se ele estiver fora)
```

Nesta máquina o banco roda no container `contability-postgres` do `docker-compose.yml` (volume `contability--_pgdata`, reinicia junto com o Docker). O container antigo `postgres` sumiu após uma falha do Docker Desktop em nov/2026; o volume anônimo dele (`fdc9a2b4…`) foi mantido, mas só tinha 2 mensagens antigas sem dono — pode ser removido com `docker volume rm` quando quiser.

**Cliente de demonstração:** `py scripts/seed_demo.py` cria/recria a cliente fictícia Mariana Costa (Doce Sabor Confeitaria, Simples Nacional) com 6 meses de transações até hoje, duas conversas com a IA (contextos separados), a empresa cadastrada (CNPJ fictício válido), 3 NF-e importadas sem lançamentos, 6 contadores afiliados e uma conversa com a contadora Ana Beatriz Rocha. Logins no topo do script: cliente em `DEMO_EMAIL`/`DEMO_PASSWORD`; contadora (vê o menu Atendimentos) em `DEMO_ACC_EMAIL`/`DEMO_ACC_PASSWORD`. Rodar de novo apaga só esse cliente e recria (a sessão aberta dele cai).

Todas as páginas exigem login. Sem banco, o app sobe mas o login mostra erro de banco indisponível.

## Estrutura de pastas

```
app.py                      ponto de entrada (create_app + init_db + app.run)
contability/                pacote da aplicação
  __init__.py               create_app(): .env, sessão, registro dos módulos de rotas
  db.py                     pool de conexões e TODAS as consultas
  schema.sql                esquema do banco (idempotente)
  routes/                   um blueprint por área (cada módulo expõe init_app(app))
  services/                 regras sem Flask (nfe.py)
  templates/                layouts/, partials/ e uma pasta por área
  static/                   css/, js/, img/
scripts/seed_demo.py        dados de demonstração
samples/nfe/                XMLs de exemplo + gerar_amostras.py
tests/                      unittest
```

Imports internos são relativos ao pacote (`from .. import db`, `from ..services import nfe`). Scripts e testes fora do pacote importam `from contability import db` (colocam a raiz no `sys.path`).

## Módulos

- `contability/__init__.py` — `create_app()`. Ordem de registro: `auth` primeiro (o `before_request` dele protege tudo), depois `chat`, `gastos`, `empresa`, `notas`, `consultoria`, `wip`.
- `routes/chat.py` — blueprint `chat`. **Conversas separadas:** `/` (`chat.home`) é uma conversa nova (em branco; só é criada no banco quando a primeira resposta da IA chega, com título vindo da primeira pergunta), `/c/<id>` (`chat.conversation`) abre uma conversa, `POST /chat` recebe `{message, conversation_id}` e manda à IA só o histórico daquela conversa (`HISTORY_LIMIT`), `POST /chat/<id>/renomear` e `POST /chat/<id>/excluir`. Cliente da IA em `client`, prompt em `SYSTEM_PROMPT`. A home aceita `?q=` para preencher o campo do chat (usado pelas páginas "Em breve"). Lista lateral agrupada por data (`_conversation_groups`).
- `routes/auth.py` — blueprint `auth`: `/login`, `/cadastro`, `POST /logout`. Sessão Flask + hash de senha do Werkzeug. `before_request` carrega `g.user` e exige login em tudo, exceto `PUBLIC_ENDPOINTS` (APIs — `/chat...`, `.../mensagens`, JSON — recebem 401 JSON).
- `routes/gastos.py` — blueprint `gastos` (`/gastos/`): resumo do mês (`?mes=AAAA-MM`), gráfico dos últimos 5 meses, gastos por categoria, CRUD de transações. Categorias fixas em `CATEGORIES`. Filtros Jinja `brl` e `pct`. `month_summary()` alimenta o painel da home.
- `routes/empresa.py` — blueprint `empresa` (`/empresa/`): CNPJ e razão social (um por usuário). CNPJ com DV inválido é aceito com aviso. Filtro Jinja `cnpj`.
- `routes/notas.py` — blueprint `notas` (`/notas/`): lista do mês com filtro entrada/saída, `POST /notas/importar` (até 50 XMLs, 2 MB cada), detalhe, download do XML, exclusão (CASCADE leva itens, parcelas e lançamentos) e `POST /notas/<id>/lancamentos`. `build_launches`: uma transação por parcela ou uma no total; compra → gasto "Operacional", venda → receita "Vendas"; vencimento futuro → pendente. `transactions.nfe_id` impede gerar duas vezes.
- `services/nfe.py` — leitor de XML de NF-e, sem Flask: `parse_nfe(bytes)` → `ParsedNFe` ou `NFeError` (mensagem pronta para o usuário); `classify(parsed, cnpj)` → `'entrada'`/`'saida'`. Usa `defusedxml`. Aceita `<nfeProc>` e `<NFe>` puro; só modelo 55 e versões em `ACCEPTED_VERSIONS` (`4.00`). Guarda o XML inteiro e extrai ~40 campos; ICMS genérico (CST/CSOSN + vICMS de qualquer variante); IBS/CBS pelo primeiro `vIBS`/`vCBS` do grupo. Viram **aviso** (não recusa): DV da chave, homologação, sem protocolo, soma dos itens ≠ vProd.
- `routes/consultoria.py` — contadores afiliados: `/especialistas/`, `/especialistas/<id>/conversar`, `/conversas/<id>` (mesma página para cliente e contador; o papel vem de quem está logado), `GET/POST /conversas/<id>/mensagens` (JSON; a página consulta a cada 4 s), `/atendimentos/` (404 para quem não é contador). Contador = linha em `accountants` com `user_id`. Mensagens em texto puro (`textContent`). Filtros `initials`, `avatar_color`; `current_accountant` no contexto.
- `routes/wip.py` — menu lateral (`MENU` → `menu_items` por context processor; `ACTIVE_ALIASES` diz qual item acende em páginas filhas) e páginas "Em breve" (`/em-breve/<slug>`, conteúdo em `MODULES`). Para lançar um módulo: crie o blueprint e troque o item do `MENU` de `wip.page` para o endpoint novo.
- `db.py` — pool lazy (config via `.env`; fuso da sessão em `DB_TIMEZONE`, padrão America/Sao_Paulo, porque o container roda em UTC), `init_db`, `transaction()` para gravações em várias tabelas. **Toda consulta recebe `user_id`** — é isso que isola os dados entre usuários.
- `schema.sql` — tabelas: `users`, `chat_conversations`, `messages` (`user_id`, `conversation_id`), `transactions` (`nfe_id`), `companies`, `nfe`, `nfe_items`, `nfe_duplicatas`, `accountants`, `consultations`, `consultation_messages` (`read_at`). Também contém migrações idempotentes (ex.: mensagens antigas → "Conversa anterior").

## Templates e estáticos

- `templates/layouts/base.html` — layout das páginas internas (sidebar, topbar, usuário + Sair, flash). Páginas fazem `{% extends "layouts/base.html" %}` e preenchem `title`, `styles`, `topbar_actions`, `content` (opcionais: `content_class`, `tip`, `scripts`). Blocos empilhados: `content_class` = `stack-page`.
- `templates/layouts/auth.html` — telas de entrada (painel da marca + cartão): `auth/login.html`, `auth/register.html`, `auth/db_error.html` (blocos `heading` e `form`).
- `templates/partials/flash.html`; uma pasta por área: `chat/index.html`, `gastos/index.html`, `notas/index.html` e `notas/detalhe.html`, `empresa/index.html`, `consultoria/{especialistas,conversa,atendimentos}.html`, `wip/index.html`.
- `static/css/` — `base.css` (tokens de cor; use as variáveis), `components.css` (componentes comuns, carregado pelo base), e um CSS por área (`chat`, `gastos`, `notas`, `consultoria`, `wip`, `login`). A conversa com contador reaproveita `chat.css`.
- `static/js/` — `script.js` (chat: envio, lista de conversas, renomear/excluir, `history.pushState`), `auth.js` (mostrar senha, Caps Lock, força da senha), `gastos.js`, `notas.js`, `especialistas.js`, `conversa.js`, `wip.js`.
- Referências nos templates: `url_for('static', filename='css/x.css')`, `'js/x.js'`, `'img/logo.png'`.
- Respostas da IA: Markdown → `marked` → **`DOMPurify.sanitize`** (`renderMarkdown` em `script.js`) → DOM. Nunca inserir HTML da IA ou do usuário sem passar por ela; texto do usuário usa `textContent`.

## Testes e amostras

- `tests/test_nfe.py` — leitor de NF-e (sem banco); usa as funções de `samples/nfe/gerar_amostras.py`.
- `tests/test_chat.py` — conversas do chat com uma IA falsa (`FakeLLM`, aplicada com `mock.patch.object` em `contability.routes.chat.client`): prova que uma conversa não vê a outra.
- `tests/test_consultoria.py` — conversas cliente × contador, permissões, menu e páginas "Em breve".
- `samples/nfe/` — XMLs de exemplo (válidos, com IBS/CBS, e inválidos). `samples/nfe/para_importar/` tem 5 notas da empresa demo para testar a importação pela tela (não entram no seed).

## Estado atual (nov/2026)

Funciona: cadastro/login/logout (telas redesenhadas); chat com IA em conversas separadas (listar, renomear, excluir) e respostas sanitizadas; Gastos com CRUD; painel "Dashboard Financeiro" da home com dados reais; Notas Fiscais (importação de XML de NF-e modelo 55, detalhe, lançamentos); Especialistas com conversa cliente × contador e caixa de Atendimentos; páginas "Em breve" para os módulos ainda não construídos. Nenhum item do menu leva a `#`.

Mensagens de antes do login existir ficaram com `user_id` NULL e não aparecem para ninguém.

## Próximos passos sugeridos para o MVP

1. Proteção CSRF nos formulários (hoje só `SameSite=Lax` no cookie de sessão) — ex.: Flask-WTF.
2. Dar contexto financeiro do usuário à IA (ex.: `gastos.month_summary` no `SYSTEM_PROMPT`).
3. Streaming de respostas (o `gpt-oss-20b` pode levar ~30s).
4. Consultoria: notificação de mensagem nova, anexos, cadastro de contadores pelo app, WebSocket/SSE no lugar da consulta a cada 4 s.
5. NF-e: assinatura digital (`xmlsec`), validação pelo XSD oficial, eventos (cancelamento/CC-e), novas versões em `nfe.ACCEPTED_VERSIONS`, categoria do lançamento escolhida pelo usuário, IA consultando as notas.

## Convenções

- Interface e textos em português do Brasil.
- Segredos só no `.env` (ignorado pelo git). Novas variáveis devem ir também no `.env.example`.
- Alterações de banco: editar `contability/schema.sql` com instruções idempotentes (`CREATE ... IF NOT EXISTS`, `ADD COLUMN IF NOT EXISTS`).
- Dados sempre filtrados por `g.user["id"]`; nunca confiar em id de usuário vindo do formulário.
- Página nova = blueprint em `routes/` com `init_app(app)` registrado em `create_app()`, template em `templates/<área>/`, CSS/JS em `static/css|js/`.
