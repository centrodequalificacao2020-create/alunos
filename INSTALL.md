# INSTALL.md — Centro de Qualificacao

Sistema de gestao escolar EAD baseado em Flask + SQLAlchemy + SQLite.
Deploy em servidor self-hosted (i5-3210M, 6 GB RAM, SSD 500 GB).

---

## Requisitos

- Python 3.10 ou superior
- pip
- Git
- Sistema operacional Linux (Ubuntu 22.04 recomendado) ou Windows 10+ para desenvolvimento local

---

## 1. Clonar o repositorio

```bash
git clone https://github.com/centrodequalificacao2020-create/alunos.git
cd alunos
```

---

## 2. Criar e ativar ambiente virtual

**Linux / macOS:**
```bash
python3 -m venv venv
source venv/bin/activate
```

**Windows:**
```cmd
python -m venv venv
venv\Scripts\activate
```

---

## 3. Instalar dependencias

```bash
pip install -r requirements.txt
```

Pacotes principais utilizados pelo sistema:

- `flask` — framework web
- `flask-sqlalchemy` — ORM
- `flask-wtf` — protecao CSRF
- `flask-limiter` — rate limiting nas rotas de login
- `werkzeug` — hashing de senhas (`generate_password_hash`, `check_password_hash`)
- `python-dotenv` — carregamento do arquivo `.env`
- `reportlab` ou equivalente — geracao de PDFs (recibos e carnes)

---

## 4. Configurar variaveis de ambiente

Copie o arquivo de exemplo e edite com os valores reais:

```bash
cp .env.example .env
```

Conteudo minimo do `.env`:

```
FLASK_SECRET_KEY=substitua-por-uma-chave-gerada
FLASK_DEBUG=False
FLASK_ENV=production
```

Para gerar uma chave segura:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

**Importante:** Em producao, `FLASK_SECRET_KEY` e obrigatoria. O sistema rejeita a inicializacao com `RuntimeError` se a variavel estiver ausente e `FLASK_ENV=production`.

Variavel opcional para banco externo (padrao: SQLite local `cqp.db`):

```
DATABASE_URL=sqlite:////caminho/absoluto/cqp.db
```

---

## 5. Inicializar o banco de dados

Execute apenas no primeiro deploy ou apos resetar o banco:

```bash
python initdbauto.py
```

Este script cria todas as tabelas definidas em `models.py` via `db.create_all()`.

Alternativa de fallback (ambientes sem Flask-Migrate):

```bash
python initdb.py
```

---

## 6. Criar o usuario administrador

```bash
python criaradmin.py
```

Credenciais iniciais criadas:

- Login: `admin`
- Senha: `admin123`

Troque a senha imediatamente apos o primeiro acesso.

---

## 7. Criar indices de banco de dados (recomendado)

Melhora o desempenho das consultas mais frequentes (mensalidades, matriculas, frequencias):

```bash
python scripts/criarindices.py
```

---

## 8. Executar em desenvolvimento

```bash
python app.py
```

A aplicacao sobe em `http://127.0.0.1:5000` com `DEBUG=True` quando `FLASK_DEBUG=True` no `.env`.

---

## 9. Deploy em producao (self-hosted com Gunicorn + Nginx)

### 9.1 Instalar Gunicorn

```bash
pip install gunicorn
```

### 9.2 Testar o Gunicorn manualmente

```bash
gunicorn "app:create_app()" --bind 0.0.0.0:8000 --workers 2
```

Para a maquina de deploy (i5-3210M, 2 cores fisicos), 2 workers sincrono e o valor adequado.

### 9.3 Criar servico systemd

Crie o arquivo `/etc/systemd/system/cqp.service`:

```ini
[Unit]
Description=Centro de Qualificacao - Flask App
After=network.target

[Service]
User=www-data
WorkingDirectory=/home/site/wwwroot
ExecStart=/home/site/wwwroot/venv/bin/gunicorn "app:create_app()" \
    --bind 127.0.0.1:8000 \
    --workers 2 \
    --timeout 120 \
    --access-logfile /home/site/wwwroot/logs/access.log \
    --error-logfile /home/site/wwwroot/logs/error.log
Restart=always
EnvironmentFile=/home/site/wwwroot/.env

[Install]
WantedBy=multi-user.target
```

Ative e inicie:

```bash
sudo systemctl daemon-reload
sudo systemctl enable cqp
sudo systemctl start cqp
```

