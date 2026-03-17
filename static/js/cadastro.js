/* cadastro.js — lógica da página de alunos */

/* ── Filtro da tabela ── */
function filtrarAlunos() {
    const filtroTexto  = document.getElementById('buscaAluno').value.toLowerCase();
    const filtroStatus = document.getElementById('filtroStatus').value;

    document.querySelectorAll('.tabela-excel tbody tr').forEach(linha => {
        const nome   = linha.cells[0].innerText.toLowerCase();
        const status = linha.cells[3].innerText.trim();
        const inad   = linha.dataset.inadimplente;

        const matchTexto = nome.includes(filtroTexto);
        let matchStatus  = true;

        if      (filtroStatus === 'Inadimplente') matchStatus = inad === '1';
        else if (filtroStatus !== '')             matchStatus = status === filtroStatus;

        linha.style.display = (matchTexto && matchStatus) ? '' : 'none';
    });
}

/* ── Responsável legal: mostrar/ocultar pelo nascimento ── */
function verificarIdade() {
    const campo = document.getElementById('data_nascimento');
    const bloco = document.getElementById('bloco_responsavel');
    if (!campo || !bloco) return;

    const data = new Date(campo.value);
    if (isNaN(data)) return;

    const hoje = new Date();
    let idade   = hoje.getFullYear() - data.getFullYear();
    const m     = hoje.getMonth() - data.getMonth();
    if (m < 0 || (m === 0 && hoje.getDate() < data.getDate())) idade--;

    bloco.classList.toggle('bloco-oculto', idade >= 18);
}

/* ── Máscaras simples (sem dependência) ── */
function mascara(campo, padrao) {
    if (!campo) return;
    campo.addEventListener('input', () => {
        let v = campo.value.replace(/\D/g, '').slice(0, padrao.replace(/\D/g,'').length);
        let i = 0;
        campo.value = padrao.replace(/#/g, () => v[i++] || '');
    });
}

/* ── Modal de confirmação de exclusão ── */
let urlExclusaoAtual = '';

function confirmarExclusao(url, nome) {
    urlExclusaoAtual = url;
    const modal = document.getElementById('modalExclusao');
    const msg   = document.getElementById('modalExclusaoNome');
    if (msg) msg.textContent = nome || 'este aluno';
    if (modal) modal.classList.add('aberto');
}

function fecharModal() {
    document.getElementById('modalExclusao').classList.remove('aberto');
}

function executarExclusao() {
    if (urlExclusaoAtual) window.location.href = urlExclusaoAtual;
}

/* ── Init ── */
document.addEventListener('DOMContentLoaded', () => {
    // idade / responsável
    const campoNasc = document.getElementById('data_nascimento');
    if (campoNasc) {
        campoNasc.addEventListener('change', verificarIdade);
        verificarIdade();
    }

    // máscaras
    mascara(document.getElementById('cpf'),      '###.###.###-##');
    mascara(document.getElementById('rg'),       '#########');
    mascara(document.getElementById('telefone'), '(##) #####-####');
    mascara(document.getElementById('cep'),      '#####-###');
    mascara(document.getElementById('responsavel_cpf'), '###.###.###-##');

    // filtros (evento)
    const busca  = document.getElementById('buscaAluno');
    const filtro = document.getElementById('filtroStatus');
    if (busca)  busca.addEventListener('keyup', filtrarAlunos);
    if (filtro) filtro.addEventListener('change', filtrarAlunos);

    // fechar modal clicando fora
    const overlay = document.getElementById('modalExclusao');
    if (overlay) overlay.addEventListener('click', e => { if (e.target === overlay) fecharModal(); });
});
