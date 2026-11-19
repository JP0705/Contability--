"""Consultoria com contadores afiliados: diretório de especialistas,
conversa cliente x contador e caixa de atendimentos do contador.

Permissões: o cliente só acessa as próprias conversas; o contador só as
conversas em que ele é o contador (accountants.user_id = usuário logado).
Mensagens são texto puro (renderizadas com textContent no navegador).
"""
from flask import Blueprint, abort, flash, g, jsonify, redirect, render_template, request, url_for

from .. import db

bp = Blueprint("consultoria", __name__)

MAX_MESSAGE = 2000
AVATAR_COLORS = ["#b91c1c", "#9a3412", "#7c2d12", "#be123c", "#86198f", "#1e3a8a", "#065f46", "#334155"]


def init_app(app):
    app.register_blueprint(bp)

    @app.template_filter("initials")
    def initials(name):
        parts = [p for p in (name or "").split() if p[:1].isalpha()]
        return ((parts[0][0] + (parts[-1][0] if len(parts) > 1 else "")) if parts else "?").upper()

    @app.template_filter("avatar_color")
    def avatar_color(seed):
        return AVATAR_COLORS[int(seed or 0) % len(AVATAR_COLORS)]

    @app.context_processor
    def accountant_context():
        """Disponibiliza o perfil de contador do usuário logado (para o menu)."""
        acc = None
        if getattr(g, "user", None):
            if "accountant" not in g:
                try:
                    g.accountant = db.get_accountant_by_user(g.user["id"])
                except Exception:
                    g.accountant = None
            acc = g.accountant
        return {"current_accountant": acc}


def _current_accountant():
    if "accountant" not in g:
        g.accountant = db.get_accountant_by_user(g.user["id"])
    return g.accountant


def _load_thread(consultation_id):
    """Conversa + papel do usuário logado nela ('cliente' ou 'contador'); 404 se não tiver acesso."""
    conv = db.get_consultation(consultation_id)
    if not conv:
        abort(404)
    if conv["user_id"] == g.user["id"]:
        return conv, "cliente"
    if conv["acc_user_id"] is not None and conv["acc_user_id"] == g.user["id"]:
        return conv, "contador"
    abort(404)


def _serialize(msgs):
    return [{"id": m["id"], "sender": m["sender"], "content": m["content"],
             "time": m["created_at"].strftime("%H:%M"),
             "date": m["created_at"].strftime("%d/%m/%Y")} for m in msgs]


# =========================
# CLIENTE
# =========================

@bp.route("/especialistas/")
def directory():
    accountants = db.list_accountants()
    threads = {t["accountant_id"]: t for t in db.list_client_threads(g.user["id"])}
    specialties = sorted({s for a in accountants for s in a["specialties"]})
    return render_template("consultoria/especialistas.html", accountants=accountants,
                           threads=threads, specialties=specialties)


@bp.route("/especialistas/<int:accountant_id>/conversar")
def start(accountant_id):
    acc = db.get_accountant(accountant_id)
    if not acc:
        abort(404)
    if acc["user_id"] == g.user["id"]:
        flash("Você não pode abrir uma consultoria com você mesmo.", "danger")
        return redirect(url_for("consultoria.directory"))
    cid = db.get_or_create_consultation(g.user["id"], accountant_id)
    return redirect(url_for("consultoria.thread", consultation_id=cid))


# =========================
# CONTADOR
# =========================

@bp.route("/atendimentos/")
def inbox():
    acc = _current_accountant()
    if not acc:
        abort(404)
    return render_template("consultoria/atendimentos.html", accountant=acc,
                           threads=db.list_accountant_threads(acc["id"]))


# =========================
# CONVERSA (os dois lados)
# =========================

@bp.route("/conversas/<int:consultation_id>")
def thread(consultation_id):
    conv, role = _load_thread(consultation_id)
    db.mark_consultation_read(consultation_id, role)
    messages = db.list_consultation_messages(consultation_id)
    cliente = role == "cliente"
    return render_template("consultoria/conversa.html", conv=conv, role=role, cliente=cliente,
                           other_name=conv["acc_name"] if cliente else conv["client_name"],
                           other_seed=conv["accountant_id"] if cliente else conv["user_id"],
                           messages=_serialize(messages),
                           last_id=messages[-1]["id"] if messages else 0)


@bp.route("/conversas/<int:consultation_id>/mensagens", methods=["GET"])
def poll(consultation_id):
    """Mensagens novas (id > depois). Usado pela página a cada poucos segundos."""
    _, role = _load_thread(consultation_id)
    after = request.args.get("depois", default=0, type=int)
    msgs = db.list_consultation_messages(consultation_id, after)
    if any(m["sender"] != role for m in msgs):
        db.mark_consultation_read(consultation_id, role)
    return jsonify({"messages": _serialize(msgs)})


@bp.route("/conversas/<int:consultation_id>/mensagens", methods=["POST"])
def send(consultation_id):
    _, role = _load_thread(consultation_id)
    data = request.get_json(silent=True) or {}
    content = (data.get("content") or "").strip()
    if not content:
        return jsonify({"error": "Mensagem vazia."}), 400
    if len(content) > MAX_MESSAGE:
        return jsonify({"error": f"Mensagem muito longa (máx. {MAX_MESSAGE} caracteres)."}), 400
    msg = db.add_consultation_message(consultation_id, role, content)
    return jsonify({"message": _serialize([msg])[0]}), 201
