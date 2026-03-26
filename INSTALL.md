# Guia de Instalação — Servidor CQP

> **Para quem é este guia?**
> Este documento foi escrito para você instalar o sistema CQP no seu servidor.
> Você vai digitar comandos no terminal. Não é necessário saber programar.
> Siga os passos **na ordem** e não pule nenhum.

---

## O que você vai precisar

- O servidor ligado e conectado à internet
- Um segundo computador (notebook ou desktop) na mesma rede
- O arquivo de backup do banco de dados (`.sql`) — fornecido pelo desenvolvedor
- Os arquivos `logo_escola.png` e `assinatura.png` — fornecidos pelo desenvolvedor
- A senha de administrador do servidor (definida durante a instalação do Ubuntu)

---

## Parte 1 — Conectar ao servidor pelo segundo computador

Você não vai usar monitor ou teclado no servidor. O acesso é feito remotamente pelo
computador normal, usando um programa chamado **SSH**.

### 1.1 Descobrir o IP do servidor

No servidor (com monitor e teclado conectados *apenas desta vez*), digite:

```
ip a
```

Procure uma linha parecida com `inet 192.168.1.XX/24`. O número `192.168.1.XX`
é o IP do servidor. Anote esse número.

### 1.2 Conectar pelo segundo computador

**No Windows:** abra o terminal (pressione `Win + R`, digite `cmd`, pressione Enter).

Digite o comando abaixo, substituindo `192.168.1.XX` pelo IP anotado:

```
ssh usuario@192.168.1.XX
```

Quando perguntar `Are you sure you want to continue connecting?`, digite `yes` e Enter.
Depois digite a senha do servidor.

Se aparecer uma linha como `usuario@servidor:~$`, você está conectado. ✅

> **A partir daqui, todos os comandos são digitados nesta janela.**

---

## Parte 2 — Instalar o Docker

O Docker é o programa que vai rodar o sistema CQP. Copie e cole os comandos abaixo:

```bash
curl -fsSL https://get.docker.com | sudo sh
```

> Vai pedir a senha do servidor. Digite e pressione Enter.
> (A senha não aparece enquanto você digita — isso é normal.)

Depois, execute:

```bash
sudo usermod -aG docker $USER
```

```bash
newgrp docker
```

Verifique se o Docker foi instalado corretamente:

```bash
docker --version
```

Deve aparecer algo como `Docker version 26.x.x`. ✅

---

## Parte 3 — Configurar acesso ao repositório privado

O sistema fica em um repositório privado no GitHub. Você precisa criar uma
"chave" para que o servidor possa baixar o sistema sem precisar de senha.

### 3.1 Gerar a chave

```bash
ssh-keygen -t ed25519 -C "cqp-servidor" -f ~/.ssh/cqp_deploy
```

Quando perguntar por uma senha (`Enter passphrase`), pressione **Enter duas vezes**
sem digitar nada.

### 3.2 Ver a chave pública

```bash
cat ~/.ssh/cqp_deploy.pub
```

Vai aparecer uma linha longa começando com `ssh-ed25519 AAAA...`.
Copie essa linha inteira e envie para o desenvolvedor.

> O desenvolvedor vai cadastrar essa chave no GitHub e avisar quando estiver pronto.
> Aguarde a confirmação antes de continuar.

### 3.3 Configurar o SSH para usar a chave

```bash
mkdir -p ~/.ssh && nano ~/.ssh/config
```

Uma tela de editor vai abrir. Cole exatamente o texto abaixo:

```
Host github-cqp
    HostName github.com
    User git
    IdentityFile ~/.ssh/cqp_deploy
    IdentitiesOnly yes
```

Para salvar: pressione `Ctrl + X`, depois `Y`, depois `Enter`.

### 3.4 Testar a conexão

```bash
ssh -T github-cqp
```

Deve aparecer uma mensagem como:
`Hi centrodequalificacao2020-create! You've successfully authenticated...`

Se aparecer essa mensagem, está funcionando. ✅

---

## Parte 4 — Baixar o sistema

