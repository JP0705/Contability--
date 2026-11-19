const sendBtn = document.getElementById("send-btn");
const userInput = document.getElementById("user-input");
const chatBody = document.getElementById("chat-body");

let typingIndicator = null;

// conversa atual (vazio = conversa nova, criada no servidor na primeira resposta)
const chatWrapper = document.getElementById("chat-wrapper");
let conversationId = chatWrapper.dataset.conversationId || null;

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
                message: message,
                conversation_id: conversationId
            })
        });

        if(response.status === 401){
            window.location.href = "/login";
            return;
        }

        const data = await response.json();

        removeTypingIndicator();

        addMessage(response.ok ? data.reply : (data.error || "Erro ao conectar com a IA."));

        if(response.ok && data.conversation){
            onConversationActivity(data.conversation, data.created);
        }

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

// =========================
// CONVERSAS (lista lateral)
// =========================

const lists = () => document.querySelectorAll("[data-conv-list]");
const titleEl = document.getElementById("chat-title");
const renameCurrentBtn = document.getElementById("rename-current");

function itemsFor(id){
    return document.querySelectorAll(`.conv-item[data-id="${id}"]`);
}

function buildItem(conv){
    const item = document.createElement("div");
    item.className = "conv-item";
    item.dataset.id = conv.id;

    const link = document.createElement("a");
    link.className = "conv-link";
    link.href = conv.url;
    link.title = conv.title;
    const icon = document.createElement("i");
    icon.className = "bi bi-chat-left-text";
    const span = document.createElement("span");
    span.className = "conv-title";
    span.textContent = conv.title;
    link.append(icon, span);

    const actions = document.createElement("div");
    actions.className = "conv-actions";
    [["rename", "bi-pencil", "Renomear"], ["delete", "bi-trash", "Excluir"]].forEach(([action, ic, label]) => {
        const b = document.createElement("button");
        b.type = "button";
        b.className = "conv-btn" + (action === "delete" ? " danger" : "");
        b.dataset.action = action;
        b.title = label;
        b.setAttribute("aria-label", label + " conversa");
        const i = document.createElement("i");
        i.className = "bi " + ic;
        b.appendChild(i);
        actions.appendChild(b);
    });

    item.append(link, actions);
    return item;
}

function todayGroup(list){
    let grp = list.querySelector('.conv-group[data-group="Hoje"]');
    if(!grp){
        grp = document.createElement("div");
        grp.className = "conv-group";
        grp.dataset.group = "Hoje";
        const label = document.createElement("div");
        label.className = "conv-group-label";
        label.textContent = "Hoje";
        grp.appendChild(label);
        list.prepend(grp);
    }
    return grp;
}

function cleanupGroups(){
    lists().forEach(list => {
        list.querySelectorAll(".conv-group").forEach(g => {
            if(!g.querySelector(".conv-item")) g.remove();
        });
        const empty = list.querySelector(".conv-empty");
        if(empty) empty.hidden = !!list.querySelector(".conv-item");
    });
}

// conversa recebeu mensagem: vai para o topo de "Hoje"; se é nova, entra na lista e vira a atual
function onConversationActivity(conv, created){

    if(created){
        conversationId = String(conv.id);
        chatWrapper.dataset.conversationId = conversationId;
        history.pushState({conversationId}, "", conv.url);
        titleEl.textContent = conv.title;
        document.title = conv.title + " • Contability";
        renameCurrentBtn.hidden = false;
    }

    lists().forEach(list => {
        let item = list.querySelector(`.conv-item[data-id="${conv.id}"]`);
        if(!item) item = buildItem(conv);
        const grp = todayGroup(list);
        grp.insertBefore(item, grp.querySelector(".conv-item"));
    });

    document.querySelectorAll(".conv-item").forEach(i =>
        i.classList.toggle("active", i.dataset.id === String(conv.id)));
    cleanupGroups();
}

async function postJSON(url, body){
    const r = await fetch(url, {
        method: "POST",
        headers: {"Content-Type": "application/json", "Accept": "application/json"},
        body: JSON.stringify(body || {})
    });
    if(r.status === 401){ window.location.href = "/login"; throw new Error("sessão expirada"); }
    const data = await r.json().catch(() => ({}));
    if(!r.ok) throw new Error(data.error || "Falha na operação.");
    return data;
}

function applyTitle(id, title){
    itemsFor(id).forEach(item => {
        item.querySelector(".conv-title").textContent = title;
        item.querySelector(".conv-link").title = title;
    });
    if(String(id) === String(conversationId)){
        titleEl.textContent = title;
        document.title = title + " • Contability";
    }
}

// renomear: edição no próprio lugar (Enter salva, Esc cancela)
function startRename(id, targetEl){

    const current = targetEl.textContent;
    const input = document.createElement("input");
    input.type = "text";
    input.className = "form-control form-control-sm conv-rename-input";
    input.value = current;
    input.maxLength = 80;
    targetEl.replaceWith(input);
    input.focus();
    input.select();

    let done = false;
    const finish = async (save) => {
        if(done) return;
        done = true;
        const title = input.value.trim();
        input.replaceWith(targetEl);
        if(!save || !title || title === current) return;
        try{
            const data = await postJSON(`/chat/${id}/renomear`, {title});
            applyTitle(id, data.title);
        }catch(e){
            alert(e.message);
        }
    };

    input.addEventListener("keydown", (e) => {
        if(e.key === "Enter"){ e.preventDefault(); finish(true); }
        if(e.key === "Escape"){ e.preventDefault(); finish(false); }
    });
    input.addEventListener("blur", () => finish(true));
}

renameCurrentBtn.addEventListener("click", () => {
    if(conversationId) startRename(conversationId, titleEl);
});

// excluir: confirmação em modal
const deleteModalEl = document.getElementById("conv-delete-modal");
const deleteModal = bootstrap.Modal.getOrCreateInstance(deleteModalEl);
let pendingDelete = null;

document.getElementById("conv-delete-confirm").addEventListener("click", async () => {
    if(!pendingDelete) return;
    const id = pendingDelete;
    try{
        await postJSON(`/chat/${id}/excluir`);
        deleteModal.hide();
        if(String(id) === String(conversationId)){
            window.location.href = "/";      // apagou a conversa aberta: abre uma nova
            return;
        }
        itemsFor(id).forEach(i => i.remove());
        cleanupGroups();
    }catch(e){
        alert(e.message);
    }finally{
        pendingDelete = null;
    }
});

// ações dos itens (delegação: vale para itens criados depois também)
document.addEventListener("click", (e) => {
    const btn = e.target.closest(".conv-item .conv-btn");
    if(!btn) return;
    e.preventDefault();
    const item = btn.closest(".conv-item");
    const id = item.dataset.id;

    if(btn.dataset.action === "rename"){
        startRename(id, item.querySelector(".conv-title"));
    }else if(btn.dataset.action === "delete"){
        pendingDelete = id;
        document.getElementById("conv-delete-name").textContent =
            "“" + item.querySelector(".conv-title").textContent + "”";
        deleteModal.show();
    }
});

// voltar/avançar do navegador depois de criar uma conversa: recarrega a página certa
window.addEventListener("popstate", () => window.location.reload());
