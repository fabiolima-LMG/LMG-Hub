#!/usr/bin/env python3
"""Build LMG Hub: merge lmg_intel_v4.html + lmg_asset_generator_v9.html into index.html"""

import re

INTEL_FILE = '/root/.claude/uploads/2ed4a71b-8a9d-5c7d-82c8-82a9d223c399/0d12ac94-lmg_intel_v4.html'
ASSETS_FILE = '/root/.claude/uploads/2ed4a71b-8a9d-5c7d-82c8-82a9d223c399/3319c069-lmg_asset_generator_v9.html'
OUTPUT_FILE = '/home/claude/lmg-hub/index.html'

with open(INTEL_FILE, 'r') as f:
    intel_lines = f.readlines()

with open(ASSETS_FILE, 'r') as f:
    assets_lines = f.readlines()

intel_src = ''.join(intel_lines)
assets_src = ''.join(assets_lines)

# ─── EXTRACT INTEL PARTS ───────────────────────────────────────────────────

# CSS: lines 19-234 (0-indexed: 18-233) → all <style> content minus first root/body lines
# line 9 is `:root{`, line 19 is `html,body{...}`, line 21 is `/* LAYOUT */`
# We want lines 21 onwards (layout+) through line 233 (end of </style>)
# The global modal CSS is lines 199-233 (0-indexed 198-232)

# Extract full style block from intel
intel_style_match = re.search(r'<style>(.*?)</style>', intel_src, re.DOTALL)
intel_style = intel_style_match.group(1)

# Split intel CSS into sections
# Global @keyframes b line
intel_keyframes_b = '@keyframes b{0%,80%,100%{transform:translateY(0);opacity:.4}40%{transform:translateY(-5px);opacity:1}}'

# Modal CSS (keep global) - lines 199-233
modal_css_match = re.search(r'/\* MODAL \*/(.*?)$', intel_style, re.DOTALL)
modal_css = ''
if modal_css_match:
    modal_css = '/* MODAL */\n' + modal_css_match.group(1).strip()

# Get everything from /* LAYOUT */ to just before @keyframes b
# and from @keyframes b to just before /* MODAL */
layout_section = re.search(r'/\* LAYOUT \*/(.*?)@keyframes b', intel_style, re.DOTALL)
layout_css_raw = ''
if layout_section:
    layout_css_raw = layout_section.group(1)

# Responsive block and competitor management are part of non-modal CSS
# Get all CSS from /* LAYOUT */ to the end of /* COMPETITOR MANAGEMENT */ section (before /* MODAL */)
non_modal_match = re.search(r'/\* LAYOUT \*/(.*?)/\* MODAL \*/', intel_style, re.DOTALL)
non_modal_css_raw = ''
if non_modal_match:
    non_modal_css_raw = non_modal_match.group(1).strip()

# Scope all non-modal intel CSS under #panel-intel
# We need to prefix each CSS rule with #panel-intel
# Rules are either selectors { ... } or @media { ... }
def scope_css(css_text, prefix):
    """Add prefix to CSS selectors, preserving @keyframes and @media."""
    result = []
    i = 0
    text = css_text

    # Process line by line for comments and rules
    # Use a simple approach: find all top-level blocks
    out = []
    pos = 0
    while pos < len(text):
        # Skip whitespace
        if text[pos] in ' \t\n\r':
            out.append(text[pos])
            pos += 1
            continue

        # Comment
        if text[pos:pos+2] == '/*':
            end = text.find('*/', pos+2)
            if end == -1:
                out.append(text[pos:])
                break
            out.append(text[pos:end+2])
            pos = end + 2
            continue

        # @keyframes - keep as-is
        if text[pos:].startswith('@keyframes'):
            brace = text.find('{', pos)
            depth = 0
            j = brace
            while j < len(text):
                if text[j] == '{': depth += 1
                elif text[j] == '}':
                    depth -= 1
                    if depth == 0:
                        out.append(text[pos:j+1])
                        pos = j + 1
                        break
                j += 1
            continue

        # @media block
        if text[pos:].startswith('@media'):
            brace = text.find('{', pos)
            # Find the content and scope each rule inside
            depth = 0
            j = brace
            while j < len(text):
                if text[j] == '{': depth += 1
                elif text[j] == '}':
                    depth -= 1
                    if depth == 0:
                        media_block = text[pos:j+1]
                        # Scope inner rules
                        inner_start = media_block.index('{') + 1
                        inner_end = len(media_block) - 1
                        inner = media_block[inner_start:inner_end]
                        scoped_inner = scope_css(inner, prefix)
                        out.append(media_block[:inner_start] + scoped_inner + '}')
                        pos = j + 1
                        break
                j += 1
            continue

        # Regular rule: find selector and block
        brace = text.find('{', pos)
        if brace == -1:
            out.append(text[pos:])
            break

        selector = text[pos:brace].strip()
        # Find matching closing brace
        depth = 0
        j = brace
        while j < len(text):
            if text[j] == '{': depth += 1
            elif text[j] == '}':
                depth -= 1
                if depth == 0:
                    block = text[brace:j+1]
                    # Scope the selector
                    if selector:
                        parts = [s.strip() for s in selector.split(',')]
                        scoped_parts = []
                        for part in parts:
                            if part:
                                scoped_parts.append(prefix + ' ' + part)
                        scoped_selector = ',\n'.join(scoped_parts)
                        out.append(scoped_selector + block)
                    pos = j + 1
                    break
            j += 1
        continue

    return ''.join(out)

# Scope non-modal intel CSS
intel_scoped_css = '#panel-intel ' + ''.join([
    '.shell{display:flex;height:100%}\n',
])

# Simpler approach: manually scope by doing text replacement for known selectors
# and wrapping in #panel-intel { } where possible
# Actually let's do a clean line-by-line scope

def simple_scope_css(css_block, prefix):
    """Simple CSS scoping: prefix each selector block."""
    lines = css_block.split('\n')
    output_lines = []
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Comment line
        if stripped.startswith('/*') or not stripped:
            output_lines.append(line)
            i += 1
            continue

        # @keyframes - pass through
        if stripped.startswith('@keyframes'):
            output_lines.append(line)
            i += 1
            continue

        # @media - wrap content
        if stripped.startswith('@media'):
            output_lines.append(line)
            i += 1
            continue

        output_lines.append(line)
        i += 1

    return '\n'.join(output_lines)


# ─── EXTRACT ASSETS PARTS ─────────────────────────────────────────────────

assets_style_match = re.search(r'<style>(.*?)</style>', assets_src, re.DOTALL)
assets_style = assets_style_match.group(1)

# Global overlay CSS (keep global): .sav-ov and .sav-*
overlay_match = re.search(r'/\* OVERLAY \*/(.*?)$', assets_style, re.DOTALL)
assets_overlay_css = ''
if overlay_match:
    assets_overlay_css = '/* OVERLAY */\n' + overlay_match.group(1).strip()

# Assets CSS excluding :root/*/body (first 3 lines) and excluding OVERLAY section
# Lines 12-143 (0-indexed 11-142) → from .hd to .btn-new
assets_main_css_match = re.search(r'\*/\s*\n(.*?)/\* OVERLAY \*/', assets_style, re.DOTALL)
assets_main_css = ''
if assets_main_css_match:
    assets_main_css = assets_main_css_match.group(1).strip()

# ─── EXTRACT HTML BODIES ──────────────────────────────────────────────────

# Intel body: everything between <body> and </body>, minus the outer <div class="shell"> wrapper...
# Actually keep the shell div, just put it inside #panel-intel
intel_body_match = re.search(r'<body>\s*(.*?)\s*<script>', intel_src, re.DOTALL)
intel_body = intel_body_match.group(1).strip() if intel_body_match else ''

# Assets body: everything between <body> and <script>
assets_body_match = re.search(r'<body>\s*(.*?)\s*<script>', assets_src, re.DOTALL)
assets_body = assets_body_match.group(1).strip() if assets_body_match else ''

# ─── EXTRACT JAVASCRIPT ───────────────────────────────────────────────────

intel_js_match = re.search(r'<script>(.*?)</script>', intel_src, re.DOTALL)
intel_js = intel_js_match.group(1).strip() if intel_js_match else ''

assets_js_match = re.search(r'<script>(.*?)</script>', assets_src, re.DOTALL)
assets_js = assets_js_match.group(1).strip() if assets_js_match else ''

# ─── MODIFY INTEL JS ─────────────────────────────────────────────────────

# 1. Rename const KB = "..." to const INTEL_KB = "..."
intel_js = intel_js.replace('const KB = "', 'const INTEL_KB = "', 1)

# 2. Remove standalone buildSidebar(); call (line 714 - not inside a function)
intel_js = intel_js.replace('\nbuildSidebar();\n', '\n', 1)

# 3. Replace ${KB} with ${INTEL_KB} in string template literals
intel_js = intel_js.replace('${KB}', '${INTEL_KB}')

# 4. Route Intel fetch through WORKER (remove the full URL)
intel_js = intel_js.replace(
    "fetch('https://mkt-intel-api.lmglasers.workers.dev',{",
    "fetch(WORKER,{"
)

