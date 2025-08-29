# jogo.py
import os, re, json, random
import streamlit as st
from streamlit.components.v1 import html as st_html
import google.generativeai as genai

# -------------------- Config básica --------------------
# -------------------- Config básica --------------------
st.set_page_config(page_title="Jogo de Associação - Concursos", layout="wide")
st.title("🎮 Jogo de Associação de Palavras - Concursos")

# -------------------- API KEY (3 opções) --------------------
def load_api_key():
    import os
    import streamlit as st

    # 0) Já digitada nesta sessão?
    if st.session_state.get("GOOGLE_API_KEY"):
        return st.session_state["GOOGLE_API_KEY"]

    # 1) Tentar secrets.toml (sem quebrar se não existir)
    try:
        # Alguns Streamlit não suportam .get() em secrets; então usamos try/except
        val = st.secrets.get("GOOGLE_API_KEY") if hasattr(st.secrets, "get") else st.secrets["GOOGLE_API_KEY"]  # noqa
        if val:
            return val
    except Exception:
        pass  # nada de secrets.toml, seguimos

    # 2) Variável de ambiente
    val = os.getenv("GOOGLE_API_KEY")
    if val:
        return val

    # 3) Pedir na UI
    st.warning("⚠️ Nenhuma chave do Gemini encontrada. Informe abaixo para continuar:")
    key = st.text_input("Digite sua GOOGLE_API_KEY", type="password")
    if key:
        st.session_state["GOOGLE_API_KEY"] = key
        return key

    return None

API_KEY = load_api_key()

if not API_KEY:
    st.stop()  # espera o usuário digitar a chave

# Só configura a SDK depois que temos a chave
import google.generativeai as genai
genai.configure(api_key=API_KEY)
# -------------------- UI: pergunta e controles --------------------
st.write("Digite sua pergunta (ex.: **Quais são os princípios da Administração Pública?**) e clique em **Gerar Desafio**:")

pergunta = st.text_input("Pergunta", placeholder="Ex.: Quais são os princípios da Administração Pública?")

col_a, col_b, col_c = st.columns([1,1,1])
with col_a:
    qtd_pares = st.slider("Quantidade de pares", 4, 10, 6, help="Quantos termos/conceitos o Gemini deve propor.")
with col_b:
    modelo = st.selectbox("Modelo do Gemini", ["gemini-1.5-flash", "gemini-1.5-pro"], index=0)
with col_c:
    embaralhar_auto = st.checkbox("Embaralhar ao gerar", value=True)

# -------------------- Gemini helpers --------------------
def _limpar_texto(s: str) -> str:
    s = (s or "").strip()
    s = re.sub(r"\s+", " ", s)
    return s

def gerar_pares_gemini(pergunta: str, max_itens: int = 6, modelo: str = "gemini-1.5-flash"):
    """
    Retorna (termos, conceitos, gabarito_dict)
    """
    prompt = f"""
Você é um gerador de flashcards objetivos para concursos públicos no Brasil.

Tarefa: Dada a pergunta abaixo, gere entre 4 e {max_itens} pares de "termo" e "conceito" curtos, corretos e não ambíguos.
- Evite termos quase iguais entre si.
- Conceitos devem ter 1–2 frases, no máximo ~160 caracteres cada.
- Responda exclusivamente em português do Brasil.
- Saída ESTRITAMENTE em JSON no formato:
[
  {{"termo": "Texto do termo", "conceito": "Texto do conceito"}},
  ...
]

Pergunta do usuário: "{pergunta}"
Somente JSON. Sem comentários, sem markdown, sem texto extra antes ou depois.
"""
    model = genai.GenerativeModel(modelo)
    resp = model.generate_content(prompt)
    text = resp.text or ""

    m = re.search(r"\[\s*\{.*?\}\s*\]", text, flags=re.S)
    if not m:
        raise ValueError(f"JSON não encontrado na resposta do modelo: {text[:200]}...")

    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError as e:
        raise ValueError(f"Falha ao decodificar JSON: {e}") from e

    data = json.loads(m.group(0))

    pares = []
    vistos_termos = set()
    for item in data:
        termo = _limpar_texto(item.get("termo", ""))
        conceito = _limpar_texto(item.get("conceito", ""))
        if not termo or not conceito:
            continue
        if termo.lower() in vistos_termos:
            continue
        if len(conceito) > 220:
            conceito = conceito[:217].rstrip() + "..."
        vistos_termos.add(termo.lower())
        pares.append((termo, conceito))

    if len(pares) < 4:
        raise ValueError("Poucos pares válidos retornados pelo modelo.")

    termos = [t for t, _ in pares]
    conceitos = [c for _, c in pares]
    gabarito = {t: c for t, c in pares}

    return termos, conceitos, gabarito

