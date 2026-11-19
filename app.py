import os
import secrets
from datetime import timedelta

from dotenv import load_dotenv
from flask import Flask, g, jsonify, render_template, request
from openai import OpenAI

import auth
import consultoria
import db
import empresa
import gastos
import notas
import wip

load_dotenv()

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

auth.init_app(app)
gastos.init_app(app)
empresa.init_app(app)
notas.init_app(app)
consultoria.init_app(app)
wip.init_app(app)

MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")

client = OpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1",
    timeout=60,      # o padrão (10 min) deixava o chat "analisando" indefinidamente
    max_retries=1,
)

@app.route("/")
def home():
    try:
        history = db.get_history(g.user["id"], limit=50)
    except Exception as exc:
        app.logger.warning("Histórico indisponível: %s", exc)
        history = []

    history = [
        {"role": m["role"], "content": m["content"], "time": m["created_at"].strftime("%H:%M")}
        for m in history
    ]

    try:
        summary = gastos.month_summary(g.user["id"])
    except Exception as exc:
        app.logger.warning("Resumo financeiro indisponível: %s", exc)
        summary = None

    return render_template("index.html", history=history, summary=summary)

@app.route("/chat", methods=["POST"])
def chat():

    data = request.get_json(silent=True) or {}

    user_message = (data.get("message") or "").strip()

    if not user_message:
        return jsonify({"error": "Mensagem vazia."}), 400

    try:
        history = [
            {"role": m["role"], "content": m["content"]}
            for m in db.get_history(g.user["id"], limit=20)
        ]
    except Exception as exc:
        app.logger.warning("Histórico indisponível (banco fora do ar?): %s", exc)
        history = []

    messages = [
        {
            "role": "system",
            "content": """
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
        }
    ]

    messages.extend(history)

    messages.append({
        "role": "user",
        "content": user_message
    })

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages
        )
    except Exception as exc:
        app.logger.error("Falha na chamada à Groq: %s", exc)
        return jsonify({"error": "Não foi possível obter resposta da IA."}), 502

    reply = response.choices[0].message.content

    try:
        db.save_message(g.user["id"], "user", user_message)
        db.save_message(g.user["id"], "assistant", reply)
    except Exception as exc:
        app.logger.warning("Não foi possível salvar o histórico: %s", exc)

    return jsonify({"reply": reply})


@app.route("/new-chat", methods=["POST"])
def new_chat():

    try:
        db.clear_history(g.user["id"])
    except Exception as exc:
        app.logger.warning("Não foi possível limpar o histórico: %s", exc)
        return jsonify({"success": False}), 503

    return jsonify({"success": True})


if __name__ == "__main__":
    try:
        db.init_db()
    except Exception as exc:
        app.logger.warning("Banco indisponível na inicialização: %s", exc)

    app.run(debug=os.getenv("FLASK_DEBUG", "1") == "1")
