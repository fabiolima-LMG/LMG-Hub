# Homologação (staging) + versionamento — configuração (uma vez só)

Isso monta dois ambientes completos e separados:

| | Produção | Homologação |
|---|---|---|
| Branch | `main` | `staging` |
| App (Pages) | `lmg-hub.pages.dev` | `staging.lmg-hub.pages.dev` |
| Worker | `lmg-auth` | `lmg-auth-staging` |
| Banco de usuários (KV) | um | outro, separado |

Homologação usa **dados totalmente separados** de produção — pode criar
usuário de teste, gerar artes de teste etc. sem afetar quem usa o app de
verdade.

Todos os comandos abaixo rodam no seu terminal (Mac). Sempre que eu pedir para
colar algo sensível (token, senha), você mesmo cola direto no terminal — eu
nunca peço para colar isso no chat.

---

## 1. Subir o código para o GitHub

Se ainda não tem um repositório para este projeto:

1. Crie um repositório novo (privado) em https://github.com/new — nome
   sugerido: `lmg-hub`. **Não** marque "Add a README" (para não conflitar).
2. No terminal, na pasta do projeto que você recebeu de mim:
   ```
   cd caminho/para/lmg-hub
   git remote add origin https://github.com/SEU-USUARIO/lmg-hub.git
   git push -u origin main
   ```
3. Crie a branch de homologação e envie também:
   ```
   git checkout -b staging
   git push -u origin staging
   ```

A partir de agora, todo `git add` + `git commit` + `git push` fica registrado
no histórico do GitHub — é o seu versionamento.

## 2. Conectar o Cloudflare Pages ao GitHub

1. Painel Cloudflare → **Workers & Pages → Create → Pages → Connect to Git**.
2. Escolha o repositório `lmg-hub`.
3. Configuração do build:
   - **Production branch:** `main`
   - **Build command:** deixe em branco (é HTML estático)
   - **Build output directory:** `public`
4. **Save and Deploy.**

Pronto — a partir de agora:
- push/merge em **`main`** → publica sozinho em produção (`lmg-hub.pages.dev`).
- push em **`staging`** (ou qualquer outra branch) → Cloudflare cria
  automaticamente uma URL de preview, e como o nome da branch é `staging`,
  ela fica em **`staging.lmg-hub.pages.dev`**. Nenhum comando manual — é o
  recurso nativo do Cloudflare Pages.

## 3. Criar o Worker de homologação (`lmg-auth-staging`)

No terminal:
```
cd worker
npx wrangler kv namespace create USERS --env staging
```
Copia o `id` que aparece e cola em `worker/wrangler.toml`, no lugar de
`COLE_AQUI_O_ID_DO_KV_STAGING`.

Defina o segredo de configuração do ambiente de staging (pode ser um valor
diferente do de produção):
```
npx wrangler secret put SETUP_SECRET --env staging
```

Se o gerador de imagem com IA também for usado em homologação, defina a
chave da OpenAI nesse ambiente também:
```
npx wrangler secret put OPENAI_API_KEY --env staging
```

Publique manualmente essa primeira vez (depois o GitHub Actions cuida disso):
```
npx wrangler deploy --env staging
cd ..
```
Confirme testando `https://lmg-auth-staging.SUACONTA.workers.dev/status`.

## 4. Automatizar o deploy do Worker (GitHub Actions)

O repositório já vem com `.github/workflows/deploy-worker.yml` configurado:
push em `main` publica o Worker de produção, push em `staging` publica o de
homologação. Falta só autorizar o GitHub a publicar por você:

1. Crie um token da API Cloudflare: painel Cloudflare → ícone de perfil →
   **My Profile → API Tokens → Create Token** → template **"Edit Cloudflare
   Workers"** → gere e copie o token (só aparece uma vez).
2. Pegue seu **Account ID**: painel Cloudflare → qualquer domínio/Workers →
   fica no canto direito da tela.
3. No GitHub: seu repositório → **Settings → Secrets and variables →
   Actions → New repository secret** → crie dois:
   - `CLOUDFLARE_API_TOKEN` = o token do passo 1
   - `CLOUDFLARE_ACCOUNT_ID` = o id do passo 2

Pronto. Da próxima vez que algo em `worker/` mudar e for enviado via
`git push`, o GitHub publica sozinho.

---

## Fluxo do dia a dia (depois de configurado)

```
git checkout staging
# ... eu edito o app/worker, ou você pede uma mudança ...
git add -A
git commit -m "descrição da mudança"
git push
```
→ confira em `staging.lmg-hub.pages.dev` (e no Worker de staging, se mexeu
em `worker/`).

Quando estiver aprovado:
```
git checkout main
git merge staging
git push
```
→ publica em produção automaticamente. Registre a mudança em
`CHANGELOG.md` antes do merge.

## Se algo não conectar
- Preview de staging não atualiza → confira em Cloudflare Pages → aba
  **Deployments** se o build rodou e qual branch ele pegou.
- Worker de staging não publica sozinho → confira a aba **Actions** do
  GitHub (mostra o log do que rodou/falhou) e os dois secrets do passo 4.
- App de homologação não conecta no Worker → confira se `AUTH_API_STAGING`
  em `public/index.html` bate com a URL real do `lmg-auth-staging`.