### 9.4 Configurar Nginx como proxy reverso

Crie `/etc/nginx/sites-available/cqp`:

```nginx
server {
    listen 80;
    server_name seu-dominio-ou-ip;

    client_max_body_size 55M;

    location /static/ {
        alias /home/site/wwwroot/static/;
        expires 7d;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Ative o site:

```bash
sudo ln -s /etc/nginx/sites-available/cqp /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

O limite `client_max_body_size 55M` respeita o `MAX_CONTENT_LENGTH = 50 * 1024 * 1024` definido em `config.py`.

---

## 10. Migracoes e scripts de manutencao

Os scripts abaixo ficam na pasta `scripts/` e devem ser executados pontualmente conforme necessidade:

| Script | Quando executar |
|---|---|
| `scripts/migrar_senhas.py` | Primeiro deploy com alunos sem senha cadastrada |
| `scripts/migrate_status_matricula.py` | Padronizar `matriculas.status` para maiusculas |
| `scripts/migrate_unique_cursomateria.py` | Adicionar indice UNIQUE em `cursos_materias` |
| `scripts/criar_indices.py` | Otimizar consultas apos primeiro deploy |

Exemplo de execucao:

```bash
python scripts/migrar_senhas.py
```

---

## 11. Backup do banco de dados

O sistema disponibiliza rota de download do banco autenticada para administradores em `/backup`.

Para automacao via cron, utilize o script de backup:

```bash
bash scripts/backup_auto.sh
```

Agende no crontab para execucao diaria:

```
0 2 * * * /bin/bash /home/site/wwwroot/scripts/backup_auto.sh
```

O arquivo gerado segue o padrao `backup_cqp_YYYYMMDDHHMMSS.db`.

---

## 12. Estrutura de pastas relevante

```
.
+-- app.py                  # factory create_app(), registro dos blueprints
+-- config.py               # classe Config, leitura do .env
+-- db.py                   # instancia SQLAlchemy, init_db()
+-- models.py               # todos os modelos ORM
+-- security.py             # decoradores de acesso, hash de senhas
+-- enums.py                # constantes de dominio (perfis, status)
+-- routes/                 # blueprints por modulo funcional
+-- services/               # logica de negocio (matricula, pdf, notas, etc.)
+-- templates/              # templates Jinja2
+-- static/
|   +-- uploads/            # arquivos enviados por usuarios (pdf, imagens, mp4)
+-- scripts/                # scripts de migracao e manutencao
+-- logs/                   # logs rotativos (app.log)
+-- cqp.db                  # banco SQLite (nao versionar)
+-- .env                    # variaveis de ambiente (nao versionar)
```

---

## 13. Perfis de acesso

| Perfil | Descricao |
|---|---|
| `admin` / `administrador` | Acesso total, incluindo exclusao de dados e backup |
| `financeiro` | Acesso ao modulo financeiro (parcelas, recibos, carnes, despesas) |
| `secretaria` | Gestao de alunos, matriculas e conteudos |
| `instrutor` | Notas, frequencia e atividades |
| `aluno` | Portal do aluno (rota `/aluno/`) |

O modulo financeiro (`/financeiro`, `/despesas`) exige perfil `administrador`, `admin` ou `financeiro` via decorador `@financeiro_required`.

---

## 14. Variaveis de configuracao disponiveis

| Variavel | Padrao | Descricao |
|---|---|---|
| `FLASK_SECRET_KEY` | Obrigatoria em producao | Chave de assinatura das sessoes |
| `FLASK_DEBUG` | `False` | Ativa modo debug (nunca usar em producao) |
| `FLASK_ENV` | `production` | Controla comportamento do `config.py` |
| `DATABASE_URL` | `sqlite:///cqp.db` | URI do banco de dados |

---

## Observacoes gerais

- O banco `cqp.db` e o arquivo `.env` nao devem ser commitados. Ambos estao no `.gitignore`.
- A pasta `static/uploads/` e criada automaticamente pela aplicacao na primeira execucao.
- A pasta `logs/` e criada automaticamente pelo modulo `logging_config.py`.
- Sessoes expiram em 1 hora (`PERMANENT_SESSION_LIFETIME = timedelta(hours=1)`).
- O cookie de sessao e marcado como `HttpOnly` e `SameSite=Lax`. Em producao com HTTPS, e tambem `Secure`.
