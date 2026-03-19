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

/* ── Máscaras ── */
function mascara(campo, padrao) {
    if (!campo) return;
    campo.addEventListener('input', () => {
        const digitos = campo.value.replace(/\D/g, '');
        let resultado = '';
        let di = 0;
        for (let pi = 0; pi < padrao.length && di < digitos.length; pi++) {
            if (padrao[pi] === '#') resultado += digitos[di++];
            else                   resultado += padrao[pi];
        }
        campo.value = resultado;
    });
}

/* ── Validação de CPF ──
   Algoritmo: módulo 11 com pesos decrescentes (10→2 e 11→2)
   Fonte: https://www.campuscode.com.br/conteudos/o-calculo-do-digito-verificador-do-cpf-e-do-cnpj
*/
function cpfValido(cpf) {
    const d = cpf.replace(/\D/g, '');
    if (d.length !== 11) return false;
    if (/^(\d)\1{10}$/.test(d)) return false;

    function calcDV(base, pesoInicial) {
        let soma = 0;
        for (let i = 0; i < base.length; i++)
            soma += parseInt(base[i]) * (pesoInicial - i);
        const resto = soma % 11;
        return resto < 2 ? 0 : 11 - resto;
    }

    const dv1 = calcDV(d.slice(0, 9), 10);
    if (dv1 !== parseInt(d[9])) return false;

    const dv2 = calcDV(d.slice(0, 10), 11);
    return dv2 === parseInt(d[10]);
}

function aplicarValidacaoCPF(campo) {
    if (!campo) return;
    const feedback = document.createElement('span');
    feedback.id        = campo.id + '_feedback';
    feedback.className = 'campo-feedback';
    campo.parentNode.appendChild(feedback);

    campo.addEventListener('input', () => {
        const digitos = campo.value.replace(/\D/g, '');
        if (digitos.length < 11) {
            feedback.textContent = '';
            feedback.className   = 'campo-feedback';
            campo.classList.remove('campo-valido', 'campo-invalido');
        } else {
            if (cpfValido(campo.value)) {
                feedback.textContent = 'CPF válido';
                feedback.className   = 'campo-feedback campo-feedback--ok';
                campo.classList.add('campo-valido');
                campo.classList.remove('campo-invalido');
            } else {
                feedback.textContent = 'CPF inválido';
                feedback.className   = 'campo-feedback campo-feedback--erro';
                campo.classList.add('campo-invalido');
                campo.classList.remove('campo-valido');
            }
        }
    });
}

/* ── Modal de confirmação de exclusão ── */
let urlExclusaoAtual = '';

function confirmarExclusao(url, nome, alunoId) {
    urlExclusaoAtual = url;
    document.getElementById('modalExclusaoNome').textContent = nome || 'este aluno';
    document.getElementById('senhaExclusao').value = '';
    const aviso = document.getElementById('modalExclusaoAviso');
    aviso.style.display = 'none';
    aviso.textContent   = '';

    fetch('/aluno/' + alunoId + '/pendencias')
        .then(r => r.json())
        .then(data => {
            if (data.total_parcelas > 0) {
                aviso.textContent = 'Atenção: este aluno possui ' + data.total_parcelas +
                    ' parcela(s) pendente(s) totalizando R$ ' +
                    data.total_valor.toFixed(2).replace('.', ',') +
                    '. Ao excluir, todos os registros financeiros serão removidos.';
                aviso.style.display = 'block';
            }
        });

    document.getElementById('modalExclusao').classList.add('aberto');
}

function fecharModal() {
    document.getElementById('modalExclusao').classList.remove('aberto');
}

function executarExclusao() {
    const senha = document.getElementById('senhaExclusao').value;
    if (!senha) { alert('Digite a senha do administrador.'); return; }
    const form  = document.createElement('form');
    form.method = 'POST';
    form.action = urlExclusaoAtual;
    const input = document.createElement('input');
    input.type  = 'hidden';
    input.name  = 'senha';
    input.value = senha;
    form.appendChild(input);
    document.body.appendChild(form);
    form.submit();
}

/* ── Init ── */
document.addEventListener('DOMContentLoaded', () => {
    const campoNasc = document.getElementById('data_nascimento');
    if (campoNasc) {
        campoNasc.addEventListener('change', verificarIdade);
        verificarIdade();
    }

    mascara(document.getElementById('cpf'),             '###.###.###-##');
    mascara(document.getElementById('rg'),              '#########');
    mascara(document.getElementById('telefone'),        '(##) #####-####');
    mascara(document.getElementById('cep'),             '#####-###');
    mascara(document.getElementById('responsavel_cpf'), '###.###.###-##');

    aplicarValidacaoCPF(document.getElementById('cpf'));
    aplicarValidacaoCPF(document.getElementById('responsavel_cpf'));

    const busca  = document.getElementById('buscaAluno');
    const filtro = document.getElementById('filtroStatus');
    if (busca)  busca.addEventListener('keyup', filtrarAlunos);
    if (filtro) filtro.addEventListener('change', filtrarAlunos);

    const overlay = document.getElementById('modalExclusao');
    if (overlay) overlay.addEventListener('click', e => { if (e.target === overlay) fecharModal(); });
});
