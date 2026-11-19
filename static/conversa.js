// Conversa cliente x contador: envio de mensagens e atualização automática.
// Mensagens são texto puro: sempre inseridas com textContent (nunca innerHTML).

const chat = document.getElementById("consult-chat");
const body = document.getElementById("consult-body");
const form = document.getElementById("consult-form");
const input = document.getElementById("consult-input");
const intro = document.getElementById("consult-intro");
const live = document.getElementById("live-status");

const role = chat.dataset.role;          // "cliente" ou "contador"
const url = chat.dataset.url;
let lastId = Number(chat.dataset.lastId || 0);
let lastDate = null;

const POLL_MS = 4000;
const seen = new Set();                  // ids já desenhados (evita duplicar após envio + poll)

function today(){
    return new Date().toLocaleDateString("pt-BR");
}

function addDaySeparator(date){
    if(date === lastDate) return;
    lastDate = date;
    const sep = document.createElement("div");
    sep.className = "day-sep";
    const span = document.createElement("span");
    span.textContent = date === today() ? "Hoje" : date;
    sep.appendChild(span);
    body.appendChild(sep);
}

function render(msg, {pending = false} = {}){

    if(msg.id && seen.has(msg.id)) return null;
    if(msg.id) seen.add(msg.id);

    if(intro) intro.hidden = true;
    addDaySeparator(msg.date || today());

    const mine = msg.sender === role;
    const div = document.createElement("div");
    div.className = "message " + (mine ? "user" : "bot") + (pending ? " pending" : "");

    if(!mine){
        const who = document.createElement("span");
        who.className = "sender-name";
        who.textContent = msg.sender === "contador" ? "Contador" : "Cliente";
        div.appendChild(who);
    }

    const text = document.createElement("div");
    text.textContent = msg.content;

    const small = document.createElement("small");
    small.textContent = msg.time || "enviando...";

    div.append(text, small);
    body.appendChild(div);

    // só rola para o fim se o usuário já estava perto do fim
    const nearBottom = body.scrollHeight - body.scrollTop - body.clientHeight < 160;
    if(mine || nearBottom) body.scrollTop = body.scrollHeight;
    return div;
}

// mensagens que vieram com a página
JSON.parse(document.getElementById("consult-messages").textContent || "[]").forEach(m => render(m));
body.scrollTop = body.scrollHeight;

async function poll(){
    try{
        const r = await fetch(`${url}?depois=${lastId}`, {headers: {"Accept": "application/json"}});
        if(r.status === 401){ window.location.href = "/login"; return; }
        if(!r.ok) throw new Error(r.status);
        const data = await r.json();
        data.messages.forEach(m => {
            render(m);
            lastId = Math.max(lastId, m.id);
        });
        live.classList.remove("offline");
        live.title = "Atualizando automaticamente";
    }catch(e){
        live.classList.add("offline");
        live.title = "Sem conexão — tentando novamente";
    }
}

let timer = setInterval(poll, POLL_MS);

// pausa quando a aba está escondida, retoma (e atualiza) ao voltar
document.addEventListener("visibilitychange", () => {
    clearInterval(timer);
    if(!document.hidden){
        poll();
        timer = setInterval(poll, POLL_MS);
    }
});

async function send(){

    const content = input.value.trim();
    if(!content) return;

    input.value = "";
    autosize();

    const temp = render({sender: role, content, date: today()}, {pending: true});

    try{
        const r = await fetch(url, {
            method: "POST",
            headers: {"Content-Type": "application/json", "Accept": "application/json"},
            body: JSON.stringify({content})
        });
        if(r.status === 401){ window.location.href = "/login"; return; }
        const data = await r.json();
        if(!r.ok) throw new Error(data.error || "Falha ao enviar.");

        // troca a bolha provisória pela definitiva
        temp.remove();
        render(data.message);
        lastId = Math.max(lastId, data.message.id);
    }catch(e){
        temp.classList.remove("pending");
        temp.classList.add("failed");
        temp.querySelector("small").textContent = "não enviada — " + e.message;
        input.value = content;
    }
}

form.addEventListener("submit", (e) => { e.preventDefault(); send(); });

input.addEventListener("keydown", (e) => {
    if(e.key === "Enter" && !e.shiftKey && !e.isComposing){
        e.preventDefault();
        send();
    }
});

// textarea cresce conforme o texto
function autosize(){
    input.style.height = "auto";
    input.style.height = Math.min(input.scrollHeight, 140) + "px";
}
input.addEventListener("input", autosize);
input.focus();
