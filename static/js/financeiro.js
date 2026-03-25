/* financeiro.js — lógica da página financeiro */

let formAtual = null;

/* Abre o modal de senha para confirmar exclusão de parcela */
function confirmarExclusao(form) {
    formAtual = form;
    document.getElementById('campo-senha').value = '';
    const modal = document.getElementById('modal-senha');
    modal.classList.add('aberto');
    setTimeout(() => document.getElementById('campo-senha').focus(), 100);
    return false; // impede submit imediato
}

function confirmarSenha() {
    const senha = document.getElementById('campo-senha').value.trim();
    if (!senha) { document.getElementById('campo-senha').focus(); return; }

    // Salva referência LOCAL antes de fechar o modal
    // (fecharModalSenha faz formAtual = null, então precisamos da cópia)
    const form = formAtual;
    form.querySelector('input[name="senha"]').value = senha;

    fecharModalSenha(); // zera formAtual — mas já temos a cópia em `form`
    form.submit();      // envia o formulário correto
}

function fecharModalSenha() {
    document.getElementById('modal-senha').classList.remove('aberto');
    formAtual = null;
}

document.addEventListener('DOMContentLoaded', () => {
    const campo = document.getElementById('campo-senha');
    if (campo) {
        campo.addEventListener('keydown', e => {
            if (e.key === 'Enter')  confirmarSenha();
            if (e.key === 'Escape') fecharModalSenha();
        });
    }

    const overlay = document.getElementById('modal-senha');
    if (overlay) overlay.addEventListener('click', e => {
        if (e.target === overlay) fecharModalSenha();
    });
});
