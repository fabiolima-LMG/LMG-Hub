# Changelog

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/).
Cada entrada indica se a mudança tocou o **App** (`public/index.html`) e/ou o
**Worker** (`worker/lmg-auth-worker.js`).

## [Unreleased]

## [1.0.0] - 2026-08-10
### Alterado
- **App** — Redesign completo do chrome/UI do LMG Hub com base na identidade
  visual real da LMG: paleta de cor (`#1E1E1E`/`#2B2B2B`/laranja `#E96624`),
  tipografia Roboto no lugar de Inter, cantos retos (4px), ícones de linha
  substituindo emojis na navegação, tela de login, painel Admin e Gerador de
  Assets. Nenhuma funcionalidade do gerador foi alterada nesta mudança.
- **App/Worker** — Estilos de fundo com IA "Lifestyle Clínica" e "Textura
  Luxury": removidas pessoas e equipamentos, tom mais escuro/cinematográfico
  com luzes laranja, visual ultra futurista.
- **App** — Estilos "Abstrato" e "Lifestyle Clínica" agora sempre usam tons de
  laranja da marca.
- **App** — Fundos gerados por IA mais claros/visíveis por padrão (exceto nos
  estilos escuros acima, que são propositalmente escuros).
- **App** — Nunca simular equipamento nas imagens geradas por IA.
- **App** — Estilo "Clínica" reescrito para "clínica do futuro" — mais
  futurista; prompts de imagem revisados para maior qualidade geral.
- **App** — Fontes reais do site institucional (Roboto) incorporadas nas
  artes geradas; seletor de fonte por arte (Montserrat/Poppins/Roboto para
  título, Roboto/Open Sans para corpo).
- **App** — Novo campo "Prompt Próprio" no fluxo principal de Arte Visual
  (gerar o fundo com um prompt livre, antes só existia no fluxo Nominal).
- **Worker** — Nova rota `/generate-image` dedicada no Worker `lmg-auth`
  (a geração de imagem deixou de depender do Worker compartilhado
  `mkt-intel-api`); qualidade da OpenAI elevada para `high`.

## [0.1.0] — baseline
- Estado do app antes do início do versionamento formal (histórico anterior
  não documentado retroativamente).

[Unreleased]: #
[1.0.0]: #
