// Tela de Gastos: preenche os modais de nova/editar transação e de exclusão.

const txConfig = JSON.parse(document.getElementById("tx-config").textContent);

const txModal = document.getElementById("tx-modal");
const txForm = document.getElementById("tx-form");
const txTitle = document.getElementById("tx-modal-title");
const categorySelect = document.getElementById("tx-category");
const statusSelect = document.getElementById("tx-status");

function currentType(){
    return txForm.querySelector("input[name=type]:checked").value;
}

// categorias e rótulos de status dependem do tipo (gasto x receita)
function refreshOptions(selectedCategory = null){

    const type = currentType();

    categorySelect.innerHTML = "";
    txConfig.categories[type].forEach(name => {
        categorySelect.add(new Option(name, name, false, name === selectedCategory));
    });

    const labels = txConfig.statusLabels[type];
    [...statusSelect.options].forEach(opt => {
        opt.textContent = labels[opt.value];
    });
}

txForm.querySelectorAll("input[name=type]").forEach(radio => {
    radio.addEventListener("change", () => refreshOptions());
});

// URL "/gastos/transacoes/0/editar" -> troca o 0 pelo id real
function urlFor(template, id){
    return template.replace(/\/0\//, `/${id}/`);
}

txModal.addEventListener("show.bs.modal", (event) => {

    const trigger = event.relatedTarget;
    const tx = trigger && trigger.dataset.tx ? JSON.parse(trigger.dataset.tx) : null;

    txForm.reset();

    if(tx){
        txTitle.textContent = "Editar transação";
        txForm.action = urlFor(txForm.dataset.editUrl, tx.id);

        txForm.querySelector(`input[name=type][value=${tx.type}]`).checked = true;
        txForm.description.value = tx.description;
        txForm.amount.value = tx.amount;
        txForm.date.value = tx.date;
        refreshOptions(tx.category);
        statusSelect.value = tx.status;
    }else{
        txTitle.textContent = "Nova transação";
        txForm.action = txForm.dataset.createUrl;
        refreshOptions();
    }
});

txModal.addEventListener("shown.bs.modal", () => {
    txForm.description.focus();
});

// exclusão
const deleteModal = document.getElementById("delete-modal");
const deleteForm = document.getElementById("delete-form");

deleteModal.addEventListener("show.bs.modal", (event) => {
    const trigger = event.relatedTarget;
    deleteForm.action = urlFor(deleteForm.dataset.url, trigger.dataset.txId);
    document.getElementById("delete-desc").textContent = trigger.dataset.txDesc;
});
