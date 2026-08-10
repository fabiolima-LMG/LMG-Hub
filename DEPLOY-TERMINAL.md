# Publicar o LMG Hub pelo terminal (wrangler) — primeira vez / produção

> A partir de agora o projeto é versionado em Git e tem um ambiente de
> homologação separado — veja **`HOMOLOGACAO.md`** para o fluxo do dia a dia
> (branch `staging` → testa → merge em `main` → produção). Este arquivo aqui é
> o passo a passo manual de referência, útil na primeira configuração ou se
> precisar publicar manualmente.

Todos os comandos rodam **no seu computador**, no seu terminal (Mac, Linux ou
Windows PowerShell). É lá que você faz login na sua conta Cloudflare — eu nunca
vejo suas credenciais. Vá colando a saída de cada passo aqui no chat que eu te
ajudo se algo travar.

## 0. Estrutura da pasta
```
lmg-hub/
├─ worker/
│  ├─ lmg-auth-worker.js
│  └─ wrangler.toml
└─ public/
   └─ index.html
```
Precisa ter **Node.js** instalado (https://nodejs.org). Depois, no terminal:
```
cd caminho/para/lmg-hub
```

## 1. Login na Cloudflare
```
npx wrangler login
```
Abre o navegador → autorize. (Se aparecer para instalar o wrangler, aceite.)

## 2. Criar o banco de usuários (KV) — produção
```
cd worker
npx wrangler kv namespace create USERS
```
Vai imprimir algo como:
```
[[kv_namespaces]]
binding = "USERS"
id = "abc123...."
```
**Copie esse `id`** e cole no `worker/wrangler.toml`, no lugar de
`COLE_AQUI_O_ID_DO_KV_PRODUCAO`.

## 3. Definir o código secreto de configuração
```
npx wrangler secret put SETUP_SECRET
```
Ele pede o valor → digite uma senha forte sua (você usa uma vez só, para criar o
primeiro admin) e Enter. **Guarde esse valor.**

## 4. Publicar o Worker de autenticação (ainda dentro de `worker/`)
```
npx wrangler deploy
```
No fim aparece a URL, algo como:
```
https://lmg-auth.SUACONTA.workers.dev
```
**Copie essa URL.** Teste abrindo `.../status` no navegador → deve responder
`{"hasUsers":false}`.

## 5. Fixar a URL no app
Abra `public/index.html`, procure `AUTH_API_PROD` e `AUTH_API_STAGING` (perto
do fim do arquivo) e confirme que apontam para as URLs certas dos seus dois
Workers (produção e homologação).

## 6. Publicar o app no Cloudflare Pages (volte para a raiz do projeto)
```
cd ..
npx wrangler pages deploy public --project-name lmg-hub
```
Na primeira vez ele cria o projeto. No fim aparece a URL pública:
```
https://lmg-hub.pages.dev
```
Esse é o link para compartilhar.

> Depois que conectar o repositório ao Cloudflare Pages via Git (ver
> `HOMOLOGACAO.md`), você não precisa mais rodar este comando manualmente —
> basta dar `git push`.

## 7. Criar o primeiro administrador
1. Abra `https://lmg-hub.pages.dev`.
2. Em **Configuração inicial**: informe o `SETUP_SECRET` (passo 3) + usuário e
   senha do admin → **Criar administrador**.

Pronto. Depois é só usar a aba **Admin** para criar operadores.

---

## Atualizar manualmente (sem Git, se precisar)
- **Mudou o app (`public/index.html`):** `npx wrangler pages deploy public --project-name lmg-hub`
- **Mudou o Worker (`worker/lmg-auth-worker.js`):** dentro de `worker/`, `npx wrangler deploy`

## Comandos úteis (dentro de `worker/`)
- Ver usuários no KV: `npx wrangler kv key list --binding USERS` (precisa do id no toml)
- Trocar o SETUP_SECRET: `npx wrangler secret put SETUP_SECRET`
- Ver logs do Worker ao vivo: `npx wrangler tail lmg-auth`
