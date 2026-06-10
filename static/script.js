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

function addMessage(text, sender = "bot") {

    const div = document.createElement("div");

    div.classList.add("message");

    const time = new Date().toLocaleTimeString([], {
        hour: '2-digit',
        minute: '2-digit'
    });

    if(sender === "user"){

        div.classList.add("user");

        div.innerHTML = `
            <div>${text}</div>
            <small>${time}</small>
        `;

    }else{

        div.classList.add("bot");

        div.innerHTML = `
            <div class="message-content">
                ${marked.parse(text)}
            </div>
            <small>${time}</small>
        `;
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

        const data = await response.json();

        removeTypingIndicator();

        addMessage(data.reply);

    }catch(error){

        removeTypingIndicator();
        
        addMessage("Erro ao conectar com a IA.");
    }
}

sendBtn.addEventListener("click", sendMessage);

userInput.addEventListener("keydown", (e) => {
    if(e.key === "Enter"){
        sendMessage();
    }
});

async function newChat() {

    try {

        await fetch("/new-chat", {
            method: "POST"
        });

        chatBody.innerHTML = "";

        addMessage(`
            👋 Olá!

            Sou o Contability, seu assistente contábil.

            Como posso ajudar você hoje?
        `);

    } catch (error) {

        addMessage("Erro ao iniciar uma nova consulta.");
    }
}

newChatBtn.addEventListener("click", newChat);