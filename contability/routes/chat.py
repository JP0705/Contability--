"""Chat com IA em conversas separadas (cada conversa tem seu próprio contexto).

/            conversa nova (só é criada no banco quando a primeira resposta chega)
/c/<id>      abre uma conversa
POST /chat   {message, conversation_id} -> envia à IA só o histórico daquela conversa
"""
import os
import re
from datetime import date

from flask import Blueprint, abort, current_app, g, jsonify, render_template, request, url_for
from openai import OpenAI

from .. import db
from . import gastos

bp = Blueprint("chat", __name__)

MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")

client = OpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1",
    timeout=60,      # o padrão (10 min) deixava o chat "analisando" indefinidamente
    max_retries=1,
)

SYSTEM_PROMPT = """
Você é o Contability, um assistente contábil e financeiro especializado em:

- Contabilidade empresarial
- Simples Nacional
- MEI
- Impostos
- Notas fiscais
- Fluxo de caixa
- Folha de pagamento
- Planejamento tributário

Sempre formate as respostas utilizando Markdown.

Utilize sempre que possível:

- títulos
- subtítulos
- listas
- tabelas
- destaques

Nunca responda em um único bloco de texto.

Organize a resposta de forma profissional e fácil de ler.
"""

HISTORY_LIMIT = 20      # mensagens da conversa enviadas como contexto à IA
TITLE_MAX = 60


def init_app(app):
    app.register_blueprint(bp)


def _title_from(message):
    """Título da conversa a partir da primeira pergunta."""
    text = re.sub(r"\s+", " ", message).strip()
    return text if len(text) <= TITLE_MAX else text[:TITLE_MAX - 1].rstrip() + "…"


def _group_label(d, today):
    delta = (today - d).days
    if delta <= 0:
        return "Hoje"
    if delta == 1:
        return "Ontem"
    if delta < 7:
        return "Últimos 7 dias"
    if delta < 30:
        return "Últimos 30 dias"
    return "Mais antigas"


def _conversation_groups(user_id):
    """Conversas agrupadas por data (Hoje, Ontem, ...) para a lista lateral."""
    today = date.today()
    groups = []
    for c in db.list_conversations(user_id):
        label = _group_label(c["updated_at"].date(), today)
        if not groups or groups[-1]["label"] != label:
            groups.append({"label": label, "items": []})
        groups[-1]["items"].append(c)
    return groups


def _chat_page(conversation=None):
    uid = g.user["id"]
    history, groups = [], []
    try:
        if conversation:
            history = [
                {"role": m["role"], "content": m["content"], "time": m["created_at"].strftime("%H:%M")}
                for m in db.get_history(uid, conversation["id"], limit=200)
            ]
        groups = _conversation_groups(uid)
    except Exception as exc:
        current_app.logger.warning("Conversas indisponíveis: %s", exc)

    try:
        summary = gastos.month_summary(uid)
    except Exception as exc:
        current_app.logger.warning("Resumo financeiro indisponível: %s", exc)
        summary = None

    return render_template("chat/index.html", history=history, summary=summary,
                           conversation=conversation, groups=groups)


@bp.route("/")
def home():
    """Conversa nova (em branco)."""
    return _chat_page()


@bp.route("/c/<int:conversation_id>")
def conversation(conversation_id):
    conv = db.get_conversation(g.user["id"], conversation_id)
    if not conv:
        abort(404)
    return _chat_page(conv)


@bp.route("/chat", methods=["POST"])
def send():
    data = request.get_json(silent=True) or {}
    user_message = (data.get("message") or "").strip()
    conversation_id = data.get("conversation_id")
    uid = g.user["id"]

    if not user_message:
        return jsonify({"error": "Mensagem vazia."}), 400

    # contexto = só as mensagens DESTA conversa
    conv, history = None, []
    if conversation_id:
        try:
            conv = db.get_conversation(uid, int(conversation_id))
        except (TypeError, ValueError):
            conv = None
        if not conv:
            return jsonify({"error": "Conversa não encontrada."}), 404
        try:
            history = [{"role": m["role"], "content": m["content"]}
                       for m in db.get_history(uid, conv["id"], limit=HISTORY_LIMIT)]
        except Exception as exc:
            current_app.logger.warning("Histórico indisponível (banco fora do ar?): %s", exc)

    messages = [{"role": "system", "content": SYSTEM_PROMPT}, *history,
                {"role": "user", "content": user_message}]

    try:
        response = client.chat.completions.create(model=MODEL, messages=messages)
    except Exception as exc:
        current_app.logger.error("Falha na chamada à Groq: %s", exc)
        return jsonify({"error": "Não foi possível obter resposta da IA."}), 502

    reply = response.choices[0].message.content
    created = False

    try:
        if not conv:
            conv = db.create_conversation(uid, _title_from(user_message))
            created = True
        db.save_message(uid, conv["id"], "user", user_message)
        db.save_message(uid, conv["id"], "assistant", reply)
    except Exception as exc:
        current_app.logger.warning("Não foi possível salvar o histórico: %s", exc)

    payload = {"reply": reply, "created": created}
    if conv:
        payload["conversation"] = {"id": conv["id"], "title": conv["title"],
                                   "url": url_for("chat.conversation", conversation_id=conv["id"])}
    return jsonify(payload)


@bp.route("/chat/<int:conversation_id>/renomear", methods=["POST"])
def rename(conversation_id):
    title = re.sub(r"\s+", " ", (request.get_json(silent=True) or {}).get("title") or "").strip()
    if not title:
        return jsonify({"error": "Informe um título."}), 400
    if not db.rename_conversation(g.user["id"], conversation_id, title):
        return jsonify({"error": "Conversa não encontrada."}), 404
    return jsonify({"title": title[:80]})


@bp.route("/chat/<int:conversation_id>/excluir", methods=["POST"])
def delete(conversation_id):
    if not db.delete_conversation(g.user["id"], conversation_id):
        return jsonify({"error": "Conversa não encontrada."}), 404
    return jsonify({"success": True})
