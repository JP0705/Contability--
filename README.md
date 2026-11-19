# Contability — Assistente Contábil com IA

Plataforma de gestão contábil e financeira para pequenas empresas, com assistente de IA, controle de gastos, importação de notas fiscais eletrônicas e consultoria com contadores afiliados.

Desenvolvida com **Flask**, **PostgreSQL** e modelos de linguagem via **Groq**.

---

## ✨ Funcionalidades

### 🤖 Assistente contábil com IA
* Chat especializado em contabilidade, Simples Nacional, MEI, impostos, folha e planejamento tributário
* Respostas em Markdown (títulos, listas, tabelas), **sanitizadas com DOMPurify** antes de entrar na página
* **Conversas separadas**: cada conversa tem seu próprio contexto (a IA só lembra do que foi dito nela)
* Lista de conversas agrupada por data, com renomear e excluir; título criado a partir da primeira pergunta
* "Nova consulta" abre uma conversa em branco sem apagar as anteriores
* Painel **Dashboard Financeiro** com o resumo real do mês (receitas, gastos, saldo, pendências e maior categoria de gasto)

### 🔐 Contas de usuário
* Cadastro, login e logout com senha protegida por hash
* Todos os dados (chat, gastos, notas, conversas) isolados por usuário
* Cadastro da empresa (**Minha empresa**: CNPJ e razão social)

### 💰 Gastos
* Cadastro, edição e exclusão de receitas e gastos, com categoria e status (pago/pendente)
* Resumo do mês com variação em relação ao mês anterior
* Gráfico dos últimos 5 meses e gastos por categoria
* Navegação entre meses

### 🧾 Notas Fiscais (NF-e)
* Importação de XML de **NF-e modelo 55** (leiaute 4.00), autorizada (`nfeProc`) ou não (`NFe`), vários arquivos por vez
* Classificação automática em **entrada** (compra) ou **saída** (venda) pelo CNPJ da empresa
* Leitura dos campos essenciais: emitente, destinatário, itens (NCM, CFOP, CST/CSOSN), totais e impostos (ICMS, ST, IPI, PIS, COFINS e **IBS/CBS** da Reforma Tributária)
* Avisos sem bloquear a importação: homologação, sem protocolo, dígito verificador da chave, divergência de totais
* Geração de lançamentos em Gastos (um por parcela; vencimento futuro entra como pendente)
* Download do XML original
* Leitura segura com `defusedxml` (bloqueia XXE e "bomba de entidades")

### 👩‍💼 Especialistas
* Diretório de contadores afiliados com busca e filtro por especialidade
* Conversa entre cliente e contador, atualizada automaticamente para os dois lados
* Página **Atendimentos** para o contador responder seus clientes, com mensagens não lidas

### 🚧 Módulos em construção
* Impostos, Fluxo de Caixa, Folha de Pagamento, MEI & Simples, Receita Federal, Obrigações Fiscais e Relatórios Financeiros têm uma página **"Em breve"** com o progresso, as etapas planejadas e perguntas prontas para o assistente de IA

---

## 🖥️ Tecnologias

| Camada | Tecnologias |
|---|---|
| Backend | Python 3.10+, Flask, psycopg2, defusedxml |
| Banco de dados | PostgreSQL 16 (Docker) |
| IA | Groq API (compatível com OpenAI), modelo `openai/gpt-oss-20b` configurável em `GROQ_MODEL` |
| Frontend | HTML (Jinja), CSS, JavaScript, Bootstrap 5, Bootstrap Icons, Marked.js, DOMPurify |
| Testes | `unittest` (biblioteca padrão do Python) |

---

## 📁 Estrutura do projeto

```txt
Contability--/
├── app.py                    # ponto de entrada: py app.py
├── contability/              # a aplicação (pacote Flask)
│   ├── __init__.py           # create_app(): configuração e registro dos módulos
│   ├── db.py                 # conexão com o PostgreSQL e todas as consultas
│   ├── schema.sql            # esquema do banco (aplicado automaticamente)
│   ├── routes/               # páginas e APIs, uma por área
│   │   ├── auth.py           #   cadastro, login, logout e proteção das rotas
│   │   ├── chat.py           #   chat com IA em conversas separadas
│   │   ├── gastos.py         #   aba Gastos
│   │   ├── empresa.py        #   Minha empresa (CNPJ)
│   │   ├── notas.py          #   aba Notas Fiscais
│   │   ├── consultoria.py    #   Especialistas, conversas e Atendimentos
│   │   └── wip.py            #   menu lateral e páginas "Em breve"
│   ├── services/
│   │   └── nfe.py            # leitor e validador de XML de NF-e (sem Flask)
│   ├── templates/            # layouts/, partials/ e uma pasta por área
│   └── static/               # css/, js/ e img/
├── scripts/
│   └── seed_demo.py          # cria dados de demonstração
├── samples/nfe/              # XMLs de NF-e de exemplo (+ para_importar/)
├── tests/                    # testes automatizados
├── docker-compose.yml        # PostgreSQL local
├── requirements.txt
├── .env.example              # modelo das variáveis de ambiente
└── CLAUDE.md                 # contexto técnico detalhado do projeto
```