def gerar_pares_mock():
    base = {
        "Legalidade": "A administração só pode agir conforme a lei.",
        "Impessoalidade": "Os atos devem visar ao interesse público, sem favorecimento.",
        "Moralidade": "Os atos devem respeitar princípios éticos.",
        "Publicidade": "Os atos devem ser transparentes e acessíveis.",
        "Eficiência": "Os serviços devem ser prestados de forma adequada e rápida."
    }
    termos = list(base.keys())
    conceitos = list(base.values())
    return termos, conceitos, base

# -------------------- Estado --------------------
if "desafio" not in st.session_state:
    st.session_state.desafio = None

# -------------------- Geração do desafio --------------------
c1, c2 = st.columns([1,1])
with c1:
    if st.button("🎲 Gerar Desafio"):
        if API_KEY and (pergunta or "").strip():
            try:
                termos, conceitos, gabarito = gerar_pares_gemini(pergunta.strip(), max_itens=qtd_pares, modelo=modelo)
                if embaralhar_auto:
                    random.shuffle(termos); random.shuffle(conceitos)
                st.session_state.desafio = {"termos": termos, "conceitos": conceitos, "gabarito": gabarito}
            except Exception as e:
                st.warning(f"Falha ao gerar via Gemini: {e}. Usando exemplo mock.")
                termos, conceitos, gabarito = gerar_pares_mock()
                if embaralhar_auto:
                    random.shuffle(termos); random.shuffle(conceitos)
                st.session_state.desafio = {"termos": termos, "conceitos": conceitos, "gabarito": gabarito}
        else:
            if not API_KEY:
                st.warning("Sem GOOGLE_API_KEY configurada. Usando exemplo mock.")
            elif not (pergunta or "").strip():
                st.warning("Digite uma pergunta antes de gerar com o Gemini. Usando exemplo mock.")
            termos, conceitos, gabarito = gerar_pares_mock()
            if embaralhar_auto:
                random.shuffle(termos); random.shuffle(conceitos)
            st.session_state.desafio = {"termos": termos, "conceitos": conceitos, "gabarito": gabarito}

with c2:
    if st.session_state.get("desafio") and st.button("🔄 Novo Embaralhamento"):
        d = st.session_state["desafio"]
        termos, conceitos, gabarito = d["termos"], d["conceitos"], d["gabarito"]
        random.shuffle(termos); random.shuffle(conceitos)
        st.session_state.desafio = {"termos": termos, "conceitos": conceitos, "gabarito": gabarito}

# Guard antes de usar o desafio
if not st.session_state.desafio:
    st.info("Clique em **Gerar Desafio** para começar.")
    st.stop()

termos = st.session_state.desafio["termos"]
conceitos = st.session_state.desafio["conceitos"]
gabarito = st.session_state.desafio["gabarito"]

