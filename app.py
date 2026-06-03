from flask import Flask, render_template, request, jsonify
from openai import OpenAI
from dotenv import load_dotenv
import os

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

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
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
        },
        {
            "role": "user",
            "content": user_message
        }
    ]
    )

    reply = response.choices[0].message.content

    return jsonify({
        "reply": reply
    })

if __name__ == "__main__":
    app.run(debug=True)