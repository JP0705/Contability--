# Contability - Assistente Contábil com IA

Sistema inteligente de consultoria contábil e financeira utilizando IA generativa, desenvolvido com Flask, PostgreSQL e modelos LLM via Groq.

O Contability auxilia profissionais, empresas e empreendedores em dúvidas relacionadas à contabilidade, tributação, obrigações fiscais e gestão financeira.

---

## ✨ Funcionalidades

* Assistente contábil especializado
* Memória persistente de conversas
* Histórico armazenado em PostgreSQL
* Respostas formatadas em Markdown
* Interface moderna inspirada em ChatGPT e Claude
* Dashboard responsivo
* Sidebar interativa
* Nova consulta com limpeza automática de contexto
* Integração com modelos LLM da Groq
* Renderização avançada de listas, títulos e tabelas
* Comunicação em tempo real via Fetch API

---

## 🖥️ Tecnologias Utilizadas

### Backend

* Python
* Flask
* PostgreSQL
* Psycopg2
* Groq API

### Frontend

* HTML5
* CSS3
* JavaScript
* Bootstrap 5
* Bootstrap Icons
* Marked.js

### IA

* Llama 3.1 8B Instant
* Engenharia de Prompt
* Memória Conversacional

### Infraestrutura

* Docker Desktop
* PostgreSQL Container

---

## 📁 Estrutura do Projeto

```txt
Contability/
│
├── app.py
├── db.py
├── .env
├── requirements.txt
│
├── templates/
│   └── index.html
│
├── static/
│   ├── style.css
│   ├── script.js
│   └── img/
│       └── logo.png
│
└── README.md
```

---

## ⚙️ Instalação

### 1. Clonar o repositório

```bash
git clone https://github.com/JP0705/Contability--.git
```

### 2. Entrar na pasta

```bash
cd contability--
```

### 3. Instalar dependências

```bash
py -m pip install -r requirements.txt
```

---

## 🐘 Configuração do PostgreSQL

Caso utilize Docker:

```bash
docker run --name postgres ^
-e POSTGRES_PASSWORD=sua_senha ^
-p 5432:5432 ^
-d postgres:latest
```

Criar o banco:

```sql
CREATE DATABASE contability;
```

Criar a tabela de histórico:

```sql
CREATE TABLE messages (
    id SERIAL PRIMARY KEY,
    role VARCHAR(20) NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);
```

---

## 🔑 Configuração da API

Crie um arquivo `.env`:

```env
GROQ_API_KEY=sua_api_key
```

Obtenha sua chave gratuitamente:

https://console.groq.com

---

## ▶️ Executando o Projeto

```bash
py app.py
```

Abra no navegador:

```txt
http://127.0.0.1:5000
```

---

## 🧠 Modelo Utilizado

Atualmente o projeto utiliza:

```txt
llama-3.1-8b-instant
```

via Groq API.

---

## 💾 Memória Conversacional

O Contability armazena automaticamente:

* Perguntas do usuário
* Respostas da IA
* Histórico recente da conversa

Isso permite que a IA mantenha contexto entre interações, tornando as respostas mais naturais e consistentes.

---

## 📌 Roadmap

### Curto Prazo

* [x] Interface responsiva
* [x] Integração com Groq
* [x] Histórico persistente
* [x] PostgreSQL
* [x] Markdown nas respostas
* [x] Nova consulta

### Próximas Funcionalidades

* [ ] Upload de documentos PDF
* [ ] Leitura de notas fiscais
* [ ] Geração de relatórios PDF
* [ ] Exportação de conversas
* [ ] Sistema de usuários
* [ ] Multiempresa
* [ ] Dashboard financeiro
* [ ] Tema Dark Mode
* [ ] Streaming de respostas
* [ ] RAG com legislação tributária
* [ ] Integração com Receita Federal

---

## 📄 Licença

Este projeto está licenciado sob a licença MIT.

---

## 👨‍💻 Autor

Desenvolvido por JP0705

---

## ⚠️ Segurança

Nunca envie para o GitHub:

* `.env`
* senhas
* chaves de API
* credenciais de banco de dados

Utilize um `.gitignore`:

```gitignore
.env
__pycache__/
*.pyc
venv/
.env.local
```

---

## 🚀 Status do Projeto

Em desenvolvimento ativo.

Versão atual com:

* IA conversacional
* Persistência em PostgreSQL
* Interface moderna
* Contexto entre mensagens
* Arquitetura pronta para expansão
