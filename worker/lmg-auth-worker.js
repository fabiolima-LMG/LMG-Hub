/**
 * LMG Hub — Authentication, users & usage backend (Cloudflare Worker)
 * ---------------------------------------------------------------------------
 * Deploy this as a SEPARATE Worker from your AI proxy (mkt-intel-api).
 * It never touches your AI code, so your existing worker keeps running as-is.
 *
 * Requires:
 *   • A KV namespace bound as  USERS
 *   • A secret               SETUP_SECRET     (used once to create the first admin)
 *   • A secret               MKT_DELETE_PWD   (the mkt-intel-api Worker's admin password,
 *                                              never exposed to the browser — used server-side
 *                                              only to proxy competitor deletions)
 *
 * Endpoints (all JSON):
 *   GET  /status                      -> { hasUsers }
 *   POST /bootstrap {setupSecret,username,password}  -> first admin only, once
 *   POST /login    {username,password} -> { token, username, role }
 *   POST /logout                       (Bearer)
 *   GET  /me                           (Bearer) -> { username, role }
 *   POST /usage    {action,detail}     (Bearer) log an action for the caller
 *   GET  /users                        (Bearer admin) -> { users:[...] }
 *   POST /users    {username,password,role}   (Bearer admin) create operator/admin
 *   PATCH  /users/:name {active?,role?,password?}  (Bearer admin)
 *   DELETE /users/:name                (Bearer admin)
 *   GET  /usage[?user=x]               (Bearer admin) -> { usage:[...] }
 *   POST /mkt-proxy/delete-competitor {appId,prodId,concId}  (Bearer admin) -> proxies
 *       DELETE to mkt-intel-api using the server-side MKT_DELETE_PWD secret
 *   POST /generate-image {style,tone,extraInstructions,imageSize}  (Bearer) -> { imageUrl }
 *       AI background for Arte Visual — preset styles (abstract/face/clinic/texture)
 *       or free-form (style:'custom', used by the "Em Branco" nominal art type).
 *       Requires a secret  OPENAI_API_KEY  on THIS Worker (separate from any
 *       key on mkt-intel-api) — set it with: npx wrangler secret put OPENAI_API_KEY
 */

const SESSION_TTL = 60 * 60 * 24 * 7; // 7 days
const USAGE_CAP = 500;                 // max stored actions per user

function cors(origin) {
  return {
    'Access-Control-Allow-Origin': origin || '*',
    'Access-Control-Allow-Methods': 'GET,POST,PUT,PATCH,DELETE,OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type, Authorization',
    'Access-Control-Max-Age': '86400',
  };
}
function json(data, status, origin) {
  return new Response(JSON.stringify(data), {
    status: status || 200,
    headers: { 'Content-Type': 'application/json', ...cors(origin) },
  });
}

function bytesToHex(b) { return [...b].map(x => x.toString(16).padStart(2, '0')).join(''); }
function hexToBytes(h) { const a = new Uint8Array(h.length / 2); for (let i = 0; i < a.length; i++) a[i] = parseInt(h.substr(i * 2, 2), 16); return a; }
function randToken() { return bytesToHex(crypto.getRandomValues(new Uint8Array(24))); }

async function hashPw(password, saltHex) {
  const enc = new TextEncoder();
  const salt = saltHex ? hexToBytes(saltHex) : crypto.getRandomValues(new Uint8Array(16));
  const key = await crypto.subtle.importKey('raw', enc.encode(password), 'PBKDF2', false, ['deriveBits']);
  const bits = await crypto.subtle.deriveBits({ name: 'PBKDF2', salt, iterations: 100000, hash: 'SHA-256' }, key, 256);
  return { salt: bytesToHex(salt), hash: bytesToHex(new Uint8Array(bits)) };
}
function safeEq(a, b) { if (a.length !== b.length) return false; let r = 0; for (let i = 0; i < a.length; i++) r |= a.charCodeAt(i) ^ b.charCodeAt(i); return r === 0; }

async function getSession(env, req) {
  const auth = req.headers.get('Authorization') || '';
  const t = auth.startsWith('Bearer ') ? auth.slice(7) : '';
  if (!t) return null;
  const s = await env.USERS.get('session:' + t, 'json');
  return s ? { token: t, ...s } : null;
}

