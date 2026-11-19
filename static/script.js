const sendBtn = document.getElementById("send-btn");
const userInput = document.getElementById("user-input");
const chatBody = document.getElementById("chat-body");

let typingIndicator = null;

const newChatBtn = document.getElementById("new-chat-btn");

function showTypingIndicator(){

    typingIndicator = document.createElement("div");

    typingIndicator.classList.add("typing-indicator");

    typingIndicator.innerHTML = `
        Contability está analisando
        <div class="typing-dots">
            <span>.</span>
            <span>.</span>
            <span>.</span>
        </div>
    `;

    chatBody.appendChild(typingIndicator);

    chatBody.scrollTop = chatBody.scrollHeight;
}

function removeTypingIndicator(){

    if(typingIndicator){
        typingIndicator.remove();
        typingIndicator = null;
    }
}

// Markdown da IA -> HTML seguro. A resposta do modelo não é confiável (pode
// repetir HTML/scripts vindos do próprio usuário ou de prompt injection), então
// todo HTML gerado passa pelo DOMPurify antes de entrar no DOM.
function renderMarkdown(text){

    if(typeof DOMPurify === "undefined" || typeof marked === "undefined"){
        // biblioteca não carregou (CDN fora do ar): mostra como texto puro
        const tmp = document.createElement("div");
        tmp.textContent = text;
        return tmp.innerHTML.replace(/\n/g, "<br>");
    }

    return DOMPurify.sanitize(marked.parse(text), {
        USE_PROFILE: { html: true },   // sem SVG/MathML
        FORBID_TAGS: ["style", "form", "input", "button", "textarea", "select"],
        FORBID_ATTR: ["style"]
    });
}

// links das respostas abrem em nova aba, sem dar acesso a esta página
if(typeof DOMPurify !== "undefined"){
    DOMPurify.addHook("afterSanitizeAttributes", (node) => {
        if(node.tagName === "A" && node.hasAttribute("href")){
            node.setAttribute("target", "_blank");
            node.setAttribute("rel", "noopener noreferrer");
        }
    });
}

function addMessage(text, sender = "bot", time = null) {

    const div = document.createElement("div");

    div.classList.add("message");

    time = time || new Date().toLocaleTimeString([], {
        hour: '2-digit',
        minute: '2-digit'
    });

    if(sender === "user"){

        div.classList.add("user");

        // textContent evita injeção de HTML vindo do próprio usuário
        const content = document.createElement("div");
        content.textContent = text;

        const small = document.createElement("small");
        small.textContent = time;

        div.append(content, small);

    }else{

        div.classList.add("bot");

        const content = document.createElement("div");
        content.classList.add("message-content");
        content.innerHTML = renderMarkdown(text);

        const small = document.createElement("small");
        small.textContent = time;

        div.append(content, small);
    }

    chatBody.appendChild(div);
    chatBody.scrollTop = chatBody.scrollHeight;
}

async function sendMessage(){

    const message = userInput.value.trim();

    if(!message) return;

    addMessage(message, "user");

    userInput.value = "";

    showTypingIndicator();

    try{

        const response = await fetch("/chat", {
            method:"POST",
            headers:{
                "Content-Type":"application/json"
            },
            body: JSON.stringify({
                message: message
            })
        });

        if(response.status === 401){
            window.location.href = "/login";
            return;
        }

        const data = await response.json();

        removeTypingIndicator();

        addMessage(response.ok ? data.reply : (data.error || "Erro ao conectar com a IA."));

    }catch(error){

        removeTypingIndicator();
        
        addMessage("Erro ao conectar com a IA.");
    }
}

sendBtn.addEventListener("click", sendMessage);

userInput.addEventListener("keydown", (e) => {
    if(e.key === "Enter" && !e.isComposing){
        sendMessage();
    }
});

async function newChat() {

    try {

        const response = await fetch("/new-chat", {
            method: "POST"
        });

        if(response.status === 401){
            window.location.href = "/login";
            return;
        }

        if(!response.ok){
            throw new Error("falha ao limpar histórico");
        }

        chatBody.innerHTML = "";

        // sem indentação: em Markdown, linhas recuadas viram bloco de código
        addMessage([
            "👋 Olá!",
            "Sou o Contability, seu assistente contábil.",
            "Como posso ajudar você hoje?"
        ].join("\n\n"));

    } catch (error) {

        addMessage("Erro ao iniciar uma nova consulta.");
    }
}

newChatBtn.addEventListener("click", newChat);

// histórico salvo do usuário (injetado pelo servidor em index.html)
function loadHistory(){

    const el = document.getElementById("chat-history");

    if(!el) return;

    const history = JSON.parse(el.textContent || "[]");

    history.forEach(m => {
        addMessage(m.content, m.role === "user" ? "user" : "bot", m.time);
    });
}

loadHistory();

// pergunta sugerida vinda de outra página (ex.: "Em breve" → /?q=...):
// preenche o campo, sem enviar, e limpa a URL
const suggested = new URLSearchParams(window.location.search).get("q");
if(suggested){
    userInput.value = suggested.slice(0, 500);
    userInput.focus();
    history.replaceState(null, "", window.location.pathname);
}