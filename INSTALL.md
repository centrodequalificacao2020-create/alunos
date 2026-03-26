# Guia de Instalação — Servidor CQP

Este guia foi escrito para você instalar o sistema CQP no seu servidor sem precisar de conhecimento técnico. Você vai digitar alguns comandos no terminal — nada além disso. Siga os passos na ordem e não pule nenhum.

Se algo não funcionar como descrito, anote o que apareceu na tela e entre em contato com o desenvolvedor antes de tentar qualquer outra coisa.

---

## O que você vai precisar

- O servidor ligado e conectado à internet
- Um segundo computador (notebook ou desktop) na mesma rede
- O arquivo de backup do banco de dados (`.sql`) — fornecido pelo desenvolvedor
- Os arquivos `logo_escola.png` e `assinatura.png` — fornecidos pelo desenvolvedor
- A senha de administrador do servidor (definida durante a instalação do Ubuntu)

---

## Parte 1 — Conectar ao servidor pelo segundo computador

O servidor não precisa de monitor nem teclado para funcionar. Você vai acessá-lo remotamente a partir do seu computador normal, usando um recurso chamado SSH — pense nele como um controle remoto para o servidor.

### 1.1 Descobrir o IP do servidor

Na primeira vez, conecte um monitor e teclado diretamente no servidor. Ligue-o e, quando aparecer o prompt de comando, digite:

```
ip a
```

Procure uma linha com `inet 192.168.1.XX/24`. O número `192.168.1.XX` é o endereço do servidor na sua rede. Anote esse número — você vai usar várias vezes.

Depois disso, pode desconectar o monitor e o teclado. Não serão mais necessários.

### 1.2 Conectar pelo segundo computador

No Windows, abra o terminal: pressione `Win + R`, digite `cmd` e pressione Enter.

Digite o comando abaixo, trocando `192.168.1.XX` pelo IP que você anotou:

```
ssh usuario@192.168.1.XX
```

Na primeira vez, vai aparecer uma pergunta sobre confiar no servidor. Digite `yes` e pressione Enter. Depois informe a senha do servidor. A senha não aparece na tela enquanto você digita — isso é normal.

Se aparecer uma linha como `usuario@servidor:~$`, você está dentro do servidor.

A partir daqui, todos os comandos são digitados nesta janela.

---

## Parte 2 — Instalar o Docker

O Docker é o programa responsável por rodar o sistema CQP. Execute os três comandos abaixo, um de cada vez:

```bash
curl -fsSL https://get.docker.com | sudo sh
```

Este primeiro comando baixa e instala o Docker. Pode demorar alguns minutos.

```bash
sudo usermod -aG docker $USER
```

```bash
newgrp docker
```

Para confirmar que tudo correu bem:

```bash
docker --version
```

Deve aparecer algo como `Docker version 26.x.x`. Se aparecer, pode seguir em frente.

---

## Parte 3 — Configurar acesso ao repositório privado

O código do sistema fica em um repositório privado no GitHub. Para que o servidor consiga baixar esse código sem pedir senha toda vez, vamos criar uma chave de acesso dedicada.

### 3.1 Gerar a chave

```bash
ssh-keygen -t ed25519 -C "cqp-servidor" -f ~/.ssh/cqp_deploy
```

Quando perguntar por uma senha (`Enter passphrase`), pressione Enter duas vezes sem digitar nada.

### 3.2 Exibir a chave pública

```bash
cat ~/.ssh/cqp_deploy.pub
```

Vai aparecer uma linha longa começando com `ssh-ed25519 AAAA...`. Copie essa linha completa e envie para o desenvolvedor.

Aguarde a confirmação do desenvolvedor antes de continuar. Ele precisa cadastrar essa chave no GitHub.

### 3.3 Configurar o SSH para usar a chave

```bash
mkdir -p ~/.ssh && nano ~/.ssh/config
```

Um editor de texto simples vai abrir. Cole o texto abaixo exatamente como está:

