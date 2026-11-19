"""Acesso ao PostgreSQL.

Usa um pool de conexões criado sob demanda (lazy), para que o app suba
mesmo com o banco fora do ar. Configuração via variáveis de ambiente
(ver .env.example). Todas as consultas recebem o user_id para isolar
os dados de cada usuário.
"""
import os
from contextlib import contextmanager
from pathlib import Path

import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.pool import ThreadedConnectionPool
from dotenv import load_dotenv

load_dotenv()

SCHEMA_FILE = Path(__file__).with_name("schema.sql")

_pool = None


def _get_pool():
    global _pool
    if _pool is None:
        _pool = ThreadedConnectionPool(
            1, 10,
            host=os.getenv("DB_HOST", "localhost"),
            port=os.getenv("DB_PORT", "5432"),
            dbname=os.getenv("DB_NAME", "contability"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD", "postgres"),
            # NOW()/created_at no horário local (o container do Postgres roda em UTC)
            options=f"-c timezone={os.getenv('DB_TIMEZONE', 'America/Sao_Paulo')}",
        )
    return _pool


@contextmanager
def cursor():
    """Cursor (dict) em autocommit; devolve a conexão ao pool ao final."""
    pool = _get_pool()
    conn = pool.getconn()
    try:
        conn.autocommit = True
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            yield cur
    except Exception:
        # conexão quebrada (banco reiniciou etc.) não volta para o pool
        pool.putconn(conn, close=bool(conn.closed))
        raise
    else:
        pool.putconn(conn)


@contextmanager
def transaction():
    """Cursor dentro de uma transação: tudo é gravado junto ou nada é gravado."""
    pool = _get_pool()
    conn = pool.getconn()
    try:
        conn.autocommit = False
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            yield cur
        conn.commit()
    except Exception:
        if not conn.closed:
            conn.rollback()
        pool.putconn(conn, close=bool(conn.closed))
        raise
    else:
        conn.autocommit = True
        pool.putconn(conn)


def init_db():
    """Cria/atualiza as tabelas (schema.sql é idempotente)."""
    with cursor() as cur:
        cur.execute(SCHEMA_FILE.read_text(encoding="utf-8"))


# =========================
# USUÁRIOS
# =========================

def create_user(name, email, password_hash):
    with cursor() as cur:
        cur.execute(
            """INSERT INTO users (name, email, password_hash)
               VALUES (%s, %s, %s) RETURNING id, name, email""",
            (name, email.lower(), password_hash),
        )
        return cur.fetchone()


def get_user_by_email(email):
    with cursor() as cur:
        cur.execute("SELECT * FROM users WHERE email = %s", (email.lower(),))
        return cur.fetchone()


def get_user_by_id(user_id):
    with cursor() as cur:
        cur.execute("SELECT id, name, email FROM users WHERE id = %s", (user_id,))
        return cur.fetchone()


# =========================
# HISTÓRICO DO CHAT
# =========================

def create_conversation(user_id, title="Nova conversa"):
    with cursor() as cur:
        cur.execute(
            "INSERT INTO chat_conversations (user_id, title) VALUES (%s, %s) RETURNING id, title",
            (user_id, title[:80]),
        )
        return cur.fetchone()


def list_conversations(user_id):
    """Conversas do usuário, mais recentes primeiro (com a contagem de mensagens)."""
    with cursor() as cur:
        cur.execute(
            """SELECT c.id, c.title, c.updated_at,
                      (SELECT count(*) FROM messages m WHERE m.conversation_id = c.id) AS total
               FROM chat_conversations c
               WHERE c.user_id = %s
               ORDER BY c.updated_at DESC, c.id DESC""",
            (user_id,),
        )
        return cur.fetchall()


def get_conversation(user_id, conversation_id):
    with cursor() as cur:
        cur.execute(
            "SELECT * FROM chat_conversations WHERE id = %s AND user_id = %s",
            (conversation_id, user_id),
        )
        return cur.fetchone()


def rename_conversation(user_id, conversation_id, title):
    with cursor() as cur:
        cur.execute(
            "UPDATE chat_conversations SET title = %s WHERE id = %s AND user_id = %s",
            (title[:80], conversation_id, user_id),
        )
        return cur.rowcount == 1


def delete_conversation(user_id, conversation_id):
    """Exclui a conversa e as mensagens dela (CASCADE)."""
    with cursor() as cur:
        cur.execute(
            "DELETE FROM chat_conversations WHERE id = %s AND user_id = %s",
            (conversation_id, user_id),
        )
        return cur.rowcount == 1


def save_message(user_id, conversation_id, role, content):
    with transaction() as cur:
        cur.execute(
            "INSERT INTO messages (user_id, conversation_id, role, content) VALUES (%s, %s, %s, %s)",
            (user_id, conversation_id, role, content),
        )
        cur.execute(
            "UPDATE chat_conversations SET updated_at = NOW() WHERE id = %s AND user_id = %s",
            (conversation_id, user_id),
        )


def get_history(user_id, conversation_id, limit=20):
    """Últimas mensagens de UMA conversa (é o contexto enviado à IA)."""
    with cursor() as cur:
        cur.execute(
            """SELECT role, content, created_at FROM messages
               WHERE user_id = %s AND conversation_id = %s
               ORDER BY id DESC LIMIT %s""",
            (user_id, conversation_id, limit),
        )
        rows = cur.fetchall()
    rows.reverse()
    return rows


# =========================
# TRANSAÇÕES
# =========================

TRANSACTION_FIELDS = ("type", "description", "category", "amount", "date", "status")


def list_transactions(user_id, start, end):
    """Transações com start <= date < end, mais recentes primeiro."""
    with cursor() as cur:
        cur.execute(
            """SELECT * FROM transactions
               WHERE user_id = %s AND date >= %s AND date < %s
               ORDER BY date DESC, id DESC""",
            (user_id, start, end),
        )
        return cur.fetchall()


def monthly_totals(user_id, start, end):
    """Totais de receitas e gastos por mês (chave 'YYYY-MM') no intervalo."""
    with cursor() as cur:
        cur.execute(
            """SELECT to_char(date, 'YYYY-MM') AS month,
                      COALESCE(SUM(amount) FILTER (WHERE type = 'income'), 0)  AS income,
                      COALESCE(SUM(amount) FILTER (WHERE type = 'expense'), 0) AS expense
               FROM transactions
               WHERE user_id = %s AND date >= %s AND date < %s
               GROUP BY 1""",
            (user_id, start, end),
        )
        return {r["month"]: r for r in cur.fetchall()}


def get_transaction(user_id, tx_id):
    with cursor() as cur:
        cur.execute(
            "SELECT * FROM transactions WHERE id = %s AND user_id = %s",
            (tx_id, user_id),
        )
        return cur.fetchone()


def create_transaction(user_id, data):
    with cursor() as cur:
        cur.execute(
            """INSERT INTO transactions (user_id, type, description, category, amount, date, status)
               VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id""",
            (user_id, *(data[f] for f in TRANSACTION_FIELDS)),
        )
        return cur.fetchone()["id"]


def update_transaction(user_id, tx_id, data):
    with cursor() as cur:
        cur.execute(
            """UPDATE transactions
               SET type = %s, description = %s, category = %s, amount = %s, date = %s, status = %s
               WHERE id = %s AND user_id = %s""",
            (*(data[f] for f in TRANSACTION_FIELDS), tx_id, user_id),
        )
        return cur.rowcount == 1


def delete_transaction(user_id, tx_id):
    with cursor() as cur:
        cur.execute(
            "DELETE FROM transactions WHERE id = %s AND user_id = %s",
            (tx_id, user_id),
        )
        return cur.rowcount == 1


# =========================
# EMPRESA
# =========================

def get_company(user_id):
    with cursor() as cur:
        cur.execute("SELECT * FROM companies WHERE user_id = %s", (user_id,))
        return cur.fetchone()


def save_company(user_id, cnpj, razao_social):
    with cursor() as cur:
        cur.execute(
            """INSERT INTO companies (user_id, cnpj, razao_social) VALUES (%s, %s, %s)
               ON CONFLICT (user_id) DO UPDATE
               SET cnpj = EXCLUDED.cnpj, razao_social = EXCLUDED.razao_social""",
            (user_id, cnpj, razao_social),
        )


# =========================
# NF-e
# =========================

NFE_COLUMNS = (
    "chave", "versao", "numero", "serie", "emissao", "natureza", "direcao", "ambiente",
    "emit_doc", "emit_nome", "emit_uf", "dest_doc", "dest_nome", "dest_uf",
    "v_produtos", "v_desconto", "v_frete", "v_icms", "v_st", "v_ipi", "v_pis", "v_cofins",
    "v_ibs", "v_cbs", "v_total", "protocolo", "status_sefaz", "avisos", "xml",
)

ITEM_COLUMNS = (
    "n_item", "codigo", "descricao", "ncm", "cfop", "unidade", "quantidade", "valor_unitario",
    "valor_total", "icms_cst", "icms_valor", "ipi_valor", "pis_valor", "cofins_valor",
    "ibs_valor", "cbs_valor",
)


def nfe_exists(user_id, chave):
    with cursor() as cur:
        cur.execute("SELECT id FROM nfe WHERE user_id = %s AND chave = %s", (user_id, chave))
        row = cur.fetchone()
        return row["id"] if row else None


def insert_nfe(user_id, header, items, duplicatas):
    """Grava cabeçalho, itens e parcelas numa única transação. Retorna o id."""
    with transaction() as cur:
        cols = ", ".join(("user_id",) + NFE_COLUMNS)
        marks = ", ".join(["%s"] * (len(NFE_COLUMNS) + 1))
        cur.execute(
            f"INSERT INTO nfe ({cols}) VALUES ({marks}) RETURNING id",
            (user_id, *(header[c] for c in NFE_COLUMNS)),
        )
        nfe_id = cur.fetchone()["id"]

        if items:
            icols = ", ".join(("nfe_id",) + ITEM_COLUMNS)
            imarks = ", ".join(["%s"] * (len(ITEM_COLUMNS) + 1))
            cur.executemany(
                f"INSERT INTO nfe_items ({icols}) VALUES ({imarks})",
                [(nfe_id, *(it[c] for c in ITEM_COLUMNS)) for it in items],
            )

        if duplicatas:
            cur.executemany(
                "INSERT INTO nfe_duplicatas (nfe_id, numero, vencimento, valor) VALUES (%s, %s, %s, %s)",
                [(nfe_id, d["numero"], d["vencimento"], d["valor"]) for d in duplicatas],
            )
        return nfe_id


def list_nfe(user_id, start, end, direcao=None):
    """Notas emitidas em start <= emissão < end (datas locais)."""
    sql = """SELECT n.id, n.chave, n.numero, n.serie, n.emissao, n.direcao, n.ambiente,
                    n.emit_nome, n.emit_doc, n.dest_nome, n.dest_doc, n.v_total, n.v_icms,
                    n.v_ipi, n.v_pis, n.v_cofins, n.v_ibs, n.v_cbs, n.v_st,
                    n.protocolo, n.avisos,
                    EXISTS (SELECT 1 FROM transactions t WHERE t.nfe_id = n.id) AS tem_lancamentos
             FROM nfe n
             WHERE n.user_id = %s AND n.emissao >= %s AND n.emissao < %s"""
    params = [user_id, start, end]
    if direcao in ("entrada", "saida"):
        sql += " AND n.direcao = %s"
        params.append(direcao)
    sql += " ORDER BY n.emissao DESC, n.id DESC"
    with cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def get_nfe(user_id, nfe_id):
    with cursor() as cur:
        cur.execute(
            """SELECT n.*, EXISTS (SELECT 1 FROM transactions t WHERE t.nfe_id = n.id) AS tem_lancamentos
               FROM nfe n WHERE n.id = %s AND n.user_id = %s""",
            (nfe_id, user_id),
        )
        nfe = cur.fetchone()
        if not nfe:
            return None
        cur.execute("SELECT * FROM nfe_items WHERE nfe_id = %s ORDER BY n_item", (nfe_id,))
        nfe["items"] = cur.fetchall()
        cur.execute("SELECT * FROM nfe_duplicatas WHERE nfe_id = %s ORDER BY vencimento, id", (nfe_id,))
        nfe["duplicatas"] = cur.fetchall()
        cur.execute(
            "SELECT * FROM transactions WHERE nfe_id = %s AND user_id = %s ORDER BY date, id",
            (nfe_id, user_id),
        )
        nfe["lancamentos"] = cur.fetchall()
        return nfe


def delete_nfe(user_id, nfe_id):
    """Exclui a nota (itens, parcelas e lançamentos gerados saem junto, via CASCADE)."""
    with cursor() as cur:
        cur.execute("DELETE FROM nfe WHERE id = %s AND user_id = %s", (nfe_id, user_id))
        return cur.rowcount == 1


def create_nfe_launches(user_id, nfe_id, launches):
    """Cria os lançamentos de uma nota, se ela ainda não tiver nenhum. Retorna quantos criou."""
    with transaction() as cur:
        # trava a nota para dois cliques simultâneos não gerarem em dobro
        cur.execute("SELECT id FROM nfe WHERE id = %s AND user_id = %s FOR UPDATE", (nfe_id, user_id))
        if not cur.fetchone():
            return 0
        cur.execute("SELECT 1 FROM transactions WHERE nfe_id = %s LIMIT 1", (nfe_id,))
        if cur.fetchone():
            return 0
        cur.executemany(
            """INSERT INTO transactions (user_id, type, description, category, amount, date, status, nfe_id)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            [(user_id, l["type"], l["description"], l["category"], l["amount"], l["date"], l["status"], nfe_id)
             for l in launches],
        )
        return len(launches)


# =========================
# CONSULTORIA (contadores afiliados)
# =========================

def list_accountants():
    with cursor() as cur:
        cur.execute("SELECT * FROM accountants ORDER BY available DESC, rating DESC NULLS LAST, name")
        return cur.fetchall()


def get_accountant(accountant_id):
    with cursor() as cur:
        cur.execute("SELECT * FROM accountants WHERE id = %s", (accountant_id,))
        return cur.fetchone()


def get_accountant_by_user(user_id):
    with cursor() as cur:
        cur.execute("SELECT * FROM accountants WHERE user_id = %s", (user_id,))
        return cur.fetchone()


def get_or_create_consultation(user_id, accountant_id):
    with cursor() as cur:
        cur.execute(
            """INSERT INTO consultations (user_id, accountant_id) VALUES (%s, %s)
               ON CONFLICT (user_id, accountant_id) DO UPDATE SET user_id = EXCLUDED.user_id
               RETURNING id""",
            (user_id, accountant_id),
        )
        return cur.fetchone()["id"]


def get_consultation(consultation_id):
    """Conversa com dados do cliente e do contador (permissão é checada na rota)."""
    with cursor() as cur:
        cur.execute(
            """SELECT c.*, u.name AS client_name, u.email AS client_email,
                      a.name AS acc_name, a.crc AS acc_crc, a.user_id AS acc_user_id,
                      a.specialties AS acc_specialties, a.available AS acc_available,
                      co.razao_social AS client_company
               FROM consultations c
               JOIN users u ON u.id = c.user_id
               JOIN accountants a ON a.id = c.accountant_id
               LEFT JOIN companies co ON co.user_id = c.user_id
               WHERE c.id = %s""",
            (consultation_id,),
        )
        return cur.fetchone()


def _threads(where, param, other_sender):
    with cursor() as cur:
        cur.execute(
            f"""SELECT c.id, c.updated_at, c.accountant_id, a.name AS acc_name, a.crc AS acc_crc,
                       u.name AS client_name, co.razao_social AS client_company,
                       lm.content AS last_content, lm.sender AS last_sender, lm.created_at AS last_at,
                       (SELECT count(*) FROM consultation_messages m
                         WHERE m.consultation_id = c.id AND m.sender = %s AND m.read_at IS NULL) AS unread
                FROM consultations c
                JOIN accountants a ON a.id = c.accountant_id
                JOIN users u ON u.id = c.user_id
                LEFT JOIN companies co ON co.user_id = c.user_id
                LEFT JOIN LATERAL (SELECT content, sender, created_at FROM consultation_messages m
                                   WHERE m.consultation_id = c.id ORDER BY m.id DESC LIMIT 1) lm ON TRUE
                WHERE {where} AND lm.content IS NOT NULL
                ORDER BY c.updated_at DESC""",
            (other_sender, param),
        )
        return cur.fetchall()


def list_client_threads(user_id):
    """Conversas do cliente (não lidas = mensagens do contador)."""
    return _threads("c.user_id = %s", user_id, "contador")


def list_accountant_threads(accountant_id):
    """Caixa de atendimentos do contador (não lidas = mensagens do cliente)."""
    return _threads("c.accountant_id = %s", accountant_id, "cliente")


def list_consultation_messages(consultation_id, after_id=0):
    with cursor() as cur:
        cur.execute(
            """SELECT id, sender, content, created_at FROM consultation_messages
               WHERE consultation_id = %s AND id > %s ORDER BY id""",
            (consultation_id, after_id),
        )
        return cur.fetchall()


def add_consultation_message(consultation_id, sender, content):
    with transaction() as cur:
        cur.execute(
            """INSERT INTO consultation_messages (consultation_id, sender, content)
               VALUES (%s, %s, %s) RETURNING id, sender, content, created_at""",
            (consultation_id, sender, content),
        )
        msg = cur.fetchone()
        cur.execute("UPDATE consultations SET updated_at = NOW() WHERE id = %s", (consultation_id,))
        return msg


def mark_consultation_read(consultation_id, reader):
    """Marca como lidas as mensagens do outro lado."""
    other = "contador" if reader == "cliente" else "cliente"
    with cursor() as cur:
        cur.execute(
            """UPDATE consultation_messages SET read_at = NOW()
               WHERE consultation_id = %s AND sender = %s AND read_at IS NULL""",
            (consultation_id, other),
        )