# 5. Remove const WORKER and const APP_ID declarations from intel JS
intel_js = re.sub(r"^const WORKER = 'https://mkt-intel-api\.lmglasers\.workers\.dev';\s*$", '', intel_js, flags=re.MULTILINE)
intel_js = re.sub(r"^const APP_ID = 'lmg';\s*$", '', intel_js, flags=re.MULTILINE)

# 6. Add hub send button in renderDetail - after the script-box closing div before last </div>`
# Find the renderDetail function end and add the button before the closing template literal
# The pattern: after the last conc-card section, there's a main product script box
# Look for the main script-box that ends renderDetail
# Insert hub button before the closing `; of cont.innerHTML
intel_js = intel_js.replace(
    '''        <div class="script-box">
          <div class="script-label">🗣️ Script geral — ${p.name}</div>
          <div class="script-text">"${p.script}"</div>
        </div>
      </div>\`;''',
    '''        <div class="script-box">
          <div class="script-label">🗣️ Script geral — ${p.name}</div>
          <div class="script-text">"${p.script}"</div>
        </div>
        <div style="margin-top:14px">
          <button class="hub-send-btn" onclick="hubSendToAssets('${p.name}')">→ Gerar assets para ${p.name}</button>
        </div>
      </div>\`;'''
)

# ─── MODIFY ASSETS JS ────────────────────────────────────────────────────

# 1. Rename const KB={...} to const AG_KB={...}
assets_js = assets_js.replace('const KB={', 'const AG_KB={', 1)

# 2. Replace all KB[ references with AG_KB[
assets_js = assets_js.replace('KB[fd.produto]', 'AG_KB[fd.produto]')
assets_js = assets_js.replace('KB[c.produto]', 'AG_KB[c.produto]')
assets_js = assets_js.replace('KB[p]', 'AG_KB[p]')
assets_js = assets_js.replace("KB['"+'"', "AG_KB['"+'"')  # edge case

# Catch all remaining KB[ patterns
assets_js = re.sub(r'\bKB\[', 'AG_KB[', assets_js)

# 3. Route Assets fetch through WORKER
assets_js = assets_js.replace(
    "fetch('https://api.anthropic.com/v1/messages',{",
    "fetch(WORKER+'/generate-copy',{"
)

# 4. Remove Content-Type and x-api-key from assets fetch headers (WORKER handles auth)
# The assets fetch uses: headers:{'Content-Type':'application/json'}
# This is fine - WORKER accepts this and forwards to Anthropic

# 5. Add hub send button in showAsset arte case
# Find the arte section in showAsset and add button before <div class="abar">
assets_js = assets_js.replace(
    '''    <div class="abar"><div class="ainfo">''',
    '''    <div style="margin-bottom:12px;padding:0 26px"><button class="hub-send-btn" onclick="hubSendToArte(gc.arte?.headline||'',gc.arte?.cta||'')">→ Enviar para Arte Visual</button></div>
    <div class="abar"><div class="ainfo">''',
    1  # only first occurrence (there are multiple abar divs)
)

# ─── ASSEMBLE FINAL HTML ─────────────────────────────────────────────────

