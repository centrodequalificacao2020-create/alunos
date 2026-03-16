from app import create_app
from db import db
from models import Usuario
from security import hash_senha

app = create_app()
with app.app_context():
    db.create_all()
    if not Usuario.query.filter_by(usuario="admin").first():
        admin = Usuario(
            usuario = "admin",
            senha   = hash_senha("admin123"),
            nome    = "Administrador",
            perfil  = "admin",
        )
        db.session.add(admin)
        db.session.commit()
        print("Usuário admin criado! Login: admin / Senha: admin123")
        print("Troque a senha após o primeiro login.")
    else:
        print("Troque a senha após o primeiro login.")