```bash
git clone git@github-cqp:centrodequalificacao2020-create/alunos.git
```

```bash
cd alunos
```

---

## Parte 5 — Configurar o sistema

### 5.1 Criar o arquivo de configuração

```bash
cp .env.example .env
```

Agora gere uma chave de segurança única para o sistema:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

Vai aparecer uma sequencia longa de letras e números. Copie esse valor.

Abra o arquivo de configuração:

```bash
nano .env
```

Substitua o texto `substitua-por-uma-chave-gerada` pela sequencia copiada.
A linha deve ficar assim (com o seu valor):

```
FLASK_SECRET_KEY=a1b2c3d4e5f6...  (seu valor aqui)
FLASK_DEBUG=False
```

Para salvar: `Ctrl + X`, depois `Y`, depois `Enter`.

### 5.2 Restaurar o banco de dados

Crie a pasta do banco:

```bash
mkdir -p data
```

Agora transfira o arquivo `.sql` fornecido pelo desenvolvedor para o servidor.
Do **segundo computador** (Windows), abra um **novo** terminal e execute:

```
scp C:\caminho\para\backup.sql usuario@192.168.1.XX:/home/usuario/alunos/data/
```

> Substitua `C:\caminho\para\backup.sql` pelo caminho real do arquivo no seu computador.
> Substitua `192.168.1.XX` pelo IP do servidor.

Volte para o terminal conectado ao servidor e restaure o banco:

```bash
sqlite3 data/cqp.db < data/backup_cqp.sql
```

### 5.3 Copiar as imagens institucionais

Do **segundo computador**, envie os arquivos de imagem:

```
scp C:\caminho\para\logo_escola.png usuario@192.168.1.XX:/home/usuario/alunos/static/
scp C:\caminho\para\assinatura.png  usuario@192.168.1.XX:/home/usuario/alunos/static/
```

---

## Parte 6 — Subir o sistema

```bash
docker compose up -d
```

Este comando vai baixar e preparar tudo automaticamente.
Pode demorar alguns minutos na primeira vez — aguarde até voltar ao prompt `$`.

Verifique se está rodando:

```bash
docker compose ps
```

Deve aparecer dois containers com o status `Up` ou `healthy`:
- `cqp_web`
- `cqp_nginx`

Se os dois estiverem ativos, o sistema está no ar. ✅

Acesse pelo navegador de qualquer computador da rede:

```
http://192.168.1.XX
```

(substitua pelo IP do servidor)

---

## Parte 7 — Fazer o sistema iniciar automaticamente com o servidor

O Docker já está configurado para reiniciar os containers automaticamente
(`restart: always` no docker-compose.yml). Mas é necessário garantir que o
Docker em si inicie com o sistema operacional:

```bash
sudo systemctl enable docker
```

Agora se o servidor for reiniciado (queda de energia, etc.), o sistema CQP
volta automaticamente sem nenhuma intervenção. ✅

---

## Parte 8 — Atualizar o sistema no futuro

Sempre que o desenvolvedor lançar uma atualização, execute os dois comandos abaixo
a partir do segundo computador (conectado via SSH ao servidor):

```bash
cd alunos
git pull
docker compose up -d --build
```

Pronto. O sistema é atualizado sem perder nenhum dado.

---

## Comandos úteis do dia a dia

| O que fazer | Comando |
|---|---|
| Ver se o sistema está rodando | `docker compose ps` |
| Ver erros e logs | `docker compose logs -f web` |
| Reiniciar o sistema | `docker compose restart` |
| Parar o sistema | `docker compose down` |
| Subir novamente | `docker compose up -d` |

---

## Fazer backup manual do banco de dados

```bash
cp data/cqp.db backup_$(date +%Y%m%d).db
```

Esse comando cria uma cópia do banco com a data de hoje no nome.
Guarde esse arquivo em um pen drive ou outro computador.

---

## Algo deu errado?

Antes de entrar em contato com o desenvolvedor, execute:

```bash
docker compose logs web
```

Copie o que aparecer e envie junto com a descrição do problema.
Isso agiliza muito o diagnóstico.