async function logUsage(env, username, action, detail) {
  const key = 'usage:' + username;
  const arr = (await env.USERS.get(key, 'json')) || [];
  arr.push({ ts: Date.now(), action: (action || 'action').toString().slice(0, 40), detail: (detail || '').toString().slice(0, 200) });
  while (arr.length > USAGE_CAP) arr.shift();
  await env.USERS.put(key, JSON.stringify(arr));
}

const cleanUser = (u) => ({ username: u.username, role: u.role, active: u.active, createdAt: u.createdAt, createdBy: u.createdBy, lastLogin: u.lastLogin });

// ─── LMG image prompt builder ────────────────────────────────────────────────
// Used by the dedicated /generate-image route below — covers BOTH the preset
// style backgrounds (Marketing tab: Abstrato/Rosto/Clínica/Textura) and the
// free-form "custom" background (used by the "Em Branco" nominal AI background).
// This replaced calling the shared mkt-intel-api Worker's /generate-image for
// LMG's own Arte Visual, whose base prompt (a) tended to render dark/murky
// scenes and (b) still described the named equipment in its own base prompt
// even when told not to — since the real equipment photo is ALWAYS composited
// on top separately in this app, the model must never invent one of its own.
function buildLmgImagePrompt({ style, tone, extraInstructions }) {
  const BASE =
    'Advertising background plate for LMG, a premium medical-aesthetics equipment brand. ' +
    'COLOR & LIGHT (mandatory): every element must stay clearly visible, well-defined and richly detailed — the specific mood (bright and airy, or dark and cinematic) is set by the SCENE description below, but it must always look deliberate and high-production-value. NEVER muddy, NEVER accidentally underexposed, NEVER a flat undifferentiated black mass — any darkness must be rich, textured and full of visible detail, with light used purposefully to guide the eye. ' +
    'STRICTLY FORBIDDEN OBJECTS (zero exceptions): any machine, device, equipment, apparatus, laser, ultrasound unit, radiofrequency unit, console, screen, monitor, handpiece, applicator, cable, cart, treatment chair, medical chair, aesthetic chair, examination chair, stretcher, bed, or any type of clinical furniture. Do NOT generate, invent, imagine, sketch or hallucinate any version of a medical/aesthetic device or piece of equipment, even a blurred, abstract or partial one — the real product photo is ALWAYS composited on top separately afterwards, so generate ONLY the clean environment, with that area left empty and clean. ' +
    'No text, no letters, no numbers, no logos, no watermarks. ' +
    'Keep the lower third of the composition calmer and cleaner so typography can sit there. ' +
    'QUALITY (mandatory): shot as flagship advertising photography — tack-sharp focus, hyper-detailed materials and textures, rich and believable physical light behavior, subtle natural film grain, professional color grading. Avoid any AI-rendering tells: no waxy or plastic-looking surfaces, no muddy or repetitive textures, no warped geometry, no illegible ghost-text or fake logos, no oversaturated or banding gradients. 8K resolution, cinematic, editorial luxury-magazine advertising quality, the kind of image that would run in a premium print campaign.';

  const STYLES = {
    abstract:
      'SCENE: elegant abstract art — flowing translucent 3D ribbons and waves of glass and liquid, luminous particles and soft light streaks over a bright, well-lit graphite-to-soft-neutral gradient, crisp refractions and caustics where the glass catches the light. COLOR ACCENT (mandatory): weave the LMG brand orange (#E96624) through the composition as glowing light streaks, luminous particle highlights and soft warm color washes — orange must read as a clear, deliberate accent color throughout, not just a hint. Luminous, airy and alive, never dark or flat black.',
    face:
      'SCENE: high-end editorial beauty portrait of a flawless female model, porcelain retouched skin with radiant glow, serene confident expression, Vogue-cover standard, studio beauty-dish key light with soft rim light and delicate catchlights, bright well-lit backdrop, hyper-realistic skin texture with visible pores and natural highlights (not airbrushed to plastic), pin-sharp eyes, shallow depth of field.',
    clinic:
      'SCENE: a "clinic of the future" — an empty, ultra-modern, minimalist medical-aesthetic interior set slightly ahead of its time: sleek curved architecture, dark graphite and matte-black surfaces, deep charcoal walls and floors. COLOR & LIGHT (mandatory): predominantly DARK and moody — the space reads as a dim, sophisticated night interior — lit almost entirely by dramatic orange (#E96624) accent lighting: glowing orange light lines recessed into walls, floors and ceiling edges, backlit orange-rimmed panels, a soft orange volumetric glow cutting through the darkness. Clean geometric lines, minimal and uncluttered, premium sci-fi-inspired forms, ultra-futuristic. NO people, NO human figures, NO silhouettes anywhere in the frame — the space is completely empty. No visible screens, monitors or tech readouts. Cinematic, moody, high-contrast, editorial luxury quality — the kind of dark, dramatic interior shot used in a premium tech or automotive campaign.',
    texture:
      'SCENE: abstract luxury texture — a dark graphite and matte-black surface with fine metallic grain, softly catching dramatic orange (#E96624) rim light and glowing orange light streaks cutting across the frame, luminous orange particles suspended in darkness. Clean, minimal, ultra-futuristic and sophisticated — moody and cinematic rather than bright, with rich micro-detail visible up close where the orange light hits the surface. NO people, NO equipment, NO recognizable objects — pure abstract dark texture with orange light accents, premium editorial feel of a high-end tech or automotive campaign.',
  };

  const TONES = {
    'Científico': 'Mood: precise, clinical elegance — subtle glass and crystal elements, laboratory-grade cleanliness.',
    'Aspiracional': 'Mood: aspirational and dreamy — soft glow, gentle depth of field.',
    'Consultivo': 'Mood: calm, trustworthy, welcoming.',
  };

  // "custom" (free-form designer prompt, used by the "Em Branco" nominal AI
  // background) — the designer's own description is the authoritative brief;
  // no clinic/color base is forced on top of it. Brightness and the no-equipment
  // rule still apply since those are compositing/visibility requirements, not
  // style preferences.
  if (style === 'custom') {
    const FREE_BASE =
      'Advertising background plate for LMG, a premium medical-aesthetics equipment brand. ' +
      'Render EXACTLY the scene the designer describes below — their description is the authoritative creative brief and takes priority over any default style, color palette or mood; do not force any particular look onto it unless the designer explicitly asks for that. ' +
      'Unless the brief explicitly calls for a dark or night scene, keep the image clearly bright, well-lit and visible at a glance — avoid a murky or underexposed result. ' +
      'STRICTLY FORBIDDEN, even in this free-form brief, unless the designer explicitly asks for one: any medical/aesthetic machine, device, equipment, apparatus, laser, console, screen, monitor, handpiece, cable, cart, treatment chair, medical chair, stretcher, bed, or medical product of any kind — the real product photo is composited on top separately, so never invent one. ' +
      'No text, no letters, no numbers, no logos, no watermarks anywhere in the image — those are added later by the app. ' +
      'QUALITY (mandatory): tack-sharp focus, hyper-detailed materials and textures, believable physical light behavior, professional color grading. Avoid AI-rendering tells — no waxy or plastic-looking surfaces, no warped geometry, no illegible ghost-text or fake logos, no oversaturated or banding gradients. ' +
      '8K, high production value, photographic or illustrative quality matching whatever the brief calls for — the kind of image that would run in a premium print campaign.';
    let p = FREE_BASE;
    if (extraInstructions) p += '\n\nDESIGNER\'S BRIEF (follow this precisely, it is the source of truth for the scene): ' + String(extraInstructions).slice(0, 1800);
    return p;
  }

  let p = BASE + ' ' + (STYLES[style] || STYLES.abstract);
  if (TONES[tone]) p += ' ' + TONES[tone];
  if (extraInstructions) p += ' EXTRA INSTRUCTIONS FROM THE DESIGNER: ' + String(extraInstructions).slice(0, 900);
  return p;
}

