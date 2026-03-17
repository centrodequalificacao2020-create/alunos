/* financeiro.js — lógica da página financeiro */

let formAtual = null;

/* Abre o modal de senha para confirmar exclusão de parcela paga */
function confirmarExclusao(form) {
    formAtual = form;
    document.getElementById('campo-senha').value = '';
    const modal = document.getElementById('modal-senha');
    modal.classList.add('aberto');
    setTimeout(() => document.getElementById('campo-senha').focus(), 100);
    return false;
}

function confirmarSenha() {
    const senha = document.getElementById('campo-senha').value.trim();
    if (!senha) { document.getElementById('campo-senha').focus(); return; }
    formAtual.querySelector('input[name="senha"]').value = senha;
    fecharModalSenha();
    formAtual.submit();
}

function fecharModalSenha() {
    document.getElementById('modal-senha').classList.remove('aberto');
    formAtual = null;
}

document.addEventListener('DOMContentLoaded', () => {
    /* Enter / Escape no campo senha */
    const campo = document.getElementById('campo-senha');
    if (campo) {
        campo.addEventListener('keydown', e => {
            if (e.key === 'Enter')  confirmarSenha();
            if (e.key === 'Escape') fecharModalSenha();
        });
    }

    /* fechar modal clicando no overlay */
    const overlay = document.getElementById('modal-senha');
    if (overlay) overlay.addEventListener('click', e => { if (e.target === overlay) fecharModalSenha(); });
});
