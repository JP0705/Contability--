"""Contability — assistente contábil com IA.

Fábrica da aplicação: `create_app()` carrega o .env, configura a sessão e
registra os módulos de rotas (contability/routes/).
"""
import os
import secrets
from datetime import timedelta

from dotenv import load_dotenv
from flask import Flask


def create_app():
    load_dotenv()  # antes de importar as rotas (o cliente da IA lê o .env ao ser criado)

    app = Flask(__name__)

    secret_key = os.getenv("SECRET_KEY")
    if not secret_key:
        # sem SECRET_KEY no .env as sessões caem a cada reinício do servidor
        app.logger.warning("SECRET_KEY não definida no .env; usando chave temporária.")
        secret_key = secrets.token_hex(32)

    app.config.update(
        SECRET_KEY=secret_key,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",  # bloqueia POST vindo de outros sites
        PERMANENT_SESSION_LIFETIME=timedelta(days=7),
    )

    from .routes import auth, chat, consultoria, empresa, gastos, notas, wip

    # auth primeiro: o before_request dele protege todas as rotas
    for module in (auth, chat, gastos, empresa, notas, consultoria, wip):
        module.init_app(app)

    return app
