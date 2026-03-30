from db import db
from datetime import datetime, date
from enums import (
    PerfilUsuario, StatusMatricula, StatusAluno,
    StatusMensalidade, StatusFrequencia, ResultadoNota
)


# ─ Constantes de domínio (retrocompat) ──────────────────────────────────────────────────
PERFIS_VALIDOS   = PerfilUsuario.valores()
STATUS_MATRICULA = StatusMatricula.valores()


class Usuario(db.Model):
    __tablename__ = "usuarios"
    id              = db.Column(db.Integer, primary_key=True)
    usuario         = db.Column(db.String(80), unique=True, nullable=False)
    senha           = db.Column(db.String(256), nullable=False)
    nome            = db.Column(db.String(120))
    perfil          = db.Column(db.String(40), default=PerfilUsuario.SECRETARIA.value)
    cpf             = db.Column(db.String(14))
    data_nascimento = db.Column(db.String(10))
    status          = db.Column(db.String(20), default=StatusAluno.ATIVO.value)
    telefone        = db.Column(db.String(20))
    email           = db.Column(db.String(120))
    endereco        = db.Column(db.String(200))


class Curso(db.Model):
    __tablename__ = "cursos"
    id              = db.Column(db.Integer, primary_key=True)
    nome            = db.Column(db.String(120), nullable=False)
    valor_mensal    = db.Column(db.Float, default=0)
    valor_matricula = db.Column(db.Float, default=0)
    parcelas        = db.Column(db.Integer, default=1)
    valor_total     = db.Column(db.Float, default=0)
    tipo            = db.Column(db.String(60))
    duracao         = db.Column(db.String(60))
    alunos          = db.relationship("Aluno",     backref="curso",  lazy=True)
    matriculas      = db.relationship("Matricula", backref="curso",  lazy=True)
    materias        = db.relationship("Materia",   backref="curso",  lazy=True)


class Turma(db.Model):
    __tablename__ = "turmas"
    id         = db.Column(db.Integer, primary_key=True)
    nome       = db.Column(db.String(120), nullable=False)
    modalidade = db.Column(db.String(20), nullable=False)
    tipo       = db.Column(db.String(20), nullable=False)
    curso_id   = db.Column(db.Integer, db.ForeignKey("cursos.id"))
    curso      = db.relationship("Curso", backref="turmas")
    alunos     = db.relationship("TurmaAluno", backref="turma", lazy=True,
                                 cascade="all, delete-orphan")


class TurmaAluno(db.Model):
    __tablename__ = "turma_alunos"
    __table_args__ = (db.UniqueConstraint("turma_id", "aluno_id"),)
    id       = db.Column(db.Integer, primary_key=True)
    turma_id = db.Column(db.Integer, db.ForeignKey("turmas.id"), nullable=False)
    aluno_id = db.Column(db.Integer, db.ForeignKey("alunos.id"), nullable=False)
    aluno    = db.relationship("Aluno", backref="turmas")


class Aluno(db.Model):
    __tablename__ = "alunos"
    id                     = db.Column(db.Integer, primary_key=True)
    nome                   = db.Column(db.String(120), nullable=False)
    cpf                    = db.Column(db.String(14))
    rg                     = db.Column(db.String(20))
    data_nascimento        = db.Column(db.String(10))
    telefone               = db.Column(db.String(20))
    whatsapp               = db.Column(db.String(20))
    telefone_contato       = db.Column(db.String(20))
    email                  = db.Column(db.String(120))
    endereco               = db.Column(db.String(200))
    complemento            = db.Column(db.String(100))
    bairro                 = db.Column(db.String(100))
    cidade                 = db.Column(db.String(100))
    estado                 = db.Column(db.String(2))
    cep                    = db.Column(db.String(9))
    status                 = db.Column(db.String(40), default=StatusAluno.ATIVO.value)
    curso_id               = db.Column(db.Integer, db.ForeignKey("cursos.id"))
    responsavel_nome       = db.Column(db.String(120))
    responsavel_cpf        = db.Column(db.String(14))
    responsavel_telefone   = db.Column(db.String(20))
    responsavel_parentesco = db.Column(db.String(40))
    senha                  = db.Column(db.String(256))
    mensalidades           = db.relationship("Mensalidade", backref="aluno", lazy=True)
    matriculas             = db.relationship("Matricula",   backref="aluno", lazy=True)
    frequencias            = db.relationship("Frequencia",  backref="aluno", lazy=True)
    notas                  = db.relationship("Nota",        backref="aluno", lazy=True)
    login_historico        = db.relationship("LoginHistoricoAluno", backref="aluno",
                                             lazy=True, cascade="all, delete-orphan",
                                             order_by="LoginHistoricoAluno.login_em.desc()")

    @property
    def matricula_ativa(self):
        return next(
            (m for m in self.matriculas
             if m.status.upper() == StatusMatricula.ATIVA.value), None
        )

    @property
    def curso_ativo(self):
        m = self.matricula_ativa
        return m.curso if m else None

    @property
    def ultimo_login(self):
        """Retorna o registro de login mais recente ou None."""
        return (
            LoginHistoricoAluno.query
            .filter_by(aluno_id=self.id)
            .order_by(LoginHistoricoAluno.login_em.desc())
            .first()
        )


