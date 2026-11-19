// Telas de entrada: mostrar/ocultar senha, Caps Lock, força da senha,
// conferência da confirmação e estado de "enviando" no botão.

// ---------- mostrar / ocultar senha ----------
document.querySelectorAll(".toggle-pass").forEach(btn => {
    btn.addEventListener("click", () => {
        const input = document.getElementById(btn.dataset.target);
        const show = input.type === "password";
        input.type = show ? "text" : "password";
        btn.setAttribute("aria-pressed", String(show));
        btn.setAttribute("aria-label", show ? "Ocultar senha" : "Mostrar senha");
        btn.querySelector("i").className = "bi " + (show ? "bi-eye-slash" : "bi-eye");
        input.focus();
    });
});

// ---------- aviso de Caps Lock ----------
document.querySelectorAll('input[type="password"]').forEach(input => {
    const hint = input.closest(".field")?.querySelector(".caps-hint");
    if(!hint) return;
    const check = (e) => {
        if(typeof e.getModifierState === "function"){
            hint.hidden = !e.getModifierState("CapsLock");
        }
    };
    input.addEventListener("keydown", check);
    input.addEventListener("keyup", check);
    input.addEventListener("blur", () => { hint.hidden = true; });
});

// ---------- força da senha (só orientação; a regra real é validada no servidor) ----------
const strengthInput = document.querySelector("[data-strength]");
const strength = document.getElementById("strength");

const LEVELS = [
    "Use letras maiúsculas, números e símbolos para uma senha mais forte",
    "Fraca: misture maiúsculas, números e símbolos",
    "Razoável: misture maiúsculas e números",
    "Boa: um símbolo deixaria mais forte",
    "Forte",
];
const TOO_SHORT = "Muito curta: use pelo menos 8 caracteres";

function scorePassword(pw){
    if(!pw) return 0;
    if(pw.length < 8) return 1;
    let score = 1;
    if(/[a-z]/.test(pw) && /[A-Z]/.test(pw)) score++;
    if(/\d/.test(pw)) score++;
    if(/[^A-Za-z0-9]/.test(pw)) score++;
    if(pw.length >= 12 && score < 4) score++;
    return Math.min(score, 4);
}

if(strengthInput && strength){
    strengthInput.addEventListener("input", () => {
        const pw = strengthInput.value;
        const level = scorePassword(pw);
        strength.dataset.level = level;
        strength.querySelector(".strength-label").textContent =
            pw && pw.length < 8 ? TOO_SHORT : LEVELS[level];
        updateMatch();
    });
}

// ---------- confirmação da senha ----------
const confirmInput = document.querySelector("[data-match]");

function updateMatch(){
    if(!confirmInput) return;
    const original = document.getElementById(confirmInput.dataset.match);
    const hint = confirmInput.closest(".field").querySelector(".match-hint");
    const value = confirmInput.value;

    confirmInput.classList.remove("is-ok", "is-bad");
    if(!value){
        hint.hidden = true;
        return;
    }
    const ok = value === original.value;
    confirmInput.classList.add(ok ? "is-ok" : "is-bad");
    hint.hidden = false;
    hint.className = "match-hint " + (ok ? "ok" : "bad");
    hint.innerHTML = "";
    const icon = document.createElement("i");
    icon.className = "bi " + (ok ? "bi-check-circle-fill" : "bi-x-circle-fill");
    hint.append(icon, ok ? " As senhas conferem" : " As senhas não conferem");
}

if(confirmInput) confirmInput.addEventListener("input", updateMatch);

// ---------- botão "enviando" (evita clique duplo) ----------
document.querySelectorAll(".auth-form").forEach(form => {
    form.addEventListener("submit", () => {
        const btn = form.querySelector(".auth-submit");
        if(!btn) return;
        btn.disabled = true;
        btn.innerHTML = "";
        const spinner = document.createElement("span");
        spinner.className = "spinner-border spinner-border-sm";
        spinner.setAttribute("aria-hidden", "true");
        const label = document.createElement("span");
        label.textContent = form.dataset.loadingText || "Enviando...";
        btn.append(spinner, label);
    });
});
