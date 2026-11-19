// Páginas "Em breve": progresso animado e engrenagens interativas.

const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

// ---------- progresso: barra + contador ----------
const fill = document.querySelector(".wip-bar-fill");
const counter = document.querySelector(".wip-count");
const target = Number(counter ? counter.dataset.target : 0);

requestAnimationFrame(() => {
    if(fill) fill.style.width = target + "%";
});

if(counter){
    if(reduceMotion){
        counter.textContent = target;
    }else{
        const start = performance.now();
        const duration = 1400;
        const tick = (now) => {
            const t = Math.min((now - start) / duration, 1);
            const eased = 1 - Math.pow(1 - t, 3);
            counter.textContent = Math.round(target * eased);
            if(t < 1) requestAnimationFrame(tick);
        };
        requestAnimationFrame(tick);
    }
}

// ---------- engrenagens ----------
const gears = document.getElementById("gears");
const hint = document.getElementById("gears-hint");
const gearEls = document.querySelectorAll(".gear");

const cheers = [
    "Isso! Mais rápido ⚙️",
    "A equipe sentiu o empurrão!",
    "Quase lá... continue!",
    "Turbo ativado 🚀",
];

let clicks = 0;
let speed = 1;
let decay = null;

function setSpeed(value){
    speed = value;
    gearEls.forEach(g => g.style.setProperty("--speed", speed.toFixed(2)));
}

if(gears){
    gears.addEventListener("click", () => {

        clicks++;
        setSpeed(Math.min(speed + 0.8, 8));

        hint.classList.add("cheer");
        hint.textContent = clicks % 10 === 0
            ? "Obrigado pelo incentivo! 🎉"
            : cheers[Math.min(Math.floor(clicks / 3), cheers.length - 1)];

        if(clicks % 10 === 0) burst();

        // as engrenagens desaceleram sozinhas depois de um tempo
        clearInterval(decay);
        decay = setInterval(() => {
            if(speed <= 1.05){
                setSpeed(1);
                clearInterval(decay);
                hint.classList.remove("cheer");
                hint.textContent = "Clique nas engrenagens para dar um empurrão ⚙️";
                return;
            }
            setSpeed(Math.max(1, speed * 0.9));
        }, 250);
    });
}

// ---------- confete (canvas, sem biblioteca) ----------
const canvas = document.getElementById("confetti");
const ctx = canvas ? canvas.getContext("2d") : null;
const colors = ["#b91c1c", "#ef4444", "#7f1d1d", "#fca5a5", "#f59e0b", "#ffffff"];
let pieces = [];
let animating = false;

function resize(){
    if(!canvas) return;
    canvas.width = window.innerWidth * devicePixelRatio;
    canvas.height = window.innerHeight * devicePixelRatio;
    ctx.setTransform(devicePixelRatio, 0, 0, devicePixelRatio, 0, 0);
}
window.addEventListener("resize", resize);
resize();

function burst(){

    if(!ctx || reduceMotion) return;

    const rect = gears.getBoundingClientRect();
    const ox = rect.left + rect.width / 2;
    const oy = rect.top + rect.height / 2;

    for(let i = 0; i < 140; i++){
        const angle = Math.random() * Math.PI * 2;
        const v = 4 + Math.random() * 7;
        pieces.push({
            x: ox, y: oy,
            vx: Math.cos(angle) * v,
            vy: Math.sin(angle) * v - 4,
            w: 6 + Math.random() * 6,
            h: 4 + Math.random() * 4,
            rot: Math.random() * Math.PI,
            vr: (Math.random() - .5) * .3,
            color: colors[i % colors.length],
            life: 90 + Math.random() * 40,
        });
    }

    if(!animating){
        animating = true;
        requestAnimationFrame(frame);
    }
}

function frame(){

    ctx.clearRect(0, 0, window.innerWidth, window.innerHeight);

    pieces.forEach(p => {
        p.vy += 0.22;          // gravidade
        p.vx *= 0.99;
        p.x += p.vx;
        p.y += p.vy;
        p.rot += p.vr;
        p.life--;
        ctx.save();
        ctx.globalAlpha = Math.max(0, Math.min(1, p.life / 40));
        ctx.translate(p.x, p.y);
        ctx.rotate(p.rot);
        ctx.fillStyle = p.color;
        ctx.fillRect(-p.w / 2, -p.h / 2, p.w, p.h);
        ctx.restore();
    });

    pieces = pieces.filter(p => p.life > 0 && p.y < window.innerHeight + 40);

    if(pieces.length){
        requestAnimationFrame(frame);
    }else{
        animating = false;
        ctx.clearRect(0, 0, window.innerWidth, window.innerHeight);
    }
}