class Matricula(db.Model):
    __tablename__ = "matriculas"
    id                  = db.Column(db.Integer, primary_key=True)
    aluno_id            = db.Column(db.Integer, db.ForeignKey("alunos.id"),
                                    nullable=False, index=True)
    curso_id            = db.Column(db.Integer, db.ForeignKey("cursos.id"),
                                    nullable=False)
    tipo_curso          = db.Column(db.String(60))
    data_matricula      = db.Column(db.String(10))   # data em que o admin registrou a matrícula
    data_cadastro       = db.Column(db.String(19))   # timestamp ISO preenchido automaticamente
    status              = db.Column(db.String(20), default=StatusMatricula.ATIVA.value)
    valor_matricula     = db.Column(db.Float, default=0)
    valor_mensalidade   = db.Column(db.Float, default=0)
    quantidade_parcelas = db.Column(db.Integer, default=1)
    material_didatico   = db.Column(db.String(20))
    valor_material      = db.Column(db.Float, default=0)
    observacao          = db.Column(db.Text)

    def save(self, session):
        """Garante que status é sempre salvo em maiúsculo e válido.
           Preenche data_cadastro se ainda nao foi definido.
        """
        valor = (self.status or StatusMatricula.ATIVA.value).upper().strip()
        if valor not in StatusMatricula.valores():
            valor = StatusMatricula.ATIVA.value
        self.status = valor
        if not self.data_cadastro:
            self.data_cadastro = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        session.add(self)


class LoginHistoricoAluno(db.Model):
    """Registra cada login do aluno no portal."""
    __tablename__ = "login_historico_aluno"
    __table_args__ = (
        db.Index("ix_login_hist_aluno_id", "aluno_id"),
        db.Index("ix_login_hist_login_em", "login_em"),
    )
    id         = db.Column(db.Integer, primary_key=True)
    aluno_id   = db.Column(db.Integer, db.ForeignKey("alunos.id"), nullable=False)
    login_em   = db.Column(db.String(19), nullable=False)   # YYYY-MM-DD HH:MM:SS
    ip         = db.Column(db.String(45))                   # IPv4 ou IPv6
    user_agent = db.Column(db.String(300))


class Mensalidade(db.Model):
    __tablename__ = "mensalidades"
    __table_args__ = (
        db.Index("ix_mensalidades_aluno_id",  "aluno_id"),
        db.Index("ix_mensalidades_vencimento", "vencimento"),
        db.Index("ix_mensalidades_status",     "status"),
    )
    id                = db.Column(db.Integer, primary_key=True)
    aluno_id          = db.Column(db.Integer, db.ForeignKey("alunos.id"), nullable=False)
    valor             = db.Column(db.Float, nullable=False)
    vencimento        = db.Column(db.String(10), nullable=False)
    status            = db.Column(db.String(20), default=StatusMensalidade.PENDENTE.value)
    tipo              = db.Column(db.String(40))
    parcela_ref       = db.Column(db.String(20))
    data_pagamento    = db.Column(db.String(10))
    forma_pagamento   = db.Column(db.String(40))
    usuario_pagamento = db.Column(db.String(80))


