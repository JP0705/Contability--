"""Autenticação por sessão: cadastro, login, logout e proteção das rotas."""
import re

import psycopg2
from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

import db

bp = Blueprint("auth", __name__)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MIN_PASSWORD = 8

# endpoints acessíveis sem login
PUBLIC_ENDPOINTS = {"auth.login", "auth.register", "static"}


def init_app(app):
    app.register_blueprint(bp)

    @app.before_request
    def load_user_and_require_login():
        g.user = None
        user_id = session.get("user_id")
        if user_id is not None:
            try:
                g.user = db.get_user_by_id(user_id)
            except psycopg2.Error:
                app.logger.exception("Banco indisponível ao carregar usuário")
                return render_template("db_error.html"), 503
            if g.user is None:  # usuário removido
                session.clear()

        if g.user is None and request.endpoint not in PUBLIC_ENDPOINTS:
            # chamadas de API recebem 401 em vez de redirecionamento
            if (request.is_json or request.path.startswith("/chat") or request.path == "/new-chat"
                    or request.path.endswith("/mensagens")):
                return {"error": "Sessão expirada. Faça login novamente."}, 401
            target = request.full_path.rstrip("?")
            return redirect(url_for("auth.login", next=None if target == "/" else target))


def _safe_next(target):
    """Só aceita redirecionamento interno (evita open redirect)."""
    if target and target.startswith("/") and not target.startswith("//"):
        return target
    return url_for("home")


def _login(user):
    session.clear()
    session["user_id"] = user["id"]
    session.permanent = True


@bp.route("/login", methods=["GET", "POST"])
def login():
    if g.user:
        return redirect(url_for("home"))

    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        try:
            user = db.get_user_by_email(email) if email else None
        except psycopg2.Error:
            flash("Banco de dados indisponível. Tente novamente em instantes.", "danger")
            return render_template("login.html", email=email), 503

        if user and check_password_hash(user["password_hash"], password):
            _login(user)
            return redirect(_safe_next(request.args.get("next")))

        flash("E-mail ou senha inválidos.", "danger")
        return render_template("login.html", email=email), 401

    return render_template("login.html")


@bp.route("/cadastro", methods=["GET", "POST"])
def register():
    if g.user:
        return redirect(url_for("home"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")

        errors = []
        if not name:
            errors.append("Informe seu nome.")
        if not EMAIL_RE.match(email):
            errors.append("Informe um e-mail válido.")
        if len(password) < MIN_PASSWORD:
            errors.append(f"A senha deve ter pelo menos {MIN_PASSWORD} caracteres.")
        if password != confirm:
            errors.append("As senhas não conferem.")

        if not errors:
            try:
                user = db.create_user(name, email, generate_password_hash(password))
            except psycopg2.errors.UniqueViolation:
                errors.append("Já existe uma conta com este e-mail.")
            except psycopg2.Error:
                errors.append("Banco de dados indisponível. Tente novamente em instantes.")
            else:
                _login(user)
                flash(f"Bem-vindo(a), {user['name']}!", "success")
                return redirect(url_for("home"))

        for e in errors:
            flash(e, "danger")
        return render_template("register.html", name=name, email=email), 400

    return render_template("register.html")


@bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("Você saiu da sua conta.", "success")
    return redirect(url_for("auth.login"))
