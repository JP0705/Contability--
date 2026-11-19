# Contability — contexto do projeto

MVP de assistente contábil com IA (pt-BR). Flask + PostgreSQL + Groq (API compatível com OpenAI).

## Como rodar

```bash
py -m pip install -r requirements.txt
cp .env.example .env          # preencher GROQ_API_KEY e SECRET_KEY
docker compose up -d          # sobe o Postgres já com o schema.sql aplicado
py app.py                     # http://127.0.0.1:5000 (cria/atualiza as tabelas ao iniciar)
py -m unittest discover -s tests -v   # NF-e (sem banco) + consultoria/menu (banco real; pulados se ele estiver fora)
```

Nesta máquina o banco roda no container `contability-postgres` do `docker-compose.yml` (volume `contability--_pgdata`, reinicia junto com o Docker). O container antigo `postgres` sumiu após uma falha do Docker Desktop em nov/2026; o volume anônimo dele (`fdc9a2b4…`) foi mantido, mas só tinha 2 mensagens antigas sem dono — pode ser removido com `docker volume rm` quando quiser.

**Cliente de demonstração:** `py seed_demo.py` cria/recria a cliente fictícia Mariana Costa (Doce Sabor Confeitaria, Simples Nacional) com 6 meses de transações até hoje, um exemplo de conversa, a empresa cadastrada (CNPJ fictício válido), 3 NF-e importadas sem lançamentos, 6 contadores afiliados e uma conversa com a contadora Ana Beatriz Rocha. Logins no topo do script: cliente em `DEMO_EMAIL`/`DEMO_PASSWORD`; contadora (vê o menu Atendimentos) em `DEMO_ACC_EMAIL`/`DEMO_ACC_PASSWORD`. Rodar de novo apaga só esse cliente e recria (a sessão aberta dele cai).

Todas as páginas exigem login. Sem banco, o app sobe mas o login mostra erro de banco indisponível.

## Estrutura

- `app.py` — cria o app, configura sessão (`SECRET_KEY`), registra `auth`, `gastos`, `empresa`, `notas`, `consultoria` e `wip`. A home aceita `?q=` para preencher o campo do chat (usado pelas páginas "Em breve"). Rotas do chat: `/` (página), `POST /chat`, `POST /new-chat`. Prompt de sistema fica em `/chat`.
- `auth.py` — blueprint `auth`: `/login`, `/cadastro`, `POST /logout`. Sessão Flask + hash de senha do Werkzeug. Um `before_request` carrega `g.user` e exige login em tudo, exceto `PUBLIC_ENDPOINTS` (APIs recebem 401 JSON).
- `gastos.py` — blueprint `gastos` (`/gastos/`): resumo do mês (`?mes=AAAA-MM`), gráfico dos últimos 5 meses, gastos por categoria, CRUD de transações (`POST /gastos/transacoes`, `.../<id>/editar`, `.../<id>/excluir`). Categorias fixas em `CATEGORIES`. Filtros Jinja `brl` e `pct`.
- `empresa.py` — blueprint `empresa` (`/empresa/`): CNPJ e razão social do usuário (um por usuário). CNPJ com DV inválido é aceito com aviso (para testar com XMLs de exemplo). Filtro Jinja `cnpj`.
- `nfe.py` — leitor de XML de NF-e, sem Flask: `parse_nfe(bytes)` → `ParsedNFe` (header/items/duplicatas/avisos) ou `NFeError` (mensagem pronta para o usuário); `classify(parsed, cnpj)` → `'entrada'`/`'saida'`. Usa `defusedxml` (bloqueia XXE/DTD). Aceita `<nfeProc>` e `<NFe>` puro; só modelo 55 e versões em `ACCEPTED_VERSIONS` (`4.00`). Guarda o XML inteiro e extrai só ~40 campos; ICMS lido de forma genérica (CST/CSOSN + vICMS de qualquer variante); IBS/CBS pelo primeiro `vIBS`/`vCBS` do grupo. Viram **aviso** (não recusa): DV da chave errado, homologação, sem protocolo, soma dos itens ≠ vProd.
- `notas.py` — blueprint `notas` (`/notas/`): lista do mês com filtro entrada/saída, `POST /notas/importar` (até 50 XMLs, 2 MB cada), detalhe, download do XML, exclusão (CASCADE leva itens, parcelas e lançamentos gerados) e `POST /notas/<id>/lancamentos`. `build_launches`: uma transação por parcela (`<cobr><dup>`) ou uma no total; compra → gasto "Operacional", venda → receita "Vendas"; vencimento futuro → pendente. `transactions.nfe_id` marca a origem e impede gerar duas vezes.
- `consultoria.py` — contadores afiliados. `/especialistas/` (diretório com busca/filtro no navegador), `/especialistas/<id>/conversar` (cria ou reaproveita a conversa e redireciona), `/conversas/<id>` (mesma página para cliente e contador; o papel vem de quem está logado), `GET/POST /conversas/<id>/mensagens` (JSON; a página consulta a cada 4 s com `?depois=<último id>`), `/atendimentos/` (caixa do contador; 404 para quem não é contador). Contador = linha em `accountants` com `user_id` do login. Mensagens são texto puro e entram no DOM com `textContent`. Filtros Jinja `initials` e `avatar_color`; `current_accountant` no contexto dos templates.
- `wip.py` — menu lateral (`MENU`, injetado como `menu_items` por context processor; `ACTIVE_ALIASES` diz qual item acende em páginas filhas) e páginas "Em breve" (`/em-breve/<slug>`, conteúdo em `MODULES`: resumo, progresso, etapas e perguntas para o assistente). Para lançar um módulo: crie o blueprint e troque o item do `MENU` de `wip.page` para o endpoint novo.
- `db.py` — pool de conexões lazy (config via `.env`; fuso da sessão em `DB_TIMEZONE`, padrão America/Sao_Paulo, porque o container roda em UTC), `init_db` e todas as consultas. **Toda consulta recebe `user_id`** — é isso que isola os dados entre usuários.
- `schema.sql` — esquema do banco (fonte única; usado pelo `init_db` e pelo docker-compose). Tabelas: `users`, `messages` (com `user_id`), `transactions` (com `nfe_id`), `companies`, `nfe`, `nfe_items`, `nfe_duplicatas`, `accountants`, `consultations` (uma por par cliente × contador), `consultation_messages` (com `read_at` para não lidas).
- `templates/base.html` — layout padrão (sidebar à direita, topbar com logo, usuário logado + Sair, mensagens flash). Toda página nova deve fazer `{% extends "base.html" %}` e preencher os blocos `title`, `styles`, `topbar_actions`, `content` (e opcionalmente `content_class`, `tip`, `scripts`). O menu lateral vem de `wip.MENU` (itens em construção mostram um ponto âmbar e levam à página "Em breve").
- `templates/auth_base.html` — layout das telas sem sidebar (`login.html`, `register.html`, `db_error.html`).
- `templates/index.html` (chat — página principal e referência visual), `gastos.html`, `notas.html`, `nota_detalhe.html`, `empresa.html`, `especialistas.html`, `conversa.html`, `atendimentos.html`, `wip.html`, `_flash.html`. Páginas de blocos empilhados usam `{% block content_class %}stack-page{% endblock %}`.
- `static/base.css` — tokens de cor (`--primary`, `--success`, ...) e componentes compartilhados. Use as variáveis em vez de cores fixas.
- `static/components.css` — componentes comuns (cartões de resumo, `.card-header-custom`, tabela `.transactions-table`, tags/status, seletor de mês, modais, `.form-card`, layout `.stack-page`). Carregado por base.html.
- `static/chat.css`, `gastos.css`, `notas.css`, `consultoria.css`, `wip.css`, `login.css` — só o específico de cada página (a conversa com contador reaproveita `chat.css`). `script.js` — chat; `gastos.js` — modais de transação; `notas.js` — upload; `especialistas.js` — filtro do diretório; `conversa.js` — envio e atualização da conversa; `wip.js` — progresso animado, engrenagens e confete.
- `samples/nfe/` — XMLs de exemplo (o do usuário + gerados por `gerar_amostras.py`, com CNPJ/chave válidos, incluindo IBS/CBS e inválidos para teste). `tests/test_nfe.py` usa as funções do gerador.
- Respostas da IA: Markdown → `marked` → **`DOMPurify.sanitize`** (função `renderMarkdown` em `script.js`) → DOM. Nunca inserir HTML vindo da IA ou do usuário sem passar por ela; texto do usuário usa `textContent`.