```
Host github-cqp
    HostName github.com
    User git
    IdentityFile ~/.ssh/cqp_deploy
    IdentitiesOnly yes
```

Para salvar e sair: pressione `Ctrl + X`, depois `Y`, depois `Enter`.

### 3.4 Testar a conexão

```bash
ssh -T github-cqp
```

Deve aparecer uma mensagem parecida com:
`Hi centrodequalificacao2020-create! You've successfully authenticated...`

Se apareceu, a conexão está funcionando.

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

Vai aparecer uma sequência longa de letras e números. Copie esse valor.

Abra o arquivo de configuração:

```bash
nano .env
```

Substitua o texto `substitua-por-uma-chave-gerada` pela sequência copiada. O arquivo deve ficar assim:

```
FLASK_SECRET_KEY=a1b2c3d4e5f6...  (o seu valor aqui)
FLASK_DEBUG=False
```

Para salvar: `Ctrl + X`, depois `Y`, depois `Enter`.

### 5.2 Restaurar o banco de dados

Crie a pasta onde o banco vai ficar:

```bash
mkdir -p data
```

Abra um **segundo terminal** no Windows (deixe o primeiro aberto) e envie o arquivo `.sql` para o servidor:

```
scp C:\caminho\para\backup.sql usuario@192.168.1.XX:/home/usuario/alunos/data/
```

Troque o caminho pelo local real do arquivo no seu computador e `192.168.1.XX` pelo IP do servidor.

Volte ao terminal conectado ao servidor e execute:

```bash
sqlite3 data/cqp.db < data/backup_cqp.sql
```

### 5.3 Copiar as imagens institucionais

Ainda no terminal do Windows, envie os arquivos de imagem:

```
scp C:\caminho\para\logo_escola.png usuario@192.168.1.XX:/home/usuario/alunos/static/
scp C:\caminho\para\assinatura.png  usuario@192.168.1.XX:/home/usuario/alunos/static/
```

---

## Parte 6 — Subir o sistema

```bash
docker compose up -d
```

Na primeira vez esse comando demora um pouco — ele baixa as imagens necessárias e monta tudo. Aguarde até o prompt `$` aparecer novamente.

Para verificar se está tudo certo:

```bash
docker compose ps
```

Devem aparecer dois itens: `cqp_web` e `cqp_nginx`, ambos com status `Up` ou `healthy`. Se os dois estiverem assim, o sistema está no ar.

Acesse pelo navegador de qualquer computador na mesma rede:

```
http://192.168.1.XX
```

---

## Parte 7 — Iniciar automaticamente com o servidor

O sistema já está configurado para reiniciar sozinho se o Docker cair. Mas é preciso garantir que o Docker em si também inicie junto com o sistema operacional:

```bash
sudo systemctl enable docker
```

Com isso, se o servidor for desligado por queda de energia ou qualquer outro motivo, o sistema CQP volta sozinho quando a máquina ligar de novo.

---

## Parte 8 — Atualizar o sistema no futuro

Quando o desenvolvedor lançar uma atualização, conecte ao servidor via SSH e execute:

```bash
cd alunos
git pull
docker compose up -d --build
```

O sistema é atualizado sem perder nenhum dado. O banco de dados fica separado do código justamente para garantir isso.

---

## Parte 9 — Acesso externo com Cloudflare Tunnel

Esta parte é opcional. Ela permite acessar o sistema de qualquer lugar — celular, casa, outros computadores fora da escola — sem precisar mexer no roteador e com HTTPS automático. O serviço é gratuito.

Antes de começar, você precisa ter:
- Um domínio registrado (ex: `suaescola.com.br`) com o DNS gerenciado pela Cloudflare
- Uma conta na Cloudflare: https://dash.cloudflare.com/sign-up

Se ainda não tem um domínio, fale com o desenvolvedor antes de continuar.

### 9.1 Instalar o cloudflared

