"""Serviço de alunos."""
from models import Aluno
from enums import StatusAluno


def buscar_alunos(termo: str = "", status: str = None):
    """Busca alunos por nome (ilike). Filtra por status se fornecido."""
    q = Aluno.query
    if termo:
        q = q.filter(Aluno.nome.ilike(f"%{termo}%"))
    if status:
        q = q.filter(Aluno.status == status)
    return q.order_by(Aluno.nome).all()


def get_aluno_ou_404(aluno_id: int):
    return Aluno.query.get_or_404(aluno_id)