hub_html = '''<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>LMG Hub</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet">
<script src="https://cdnjs.cloudflare.com/ajax/libs/jszip/3.10.1/jszip.min.js"></script>
<style>

/* ═══════════════════════════════════════════════
   HUB GLOBAL
═══════════════════════════════════════════════ */
*{box-sizing:border-box;margin:0;padding:0}
:root{
  --bk:#0C0C0C;--s1:#111;--s2:#181818;--s3:#1F1F1F;
  --bd:#282828;--bd2:#333;
  --or:#E96624;--or2:rgba(233,102,36,.12);--or3:rgba(233,102,36,.06);
  --tx:#F0EEE8;--mu:#6A6A6A;--mu2:#888;
  --gn:#3A9A5A;--gn2:rgba(58,154,90,.15);
  --bl:#4A8FBF;--yw:#D4A017;
  --r:8px;
}
html,body{height:100%;background:var(--bk);color:var(--tx);font-family:'Inter',sans-serif;-webkit-font-smoothing:antialiased;overflow:hidden}
#hub-root{display:flex;flex-direction:column;height:100vh;overflow:hidden}
#hub-header{display:flex;align-items:center;gap:0;background:var(--s1);border-bottom:1px solid var(--bd);flex-shrink:0;padding:0 20px}
#hub-logo{display:flex;align-items:center;gap:10px;padding:10px 16px 10px 0;border-right:1px solid var(--bd);margin-right:16px}
#hub-logo img{height:24px;width:auto;filter:brightness(0) invert(1);opacity:.85}
#hub-logo .hub-brand{font-size:14px;font-weight:900;letter-spacing:-.02em;color:var(--tx)}
#hub-logo .hub-brand span{color:var(--or)}
.hub-tabs{display:flex;gap:2px}
.hub-tab{background:none;border:none;padding:10px 18px;color:var(--mu2);font-family:'Inter',sans-serif;font-size:12.5px;font-weight:600;cursor:pointer;border-bottom:2px solid transparent;transition:.15s;white-space:nowrap}
.hub-tab:hover{color:var(--tx)}
.hub-tab.active{color:var(--or);border-bottom-color:var(--or)}
#hub-context{flex-shrink:0;background:var(--or3);border-bottom:1px solid rgba(233,102,36,.15);padding:6px 20px;font-size:11px;color:var(--or);display:none;align-items:center;gap:10px}
#hub-context.show{display:flex}
#hub-panels{flex:1;overflow:hidden;position:relative}
.hub-panel{display:none;width:100%;height:100%;position:absolute;inset:0;flex-direction:column}
.hub-panel.active{display:flex}
.hub-send-btn{background:var(--or);border:none;border-radius:6px;padding:9px 18px;color:#fff;font-family:'Inter',sans-serif;font-size:12px;font-weight:700;cursor:pointer;transition:.15s}
.hub-send-btn:hover{background:#C8521A}

/* ═══════════════════════════════════════════════
   INTEL GLOBAL: @keyframes b
═══════════════════════════════════════════════ */
@keyframes b{0%,80%,100%{transform:translateY(0);opacity:.4}40%{transform:translateY(-5px);opacity:1}}

/* ═══════════════════════════════════════════════
   INTEL CSS — scoped to #panel-intel
═══════════════════════════════════════════════ */
#panel-intel .shell{display:flex;height:100%}
#panel-intel .sidebar{width:280px;flex-shrink:0;background:var(--s1);border-right:1px solid var(--bd);display:flex;flex-direction:column;overflow:hidden}
#panel-intel .sb-hdr{padding:20px 18px 16px;border-bottom:1px solid var(--bd);flex-shrink:0}
#panel-intel .brand{font-size:20px;font-weight:900;letter-spacing:-.03em}
#panel-intel .brand span{color:var(--or)}
#panel-intel .brand-sub{font-size:10px;color:var(--mu);font-weight:600;letter-spacing:.1em;text-transform:uppercase;margin-top:3px}
#panel-intel .search-box{margin-top:14px;position:relative}
#panel-intel .search-box input{width:100%;background:var(--s2);border:1px solid var(--bd);border-radius:var(--r);padding:8px 12px 8px 34px;color:var(--tx);font-family:'Inter',sans-serif;font-size:12.5px;outline:none;transition:.15s}
#panel-intel .search-box input:focus{border-color:var(--or)}
#panel-intel .search-box input::placeholder{color:var(--mu)}
#panel-intel .search-icon{position:absolute;left:10px;top:50%;transform:translateY(-50%);color:var(--mu);font-size:14px;pointer-events:none}
#panel-intel .sb-body{flex:1;overflow-y:auto;padding:10px 8px}
#panel-intel .sb-body::-webkit-scrollbar{width:3px}
#panel-intel .sb-body::-webkit-scrollbar-thumb{background:var(--bd2)}
#panel-intel .cat-label{font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:.1em;color:var(--mu);padding:10px 10px 5px}
#panel-intel .prod-btn{width:100%;background:none;border:none;text-align:left;padding:8px 10px;border-radius:6px;cursor:pointer;color:var(--mu2);font-family:'Inter',sans-serif;font-size:12.5px;display:flex;align-items:center;gap:9px;transition:.12s;font-weight:500}
#panel-intel .prod-btn:hover{background:var(--s3);color:var(--tx)}
#panel-intel .prod-btn.active{background:var(--or2);color:var(--or);font-weight:600}
#panel-intel .prod-btn .ico{font-size:15px;width:20px;text-align:center;flex-shrink:0}
#panel-intel .prod-btn .badge{margin-left:auto;font-size:9px;background:var(--s3);color:var(--mu);padding:1px 6px;border-radius:10px}
#panel-intel .prod-btn.active .badge{background:rgba(233,102,36,.2);color:var(--or)}
#panel-intel .sb-footer{padding:12px 18px;border-top:1px solid var(--bd);flex-shrink:0}
#panel-intel .chat-btn{width:100%;background:var(--or);border:none;border-radius:var(--r);padding:9px;color:#fff;font-family:'Inter',sans-serif;font-size:12px;font-weight:700;cursor:pointer;display:flex;align-items:center;justify-content:center;gap:6px;transition:.15s}
#panel-intel .chat-btn:hover{background:#c8521a}
#panel-intel .main{flex:1;display:flex;flex-direction:column;overflow:hidden}
#panel-intel .topbar{padding:14px 28px;border-bottom:1px solid var(--bd);display:flex;align-items:center;justify-content:space-between;flex-shrink:0;background:var(--s1)}
#panel-intel .topbar-left{display:flex;align-items:center;gap:12px}
#panel-intel .topbar-title{font-size:15px;font-weight:700}
#panel-intel .topbar-sub{font-size:11px;color:var(--mu)}
#panel-intel .mode-tabs{display:flex;gap:2px;background:var(--s2);padding:3px;border-radius:7px}
#panel-intel .mode-tab{background:none;border:none;padding:6px 14px;border-radius:5px;font-family:'Inter',sans-serif;font-size:11px;font-weight:600;color:var(--mu);cursor:pointer;transition:.12s}
#panel-intel .mode-tab.active{background:var(--s3);color:var(--tx)}
#panel-intel .content{flex:1;overflow-y:auto;overflow-x:hidden}
#panel-intel .content::-webkit-scrollbar{width:5px}
#panel-intel .content::-webkit-scrollbar-thumb{background:var(--bd2);border-radius:3px}
#panel-intel .home{padding:48px 40px;display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:100%;text-align:center}
#panel-intel .home-icon{font-size:56px;margin-bottom:20px;opacity:.5}
#panel-intel .home-title{font-size:22px;font-weight:800;margin-bottom:10px}
#panel-intel .home-sub{font-size:13px;color:var(--mu);max-width:400px;line-height:1.7;margin-bottom:28px}
#panel-intel .home-stats{display:flex;gap:24px;justify-content:center}
#panel-intel .stat{text-align:center}
#panel-intel .stat-val{font-size:28px;font-weight:900;color:var(--or)}
#panel-intel .stat-lbl{font-size:10px;color:var(--mu);text-transform:uppercase;letter-spacing:.08em;margin-top:2px}
#panel-intel .detail{padding:28px 32px;max-width:960px}
#panel-intel .prod-hero{display:grid;grid-template-columns:1fr auto;gap:24px;align-items:start;margin-bottom:28px}
#panel-intel .prod-hero-left{}
#panel-intel .prod-eyebrow{font-size:10px;font-weight:700;color:var(--or);text-transform:uppercase;letter-spacing:.12em;margin-bottom:8px}
#panel-intel .prod-name{font-size:26px;font-weight:900;letter-spacing:-.02em;margin-bottom:6px}
#panel-intel .prod-desc{font-size:13px;color:var(--mu2);line-height:1.65;max-width:520px}
#panel-intel .prod-tags{display:flex;gap:6px;flex-wrap:wrap;margin-top:12px}
#panel-intel .ptag{font-size:10px;background:var(--s3);border:1px solid var(--bd2);color:var(--mu2);padding:3px 9px;border-radius:12px}
#panel-intel .ptag.hot{background:var(--or2);border-color:rgba(233,102,36,.3);color:var(--or)}
#panel-intel .prod-img-box{width:200px;height:150px;background:var(--s2);border:1px solid var(--bd);border-radius:10px;display:flex;align-items:center;justify-content:center;overflow:hidden;flex-shrink:0}
#panel-intel .prod-img-box img{width:100%;height:100%;object-fit:contain;padding:12px;mix-blend-mode:normal}
#panel-intel .prod-img-box .img-placeholder{font-size:40px;opacity:.3}
#panel-intel .specs-row{display:flex;gap:10px;margin-bottom:24px;flex-wrap:wrap}
#panel-intel .spec-card{background:var(--s2);border:1px solid var(--bd);border-radius:var(--r);padding:12px 16px;flex:1;min-width:120px}
#panel-intel .spec-lbl{font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:.09em;color:var(--mu);margin-bottom:4px}
#panel-intel .spec-val{font-size:13px;font-weight:700;color:var(--tx)}
#panel-intel .spec-val.hot{color:var(--or)}
#panel-intel .section{margin-bottom:24px}
#panel-intel .section-hdr{display:flex;align-items:center;gap:8px;margin-bottom:14px}
#panel-intel .section-title{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.1em;color:var(--mu)}
#panel-intel .section-line{flex:1;height:1px;background:var(--bd)}
#panel-intel .conc-grid{display:flex;flex-direction:column;gap:10px}
#panel-intel .conc-card{background:var(--s2);border:1px solid var(--bd);border-radius:10px;overflow:hidden;transition:.15s}
#panel-intel .conc-card:hover{border-color:var(--bd2)}
#panel-intel .conc-header{display:flex;align-items:center;gap:14px;padding:14px 16px}
#panel-intel .conc-img{width:60px;height:45px;background:var(--s3);border-radius:6px;display:flex;align-items:center;justify-content:center;flex-shrink:0;overflow:hidden}
#panel-intel .conc-img img{width:100%;height:100%;object-fit:contain;padding:4px}
#panel-intel .conc-img .no-img{font-size:20px;opacity:.3}
#panel-intel .conc-info{flex:1;min-width:0}
#panel-intel .conc-name{font-size:14px;font-weight:700;margin-bottom:2px;display:flex;align-items:center;gap:8px}
#panel-intel .conc-maker{font-size:11px;color:var(--mu);display:flex;align-items:center;gap:6px}
#panel-intel .country-flag{font-size:13px}
#panel-intel .conc-right{display:flex;flex-direction:column;align-items:flex-end;gap:6px;flex-shrink:0}
#panel-intel .stars{display:flex;gap:2px}
#panel-intel .star{font-size:13px;color:var(--bd2)}
#panel-intel .star.on{color:#D4A017}
#panel-intel .star.half{color:#D4A017;opacity:.5}
#panel-intel .rating-label{font-size:9px;color:var(--mu);text-transform:uppercase;letter-spacing:.06em}
#panel-intel .conc-body{padding:0 16px 14px}
#panel-intel .conc-grid-2{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:10px}
#panel-intel .conc-section-mini{font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:.1em;color:var(--mu);margin-bottom:6px}
#panel-intel .conc-pros{display:flex;flex-direction:column;gap:4px}
#panel-intel .conc-pro{font-size:12px;color:var(--mu2);display:flex;gap:6px}
#panel-intel .conc-pro::before{content:"✓";color:var(--gn);font-weight:700;flex-shrink:0}
#panel-intel .conc-cons{display:flex;flex-direction:column;gap:4px}
#panel-intel .conc-con{font-size:12px;color:var(--mu2);display:flex;gap:6px}
#panel-intel .conc-con::before{content:"✗";color:#E05A5A;font-weight:700;flex-shrink:0}
#panel-intel .perception-bar{background:var(--s3);border-radius:6px;padding:10px 12px;margin-top:8px}
#panel-intel .perception-label{font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:var(--mu);margin-bottom:8px}
#panel-intel .perc-row{display:flex;align-items:center;gap:8px;margin-bottom:5px}
#panel-intel .perc-name{font-size:11px;color:var(--mu2);width:110px;flex-shrink:0}
#panel-intel .perc-track{flex:1;height:5px;background:var(--bd2);border-radius:3px;overflow:hidden}
#panel-intel .perc-fill{height:100%;border-radius:3px;background:var(--or);transition:width .6s ease}
#panel-intel .perc-fill.gn{background:var(--gn)}
#panel-intel .perc-fill.bl{background:var(--bl)}
#panel-intel .perc-fill.yw{background:var(--yw)}
#panel-intel .perc-pct{font-size:10px;color:var(--mu);width:32px;text-align:right;flex-shrink:0}
#panel-intel .script-box{background:linear-gradient(135deg,var(--s2),var(--s3));border:1px solid rgba(233,102,36,.2);border-left:3px solid var(--or);border-radius:0 var(--r) var(--r) 0;padding:14px 18px;margin-top:6px}
#panel-intel .script-label{font-size:9px;font-weight:700;color:var(--or);text-transform:uppercase;letter-spacing:.1em;margin-bottom:8px;display:flex;align-items:center;gap:6px}
#panel-intel .script-text{font-size:13px;color:#d0ccc4;line-height:1.7;font-style:italic}
#panel-intel .winner{display:inline-flex;align-items:center;gap:5px;background:var(--gn2);border:1px solid rgba(58,154,90,.3);color:var(--gn);font-size:10px;font-weight:700;padding:3px 10px;border-radius:12px;text-transform:uppercase;letter-spacing:.06em}
#panel-intel .risk{display:inline-flex;align-items:center;gap:5px;background:rgba(212,160,23,.1);border:1px solid rgba(212,160,23,.3);color:var(--yw);font-size:10px;font-weight:700;padding:3px 10px;border-radius:12px;text-transform:uppercase;letter-spacing:.06em}
#panel-intel .chat-view{display:flex;flex-direction:column;height:100%}
#panel-intel .chat-messages{flex:1;overflow-y:auto;padding:20px 28px;display:flex;flex-direction:column;gap:14px}
#panel-intel .chat-messages::-webkit-scrollbar{width:4px}
#panel-intel .chat-messages::-webkit-scrollbar-thumb{background:var(--bd2)}
#panel-intel .msg{display:flex;flex-direction:column;gap:4px}
#panel-intel .msg.user{align-items:flex-end}
#panel-intel .msg.ai{align-items:flex-start}
#panel-intel .bubble{padding:12px 16px;border-radius:10px;font-size:13px;line-height:1.7;max-width:82%}
#panel-intel .msg.user .bubble{background:var(--or);color:#fff;border-radius:10px 10px 3px 10px}
#panel-intel .msg.ai .bubble{background:var(--s2);border:1px solid var(--bd);border-radius:10px 10px 10px 3px;white-space:pre-wrap}
#panel-intel .ai-meta{font-size:9px;color:var(--mu);display:flex;align-items:center;gap:5px}
#panel-intel .ai-dot{width:5px;height:5px;border-radius:50%;background:var(--gn)}
#panel-intel .typing{display:flex;gap:5px;padding:12px 16px;background:var(--s2);border:1px solid var(--bd);border-radius:10px;width:fit-content}
#panel-intel .dot{width:6px;height:6px;border-radius:50%;background:var(--or);animation:b .9s infinite}
#panel-intel .dot:nth-child(2){animation-delay:.15s}
#panel-intel .dot:nth-child(3){animation-delay:.3s}
#panel-intel .chat-input-wrap{padding:14px 24px 18px;border-top:1px solid var(--bd);flex-shrink:0}
#panel-intel .chat-row{display:flex;gap:8px;align-items:flex-end}
#panel-intel .chat-inp{flex:1;background:var(--s2);border:1px solid var(--bd);border-radius:var(--r);padding:10px 14px;color:var(--tx);font-family:'Inter',sans-serif;font-size:13px;outline:none;resize:none;min-height:42px;max-height:140px;transition:border-color .15s;line-height:1.5}
#panel-intel .chat-inp:focus{border-color:var(--or)}
#panel-intel .chat-inp::placeholder{color:var(--mu)}
#panel-intel .send-btn{background:var(--or);border:none;border-radius:var(--r);width:42px;height:42px;display:flex;align-items:center;justify-content:center;cursor:pointer;flex-shrink:0;transition:.15s}
#panel-intel .send-btn:hover{background:#c8521a}
#panel-intel .send-btn:disabled{opacity:.4;cursor:not-allowed}
#panel-intel .send-btn svg{width:16px;height:16px;fill:#fff}
#panel-intel .chip-bar{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:10px}
#panel-intel .chip{background:var(--s2);border:1px solid var(--bd);color:var(--mu);font-size:11px;font-family:'Inter',sans-serif;padding:4px 11px;border-radius:16px;cursor:pointer;transition:.12s;white-space:nowrap}
#panel-intel .chip:hover{border-color:var(--or);color:var(--tx)}
@media(max-width:720px){
  #panel-intel .sidebar{width:220px}
  #panel-intel .detail{padding:18px 16px}
  #panel-intel .conc-grid-2{grid-template-columns:1fr}
  #panel-intel .prod-hero{grid-template-columns:1fr;gap:14px}
  #panel-intel .prod-img-box{width:100%;height:120px}
}
/* INTEL — Competitor management */
#panel-intel .cc-actions{display:flex;gap:6px;margin-top:8px;align-items:center}
#panel-intel .btn-add{background:var(--or);border:none;border-radius:6px;padding:6px 14px;color:#fff;font-family:'Inter',sans-serif;font-size:11px;font-weight:700;cursor:pointer;display:flex;align-items:center;gap:5px;transition:.15s}
#panel-intel .btn-add:hover{background:#c8521a}
#panel-intel .btn-del{background:none;border:1px solid #E05A5A;border-radius:6px;padding:5px 10px;color:#E05A5A;font-family:'Inter',sans-serif;font-size:10px;font-weight:600;cursor:pointer;transition:.15s;margin-left:auto}
#panel-intel .btn-del:hover{background:rgba(224,90,90,.1)}
#panel-intel .user-tag{font-size:9px;background:rgba(58,154,90,.15);border:1px solid rgba(58,154,90,.3);color:var(--gn);padding:2px 8px;border-radius:10px;font-weight:700}

/* ═══════════════════════════════════════════════
   INTEL MODAL — GLOBAL
═══════════════════════════════════════════════ */
.overlay{position:fixed;inset:0;background:rgba(0,0,0,.7);z-index:100;display:flex;align-items:center;justify-content:center;padding:20px}
.modal{background:var(--s2);border:1px solid var(--bd2);border-radius:12px;width:100%;max-width:560px;max-height:88vh;overflow-y:auto;display:flex;flex-direction:column}
.modal::-webkit-scrollbar{width:4px}
.modal::-webkit-scrollbar-thumb{background:var(--bd2)}
.modal-hdr{padding:18px 20px 14px;border-bottom:1px solid var(--bd);display:flex;align-items:center;justify-content:space-between;flex-shrink:0}
.modal-ttl{font-size:15px;font-weight:800}
.modal-close{background:none;border:none;color:var(--mu);font-size:18px;cursor:pointer;line-height:1;padding:2px 6px;border-radius:4px}
.modal-close:hover{background:var(--s3);color:var(--tx)}
.modal-body{padding:18px 20px;display:flex;flex-direction:column;gap:14px}
.field{display:flex;flex-direction:column;gap:5px}
.field label{font-size:11px;font-weight:700;color:var(--mu);text-transform:uppercase;letter-spacing:.07em}
.field input,.field textarea,.field select{background:var(--s1);border:1px solid var(--bd);border-radius:6px;padding:8px 11px;color:var(--tx);font-family:'Inter',sans-serif;font-size:13px;outline:none;transition:border-color .15s;width:100%}
.field input:focus,.field textarea:focus{border-color:var(--or)}
.field textarea{resize:vertical;min-height:72px;line-height:1.5}
.field-row{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.stars-input{display:flex;gap:4px;align-items:center}
.si-star{font-size:22px;cursor:pointer;color:var(--bd2);transition:.1s;user-select:none}
.si-star.on{color:var(--yw)}
.modal-foot{padding:12px 20px;border-top:1px solid var(--bd);display:flex;gap:8px;justify-content:flex-end;flex-shrink:0;background:var(--s2)}
.btn-cancel{background:var(--s3);border:1px solid var(--bd2);border-radius:6px;padding:8px 18px;color:var(--mu2);font-family:'Inter',sans-serif;font-size:12px;font-weight:600;cursor:pointer}
.btn-save{background:var(--or);border:none;border-radius:6px;padding:8px 22px;color:#fff;font-family:'Inter',sans-serif;font-size:12px;font-weight:700;cursor:pointer;transition:.15s}
.btn-save:hover{background:#c8521a}
.btn-save:disabled{opacity:.5;cursor:not-allowed}
.fetch-status{font-size:11px;color:var(--mu);display:flex;align-items:center;gap:6px;padding:8px 11px;background:var(--s1);border-radius:6px;border:1px solid var(--bd)}
.fetch-status.ok{color:var(--gn);border-color:rgba(58,154,90,.3)}
.fetch-status.err{color:#E05A5A;border-color:rgba(224,90,90,.3)}
.section-sep{font-size:10px;font-weight:700;color:var(--or);text-transform:uppercase;letter-spacing:.1em;margin-top:4px;display:flex;align-items:center;gap:8px}
.section-sep::after{content:'';flex:1;height:1px;background:var(--bd)}
.pwd-row{display:flex;gap:8px;align-items:center;margin-top:8px}
.pwd-inp{flex:1;background:var(--s1);border:1px solid var(--bd);border-radius:6px;padding:7px 11px;color:var(--tx);font-family:'Inter',sans-serif;font-size:13px;outline:none}
.pwd-inp:focus{border-color:var(--or)}
.btn-confirm-del{background:#E05A5A;border:none;border-radius:6px;padding:7px 16px;color:#fff;font-family:'Inter',sans-serif;font-size:12px;font-weight:700;cursor:pointer}

/* ═══════════════════════════════════════════════
   ASSETS @keyframes — GLOBAL
═══════════════════════════════════════════════ */
@keyframes fi{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:translateY(0)}}
@keyframes pulse{0%,100%{transform:scale(1)}50%{transform:scale(1.05)}}
@keyframes sp{to{transform:rotate(360deg)}}

/* ═══════════════════════════════════════════════
   ASSETS CSS VARIABLES (override root for panel)
═══════════════════════════════════════════════ */
#panel-assets{--bd:#242424;--bd2:#2e2e2e;--tx:#e8e8e8;--mu2:#444;--gn:#22c55e;--re:#ef4444;--r:6px;--ord:#C8521A}

/* ═══════════════════════════════════════════════
   ASSETS CSS — scoped to #panel-assets
═══════════════════════════════════════════════ */
#panel-assets{font-family:'Inter',sans-serif;background:var(--bk);color:var(--tx);display:flex;flex-direction:column;overflow:hidden}
#panel-assets .hd{padding:14px 28px;border-bottom:1px solid var(--bd);display:flex;align-items:center;justify-content:space-between;background:var(--s1);position:relative}
#panel-assets .hd-logo{display:flex;align-items:center;gap:10px}
#panel-assets .hd-logo img{height:28px}
#panel-assets .hd-sep{width:1px;height:18px;background:var(--bd)}
#panel-assets .hd-tag{font-size:11px;font-weight:600;color:var(--mu);letter-spacing:.08em;text-transform:uppercase}
#panel-assets .steps{display:flex;align-items:center;gap:5px}
#panel-assets .sdot{width:8px;height:8px;border-radius:50%;background:var(--bd2);transition:.3s}
#panel-assets .sdot.active{background:var(--or)}
#panel-assets .sdot.done{background:var(--gn)}
#panel-assets .sline{width:16px;height:1px;background:var(--bd)}
#panel-assets .main{flex:1;overflow:hidden;display:flex}
#panel-assets .scr{display:none;width:100%;animation:fi .3s ease}
#panel-assets .scr.active{display:flex}
#panel-assets .fs{justify-content:flex-start;align-items:flex-start;overflow-y:auto;padding:32px 28px}
#panel-assets .fc{width:100%;max-width:760px;margin:0 auto}
#panel-assets .sec{margin-bottom:28px}
#panel-assets .sec-hd{font-size:10px;font-weight:700;color:var(--mu);text-transform:uppercase;letter-spacing:.12em;padding-bottom:10px;border-bottom:1px solid var(--bd);margin-bottom:16px;display:flex;align-items:center;gap:8px}
#panel-assets .g2{display:grid;grid-template-columns:1fr 1fr;gap:14px}
#panel-assets .g3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:14px}
#panel-assets .gf{grid-column:1/-1}
#panel-assets .fg{display:flex;flex-direction:column;gap:5px}
#panel-assets .fg label{font-size:11px;font-weight:600;color:var(--mu);text-transform:uppercase;letter-spacing:.07em}
#panel-assets .fg input,#panel-assets .fg select,#panel-assets .fg textarea{background:var(--s2);border:1px solid var(--bd);border-radius:var(--r);padding:10px 13px;color:var(--tx);font-family:'Inter',sans-serif;font-size:13.5px;outline:none;transition:border-color .2s;resize:none}
#panel-assets .fg input:focus,#panel-assets .fg select:focus,#panel-assets .fg textarea:focus{border-color:var(--or)}
#panel-assets .fg select option{background:#181818}
#panel-assets .pg{display:grid;grid-template-columns:repeat(4,1fr);gap:6px}
#panel-assets .pc{background:var(--s2);border:1px solid var(--bd);border-radius:var(--r);padding:9px 11px;cursor:pointer;transition:.2s;display:flex;flex-direction:column;gap:2px}
#panel-assets .pc:hover{border-color:rgba(233,102,36,.4)}
#panel-assets .pc.sel{border-color:var(--or);background:rgba(233,102,36,.07)}
#panel-assets .pc-name{font-size:12px;font-weight:600;color:var(--tx)}
#panel-assets .pc.sel .pc-name{color:var(--or)}
#panel-assets .pc-cat{font-size:10px;color:var(--mu)}
#panel-assets .tg{display:flex;flex-wrap:wrap;gap:6px}
#panel-assets .t{padding:5px 12px;border-radius:20px;border:1px solid var(--bd);font-size:12px;font-weight:500;cursor:pointer;transition:.2s;background:var(--s2);color:var(--mu);user-select:none}
#panel-assets .t.sel{border-color:var(--or);background:rgba(233,102,36,.1);color:var(--or)}
#panel-assets .valor-row{display:grid;grid-template-columns:1fr 1fr auto;gap:12px;align-items:end}
#panel-assets .toggle-pill{display:flex;align-items:center;gap:8px;padding:10px 14px;background:var(--s2);border:1px solid var(--bd);border-radius:var(--r);cursor:pointer;transition:.2s;font-size:12.5px;color:var(--mu);font-weight:500;user-select:none;height:42px;white-space:nowrap}
#panel-assets .toggle-pill.on{border-color:var(--or);color:var(--or);background:rgba(233,102,36,.08)}
#panel-assets .toggle-pill .dot{width:28px;height:16px;border-radius:8px;background:var(--bd2);position:relative;transition:.2s;flex-shrink:0}
#panel-assets .toggle-pill.on .dot{background:var(--or)}
#panel-assets .toggle-pill .dot::after{content:'';position:absolute;width:12px;height:12px;border-radius:50%;background:#fff;top:2px;left:2px;transition:.2s}
#panel-assets .toggle-pill.on .dot::after{left:14px}
#panel-assets .premio-box{background:var(--s2);border:1px solid var(--bd);border-radius:var(--r);padding:14px;margin-top:10px;display:none}
#panel-assets .premio-box.show{display:block}
#panel-assets .conc-list{display:flex;flex-direction:column;gap:8px}
#panel-assets .conc-item{display:flex;gap:8px;align-items:center}
#panel-assets .conc-rm{background:none;border:1px solid var(--bd);border-radius:4px;color:var(--mu);padding:4px 8px;cursor:pointer;font-size:12px;transition:.2s}
#panel-assets .conc-rm:hover{border-color:var(--re);color:var(--re)}
#panel-assets .add-btn{background:none;border:1px dashed var(--bd2);border-radius:var(--r);color:var(--mu);padding:8px 14px;cursor:pointer;font-size:12.5px;transition:.2s;font-family:'Inter',sans-serif;width:100%;margin-top:6px}
#panel-assets .add-btn:hover{border-color:var(--or);color:var(--or)}
#panel-assets .srow{display:flex;justify-content:flex-end;gap:10px;margin-top:8px}
#panel-assets .btn-p{background:var(--or);border:none;color:#fff;padding:12px 28px;border-radius:var(--r);font-family:'Inter',sans-serif;font-weight:700;font-size:13.5px;cursor:pointer;transition:.2s;display:flex;align-items:center;gap:8px}
#panel-assets .btn-p:hover{background:var(--ord);transform:translateY(-1px)}
#panel-assets .btn-s{background:var(--s2);border:1px solid var(--bd);color:var(--tx);padding:10px 20px;border-radius:var(--r);font-family:'Inter',sans-serif;font-size:13px;cursor:pointer;transition:.2s}
#panel-assets .btn-s:hover{border-color:var(--mu)}
#panel-assets .gs{flex-direction:column;align-items:center;justify-content:center;gap:24px;text-align:center;padding:36px}
#panel-assets .orb{width:88px;height:88px;border-radius:50%;background:linear-gradient(135deg,var(--or),var(--ord));display:flex;align-items:center;justify-content:center;font-size:32px;animation:pulse 2s ease-in-out infinite;box-shadow:0 0 40px rgba(233,102,36,.25)}
#panel-assets .gtitle{font-size:22px;font-weight:700;letter-spacing:-.02em}
#panel-assets .gsteps{display:flex;flex-direction:column;gap:8px;width:100%;max-width:460px}
#panel-assets .gstep{display:flex;align-items:center;gap:11px;padding:10px 14px;border-radius:var(--r);background:var(--s1);border:1px solid var(--bd);font-size:13px;color:var(--mu);transition:.4s}
#panel-assets .gstep.active{border-color:var(--or);color:var(--tx);background:rgba(233,102,36,.06)}
#panel-assets .gstep.done{border-color:var(--gn);color:var(--tx)}
#panel-assets .gicon{margin-left:auto;min-width:20px;text-align:center}
#panel-assets .spin{width:14px;height:14px;border:2px solid var(--bd);border-top-color:var(--or);border-radius:50%;animation:sp .8s linear infinite;display:inline-block}
#panel-assets .prog{height:3px;background:var(--bd);border-radius:2px;margin-top:14px;width:100%;max-width:460px;overflow:hidden}
#panel-assets .progb{height:100%;background:linear-gradient(90deg,var(--or),var(--ord));width:0%;transition:width .5s}
#panel-assets .prog-info{display:flex;justify-content:space-between;align-items:center;width:100%;max-width:460px;margin-top:8px}
#panel-assets .prog-status{font-size:12px;color:var(--mu)}
#panel-assets .prog-pct{font-size:14px;font-weight:700;color:var(--or);font-variant-numeric:tabular-nums}
#panel-assets .prog-timer{font-size:11px;color:var(--mu2);margin-top:4px;text-align:center}
#panel-assets .rs{flex-direction:row;overflow:hidden}
#panel-assets .rsb{width:200px;min-width:200px;border-right:1px solid var(--bd);background:var(--s1);padding:18px 0;overflow-y:auto}
#panel-assets .rsb-sec{padding:0 12px;margin-bottom:20px}
#panel-assets .rsb-lbl{font-size:10px;font-weight:700;color:var(--mu);text-transform:uppercase;letter-spacing:.1em;margin-bottom:7px}
#panel-assets .rsb-item{display:flex;align-items:center;gap:8px;padding:8px 10px;border-radius:6px;cursor:pointer;font-size:12px;font-weight:500;color:var(--mu);transition:.2s;margin-bottom:2px}
#panel-assets .rsb-item:hover{background:var(--s2);color:var(--tx)}
#panel-assets .rsb-item.active{background:rgba(233,102,36,.1);color:var(--or)}
#panel-assets .rsb-item.done{color:var(--gn)}
#panel-assets .rsb-dot{width:5px;height:5px;border-radius:50%;background:var(--bd2);flex-shrink:0;transition:.3s}
#panel-assets .rsb-item.active .rsb-dot{background:var(--or)}
#panel-assets .rsb-item.done .rsb-dot{background:var(--gn)}
#panel-assets .rc{flex:1;overflow-y:auto;padding:26px}
#panel-assets .rh{display:flex;align-items:center;justify-content:space-between;margin-bottom:18px}
#panel-assets .rt{font-size:18px;font-weight:700;letter-spacing:-.02em}
#panel-assets .badge{padding:3px 10px;border-radius:20px;font-size:11px;font-weight:600;background:rgba(233,102,36,.12);color:var(--or);border:1px solid rgba(233,102,36,.3)}
#panel-assets .badge.appr{background:rgba(34,197,94,.1);color:var(--gn);border-color:rgba(34,197,94,.3)}
#panel-assets .card{background:var(--s1);border:1px solid var(--bd);border-radius:var(--r);overflow:hidden;margin-bottom:12px}
#panel-assets .cardh{padding:10px 15px;border-bottom:1px solid var(--bd);display:flex;align-items:center;justify-content:space-between}
#panel-assets .cardt{font-size:11px;font-weight:600;color:var(--mu);text-transform:uppercase;letter-spacing:.06em}
#panel-assets .cardb{padding:14px}
#panel-assets .ea{width:100%;background:transparent;border:none;color:var(--tx);font-family:'Inter',sans-serif;font-size:13.5px;line-height:1.7;resize:none;outline:none;min-height:52px}
#panel-assets .cpb{background:none;border:1px solid var(--bd);color:var(--mu);padding:3px 9px;border-radius:5px;font-size:11px;cursor:pointer;font-family:'Inter',sans-serif;transition:.2s}
#panel-assets .cpb:hover{border-color:var(--or);color:var(--or)}
#panel-assets .abar{background:var(--s1);border-top:1px solid var(--bd);padding:13px 26px;display:flex;align-items:center;justify-content:space-between;margin-top:26px}
#panel-assets .ainfo{font-size:12px;color:var(--mu)}
#panel-assets .btn-appr{background:rgba(34,197,94,.12);border:1px solid rgba(34,197,94,.35);color:var(--gn);padding:9px 18px;border-radius:6px;font-family:'Inter',sans-serif;font-weight:600;font-size:13px;cursor:pointer;transition:.2s}
#panel-assets .btn-appr:hover{background:rgba(34,197,94,.2)}
#panel-assets .wa-bg{background:#0b1a0d;border-radius:8px;padding:12px;border:1px solid #182a1a}
#panel-assets .wa-bubble{background:#1a5c26;border-radius:10px 10px 10px 2px;padding:11px 13px;max-width:86%;font-size:13px;line-height:1.6}
#panel-assets .wa-time{font-size:10px;color:rgba(255,255,255,.3);text-align:right;margin-top:4px}
#panel-assets .lp-prev{background:#0C0C0C;border-radius:8px;padding:20px;font-family:'Inter',sans-serif;border:1px solid var(--bd)}
#panel-assets .kv-prev{background:linear-gradient(135deg,#0C0C0C,#1a0800);border:1px solid rgba(233,102,36,.25);border-radius:10px;min-height:180px;display:flex;align-items:center;justify-content:center;position:relative;overflow:hidden;padding:24px}
#panel-assets .kv-prev::before{content:'';position:absolute;inset:0;background:radial-gradient(ellipse at 70% 50%,rgba(233,102,36,.1),transparent 60%)}
#panel-assets .kv-inner{z-index:1;text-align:center}
#panel-assets .ds{flex-direction:column;align-items:center;justify-content:center;gap:20px;text-align:center;padding:36px}
#panel-assets .done-ico{width:80px;height:80px;border-radius:50%;background:rgba(34,197,94,.1);border:2px solid rgba(34,197,94,.35);display:flex;align-items:center;justify-content:center;font-size:32px}
#panel-assets .dtitle{font-size:26px;font-weight:700;letter-spacing:-.02em}
#panel-assets .dsub{color:var(--mu);font-size:13.5px;line-height:1.6;max-width:420px}
#panel-assets .zip-card{background:var(--s1);border:1px solid var(--bd);border-radius:12px;padding:22px 28px;display:flex;align-items:center;gap:16px;min-width:400px}
#panel-assets .zip-info{flex:1;text-align:left}
#panel-assets .zip-name{font-weight:700;font-size:15px;margin-bottom:4px}
#panel-assets .zip-meta{font-size:12px;color:var(--mu)}
#panel-assets .zip-files{display:flex;flex-direction:column;gap:3px;margin-top:10px}
#panel-assets .zip-file{font-size:11px;color:var(--mu);display:flex;align-items:center;gap:6px}
#panel-assets .zip-file::before{content:'•';color:var(--or)}
#panel-assets .btn-zip{background:var(--or);border:none;color:#fff;padding:14px 24px;border-radius:var(--r);font-family:'Inter',sans-serif;font-weight:700;font-size:14px;cursor:pointer;transition:.2s;display:flex;align-items:center;gap:8px;white-space:nowrap}
#panel-assets .btn-zip:hover{background:var(--ord)}
#panel-assets .btn-zip:disabled{opacity:.6;cursor:not-allowed}
#panel-assets .btn-new{background:none;border:1px solid var(--bd);color:var(--mu);padding:9px 18px;border-radius:var(--r);font-family:'Inter',sans-serif;font-size:13px;cursor:pointer;transition:.2s}
#panel-assets .btn-new:hover{border-color:var(--tx);color:var(--tx)}

/* OVERLAY — GLOBAL */
.sav-ov{position:fixed;inset:0;background:rgba(0,0,0,.8);display:none;align-items:center;justify-content:center;z-index:100;backdrop-filter:blur(4px)}
.sav-ov.show{display:flex}
.sav-box{background:var(--s1);border:1px solid var(--bd);border-radius:12px;padding:28px 36px;text-align:center;display:flex;flex-direction:column;align-items:center;gap:12px;min-width:300px}
.sav-spin{width:36px;height:36px;border:3px solid var(--bd);border-top-color:var(--or);border-radius:50%;animation:sp .9s linear infinite}
.sav-lbl{font-size:14px;font-weight:600}
.sav-sub{font-size:12px;color:var(--mu)}

/* ═══════════════════════════════════════════════
   ARTE VISUAL CSS — scoped to #panel-arte
═══════════════════════════════════════════════ */
#panel-arte{background:var(--bk);font-family:'Inter',sans-serif;overflow:hidden}
#panel-arte .arte-wrap{display:flex;height:100%;gap:0}
#panel-arte .arte-sidebar{width:320px;flex-shrink:0;border-right:1px solid var(--bd);background:var(--s1);overflow-y:auto;padding:20px}
#panel-arte .arte-sidebar::-webkit-scrollbar{width:3px}
#panel-arte .arte-sidebar::-webkit-scrollbar-thumb{background:var(--bd2)}
#panel-arte .arte-main{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:28px;overflow:hidden}
#panel-arte .arte-field{display:flex;flex-direction:column;gap:5px;margin-bottom:14px}
#panel-arte .arte-field label{font-size:10px;font-weight:700;color:var(--mu);text-transform:uppercase;letter-spacing:.08em}
#panel-arte .arte-field input,#panel-arte .arte-field textarea,#panel-arte .arte-field select{background:var(--s2);border:1px solid var(--bd);border-radius:6px;padding:9px 12px;color:var(--tx);font-family:'Inter',sans-serif;font-size:13px;outline:none;width:100%;transition:border-color .15s}
#panel-arte .arte-field input:focus,#panel-arte .arte-field textarea:focus{border-color:var(--or)}
#panel-arte .arte-section{font-size:9px;font-weight:700;color:var(--or);text-transform:uppercase;letter-spacing:.12em;margin:18px 0 10px;display:flex;align-items:center;gap:8px}
#panel-arte .arte-section::after{content:'';flex:1;height:1px;background:var(--bd)}
#panel-arte .arte-btn{background:var(--or);border:none;border-radius:6px;padding:11px;color:#fff;font-family:'Inter',sans-serif;font-size:13px;font-weight:700;cursor:pointer;transition:.15s;width:100%;display:flex;align-items:center;justify-content:center;gap:8px;margin-bottom:8px}
#panel-arte .arte-btn:hover{background:#C8521A}
#panel-arte .arte-btn.sec{background:var(--s2);border:1px solid var(--bd);color:var(--tx)}
#panel-arte .arte-btn.sec:hover{border-color:var(--or);color:var(--or)}
#panel-arte .canvas-wrap{position:relative;box-shadow:0 8px 40px rgba(0,0,0,.6)}
#panel-arte canvas{display:block;max-width:100%;max-height:100%}
#panel-arte .arte-label{font-size:11px;color:var(--mu);text-align:center;margin-top:10px}
#panel-arte .color-row{display:flex;gap:6px;align-items:center;flex-wrap:wrap}
#panel-arte .color-swatch{width:24px;height:24px;border-radius:4px;cursor:pointer;border:2px solid transparent;transition:.15s;flex-shrink:0}
#panel-arte .color-swatch.active{border-color:var(--or)}
#panel-arte .slider-row{display:flex;align-items:center;gap:10px}
#panel-arte .slider-row input[type=range]{flex:1;accent-color:var(--or)}
#panel-arte .slider-val{font-size:11px;color:var(--mu);min-width:28px;text-align:right}
</style>
</head>
<body>
<div id="hub-root">
  <!-- HUB HEADER -->
  <div id="hub-header">
    <div id="hub-logo">
      <img src="https://images.weserv.nl/?url=lmg.com.br/wp-content/uploads/2020/11/logo-lmg-all.png&w=200&output=webp" alt="LMG" onerror="this.style.display='none'">
      <div class="hub-brand">LMG <span>Hub</span></div>
    </div>
    <div class="hub-tabs">
      <button id="tab-intel" class="hub-tab active" onclick="hubTab('intel')">🎯 MKT Intel</button>
      <button id="tab-assets" class="hub-tab" onclick="hubTab('assets')">📦 Asset Generator</button>
      <button id="tab-arte" class="hub-tab" onclick="hubTab('arte')">🎨 Arte Visual</button>
    </div>
  </div>
  <!-- HUB CONTEXT BANNER -->
  <div id="hub-context">
    <span id="hub-ctx-text">Pipeline: —</span>
    <button onclick="document.getElementById('hub-context').classList.remove('show')" style="background:none;border:none;color:var(--or);cursor:pointer;font-size:14px;margin-left:auto">✕</button>
  </div>
  <!-- PANELS -->
  <div id="hub-panels">

    <!-- ── PANEL: MKT INTEL ─────────────────────── -->
    <div id="panel-intel" class="hub-panel active">
''' + intel_body + '''
    </div>

    <!-- ── PANEL: ASSET GENERATOR ──────────────── -->
    <div id="panel-assets" class="hub-panel">
''' + assets_body + '''
    </div>

    <!-- ── PANEL: ARTE VISUAL ──────────────────── -->
    <div id="panel-arte" class="hub-panel">
      <div class="arte-wrap">
        <div class="arte-sidebar">
          <div class="arte-section">Texto</div>
          <div class="arte-field">
            <label>Eyebrow</label>
            <input type="text" id="av-eyebrow" value="LMG® LASER MEDICAL GROUP" oninput="avUpdatePreview()">
          </div>
          <div class="arte-field">
            <label>Headline</label>
            <input type="text" id="av-headline" placeholder="Ex: Hybrid CO₂" oninput="avUpdatePreview()">
          </div>
          <div class="arte-field">
            <label>Subheadline</label>
            <textarea id="av-sub" rows="2" placeholder="Ex: A tecnologia que transforma sua clínica." oninput="avUpdatePreview()"></textarea>
          </div>
          <div class="arte-field">
            <label>Dado de impacto</label>
            <input type="text" id="av-dado" placeholder="Ex: +40%" oninput="avUpdatePreview()">
          </div>
          <div class="arte-field">
            <label>Label do dado</label>
            <input type="text" id="av-dado-label" placeholder="Ex: no ticket médio" oninput="avUpdatePreview()">
          </div>
          <div class="arte-field">
            <label>CTA</label>
            <input type="text" id="av-cta" value="Saiba mais →" oninput="avUpdatePreview()">
          </div>

          <div class="arte-section">Visual</div>
          <div class="arte-field">
            <label>Formato</label>
            <select id="av-format" onchange="avUpdatePreview()">
              <option value="1080x1080">1080×1080 (Feed)</option>
              <option value="1080x1920">1080×1920 (Stories)</option>
              <option value="1080x566">1080×566 (Landscape)</option>
            </select>
          </div>
          <div class="arte-field">
            <label>Cor de fundo</label>
            <div class="color-row" id="av-bg-colors">
              <div class="color-swatch active" style="background:#0C0C0C" data-color="#0C0C0C" onclick="avSetColor('bg',this)"></div>
              <div class="color-swatch" style="background:#111827" data-color="#111827" onclick="avSetColor('bg',this)"></div>
              <div class="color-swatch" style="background:#1a0800" data-color="#1a0800" onclick="avSetColor('bg',this)"></div>
              <div class="color-swatch" style="background:#0a1628" data-color="#0a1628" onclick="avSetColor('bg',this)"></div>
              <input type="color" value="#0C0C0C" id="av-bg-custom" oninput="avSetCustomColor('bg',this.value)" style="width:24px;height:24px;border:none;cursor:pointer;border-radius:4px;padding:0">
            </div>
          </div>
          <div class="arte-field">
            <label>Cor de destaque</label>
            <div class="color-row" id="av-acc-colors">
              <div class="color-swatch active" style="background:#E96624" data-color="#E96624" onclick="avSetColor('acc',this)"></div>
              <div class="color-swatch" style="background:#3A9A5A" data-color="#3A9A5A" onclick="avSetColor('acc',this)"></div>
              <div class="color-swatch" style="background:#4A8FBF" data-color="#4A8FBF" onclick="avSetColor('acc',this)"></div>
              <div class="color-swatch" style="background:#D4A017" data-color="#D4A017" onclick="avSetColor('acc',this)"></div>
            </div>
          </div>
          <div class="arte-field">
            <label>Intensidade do gradiente</label>
            <div class="slider-row">
              <input type="range" min="0" max="30" value="8" id="av-grad-intensity" oninput="avUpdatePreview();document.getElementById('av-grad-val').textContent=this.value+'%'">
              <span class="slider-val" id="av-grad-val">8%</span>
            </div>
          </div>

          <div class="arte-section">Exportar</div>
          <button class="arte-btn" onclick="generateArte()">⚡ Gerar Arte</button>
          <button class="arte-btn sec" onclick="downloadArte()">⬇ Baixar PNG</button>
        </div>
        <div class="arte-main">
          <div class="canvas-wrap">
            <canvas id="av-canvas" width="540" height="540"></canvas>
          </div>
          <div class="arte-label">Prévia — clique em Gerar Arte para atualizar</div>
        </div>
      </div>
    </div>

  </div><!-- /hub-panels -->
</div><!-- /hub-root -->

<script>
// ═══════════════════════════════════════════════════════════
// HUB GLOBALS
// ═══════════════════════════════════════════════════════════
const WORKER = 'https://mkt-intel-api.lmglasers.workers.dev';
const APP_ID = 'lmg';

window.HUB = {product: null, assets: null, arteTitle: null, arteSub: null};

function hubTab(name) {
  document.querySelectorAll('.hub-tab').forEach((t,i)=>{
    const panels = ['intel','assets','arte'];
    t.classList.toggle('active', panels[i] === name);
  });
  document.querySelectorAll('.hub-panel').forEach(p=>p.classList.remove('active'));
  document.getElementById('panel-'+name).classList.add('active');
  // Init intel sidebar on first show
  if(name==='intel' && !window._intelInited) {
    window._intelInited = true;
    buildSidebar();
  }
}

function updateHubContext() {
  const ctx = document.getElementById('hub-context');
  const txt = document.getElementById('hub-ctx-text');
  if(window.HUB.product || window.HUB.arteTitle) {
    let parts = [];
    if(window.HUB.product) parts.push('Produto: ' + window.HUB.product);
    if(window.HUB.arteTitle) parts.push('Arte: ' + window.HUB.arteTitle);
    txt.textContent = 'Pipeline — ' + parts.join(' · ');
    ctx.classList.add('show');
  } else {
    ctx.classList.remove('show');
  }
}

function hubSendToAssets(productName) {
  window.HUB.product = productName;
  updateHubContext();
  // Switch to assets panel and pre-select product
  hubTab('assets');
  // Find product card and click it
  setTimeout(()=>{
    const cards = document.querySelectorAll('#panel-assets .pc');
    cards.forEach(card=>{
      const nameEl = card.querySelector('.pc-name');
      if(nameEl && nameEl.textContent.trim() === productName) {
        card.click();
        card.scrollIntoView({behavior:'smooth', block:'center'});
      }
    });
  }, 100);
}

function hubSendToArte(headline, cta) {
  window.HUB.arteTitle = headline;
  updateHubContext();
  hubTab('arte');
  if(headline) {
    document.getElementById('av-headline').value = headline;
  }
  if(cta) {
    document.getElementById('av-cta').value = cta;
  }
  avUpdatePreview();
}

// ═══════════════════════════════════════════════════════════
// MKT INTEL JS
// ═══════════════════════════════════════════════════════════
''' + intel_js + '''

// ═══════════════════════════════════════════════════════════
// ASSET GENERATOR JS
// ═══════════════════════════════════════════════════════════
''' + assets_js + '''

// ═══════════════════════════════════════════════════════════
// ARTE VISUAL JS
// ═══════════════════════════════════════════════════════════
const AV = {
  bg: '#0C0C0C',
  acc: '#E96624',
  gradIntensity: 8,
  w: 540,
  h: 540
};

function avParseFormat(fmt) {
  const [w,h] = fmt.split('x').map(Number);
  return {w, h};
}

function avSetColor(type, el) {
  const parent = type === 'bg' ? document.getElementById('av-bg-colors') : document.getElementById('av-acc-colors');
  parent.querySelectorAll('.color-swatch').forEach(s=>s.classList.remove('active'));
  el.classList.add('active');
  AV[type] = el.dataset.color || el.value;
  avUpdatePreview();
}

function avSetCustomColor(type, val) {
  AV[type] = val;
  const parent = type === 'bg' ? document.getElementById('av-bg-colors') : document.getElementById('av-acc-colors');
  parent.querySelectorAll('.color-swatch').forEach(s=>s.classList.remove('active'));
  avUpdatePreview();
}

function avGetValues() {
  return {
    eyebrow: document.getElementById('av-eyebrow').value || 'LMG® LASER MEDICAL GROUP',
    headline: document.getElementById('av-headline').value || 'Produto LMG®',
    sub: document.getElementById('av-sub').value || '',
    dado: document.getElementById('av-dado').value || '',
    dadoLabel: document.getElementById('av-dado-label').value || '',
    cta: document.getElementById('av-cta').value || 'Saiba mais →',
    format: document.getElementById('av-format').value,
    gradIntensity: parseInt(document.getElementById('av-grad-intensity').value) || 8
  };
}

function avUpdatePreview() {
  const v = avGetValues();
  const fmt = avParseFormat(v.format);
  // Scale for preview: max 540px width
  const scale = Math.min(540 / fmt.w, 540 / fmt.h);
  const displayW = Math.round(fmt.w * scale);
  const displayH = Math.round(fmt.h * scale);

  const canvas = document.getElementById('av-canvas');
  canvas.width = displayW;
  canvas.height = displayH;

  avDrawCanvas(canvas, v, displayW, displayH, scale);
}

function avDrawCanvas(canvas, v, w, h, scale) {
  const ctx = canvas.getContext('2d');
  scale = scale || 1;

  // Background
  ctx.fillStyle = AV.bg;
  ctx.fillRect(0, 0, w, h);

  // Gradient overlay
  const alpha = (v.gradIntensity || 8) / 100;
  const grd = ctx.createRadialGradient(w * 0.75, h * 0.5, 0, w * 0.75, h * 0.5, w * 0.6);
  const accHex = AV.acc;
  grd.addColorStop(0, accHex + Math.round(alpha * 255).toString(16).padStart(2,'0'));
  grd.addColorStop(1, 'transparent');
  ctx.fillStyle = grd;
  ctx.fillRect(0, 0, w, h);

  // Subtle grid lines
  ctx.strokeStyle = 'rgba(255,255,255,0.03)';
  ctx.lineWidth = 1;
  for(let x = 0; x < w; x += 40 * scale) {
    ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, h); ctx.stroke();
  }
  for(let y = 0; y < h; y += 40 * scale) {
    ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.stroke();
  }

  const pad = 28 * scale;

  // Eyebrow
  ctx.font = `600 ${Math.round(9 * scale)}px Inter, sans-serif`;
  ctx.fillStyle = AV.acc;
  ctx.letterSpacing = '0.15em';
  ctx.fillText(v.eyebrow, pad, pad + 16 * scale);
  ctx.letterSpacing = '0';

  // Orange accent line
  ctx.fillStyle = AV.acc;
  ctx.fillRect(pad, pad + 24 * scale, 32 * scale, 2 * scale);

  // Dado de impacto (if present)
  let headlineY = h * 0.42;
  if(v.dado) {
    const dadoSize = Math.round(52 * scale);
    ctx.font = `900 ${dadoSize}px Inter, sans-serif`;
    ctx.fillStyle = AV.acc;
    ctx.fillText(v.dado, pad, headlineY);

    if(v.dadoLabel) {
      ctx.font = `500 ${Math.round(11 * scale)}px Inter, sans-serif`;
      ctx.fillStyle = 'rgba(255,255,255,0.5)';
      ctx.fillText(v.dadoLabel.toUpperCase(), pad, headlineY + 16 * scale);
    }
    headlineY = h * 0.62;
  }

  // Headline
  const hlSize = Math.round(30 * scale);
  ctx.font = `900 ${hlSize}px Inter, sans-serif`;
  ctx.fillStyle = '#FFFFFF';

  // Word wrap headline
  const maxW = w - pad * 2;
  const hlWords = v.headline.split(' ');
  let hlLine = '';
  let hlY = headlineY;
  hlWords.forEach((word, i) => {
    const test = hlLine + (hlLine ? ' ' : '') + word;
    if(ctx.measureText(test).width > maxW && hlLine) {
      ctx.fillText(hlLine, pad, hlY);
      hlLine = word;
      hlY += hlSize * 1.2;
    } else {
      hlLine = test;
    }
    if(i === hlWords.length - 1) {
      ctx.fillText(hlLine, pad, hlY);
      hlY += hlSize * 1.2;
    }
  });

  // Sub
  if(v.sub) {
    ctx.font = `400 ${Math.round(12 * scale)}px Inter, sans-serif`;
    ctx.fillStyle = 'rgba(240,238,232,0.65)';
    const subWords = v.sub.split(' ');
    let subLine = '';
    let subY = hlY + 8 * scale;
    subWords.forEach((word, i) => {
      const test = subLine + (subLine ? ' ' : '') + word;
      if(ctx.measureText(test).width > maxW * 0.8 && subLine) {
        ctx.fillText(subLine, pad, subY);
        subLine = word;
        subY += 18 * scale;
      } else {
        subLine = test;
      }
      if(i === subWords.length - 1) {
        ctx.fillText(subLine, pad, subY);
      }
    });
  }

  // CTA button area at bottom
  const ctaY = h - pad - 4 * scale;
  ctx.font = `700 ${Math.round(12 * scale)}px Inter, sans-serif`;
  const ctaW = ctx.measureText(v.cta).width + 24 * scale;
  const ctaH = 32 * scale;
  const ctaX = pad;
  const ctaTop = ctaY - ctaH;

  // CTA bg
  ctx.fillStyle = AV.acc;
  ctx.beginPath();
  ctx.roundRect(ctaX, ctaTop, ctaW, ctaH, 5 * scale);
  ctx.fill();

  // CTA text
  ctx.fillStyle = '#FFFFFF';
  ctx.fillText(v.cta, ctaX + 12 * scale, ctaTop + ctaH / 2 + 4 * scale);

  // LMG logo text (bottom right)
  ctx.font = `800 ${Math.round(10 * scale)}px Inter, sans-serif`;
  ctx.fillStyle = 'rgba(255,255,255,0.3)';
  const logoTxt = 'LMG® Laser Medical Group';
  const logoW = ctx.measureText(logoTxt).width;
  ctx.fillText(logoTxt, w - logoW - pad, h - pad + 4 * scale);
}

function generateArte() {
  avUpdatePreview();
}

function downloadArte() {
  const v = avGetValues();
  const fmt = avParseFormat(v.format);

  // Create high-res canvas
  const canvas = document.createElement('canvas');
  canvas.width = fmt.w;
  canvas.height = fmt.h;

  avDrawCanvas(canvas, v, fmt.w, fmt.h, 1);

  const link = document.createElement('a');
  link.download = `LMG_Arte_${(v.headline||'arte').replace(/\s+/g,'_')}_${v.format}.png`;
  link.href = canvas.toDataURL('image/png');
  link.click();
}

// ═══════════════════════════════════════════════════════════
// INIT
// ═══════════════════════════════════════════════════════════
document.addEventListener('DOMContentLoaded', ()=>{
  // Intel sidebar is built lazily (on first tab switch to intel)
  // But intel panel starts active, so build now
  buildSidebar();
  window._intelInited = true;
  // Draw initial arte preview
  avUpdatePreview();
});

</script>
</body>
</html>
'''

with open(OUTPUT_FILE, 'w') as f:
    f.write(hub_html)

print(f"Done! Written to {OUTPUT_FILE}")
print(f"File size: {len(hub_html):,} bytes")

# Verify
with open(OUTPUT_FILE) as f:
    content = f.read()
print(f"Verified: {len(content):,} bytes")
print("Intel JS length:", len(intel_js))
print("Assets JS length:", len(assets_js))