```bash
curl -fsSL https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb -o cloudflared.deb
sudo dpkg -i cloudflared.deb
rm cloudflared.deb
```

Confirme a instalação:

```bash
cloudflared --version
```

### 9.2 Autenticar na Cloudflare

Como o servidor não tem navegador, a autenticação funciona assim: o servidor gera um link, você copia e abre no seu computador normal.

No servidor, execute:

```bash
cloudflared tunnel login
```

Vai aparecer um link longo começando com `https://dash.cloudflare.com/argotunnel?...`

Não feche esse terminal. Copie o link, abra no navegador do segundo computador e faça login na sua conta Cloudflare. Selecione o domínio e clique em Authorize.

Volte ao terminal do servidor. Em alguns segundos vai aparecer a confirmação de que o login foi concluído.

### 9.3 Criar o túnel

```bash
cloudflared tunnel create cqp
```

Vai aparecer o ID do túnel, parecido com:

```
Created tunnel cqp with id a1b2c3d4-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

Anote esse ID. Você vai usá-lo no próximo passo.

### 9.4 Criar o arquivo de configuração do túnel

```bash
nano ~/.cloudflared/config.yml
```

Cole o conteúdo abaixo, fazendo as substituições indicadas:

```yaml
tunnel: cqp
credentials-file: /home/USUARIO/.cloudflared/a1b2c3d4-xxxx-xxxx-xxxx-xxxxxxxxxxxx.json

ingress:
  - hostname: sistema.suaescola.com.br
    service: http://localhost:80
  - service: http_status:404
```

Substitua `USUARIO` pelo nome do seu usuário no servidor, o ID pelo que você anotou, e o subdomínio pelo endereço que preferir.

Para salvar: `Ctrl + X`, depois `Y`, depois `Enter`.

### 9.5 Criar o registro DNS

```bash
cloudflared tunnel route dns cqp sistema.suaescola.com.br
```

Troque pelo subdomínio que você usou. Deve aparecer a confirmação de que o registro foi criado.

### 9.6 Ativar o túnel como serviço

```bash
sudo cloudflared service install
sudo systemctl enable cloudflared
sudo systemctl start cloudflared
```

Para confirmar que está rodando:

```bash
sudo systemctl status cloudflared
```

Deve aparecer `active (running)`.

### 9.7 Testar

No celular fora do Wi-Fi da escola, ou em qualquer outro computador, abra o navegador e acesse:

```
https://sistema.suaescola.com.br
```

O sistema deve carregar normalmente com o cadeado de segurança. O HTTPS é configurado automaticamente pela Cloudflare, não é preciso fazer mais nada.

### 9.8 Ajuste final no .env

Com o Cloudflare ativo, certifique-se de que o arquivo `.env` não contém a linha `SESSION_COOKIE_SECURE=False`. Se tiver, remova-a. Depois reinicie:

```bash
cd ~/alunos
docker compose restart
```

---

## Comandos do dia a dia

| Situação | Comando |
|---|---|
| Ver se o sistema está rodando | `docker compose ps` |
| Ver o que está acontecendo | `docker compose logs -f web` |
| Reiniciar o sistema | `docker compose restart` |
| Parar o sistema | `docker compose down` |
| Ligar o sistema novamente | `docker compose up -d` |
| Ver se o túnel Cloudflare está ativo | `sudo systemctl status cloudflared` |
| Reiniciar o túnel Cloudflare | `sudo systemctl restart cloudflared` |

---

## Backup manual do banco de dados

```bash
cp ~/alunos/data/cqp.db ~/backup_$(date +%Y%m%d).db
```

Isso cria um arquivo com a data de hoje no nome. Guarde em um pen drive ou em outro computador.

---

## Algo deu errado?

Antes de entrar em contato com o desenvolvedor, execute:

```bash
docker compose logs web
```

Copie tudo que aparecer e envie junto com a descrição do que aconteceu. Com essa informação o problema é resolvido muito mais rápido.