# -------------------- HTML/JS (com chaves escapadas) --------------------
html_code = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8" />
<style>
  :root {{
    --border:#e5e7eb; --muted:#cbd5e1; --bg:#ffffff; --panel:#f8fafc;
    --ok:#16a34a; --err:#dc2626; --brand:#1d4ed8; --ink:#0f172a; --warn:#f59e0b;
  }}
  * {{ box-sizing:border-box; }}
  body {{ font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; margin:0; }}
  .game-root {{
    border:1px solid var(--border); border-radius:14px; background:var(--bg);
    box-shadow:0 1px 4px rgba(0,0,0,.05);
  }}
  .toolbar {{
    position: sticky; top: 0; z-index: 10;
    display:flex; gap:12px; align-items:center; justify-content:flex-start;
    padding:12px; background:var(--bg); border-bottom:1px solid var(--border);
  }}
  .btn {{
    padding:8px 12px; border-radius:10px; border:1px solid var(--muted);
    background:#fff; cursor:pointer; font-weight:500;
  }}
  .btn:hover {{ background:#f8fafc; }}
  .score {{ margin-left:auto; font-weight:600; }}

  .row {{ display:flex; gap:24px; padding:14px; background:var(--panel); border-radius:0 0 14px 14px; }}
  .col {{ flex:1; min-width:0; }}
  .panel {{
    background:#fff; border:1px solid var(--border); border-radius:12px;
    box-shadow:0 1px 3px rgba(0,0,0,0.06); display:flex; flex-direction:column; min-height:660px;
  }}
  .panel h3 {{ margin:14px 14px 8px; }}
  .panel-body {{
    margin:0 14px 14px; border:1px dashed var(--muted); border-radius:10px;
    background:#fafafa; padding:12px; height:600px; overflow-y:auto;
  }}

  .card-term {{
    padding:14px 16px; background:var(--brand); color:white; border-radius:12px;
    margin:8px 0; cursor:grab; user-select:none; font-weight:600; font-size:15px; text-align:center;
    transition: transform 0.15s, box-shadow .15s; box-shadow:0 1px 2px rgba(0,0,0,.08);
  }}
  .card-term:active {{ cursor:grabbing; }}
  .card-term:hover {{ transform:scale(1.03); }}

  .concept-card {{
    border:1px solid var(--muted); border-radius:12px; padding:12px; margin:10px 0; background:#ffffff;
    box-shadow:0 1px 2px rgba(0,0,0,0.05);
  }}
  .concept-text {{ color:var(--ink); margin-bottom:8px; font-size:15px; font-weight:500; }}
  .drop {{
    border:2px dashed var(--muted); min-height:64px; border-radius:12px; padding:8px;
    display:flex; align-items:center; justify-content:center; background:#fff; transition: background .15s, border-color .15s;
  }}
  .drop.over {{ background:#f1f5f9; }}
  .correct {{ border-color:var(--ok) !important; background:#ecfdf5 !important; }}
  .wrong   {{ border-color:var(--err) !important; background:#fef2f2 !important; }}

  .badge {{ display:inline-block; padding:4px 8px; border-radius:8px; font-size:12px; margin-left:8px; }}
  .ok  {{ background:var(--ok);  color:#fff; }}
  .err {{ background:var(--err); color:#fff; }}

  /* ===== Modal (popup) ===== */
  .modal-backdrop {{
    position: fixed; inset: 0; background: rgba(0,0,0,0.45);
    display: none; align-items: center; justify-content: center; z-index: 9999;
  }}
  .modal {{
    width: min(520px, 92vw);
    background: #fff; border-radius: 16px; border: 1px solid var(--border);
    box-shadow: 0 20px 60px rgba(0,0,0,.25);
    padding: 24px; text-align: center; position: relative; overflow: hidden;
  }}
  .modal h2 {{ margin: 0 0 8px; }}
  .modal p  {{ margin: 8px 0 16px; color: #334155; }}
  .modal .close {{
    position: absolute; top: 10px; right: 12px; border:1px solid var(--muted);
    background:#fff; border-radius: 8px; padding: 6px 10px; cursor:pointer;
  }}

  /* Confetti simples */
  .confetti {{
    position: absolute; top: -10px; width: 8px; height: 14px; opacity: .9;
    animation: fall 2.1s linear forwards;
  }}
  @keyframes fall {{
    0%   {{ transform: translateY(-20px) rotate(0deg);   }}
    100% {{ transform: translateY(700px) rotate(720deg); }}
  }}

  /* Animação de pulso para motivação */
  .pulse {{ display:inline-block; animation: pulser 1s ease-in-out infinite; }}
  @keyframes pulser {{
    0%   {{ transform: scale(1);   }}
    50%  {{ transform: scale(1.12);}}
    100% {{ transform: scale(1);   }}
  }}

  .bar-wrap {{
    height: 10px; background:#f1f5f9; border-radius: 999px; overflow:hidden; margin: 12px 0 6px;
    border:1px solid var(--border);
  }}
  .bar-fill {{
    height:100%; width:0%; background: linear-gradient(90deg, #22c55e, #3b82f6);
    transition: width .6s ease;
  }}
  .hint {{ font-size: 13px; color:#64748b; }}
</style>
</head>
<body>

<div class="game-root">
  <div class="toolbar">
    <button class="btn" id="btnCheck">✅ Verificar</button>
    <button class="btn" id="btnReset">🧹 Limpar</button>
    <button class="btn" id="btnShow">👀 Mostrar gabarito</button>
    <div id="score" class="score"></div>
  </div>

  <div class="row">
    <!-- COLUNA TERMOS -->
    <div class="col panel">
      <h3>📝 Termos</h3>
      <div class="panel-body" id="termsScroll">
        <div id="terms"></div>
      </div>
    </div>

    <!-- COLUNA CONCEITOS -->
    <div class="col panel">
      <h3>📖 Conceitos</h3>
      <div class="panel-body" id="conceptsScroll">
        <div id="concepts"></div>
      </div>
    </div>
  </div>
</div>

<!-- Modal -->
<div class="modal-backdrop" id="modalBackdrop" aria-hidden="true">
  <div class="modal" role="dialog" aria-modal="true" aria-labelledby="modalTitle">
    <button class="close" id="modalClose">✖</button>
    <div id="modalContent"></div>
  </div>
</div>

<script>
const termos = {json.dumps(termos, ensure_ascii=False)};
const conceitos = {json.dumps(conceitos, ensure_ascii=False)};
const gabarito = {json.dumps(gabarito, ensure_ascii=False)};

const $terms = document.getElementById("terms");
const $concepts = document.getElementById("concepts");
const $termsScroll = document.getElementById("termsScroll");
const $conceptsScroll = document.getElementById("conceptsScroll");

// Monta Termos
for (let i=0;i<termos.length;i++) {{
  const t = termos[i];
  const el = document.createElement("div");
  el.className = "card-term";
  el.id = "drag-" + i;
  el.textContent = t;
  el.draggable = true;
  el.addEventListener("dragstart", function(e) {{
    e.dataTransfer.setData("text/plain", el.id);
  }});
  $terms.appendChild(el);
}}

// Monta Conceitos + drops
for (let i=0;i<conceitos.length;i++) {{
  const c = conceitos[i];
  const card = document.createElement("div");
  card.className = "concept-card";
  const text = document.createElement("div");
  text.className = "concept-text";
  text.textContent = c;
  const drop = document.createElement("div");
  drop.className = "drop";
  drop.id = "drop-" + i;

  drop.addEventListener("dragover", function(e) {{
    e.preventDefault();
    drop.classList.add("over");
  }});
  drop.addEventListener("dragleave", function() {{ drop.classList.remove("over"); }});
  drop.addEventListener("drop", function(e) {{
    e.preventDefault();
    drop.classList.remove("over");
    const id = e.dataTransfer.getData("text/plain");
    const dragged = document.getElementById(id);
    if (!dragged) return;
    if (drop.firstElementChild) {{
      $terms.insertBefore(drop.firstElementChild, $terms.firstChild);
    }}
    drop.innerHTML = "";
    drop.appendChild(dragged);
  }});

  card.appendChild(text);
  card.appendChild(drop);
  $concepts.appendChild(card);
}}

// ===== Modal =====
const modalBackdrop = document.getElementById("modalBackdrop");
const modalClose = document.getElementById("modalClose");
const modalContent = document.getElementById("modalContent");

function closeModal() {{
  modalBackdrop.style.display = "none";
  modalBackdrop.setAttribute("aria-hidden", "true");
  // remove confetes remanescentes
  const confs = document.querySelectorAll(".confetti");
  for (let i=0;i<confs.length;i++) confs[i].remove();
}}
modalClose.addEventListener("click", closeModal);
modalBackdrop.addEventListener("click", function(e) {{
  if (e.target === modalBackdrop) closeModal();
}});
document.addEventListener("keydown", function(e) {{
  if (e.key === "Escape") closeModal();
}});

// Confete
function spawnConfetti(n) {{
  if (!n) n = 60;
  for (let i = 0; i < n; i++) {{
    const piece = document.createElement("div");
    piece.className = "confetti";
    const left = Math.random() * 100;
    const hue  = Math.floor(Math.random() * 360);
    piece.style.left = left + "%";
    piece.style.background = 'hsl(' + hue + ', 90%, 55%)';
    piece.style.animationDelay = (Math.random() * 0.8) + "s";
    piece.style.transform = 'translateY(-20px) rotate(' + (Math.random()*360) + 'deg)';
    modalBackdrop.appendChild(piece);
    setTimeout(function() {{ piece.remove(); }}, 2500);
  }}
}}

function showSuccessModal(acertos, total, perc) {{
  modalContent.innerHTML = ''
    + '<h2 id="modalTitle">🎉 Parabéns! Resultado Perfeito</h2>'
    + '<p>Você acertou <b>' + acertos + ' / ' + total + '</b> (' + Math.round(perc) + '%). Excelente!</p>'
    + '<div class="bar-wrap"><div class="bar-fill" style="width:100%"></div></div>'
    + '<p class="hint">Dica: tente aumentar a velocidade mantendo a precisão — você está pronto para o próximo nível! 🚀</p>';
  modalBackdrop.style.display = "flex";
  modalBackdrop.setAttribute("aria-hidden", "false");
  spawnConfetti(80);
}}

function showMotivationModal(acertos, total, perc) {{
  var tips = [
    "Leia com calma os conceitos: identifique palavras-chave ⚡",
    "Tente agrupar termos semelhantes e elimine os óbvios primeiro 🧠",
    "Se pintar dúvida, use o gabarito para aprender e tente de novo 😉"
  ];
  var tip = tips[Math.floor(Math.random()*tips.length)];
  modalContent.innerHTML = ''
    + '<h2 id="modalTitle"><span class="pulse">💪 Quase lá!</span></h2>'
    + '<p>Você acertou <b>' + acertos + ' / ' + total + '</b> (' + Math.round(perc) + '%). Continue — cada tentativa reforça a memória!</p>'
    + '<div class="bar-wrap"><div class="bar-fill" id="barFill" style="width:0%"></div></div>'
    + '<p class="hint">Sugestão: ' + tip + '</p>'
    + '<button class="btn" id="btnTryAgain">Tentar novamente</button>';
  modalBackdrop.style.display = "flex";
  modalBackdrop.setAttribute("aria-hidden", "false");
  setTimeout(function() {{
    var fill = document.getElementById("barFill");
    if (fill) fill.style.width = perc + "%";
  }}, 50);
  var btn = document.getElementById("btnTryAgain");
  if (btn) btn.addEventListener("click", closeModal);
}}

// ===== Verificação, Limpar e Gabarito =====
function verificar() {{
  var acertos = 0;
  var drops = document.querySelectorAll(".drop");
  for (var d=0; d<drops.length; d++) drops[d].classList.remove("correct","wrong");
  var badges = document.querySelectorAll(".badge");
  for (var b=0; b<badges.length; b++) badges[b].remove();

  var cards = document.querySelectorAll(".concept-card");
  for (var i=0; i<cards.length; i++) {{
    var card = cards[i];
    var conceptTxt = card.querySelector(".concept-text").textContent.trim();
    var drop = card.querySelector(".drop");
    var termoEl = drop.firstElementChild;
    if (!termoEl) continue;

    var termo = termoEl.textContent.trim();
    var conceitoCorreto = gabarito[termo];

    if (conceitoCorreto && conceitoCorreto === conceptTxt) {{
      drop.classList.add("correct");
      acertos += 1;
      var ok = document.createElement("span");
      ok.className = "badge ok";
      ok.textContent = "✔";
      card.querySelector(".concept-text").appendChild(ok);
    }} else {{
      drop.classList.add("wrong");
      var err = document.createElement("span");
      err.className = "badge err";
      err.textContent = "✘";
      card.querySelector(".concept-text").appendChild(err);
    }}
  }}
  var total = Object.keys(gabarito).length;
  var perc = total ? (acertos/total)*100 : 0;
  document.getElementById("score").textContent = 'Pontuação: ' + acertos + ' / ' + total;

  if (acertos === total && total > 0) {{
    showSuccessModal(acertos, total, perc);
  }} else {{
    showMotivationModal(acertos, total, perc);
  }}
}}

function limpar() {{
  document.getElementById("score").textContent = "";
  var drops = document.querySelectorAll(".drop");
  for (var i=0; i<drops.length; i++) {{
    var drop = drops[i];
    drop.classList.remove("correct","wrong");
    var termo = drop.firstElementChild;
    if (termo) $terms.insertBefore(termo, $terms.firstChild);
  }}
  var badges = document.querySelectorAll(".badge");
  for (var b=0; b<badges.length; b++) badges[b].remove();
}}

function mostrarGabarito() {{
  limpar();
  var cards = document.querySelectorAll(".concept-card");
  for (var i=0; i<cards.length; i++) {{
    var card = cards[i];
    var conceptTxt = card.querySelector(".concept-text").textContent.trim();
    var termoCorreto = null;
    for (var t in gabarito) {{
      if (gabarito[t] === conceptTxt) {{ termoCorreto = t; break; }}
    }}
    if (!termoCorreto) continue;
    var termosEls = document.querySelectorAll(".card-term");
    var termoEl = null;
    for (var k=0; k<termosEls.length; k++) {{
      if (termosEls[k].textContent.trim() === termoCorreto) {{ termoEl = termosEls[k]; break; }}
    }}
    if (!termoEl) continue;
    var drop = card.querySelector(".drop");
    drop.innerHTML = "";
    drop.appendChild(termoEl);
  }}
  verificar();
}}

document.getElementById("btnCheck").addEventListener("click", verificar);
document.getElementById("btnReset").addEventListener("click", limpar);
document.getElementById("btnShow").addEventListener("click", mostrarGabarito);

// Auto-scroll em cada coluna
function setupAutoScroll(container) {{
  container.addEventListener("dragover", function(e) {{
    var rect = container.getBoundingClientRect();
    var threshold = 60;
    var speed = 16;
    if (e.clientY < rect.top + threshold) {{
      container.scrollTop -= speed;
    }} else if (e.clientY > rect.bottom - threshold) {{
      container.scrollTop += speed;
    }}
  }});
}}
setupAutoScroll($termsScroll);
setupAutoScroll($conceptsScroll);
</script>

</body>
</html>
"""

st_html(html_code, height=840, scrolling=False)