## Estado atual (nov/2026)

Funciona: cadastro/login/logout; chat com IA com histórico por usuário (recarregado ao abrir a página) e respostas sanitizadas; tela de Gastos com dados reais e cadastro, edição e exclusão de transações; painel "Dashboard Financeiro" da home com o resumo real do mês atual (`gastos.month_summary`); aba Notas Fiscais com importação de XML de NF-e modelo 55, detalhe e geração de lançamentos; Especialistas com conversa cliente × contador (e caixa de Atendimentos do contador); páginas "Em breve" para os módulos ainda não construídos.

Nenhum item do menu leva mais a `#`.

Mensagens antigas, de antes do login existir, ficaram no banco com `user_id` NULL e não aparecem para ninguém.

## Próximos passos sugeridos para o MVP

1. Proteção CSRF nos formulários (hoje só `SameSite=Lax` no cookie de sessão) — ex.: Flask-WTF.
2. Dar contexto financeiro do usuário à IA (ex.: `gastos.month_summary` no prompt de sistema).
3. Streaming de respostas (o `gpt-oss-20b` pode levar ~30s).
4. Consultoria, próximas fases: notificação de mensagem nova (e-mail ou contador no menu), anexos (enviar NF-e/documentos na conversa), cadastro de contadores pelo app (hoje só pelo seed/SQL), WebSocket/SSE no lugar da consulta a cada 4 s.
5. NF-e, próximas fases: verificar assinatura digital (`xmlsec`), validar contra o XSD oficial, eventos (cancelamento/CC-e), aceitar novas versões de leiaute em `nfe.ACCEPTED_VERSIONS`, categoria do lançamento escolhida pelo usuário, IA consultando as notas.

## Convenções

- Interface e textos em português do Brasil.
- Segredos só no `.env` (ignorado pelo git). Novas variáveis devem ir também no `.env.example`.
- Alterações de banco: editar `schema.sql` com instruções idempotentes (`CREATE ... IF NOT EXISTS`, `ADD COLUMN IF NOT EXISTS`).
- Dados sempre filtrados por `g.user["id"]`; nunca confiar em id de usuário vindo do formulário.
