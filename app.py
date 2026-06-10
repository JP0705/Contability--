from flask import Flask, render_template, request, jsonify
from openai import OpenAI
from dotenv import load_dotenv
import os

from db import get_history, save_message, clear_history

load_dotenv()

app = Flask(__name__)

client = OpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1"
)

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():

    data = request.get_json()

    user_message = data["message"]

    history = get_history(limit=20)

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

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=messages
    )

    reply = response.choices[0].message.content

    save_message("user", user_message)
    save_message("assistant", reply)

    return {
        "reply": reply
    }
    
@app.route("/new-chat", methods=["POST"])
def new_chat():

    print("ROTA NEW-CHAT CHAMADA")

    clear_history()

    return {
        "success": True
    }
    
if __name__ == "__main__":
    app.run(debug=True)