export default {
  async fetch(req, env) {
    const url = new URL(req.url);
    const origin = req.headers.get('Origin');
    const path = url.pathname.replace(/\/+$/, '') || '/';
    if (req.method === 'OPTIONS') return new Response(null, { status: 204, headers: cors(origin) });
    if (!env.USERS) return json({ error: 'KV namespace "USERS" não está vinculada ao Worker.' }, 500, origin);

    try {
      // ---- status ----
      if (path === '/status' && req.method === 'GET') {
        const list = await env.USERS.list({ prefix: 'user:', limit: 1 });
        return json({ hasUsers: list.keys.length > 0 }, 200, origin);
      }

      // ---- bootstrap first admin (once) ----
      if (path === '/bootstrap' && req.method === 'POST') {
        const list = await env.USERS.list({ prefix: 'user:', limit: 1 });
        if (list.keys.length > 0) return json({ error: 'Já existe usuário — bootstrap desabilitado.' }, 403, origin);
        const { setupSecret, username, password } = await req.json();
        if (!env.SETUP_SECRET || setupSecret !== env.SETUP_SECRET) return json({ error: 'Código de configuração inválido.' }, 403, origin);
        if (!username || !password || password.length < 6) return json({ error: 'Usuário e senha (mín. 6 caracteres) obrigatórios.' }, 400, origin);
        const { salt, hash } = await hashPw(password);
        await env.USERS.put('user:' + username, JSON.stringify({ username, role: 'admin', salt, hash, active: true, createdAt: Date.now(), createdBy: 'bootstrap', lastLogin: Date.now() }));
        const tk = randToken();
        await env.USERS.put('session:' + tk, JSON.stringify({ username, role: 'admin' }), { expirationTtl: SESSION_TTL });
        await logUsage(env, username, 'bootstrap', '');
        return json({ token: tk, username, role: 'admin' }, 200, origin);
      }

      // ---- login ----
      if (path === '/login' && req.method === 'POST') {
        const { username, password } = await req.json();
        const u = await env.USERS.get('user:' + username, 'json');
        if (!u || !u.active) return json({ error: 'Usuário ou senha inválidos.' }, 401, origin);
        const { hash } = await hashPw(password, u.salt);
        if (!safeEq(hash, u.hash)) return json({ error: 'Usuário ou senha inválidos.' }, 401, origin);
        const tk = randToken();
        await env.USERS.put('session:' + tk, JSON.stringify({ username, role: u.role }), { expirationTtl: SESSION_TTL });
        u.lastLogin = Date.now();
        await env.USERS.put('user:' + username, JSON.stringify(u));
        await logUsage(env, username, 'login', '');
        return json({ token: tk, username, role: u.role }, 200, origin);
      }

      const session = await getSession(env, req);

      // ---- me ----
      if (path === '/me' && req.method === 'GET') {
        if (!session) return json({ error: 'unauth' }, 401, origin);
        return json({ username: session.username, role: session.role }, 200, origin);
      }
      // ---- logout ----
      if (path === '/logout' && req.method === 'POST') {
        if (session) await env.USERS.delete('session:' + session.token);
        return json({ ok: true }, 200, origin);
      }
      // ---- usage log (any authenticated user) ----
      if (path === '/usage' && req.method === 'POST') {
        if (!session) return json({ error: 'unauth' }, 401, origin);
        const { action, detail } = await req.json();
        await logUsage(env, session.username, action, detail);
        return json({ ok: true }, 200, origin);
      }

      const isAdmin = session && session.role === 'admin';

      // ---- shared photo library (any authenticated user reads; admin writes) ----
      if (path === '/photos' && req.method === 'GET') {
        if (!session) return json({ error: 'unauth' }, 401, origin);
        const logo = await env.USERS.get('photo:logo');
        const list = await env.USERS.list({ prefix: 'photo:equip:' });
        const equip = {};
        for (const k of list.keys) {
          const name = decodeURIComponent(k.name.slice('photo:equip:'.length));
          const val = await env.USERS.get(k.name);
          if (val) equip[name] = val;
        }
        return json({ logo: logo || null, equip }, 200, origin);
      }
      if (path === '/photos/logo' && req.method === 'PUT') {
        if (!isAdmin) return json({ error: 'forbidden' }, 403, origin);
        const { b64 } = await req.json();
        if (!b64) return json({ error: 'b64 obrigatório.' }, 400, origin);
        if (b64.length > 3 * 1024 * 1024) return json({ error: 'Logo muito grande.' }, 400, origin);
        await env.USERS.put('photo:logo', b64);
        await logUsage(env, session.username, 'upload_logo', '');
        return json({ ok: true }, 200, origin);
      }
      if (path === '/photos/logo' && req.method === 'DELETE') {
        if (!isAdmin) return json({ error: 'forbidden' }, 403, origin);
        await env.USERS.delete('photo:logo');
        await logUsage(env, session.username, 'remove_logo', '');
        return json({ ok: true }, 200, origin);
      }
      if (path === '/photos/equip' && req.method === 'PUT') {
        if (!isAdmin) return json({ error: 'forbidden' }, 403, origin);
        const { name, b64 } = await req.json();
        if (!name || !b64) return json({ error: 'name e b64 obrigatórios.' }, 400, origin);
        if (b64.length > 2.5 * 1024 * 1024) return json({ error: 'Foto muito grande (máx ~1.5MB).' }, 400, origin);
        await env.USERS.put('photo:equip:' + encodeURIComponent(name), b64);
        await logUsage(env, session.username, 'upload_equip_photo', name);
        return json({ ok: true }, 200, origin);
      }
      if (path.startsWith('/photos/equip/') && req.method === 'DELETE') {
        if (!isAdmin) return json({ error: 'forbidden' }, 403, origin);
        const name = decodeURIComponent(path.slice('/photos/equip/'.length));
        await env.USERS.delete('photo:equip:' + encodeURIComponent(name));
        await logUsage(env, session.username, 'remove_equip_photo', name);
        return json({ ok: true }, 200, origin);
      }

      // ---- hidden built-in competitors / MKT Intel benchmark (any authenticated user reads; admin writes) ----
      if (path === '/hidden-concs' && req.method === 'GET') {
        if (!session) return json({ error: 'unauth' }, 401, origin);
        const data = (await env.USERS.get('hiddenconcs', 'json')) || {};
        return json({ hidden: data }, 200, origin);
      }
      if (path === '/hidden-concs' && req.method === 'PUT') {
        if (!isAdmin) return json({ error: 'forbidden' }, 403, origin);
        const { prodId, name } = await req.json();
        if (!prodId || !name) return json({ error: 'prodId e name obrigatórios.' }, 400, origin);
        const data = (await env.USERS.get('hiddenconcs', 'json')) || {};
        if (!data[prodId]) data[prodId] = [];
        if (!data[prodId].includes(name)) data[prodId].push(name);
        await env.USERS.put('hiddenconcs', JSON.stringify(data));
        await logUsage(env, session.username, 'hide_competitor', prodId + ' / ' + name);
        return json({ ok: true }, 200, origin);
      }
      if (path === '/hidden-concs' && req.method === 'DELETE') {
        if (!isAdmin) return json({ error: 'forbidden' }, 403, origin);
        const { prodId, name } = await req.json();
        if (!prodId || !name) return json({ error: 'prodId e name obrigatórios.' }, 400, origin);
        const data = (await env.USERS.get('hiddenconcs', 'json')) || {};
        if (data[prodId]) data[prodId] = data[prodId].filter(n => n !== name);
        await env.USERS.put('hiddenconcs', JSON.stringify(data));
        await logUsage(env, session.username, 'restore_competitor', prodId + ' / ' + name);
        return json({ ok: true }, 200, origin);
      }

      // ---- product field overrides (cat/segment corrections) — any authenticated user reads; admin writes ----
      if (path === '/product-overrides' && req.method === 'GET') {
        if (!session) return json({ error: 'unauth' }, 401, origin);
        const data = (await env.USERS.get('productoverrides', 'json')) || {};
        return json({ overrides: data }, 200, origin);
      }
      if (path === '/product-overrides' && req.method === 'PUT') {
        if (!isAdmin) return json({ error: 'forbidden' }, 403, origin);
        const { prodId, cat, segment } = await req.json();
        if (!prodId) return json({ error: 'prodId obrigatório.' }, 400, origin);
        const data = (await env.USERS.get('productoverrides', 'json')) || {};
        data[prodId] = { cat: (cat || '').toString().slice(0, 80), segment: (segment || '').toString().slice(0, 120) };
        await env.USERS.put('productoverrides', JSON.stringify(data));
        await logUsage(env, session.username, 'edit_product_segment', prodId);
        return json({ ok: true }, 200, origin);
      }
      if (path.startsWith('/product-overrides/') && req.method === 'DELETE') {
        if (!isAdmin) return json({ error: 'forbidden' }, 403, origin);
        const prodId = decodeURIComponent(path.slice('/product-overrides/'.length));
        const data = (await env.USERS.get('productoverrides', 'json')) || {};
        delete data[prodId];
        await env.USERS.put('productoverrides', JSON.stringify(data));
        await logUsage(env, session.username, 'reset_product_segment', prodId);
        return json({ ok: true }, 200, origin);
      }

      // ---- AI background image (any authenticated user) ----
      // Dedicated to LMG's own OpenAI key so the app has full control over the
      // prompt — unlike mkt-intel-api's /generate-image (previously used by all
      // of Arte Visual), which always prepends its own clinic/equipment base
      // prompt: that made scenes come out dark/murky and, since its base prompt
      // describes the named equipment itself, it could still render a device
      // even when told not to. Covers both preset styles (Marketing tab) and
      // the free-form "custom" background (the "Em Branco" nominal AI fundo).
      if (path === '/generate-image' && req.method === 'POST') {
        if (!session) return json({ error: 'unauth' }, 401, origin);
        if (!env.OPENAI_API_KEY) return json({ error: 'OPENAI_API_KEY não configurada no Worker lmg-auth. Rode: npx wrangler secret put OPENAI_API_KEY' }, 500, origin);
        const { style, tone, extraInstructions, imageSize } = await req.json();
        const ALLOWED_SIZES = ['1024x1024', '1536x1024', '1024x1536'];
        const size = ALLOWED_SIZES.includes(imageSize) ? imageSize : '1024x1024';
        const prompt = buildLmgImagePrompt({ style, tone, extraInstructions });
        try {
          const oa = await fetch('https://api.openai.com/v1/images/generations', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + env.OPENAI_API_KEY },
            body: JSON.stringify({ model: 'gpt-image-1', prompt, size, quality: 'high', n: 1 }),
          });
          const data = await oa.json();
          if (!oa.ok) return json({ error: (data.error && data.error.message) || 'Erro na OpenAI.' }, 502, origin);
          const b64 = data.data && data.data[0] && data.data[0].b64_json;
          if (!b64) return json({ error: 'OpenAI não retornou imagem.' }, 502, origin);
          await logUsage(env, session.username, 'generate_image', style || 'abstract');
          return json({ success: true, imageUrl: 'data:image/png;base64,' + b64 }, 200, origin);
        } catch (e) {
          return json({ error: 'Erro ao contatar a OpenAI: ' + String((e && e.message) || e) }, 502, origin);
        }
      }

      // ---- proxy: delete a competitor on mkt-intel-api using the server-side password (admin) ----
      if (path === '/mkt-proxy/delete-competitor' && req.method === 'POST') {
        if (!isAdmin) return json({ error: 'forbidden' }, 403, origin);
        if (!env.MKT_DELETE_PWD) return json({ error: 'MKT_DELETE_PWD não configurado no Worker.' }, 500, origin);
        const { appId, prodId, concId } = await req.json();
        if (!appId || !prodId || !concId) return json({ error: 'appId, prodId e concId obrigatórios.' }, 400, origin);
        try {
          const upstream = await fetch(
            `https://mkt-intel-api.lmglasers.workers.dev/competitors/${encodeURIComponent(appId)}/${encodeURIComponent(concId)}?prod=${encodeURIComponent(prodId)}`,
            { method: 'DELETE', headers: { 'Content-Type': 'application/json', 'X-Admin-Password': env.MKT_DELETE_PWD } }
          );
          const data = await upstream.json();
          await logUsage(env, session.username, 'delete_competitor', appId + '/' + prodId + '/' + concId);
          return json(data, upstream.status, origin);
        } catch (e) {
          return json({ error: 'Erro ao contatar mkt-intel-api.' }, 502, origin);
        }
      }

      // ---- list users (admin) ----
      if (path === '/users' && req.method === 'GET') {
        if (!isAdmin) return json({ error: 'forbidden' }, 403, origin);
        const list = await env.USERS.list({ prefix: 'user:' });
        const users = [];
        for (const k of list.keys) { const u = await env.USERS.get(k.name, 'json'); if (u) users.push(cleanUser(u)); }
        users.sort((a, b) => (a.createdAt || 0) - (b.createdAt || 0));
        return json({ users }, 200, origin);
      }
      // ---- create user (admin) ----
      if (path === '/users' && req.method === 'POST') {
        if (!isAdmin) return json({ error: 'forbidden' }, 403, origin);
        const { username, password, role } = await req.json();
        if (!username || !password || password.length < 6) return json({ error: 'Usuário e senha (mín. 6 caracteres) obrigatórios.' }, 400, origin);
        if (await env.USERS.get('user:' + username)) return json({ error: 'Este usuário já existe.' }, 409, origin);
        const { salt, hash } = await hashPw(password);
        await env.USERS.put('user:' + username, JSON.stringify({ username, role: role === 'admin' ? 'admin' : 'operator', salt, hash, active: true, createdAt: Date.now(), createdBy: session.username, lastLogin: null }));
        await logUsage(env, session.username, 'create_user', username);
        return json({ ok: true }, 200, origin);
      }
      // ---- update / delete user (admin) ----
      if (path.startsWith('/users/') && (req.method === 'PATCH' || req.method === 'DELETE')) {
        if (!isAdmin) return json({ error: 'forbidden' }, 403, origin);
        const uname = decodeURIComponent(path.slice('/users/'.length));
        const u = await env.USERS.get('user:' + uname, 'json');
        if (!u) return json({ error: 'Usuário não encontrado.' }, 404, origin);
        if (req.method === 'DELETE') {
          if (uname === session.username) return json({ error: 'Você não pode excluir a si mesmo.' }, 400, origin);
          await env.USERS.delete('user:' + uname);
          await env.USERS.delete('usage:' + uname);
          await logUsage(env, session.username, 'delete_user', uname);
          return json({ ok: true }, 200, origin);
        }
        const body = await req.json();
        if (typeof body.active === 'boolean') {
          if (uname === session.username && !body.active) return json({ error: 'Você não pode desativar a si mesmo.' }, 400, origin);
          u.active = body.active;
        }
        if (body.role === 'admin' || body.role === 'operator') u.role = body.role;
        if (body.password) { if (body.password.length < 6) return json({ error: 'Senha deve ter no mínimo 6 caracteres.' }, 400, origin); const h = await hashPw(body.password); u.salt = h.salt; u.hash = h.hash; }
        await env.USERS.put('user:' + uname, JSON.stringify(u));
        await logUsage(env, session.username, 'update_user', uname);
        return json({ ok: true }, 200, origin);
      }
      // ---- usage feed (admin) ----
      if (path === '/usage' && req.method === 'GET') {
        if (!isAdmin) return json({ error: 'forbidden' }, 403, origin);
        const who = url.searchParams.get('user');
        let entries = [];
        if (who) {
          const arr = (await env.USERS.get('usage:' + who, 'json')) || [];
          entries = arr.map(e => ({ ...e, username: who }));
        } else {
          const list = await env.USERS.list({ prefix: 'usage:' });
          for (const k of list.keys) {
            const uname = k.name.slice('usage:'.length);
            const arr = (await env.USERS.get(k.name, 'json')) || [];
            arr.forEach(e => entries.push({ ...e, username: uname }));
          }
        }
        entries.sort((a, b) => b.ts - a.ts);
        return json({ usage: entries.slice(0, 300) }, 200, origin);
      }

      return json({ error: 'not found' }, 404, origin);
    } catch (e) {
      return json({ error: String((e && e.message) || e) }, 500, origin);
    }
  },
};
