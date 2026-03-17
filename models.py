from db import db
from datetime import datetime, date

class Usuario(db.Model):
    __tablename__ = "usuarios"
    id              = db.Column(db.Integer, primary_key=True)
    usuario         = db.Column(db.String(80), unique=True, nullable=False)
    senha           = db.Column(db.String(256), nullable=False)
    nome            = db.Column(db.String(120))
    perfil          = db.Column(db.String(40), default="secretaria")
    cpf             = db.Column(db.String(14))
    data_nascimento = db.Column(db.String(10))
    status          = db.Column(db.String(20), default="Ativo")
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
    tipo            = db.Column(db.String(60))
    alunos          = db.relationship("Aluno",     backref="curso",    lazy=True)
    matriculas      = db.relationship("Matricula", backref="curso",    lazy=True)

class Aluno(db.Model):
    __tablename__ = "alunos"
    id                    = db.Column(db.Integer, primary_key=True)
    nome                  = db.Column(db.String(120), nullable=False)
    cpf                   = db.Column(db.String(14))
    rg                    = db.Column(db.String(20))
    data_nascimento       = db.Column(db.String(10))
    telefone              = db.Column(db.String(20))
    whatsapp              = db.Column(db.String(20))
    telefone_contato      = db.Column(db.String(20))
    email                 = db.Column(db.String(120))
    endereco              = db.Column(db.String(200))
    status                = db.Column(db.String(40), default="Ativo")
    curso_id              = db.Column(db.Integer, db.ForeignKey("cursos.id"))
    responsavel_nome      = db.Column(db.String(120))
    responsavel_cpf       = db.Column(db.String(14))
    responsavel_telefone  = db.Column(db.String(20))
    responsavel_parentesco= db.Column(db.String(40))
    senha                 = db.Column(db.String(256))
    mensalidades          = db.relationship("Mensalidade", backref="aluno", lazy=True)
    matriculas            = db.relationship("Matricula",   backref="aluno", lazy=True)
    frequencias           = db.relationship("Frequencia",  backref="aluno", lazy=True)

class Matricula(db.Model):
    __tablename__ = "matriculas"
    id                  = db.Column(db.Integer, primary_key=True)
    aluno_id            = db.Column(db.Integer, db.ForeignKey("alunos.id"), nullable=False, index=True)
    curso_id            = db.Column(db.Integer, db.ForeignKey("cursos.id"), nullable=False)
    tipo_curso          = db.Column(db.String(60))
    data_matricula      = db.Column(db.String(10))
    status              = db.Column(db.String(20), default="ATIVA")
    valor_matricula     = db.Column(db.Float, default=0)
    valor_mensalidade   = db.Column(db.Float, default=0)
    quantidade_parcelas = db.Column(db.Integer, default=1)
    material_didatico   = db.Column(db.String(20))
    valor_material      = db.Column(db.Float, default=0)
    observacao          = db.Column(db.Text)

class Mensalidade(db.Model):
    __tablename__ = "mensalidades"
    __table_args__ = (
        db.Index("ix_mensalidades_aluno_id",  "aluno_id"),
        db.Index("ix_mensalidades_vencimento", "vencimento"),
        db.Index("ix_mensalidades_status",     "status"),
    )
    id               = db.Column(db.Integer, primary_key=True)
    aluno_id         = db.Column(db.Integer, db.ForeignKey("alunos.id"), nullable=False)
    valor            = db.Column(db.Float, nullable=False)
    vencimento       = db.Column(db.String(10), nullable=False)
    status           = db.Column(db.String(20), default="Pendente")
    tipo             = db.Column(db.String(40))
    parcela_ref      = db.Column(db.String(20))
    data_pagamento   = db.Column(db.String(10))
    forma_pagamento  = db.Column(db.String(40))
    usuario_pagamento= db.Column(db.String(80))

class Despesa(db.Model):
    __tablename__ = "despesas"
    id             = db.Column(db.Integer, primary_key=True)
    descricao      = db.Column(db.String(200))
    valor          = db.Column(db.Float, default=0)
    tipo           = db.Column(db.String(40))
    categoria      = db.Column(db.String(60))
    data           = db.Column(db.String(10))
    observacao     = db.Column(db.Text)
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
    __table_args__ = (db.Index("ix_frequencias_aluno_id", "aluno_id"),)
    id       = db.Column(db.Integer, primary_key=True)
    aluno_id = db.Column(db.Integer, db.ForeignKey("alunos.id"), nullable=False)
    data     = db.Column(db.String(10))
    status   = db.Column(db.String(20))  # Presente / Falta

class Materia(db.Model):
    __tablename__ = "materias"
    id       = db.Column(db.Integer, primary_key=True)
    nome     = db.Column(db.String(120))
    curso_id = db.Column(db.Integer, db.ForeignKey("cursos.id"))
    conteudos = db.relationship("Conteudo", backref="materia", lazy=True)

class CursoMateria(db.Model):
    __tablename__ = "cursos_materias"
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
    video      = db.Column(db.String(300))  # URL de vídeo externo (YouTube etc.)
    data       = db.Column(db.String(10))

class ProgressoAula(db.Model):
    __tablename__ = "progresso_aulas"
    id          = db.Column(db.Integer, primary_key=True)
    aluno_id    = db.Column(db.Integer, db.ForeignKey("alunos.id"))
    conteudo_id = db.Column(db.Integer, db.ForeignKey("conteudos.id"))
    concluido   = db.Column(db.Integer, default=0)
    __table_args__ = (db.UniqueConstraint("aluno_id", "conteudo_id"),)
