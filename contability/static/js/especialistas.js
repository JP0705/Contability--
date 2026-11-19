// Especialistas: busca por texto + filtro por especialidade (no navegador).

const search = document.getElementById("acc-search");
const chips = document.querySelectorAll("#acc-chips .chip");
const cards = document.querySelectorAll(".acc-card");
const empty = document.getElementById("acc-empty");

let specialty = "";

function normalize(text){
    // ignora acentos e maiúsculas ("previdência" == "previdencia")
    return (text || "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
}

function applyFilter(){

    const term = normalize(search ? search.value.trim() : "");
    let visible = 0;

    cards.forEach(card => {
        const matchText = !term || normalize(card.dataset.search).includes(term);
        const matchSpec = !specialty || card.dataset.specialties.split("|").includes(specialty);
        const show = matchText && matchSpec;
        card.hidden = !show;
        if(show) visible++;
    });

    if(empty) empty.classList.toggle("d-none", visible > 0);
}

if(search) search.addEventListener("input", applyFilter);

chips.forEach(chip => chip.addEventListener("click", () => {
    chips.forEach(c => c.classList.remove("active"));
    chip.classList.add("active");
    specialty = chip.dataset.specialty;
    applyFilter();
}));
