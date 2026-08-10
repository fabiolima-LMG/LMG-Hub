# LMG Hub

App interno de marketing da LMG (Laser Medical Group): inteligência competitiva,
gerador de assets de campanha e gerador de artes visuais com IA.

## Estrutura

```
lmg-hub/
├── public/
│   └── index.html          ← o app (Cloudflare Pages publica esta pasta)
├── worker/
│   ├── lmg-auth-worker.js  ← Worker de autenticação/usuários (+ geração de imagem IA)
│   └── wrangler.toml       ← config do Worker (produção + homologação)
├── .github/workflows/
│   └── deploy-worker.yml   ← publica o Worker automaticamente via GitHub Actions
├── CHANGELOG.md
└── DEPLOY-TERMINAL.md      ← passo a passo de publicação manual (primeira vez)
```

## Ambientes

| Ambiente     | Branch    | App (Cloudflare Pages)                  | Worker (Cloudflare Workers)              |
|---           |---        |---                                       |---                                        |
| Produção     | `main`    | `lmg-hub.pages.dev`                     | `lmg-auth.<sua-conta>.workers.dev`        |
| Homologação  | `staging` | `staging.lmg-hub.pages.dev` (automático)| `lmg-auth-staging.<sua-conta>.workers.dev`|

Veja `HOMOLOGACAO.md` para o passo a passo completo de configuração (feito uma
única vez) e o fluxo do dia a dia.

## Fluxo do dia a dia

1. Crie uma branch a partir de `staging` (ou trabalhe direto em `staging`) para
   qualquer mudança.
2. `git push` → Cloudflare Pages publica sozinho em
   `staging.lmg-hub.pages.dev`; se a mudança tocou `worker/`, o GitHub Actions
   publica o Worker de homologação.
3. Teste em homologação.
4. Confirmando que está tudo certo, abra um Pull Request de `staging` para
   `main` (ou faça o merge) → publica em produção automaticamente.
5. Registre a mudança em `CHANGELOG.md`.
