-- Esquema do banco Contability.
-- Aplicado automaticamente por db.init_db() na inicialização do app
-- e pelo container Postgres do docker-compose na primeira subida.
-- Todas as instruções são idempotentes (podem rodar várias vezes).

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    name VARCHAR(120) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS messages (
    id SERIAL PRIMARY KEY,
    role VARCHAR(20) NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- histórico por usuário (mensagens antigas, sem dono, ficam com NULL e não aparecem para ninguém)
ALTER TABLE messages
    ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id) ON DELETE CASCADE;

CREATE INDEX IF NOT EXISTS idx_messages_user ON messages (user_id, id);

CREATE TABLE IF NOT EXISTS transactions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type VARCHAR(10) NOT NULL CHECK (type IN ('income', 'expense')),
    description VARCHAR(200) NOT NULL,
    category VARCHAR(60) NOT NULL,
    amount NUMERIC(12, 2) NOT NULL CHECK (amount > 0),
    date DATE NOT NULL,
    status VARCHAR(10) NOT NULL DEFAULT 'done' CHECK (status IN ('done', 'pending')),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_transactions_user_date ON transactions (user_id, date);

-- =========================================================
-- EMPRESA DO USUÁRIO (uma por usuário no MVP)
-- usada para saber se a NF-e é de compra (entrada) ou venda (saída)
-- =========================================================
CREATE TABLE IF NOT EXISTS companies (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    cnpj CHAR(14) NOT NULL,
    razao_social VARCHAR(200) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- =========================================================
-- NF-e (modelo 55)
-- o XML original fica guardado inteiro; só os campos essenciais
-- são extraídos para colunas
-- =========================================================
CREATE TABLE IF NOT EXISTS nfe (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    chave CHAR(44) NOT NULL,
    versao VARCHAR(10) NOT NULL,
    numero INTEGER NOT NULL,
    serie INTEGER NOT NULL,
    emissao TIMESTAMPTZ NOT NULL,
    natureza VARCHAR(120),
    direcao VARCHAR(10) NOT NULL CHECK (direcao IN ('entrada', 'saida')),
    ambiente SMALLINT NOT NULL,              -- 1 = produção, 2 = homologação
    emit_doc VARCHAR(14) NOT NULL,
    emit_nome VARCHAR(200) NOT NULL,
    emit_uf CHAR(2),
    dest_doc VARCHAR(14),
    dest_nome VARCHAR(200),
    dest_uf CHAR(2),
    v_produtos NUMERIC(15, 2) NOT NULL DEFAULT 0,
    v_desconto NUMERIC(15, 2) NOT NULL DEFAULT 0,
    v_frete NUMERIC(15, 2) NOT NULL DEFAULT 0,
    v_icms NUMERIC(15, 2) NOT NULL DEFAULT 0,
    v_st NUMERIC(15, 2) NOT NULL DEFAULT 0,
    v_ipi NUMERIC(15, 2) NOT NULL DEFAULT 0,
    v_pis NUMERIC(15, 2) NOT NULL DEFAULT 0,
    v_cofins NUMERIC(15, 2) NOT NULL DEFAULT 0,
    v_ibs NUMERIC(15, 2) NOT NULL DEFAULT 0,
    v_cbs NUMERIC(15, 2) NOT NULL DEFAULT 0,
    v_total NUMERIC(15, 2) NOT NULL,
    protocolo VARCHAR(20),                   -- NULL = XML sem autorização (sem protNFe)
    status_sefaz VARCHAR(5),
    avisos TEXT[] NOT NULL DEFAULT '{}',
    xml TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE (user_id, chave)
);

CREATE INDEX IF NOT EXISTS idx_nfe_user_emissao ON nfe (user_id, emissao);

CREATE TABLE IF NOT EXISTS nfe_items (
    id SERIAL PRIMARY KEY,
    nfe_id INTEGER NOT NULL REFERENCES nfe(id) ON DELETE CASCADE,
    n_item INTEGER NOT NULL,
    codigo VARCHAR(60),
    descricao VARCHAR(200) NOT NULL,
    ncm VARCHAR(8),
    cfop VARCHAR(4),
    unidade VARCHAR(10),
    quantidade NUMERIC(15, 4) NOT NULL DEFAULT 0,
    valor_unitario NUMERIC(21, 10) NOT NULL DEFAULT 0,
    valor_total NUMERIC(15, 2) NOT NULL DEFAULT 0,
    icms_cst VARCHAR(3),                     -- CST (regime normal) ou CSOSN (Simples)
    icms_valor NUMERIC(15, 2) NOT NULL DEFAULT 0,
    ipi_valor NUMERIC(15, 2) NOT NULL DEFAULT 0,
    pis_valor NUMERIC(15, 2) NOT NULL DEFAULT 0,
    cofins_valor NUMERIC(15, 2) NOT NULL DEFAULT 0,
    ibs_valor NUMERIC(15, 2) NOT NULL DEFAULT 0,
    cbs_valor NUMERIC(15, 2) NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_nfe_items_nfe ON nfe_items (nfe_id);

CREATE TABLE IF NOT EXISTS nfe_duplicatas (
    id SERIAL PRIMARY KEY,
    nfe_id INTEGER NOT NULL REFERENCES nfe(id) ON DELETE CASCADE,
    numero VARCHAR(60),
    vencimento DATE NOT NULL,
    valor NUMERIC(15, 2) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_nfe_dup_nfe ON nfe_duplicatas (nfe_id);

-- lançamentos gerados a partir de uma NF-e (excluir a nota exclui os lançamentos dela)
ALTER TABLE transactions
    ADD COLUMN IF NOT EXISTS nfe_id INTEGER REFERENCES nfe(id) ON DELETE CASCADE;

CREATE INDEX IF NOT EXISTS idx_transactions_nfe ON transactions (nfe_id);

-- =========================================================
-- CONSULTORIA COM CONTADORES AFILIADOS
-- =========================================================
CREATE TABLE IF NOT EXISTS accountants (
    id SERIAL PRIMARY KEY,
    user_id INTEGER UNIQUE REFERENCES users(id) ON DELETE SET NULL,  -- login do contador (opcional)
    name VARCHAR(120) NOT NULL,
    crc VARCHAR(30) NOT NULL,                  -- registro no Conselho Regional de Contabilidade
    city VARCHAR(80),
    uf CHAR(2),
    specialties TEXT[] NOT NULL DEFAULT '{}',
    bio TEXT,
    years_experience SMALLINT,
    rating NUMERIC(2, 1),
    available BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- uma conversa por par cliente x contador
CREATE TABLE IF NOT EXISTS consultations (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    accountant_id INTEGER NOT NULL REFERENCES accountants(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE (user_id, accountant_id)
);

CREATE INDEX IF NOT EXISTS idx_consultations_acc ON consultations (accountant_id, updated_at);

CREATE TABLE IF NOT EXISTS consultation_messages (
    id SERIAL PRIMARY KEY,
    consultation_id INTEGER NOT NULL REFERENCES consultations(id) ON DELETE CASCADE,
    sender VARCHAR(10) NOT NULL CHECK (sender IN ('cliente', 'contador')),
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    read_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_cmsg_consultation ON consultation_messages (consultation_id, id);

-- =========================================================
-- CHAT COM IA: CONVERSAS SEPARADAS (cada uma com seu próprio contexto)
-- =========================================================
CREATE TABLE IF NOT EXISTS chat_conversations (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(80) NOT NULL DEFAULT 'Nova conversa',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chatconv_user ON chat_conversations (user_id, updated_at);

ALTER TABLE messages
    ADD COLUMN IF NOT EXISTS conversation_id INTEGER REFERENCES chat_conversations(id) ON DELETE CASCADE;

CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages (conversation_id, id);

-- migração: mensagens de antes das conversas viram uma "Conversa anterior" por usuário
DO $$
DECLARE
    r RECORD;
    cid INTEGER;
BEGIN
    FOR r IN SELECT DISTINCT user_id FROM messages
             WHERE user_id IS NOT NULL AND conversation_id IS NULL LOOP
        INSERT INTO chat_conversations (user_id, title, created_at, updated_at)
        SELECT r.user_id, 'Conversa anterior', min(created_at), max(created_at)
        FROM messages WHERE user_id = r.user_id AND conversation_id IS NULL
        RETURNING id INTO cid;

        UPDATE messages SET conversation_id = cid
        WHERE user_id = r.user_id AND conversation_id IS NULL;
    END LOOP;
END $$;