---

## ⚙️ Como rodar

### 1. Clonar e instalar

```bash
git clone https://github.com/JP0705/Contability--.git
```

```bash
cd Contability--
```

```bash
py -m pip install -r requirements.txt
```

### 2. Configurar o `.env`

Copie `.env.example` para `.env` e preencha ao menos:

```env
GROQ_API_KEY=sua_api_key
SECRET_KEY=uma_chave_aleatoria
```

* Chave da Groq (gratuita): https://console.groq.com
* Para gerar a `SECRET_KEY`:

```bash
py -c "import secrets; print(secrets.token_hex(32))"
```

As credenciais do banco (`DB_HOST`, `DB_USER`, `DB_PASSWORD`...) e o fuso (`DB_TIMEZONE`, padrão `America/Sao_Paulo`) também ficam no `.env`.

### 3. Subir o banco

Com o Docker Desktop aberto:

```bash
docker compose up -d
```

O container reinicia sozinho junto com o Docker. Sem Docker, crie um database `contability` no PostgreSQL; as tabelas são criadas ao iniciar o app.

### 4. Iniciar

```bash
py app.py
```

Abra http://127.0.0.1:5000 e crie sua conta.

---

## 🧪 Dados de demonstração

Para testar com tudo preenchido:

```bash
py scripts/seed_demo.py
```

Cria a cliente fictícia **Mariana Costa — Doce Sabor Confeitaria** (Simples Nacional) com:

* 6 meses de receitas e despesas
* empresa cadastrada e 3 NF-e importadas (compra com parcelas, venda e compra com IBS/CBS)
* 6 contadores afiliados e uma conversa em andamento
* uma conta de **contadora** para testar a página Atendimentos

Os e-mails e senhas das contas demo estão no topo de `scripts/seed_demo.py` (`DEMO_EMAIL`, `DEMO_ACC_EMAIL`). Rodar de novo recria só os dados demo.

Os XMLs de exemplo ficam em `samples/nfe/`; em `samples/nfe/para_importar/` há 5 notas extras da empresa demo para testar a importação pela tela. Para recriá-los com datas atuais:

```bash
py samples/nfe/gerar_amostras.py
```

---

## ✅ Testes

```bash
py -m unittest discover -s tests -v
```

* `tests/test_nfe.py`: leitor de NF-e (leitura, recusas, segurança do XML, geração de lançamentos). Não precisa de banco.
* `tests/test_chat.py`: conversas do chat com IA (contexto separado, renomear, excluir, isolamento entre usuários), usando uma IA falsa.
* `tests/test_consultoria.py`: conversas, permissões, menu e páginas "Em breve". Usa o banco real com usuários temporários e é pulado se o PostgreSQL estiver fora do ar.

---

## 📌 Roadmap

### Concluído
* [x] Chat com IA em conversas separadas, com histórico persistente
* [x] Sistema de usuários com dados isolados
* [x] Controle de gastos e receitas
* [x] Dashboard financeiro da home com dados reais
* [x] Leitura de notas fiscais (XML de NF-e modelo 55)
* [x] Consultoria com contadores afiliados
* [x] Sanitização das respostas da IA

### Próximos passos
* [ ] Proteção CSRF nos formulários
* [ ] IA com contexto financeiro do usuário (gastos e notas no prompt)
* [ ] Streaming das respostas da IA
* [ ] Notificação de mensagens novas dos contadores
* [ ] NF-e: verificação de assinatura digital, validação pelo XSD oficial e eventos (cancelamento, CC-e)
* [ ] Módulos Impostos, Fluxo de Caixa, Folha de Pagamento, MEI & Simples, Receita Federal, Obrigações Fiscais e Relatórios
* [ ] Upload de PDF e exportação de relatórios
* [ ] Multiempresa
* [ ] Tema escuro

---

## ⚠️ Segurança

* Segredos ficam só no `.env`, que está no `.gitignore` e **nunca** deve ser enviado ao GitHub. Use o `.env.example` como modelo.
* Senhas são guardadas apenas como hash (Werkzeug).
* Todas as consultas ao banco filtram pelo usuário logado.
* Conteúdo da IA e das conversas é sanitizado ou inserido como texto puro na página.
* XMLs enviados são lidos com `defusedxml`.
* As senhas do `scripts/seed_demo.py` são apenas para as contas demo em ambiente local.

---

## 📄 Licença

Este projeto está licenciado sob a licença MIT.

---

## 👨‍💻 Autor

Desenvolvido por JP0705.