class Despesa(db.Model):
    """Despesa avulsa (tipo=variavel) ou recorrente (tipo=fixa)."""
    __tablename__ = "despesas"
    id           = db.Column(db.Integer, primary_key=True)
    descricao    = db.Column(db.String(200))
    valor        = db.Column(db.Float, default=0)
    tipo         = db.Column(db.String(40))
    categoria    = db.Column(db.String(60))
    data         = db.Column(db.String(10))
    observacao   = db.Column(db.Text)
    data_inicio  = db.Column(db.String(7))
    data_fim     = db.Column(db.String(7))
    recorrente     = db.Column(db.Integer, default=0)
    dia_vencimento = db.Column(db.Integer)


class Relatorio(db.Model):
    __tablename__ = "relatorios"
    id               = db.Column(db.Integer, primary_key=True)
    mes              = db.Column(db.String(7), unique=True)
    meta             = db.Column(db.Integer, default=0)
    realizado        = db.Column(db.Integer, default=0)
    matriculas       = db.Column(db.Integer, default=0)
    matriculas_venda = db.Column(db.Integer, default=0)


class Frequencia(db.Model):
    __tablename__ = "frequencias"
    __table_args__ = (
        db.Index("ix_frequencias_aluno_id", "aluno_id"),
        db.UniqueConstraint("aluno_id", "curso_id", "data",
                            name="uq_frequencias_aluno_curso_data"),
    )
    id       = db.Column(db.Integer, primary_key=True)
    aluno_id = db.Column(db.Integer, db.ForeignKey("alunos.id"), nullable=False)
    curso_id = db.Column(db.Integer, db.ForeignKey("cursos.id"))
    data     = db.Column(db.String(10))
    status   = db.Column(db.String(20), default=StatusFrequencia.PRESENTE.value)


class Materia(db.Model):
    __tablename__ = "materias"
    id        = db.Column(db.Integer, primary_key=True)
    nome      = db.Column(db.String(120), nullable=False)
    ativa     = db.Column(db.Integer, default=1)
    curso_id  = db.Column(db.Integer, db.ForeignKey("cursos.id"))
    conteudos = db.relationship("Conteudo", backref="materia", lazy=True,
                                cascade="all, delete-orphan")
    notas     = db.relationship("Nota", backref="materia", lazy=True)


class CursoMateria(db.Model):
    __tablename__ = "cursos_materias"
    __table_args__ = (
        db.UniqueConstraint("curso_id", "materia_id", name="uq_cursos_materias"),
        db.Index("ix_cursos_materias_curso_id",   "curso_id"),
        db.Index("ix_cursos_materias_materia_id", "materia_id"),
    )
    id         = db.Column(db.Integer, primary_key=True)
    curso_id   = db.Column(db.Integer, db.ForeignKey("cursos.id"))
    materia_id = db.Column(db.Integer, db.ForeignKey("materias.id"))


class Conteudo(db.Model):
    __tablename__ = "conteudos"
    id         = db.Column(db.Integer, primary_key=True)
    titulo     = db.Column(db.String(200))
    materia_id = db.Column(db.Integer, db.ForeignKey("materias.id"))
    modulo     = db.Column(db.String(60))
    arquivo    = db.Column(db.String(300))
    video      = db.Column(db.String(300))
    data       = db.Column(db.String(10))


class Nota(db.Model):
    __tablename__ = "notas"
    __table_args__ = (
        db.UniqueConstraint("aluno_id", "materia_id", "curso_id"),
    )
    id         = db.Column(db.Integer, primary_key=True)
    aluno_id   = db.Column(db.Integer, db.ForeignKey("alunos.id"),   nullable=False, index=True)
    materia_id = db.Column(db.Integer, db.ForeignKey("materias.id"), nullable=False)
    curso_id   = db.Column(db.Integer, db.ForeignKey("cursos.id"),   nullable=False)
    nota       = db.Column(db.Float)
    resultado  = db.Column(db.String(40))


class ProgressoAula(db.Model):
    __tablename__ = "progresso_aulas"
    __table_args__ = (db.UniqueConstraint("aluno_id", "conteudo_id"),)
    id          = db.Column(db.Integer, primary_key=True)
    aluno_id    = db.Column(db.Integer, db.ForeignKey("alunos.id"))
    conteudo_id = db.Column(db.Integer, db.ForeignKey("conteudos.id"))
    concluido   = db.Column(db.Integer, default=0)
