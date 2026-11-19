"""Ponto de entrada do Contability.

    py app.py

A aplicação fica no pacote contability/ (create_app em contability/__init__.py).
"""
import os

from contability import create_app, db

app = create_app()


if __name__ == "__main__":
    try:
        db.init_db()  # cria/atualiza as tabelas (schema.sql é idempotente)
    except Exception as exc:
        app.logger.warning("Banco indisponível na inicialização: %s", exc)

    app.run(debug=os.getenv("FLASK_DEBUG", "1") == "1")
