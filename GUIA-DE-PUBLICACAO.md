# LMG Hub — Publicação e Controle de Acesso

Este guia deixa o LMG Hub no ar com **acesso externo** e **controle de usuários**
(administrador cria operadores; operadores não veem uns aos outros; admin acompanha o uso).

São **duas peças**:

1. **`lmg-auth-worker.js`** — um Worker separado (login, usuários, uso). Não mexe no seu Worker de IA (`mkt-intel-api`), que continua funcionando igual.
2. **`index.html`** — o app, publicado no **Cloudflare Pages**.

> Tempo estimado: ~15 minutos, tudo pelo painel da Cloudflare (sem linha de comando).

---

## Parte 1 — Publicar o Worker de autenticação

### 1.1 Criar o banco de usuários (KV)
1. Painel Cloudflare → **Storage & Databases → KV**.
2. **Create namespace** → nome: `lmg-users` → **Add**.

### 1.2 Criar o Worker
1. **Workers & Pages → Create → Create Worker**.
2. Nome: `lmg-auth` → **Deploy** (aceite o código de exemplo por enquanto).
3. **Edit code** → apague tudo e cole o conteúdo de **`lmg-auth-worker.js`** → **Deploy**.

### 1.3 Vincular o KV e o segredo
No Worker `lmg-auth` → aba **Settings**:
1. **Bindings → Add → KV namespace**
   - Variable name: **`USERS`** (exatamente assim, maiúsculas)
   - KV namespace: `lmg-users` → **Deploy**.
2. **Variables and Secrets → Add → Secret**
   - Name: **`SETUP_SECRET`**
   - Value: uma senha forte sua (ex.: `lmg-2027-#SuaFrase`) — guarde, você usa uma vez só para criar o primeiro admin.
   - **Deploy**.

### 1.4 Anotar a URL do Worker
Fica algo como: `https://lmg-auth.SUACONTA.workers.dev`
Teste abrindo `https://lmg-auth.SUACONTA.workers.dev/status` — deve responder `{"hasUsers":false}`.

---

## Parte 2 — Publicar o app no Cloudflare Pages

1. **Workers & Pages → Create → Pages → Upload assets** (upload direto, sem Git).
2. Nome do projeto: `lmg-hub` → **Create project**.
3. Arraste o arquivo **`index.html`** (pode arrastar a pasta toda) → **Deploy site**.
4. Seu app fica em: `https://lmg-hub.pages.dev` (link público para compartilhar).

> Para atualizar depois: **Pages → lmg-hub → Create deployment** e suba o `index.html` novo.

---

## Parte 3 — Conectar e criar o primeiro administrador

1. Abra `https://lmg-hub.pages.dev`.
2. Na primeira vez ele pede a **URL do servidor** → cole a URL do Worker (Parte 1.4) → **Salvar e conectar**.
   *(Opcional: em vez disso você pode editar no `index.html` a linha `const AUTH_API_DEFAULT = '...'` e já deixar a URL fixa.)*
3. Aparece **Configuração inicial**:
   - **Código de configuração** = o `SETUP_SECRET` que você definiu (Parte 1.3).
   - Usuário e senha do **administrador**.
   - **Criar administrador**.
4. Pronto — você entra como admin. A partir daí o botão de setup some (só funciona uma vez).

---

## Como usar o controle de acesso

- Aba **⚙️ Admin** (só aparece para administradores):
  - **Criar** operadores ou outros admins (login + senha).
  - **⏸ / ▶** ativar/desativar acesso · **🔑** redefinir senha · **🗑** excluir.
  - **Uso da ferramenta**: nº de ações por operador + atividade recente (login, geração de copy/arte, etc.).
- **Operadores** entram com login próprio, **não veem** a aba Admin nem os outros usuários.
- **Sair** (canto superior direito) encerra a sessão.

---

## Segurança — o que este sistema garante

- Senhas guardadas com **hash PBKDF2 + salt** (nunca em texto puro).
- Permissões de administrador são checadas **no servidor** (o Worker), não só na tela — um operador não consegue acessar recursos de admin nem “editando” o navegador.
- Sessões expiram em 7 dias.
- **Importante:** as chaves de IA continuam no seu Worker `mkt-intel-api`. Se quiser que **apenas usuários logados** consumam IA, o próximo passo é o `mkt-intel-api` também exigir o token — me avise que eu adapto.

## Se algo não conectar
- `/status` do Worker não responde → confira se o KV está vinculado como **`USERS`**.
- App diz “não consegui conectar” → confira a URL do Worker (sem barra no fim).
- Erro de CORS no console → o Worker de auth já libera qualquer origem; se aparecer em chamadas de **IA**, me avise para liberar o domínio `pages.dev` no `mkt-intel-api`.
