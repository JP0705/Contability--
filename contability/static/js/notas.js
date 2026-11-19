// Notas Fiscais: lista os arquivos escolhidos e permite arrastar/soltar.

const input = document.getElementById("xml-input");
const dropzone = document.getElementById("dropzone");
const fileList = document.getElementById("file-list");
const form = document.getElementById("upload-form");
const submitBtn = document.getElementById("upload-submit");

const MAX_FILES = 50;
const MAX_BYTES = 2 * 1024 * 1024;

function formatSize(bytes){
    return bytes < 1024 ? `${bytes} B` : `${(bytes / 1024).toFixed(1).replace(".", ",")} KB`;
}

function renderFiles(){

    fileList.innerHTML = "";
    const files = [...input.files];

    files.forEach(f => {
        const li = document.createElement("li");
        const problem = !f.name.toLowerCase().endsWith(".xml") ? "não é .xml"
                      : f.size > MAX_BYTES ? "maior que 2 MB" : null;

        const name = document.createElement("span");
        name.textContent = f.name;

        const info = document.createElement("small");
        info.textContent = problem || formatSize(f.size);

        if(problem) li.classList.add("invalid");
        li.append(name, info);
        fileList.appendChild(li);
    });

    if(files.length > MAX_FILES){
        const li = document.createElement("li");
        li.classList.add("invalid");
        li.textContent = `Máximo de ${MAX_FILES} arquivos por envio (${files.length} selecionados).`;
        fileList.prepend(li);
    }
}

input.addEventListener("change", renderFiles);

["dragenter", "dragover"].forEach(ev => dropzone.addEventListener(ev, (e) => {
    e.preventDefault();
    dropzone.classList.add("dragover");
}));

["dragleave", "drop"].forEach(ev => dropzone.addEventListener(ev, (e) => {
    e.preventDefault();
    dropzone.classList.remove("dragover");
}));

dropzone.addEventListener("drop", (e) => {
    if(e.dataTransfer && e.dataTransfer.files.length){
        input.files = e.dataTransfer.files;
        renderFiles();
    }
});

// evita envio duplo enquanto o servidor processa
form.addEventListener("submit", () => {
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Importando...';
});
