"""
Componentes visuais e de sessão compartilhados entre todas as páginas:
- injeção de CSS/fontes (tema "painel de posto")
- cabeçalho padrão
- medidor circular (gauge) estilo marcador de combustível
- seletor de vendedor logado (controle leve por PIN, não é autenticação forte)
"""
import streamlit as st
import base64
from pathlib import Path
import db

ICONS_DIR = Path(__file__).parent / "assets" / "icons"


@st.cache_data
def _icon_b64(nome_arquivo):
    """Carrega um ícone PNG de assets/icons/ e devolve em base64 (cacheado)."""
    caminho = ICONS_DIR / nome_arquivo
    if not caminho.exists():
        return None
    with open(caminho, "rb") as f:
        return base64.b64encode(f.read()).decode()


PALETTE = {
    "bg": "#0B1220",
    "surface": "#121C30",
    "surface_2": "#182842",
    "border": "#263654",
    "amber": "#8DC63F",
    "amber_dim": "#4E7A22",
    "steel": "#3AA6A0",
    "green": "#3FA796",
    "red": "#D9534F",
    "text": "#E8EAED",
    "muted": "#8B95A1",
}


def inject_css():
    st.markdown(f"""
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@600;700;800&family=Inter:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
    <style>
        html, body, [class*="css"] {{
            font-family: 'Inter', sans-serif;
        }}
        h1, h2, h3 {{
            font-family: 'Poppins', sans-serif !important;
            letter-spacing: 0.02em;
            text-transform: uppercase;
        }}
        .stApp {{
            background: {PALETTE['bg']};
        }}
        [data-testid="stSidebar"] {{
            background: {PALETTE['surface']};
            border-right: 1px solid {PALETTE['border']};
        }}
        .op-header {{
            display: flex;
            align-items: center;
            gap: 14px;
            padding: 14px 20px;
            background: linear-gradient(90deg, {PALETTE['surface_2']} 0%, {PALETTE['surface']} 100%);
            border: 1px solid {PALETTE['border']};
            border-left: 4px solid {PALETTE['amber']};
            border-radius: 6px;
            margin-bottom: 22px;
        }}
        .op-header .op-brand {{
            font-family: 'Poppins', sans-serif;
            font-weight: 700;
            font-size: 11px;
            letter-spacing: 0.12em;
            color: {PALETTE['amber']};
            margin: 0 0 2px 0;
            text-transform: uppercase;
        }}
        .op-header .op-title {{
            font-family: 'Poppins', sans-serif;
            font-weight: 700;
            font-size: 26px;
            text-transform: uppercase;
            letter-spacing: 0.03em;
            color: {PALETTE['text']};
            margin: 0;
        }}
        .op-header .op-subtitle {{
            font-family: 'Inter', sans-serif;
            font-size: 13px;
            color: {PALETTE['muted']};
            margin: 0;
        }}
        .op-card {{
            background: {PALETTE['surface']};
            border: 1px solid {PALETTE['border']};
            border-radius: 8px;
            padding: 16px 18px;
            margin-bottom: 12px;
        }}
        .op-card.op-accent {{
            border-left: 3px solid {PALETTE['amber']};
        }}
        .op-badge {{
            display: inline-block;
            font-family: 'IBM Plex Mono', monospace;
            font-size: 11px;
            font-weight: 500;
            padding: 3px 9px;
            border-radius: 4px;
            letter-spacing: 0.03em;
        }}
        .op-badge-a {{ background: rgba(242,169,59,0.18); color: {PALETTE['amber']}; border: 1px solid {PALETTE['amber_dim']}; }}
        .op-badge-b {{ background: rgba(61,165,217,0.15); color: {PALETTE['steel']}; border: 1px solid #235C7A; }}
        .op-badge-c {{ background: rgba(139,149,161,0.12); color: {PALETTE['muted']}; border: 1px solid {PALETTE['border']}; }}
        .op-badge-green {{ background: rgba(76,154,106,0.18); color: {PALETTE['green']}; border: 1px solid #2E5E3F; }}
        .op-badge-red {{ background: rgba(217,83,79,0.15); color: {PALETTE['red']}; border: 1px solid #7A2C29; }}
        .op-mono {{ font-family: 'IBM Plex Mono', monospace; }}
        [data-testid="stMetric"] {{
            background: {PALETTE['surface']};
            border: 1px solid {PALETTE['border']};
            border-radius: 8px;
            padding: 12px 16px;
        }}
        [data-testid="stMetricValue"] {{
            font-family: 'IBM Plex Mono', monospace;
            color: {PALETTE['amber']};
        }}
        div[data-testid="stButton"] > button, .stDownloadButton > button, .stLinkButton > a {{
            border-radius: 6px;
            font-weight: 600;
            border: 1px solid {PALETTE['amber_dim']};
        }}
        div[data-testid="stButton"] > button[kind="primary"] {{
            background: {PALETTE['amber']};
            color: #0B1220;
        }}
        hr {{ border-color: {PALETTE['border']}; }}
    </style>
    """, unsafe_allow_html=True)


def header(titulo, subtitulo="", icone=None):
    icon_html = ""
    if icone:
        b64 = _icon_b64(f"nav_{icone}.png")
        if b64:
            icon_html = f'<img src="data:image/png;base64,{b64}" style="height:54px;width:auto" />'
    st.markdown(f"""
    <div class="op-header">
        {icon_html}
        <div>
            <p class="op-brand">⛽ PetroSales</p>
            <p class="op-title">{titulo}</p>
            <p class="op-subtitle">{subtitulo}</p>
        </div>
    </div>
    """, unsafe_allow_html=True)


def pin_icon_path(nome):
    """Caminho absoluto pro arquivo de ícone de pin (assets/icons/pin_*.png),
    pra usar com folium.CustomIcon() na página de Mapa."""
    caminho = ICONS_DIR / f"pin_{nome}.png"
    return str(caminho) if caminho.exists() else None


def gauge_svg(percentual, label="META", size=150):
    """Medidor circular estilo marcador de combustível, de 0 a 100%+."""
    percentual_clamped = max(0, min(percentual, 130))
    angulo = -90 + (percentual_clamped / 100) * 180  # semicírculo -90 a +90
    if percentual >= 100:
        cor = PALETTE["green"]
    elif percentual >= 60:
        cor = PALETTE["amber"]
    else:
        cor = PALETTE["steel"]

    import math
    cx, cy, r = 75, 80, 60
    rad = math.radians(angulo)
    x2 = cx + r * math.sin(rad)
    y2 = cy - r * math.cos(rad)

    # arco de fundo (semicírculo completo)
    svg = f"""
    <svg width="{size}" height="{size*0.75}" viewBox="0 0 150 110" xmlns="http://www.w3.org/2000/svg">
        <path d="M 15 80 A 60 60 0 0 1 135 80" fill="none" stroke="{PALETTE['border']}" stroke-width="10" stroke-linecap="round"/>
        <path d="M 15 80 A 60 60 0 0 1 {cx + r*math.sin(math.radians(-90+(min(percentual,100)/100)*180))} {cy - r*math.cos(math.radians(-90+(min(percentual,100)/100)*180))}"
              fill="none" stroke="{cor}" stroke-width="10" stroke-linecap="round"/>
        <line x1="{cx}" y1="{cy}" x2="{x2}" y2="{y2}" stroke="{PALETTE['text']}" stroke-width="3" stroke-linecap="round"/>
        <circle cx="{cx}" cy="{cy}" r="5" fill="{PALETTE['text']}"/>
        <text x="75" y="100" text-anchor="middle" font-family="IBM Plex Mono, monospace" font-size="16" font-weight="600" fill="{cor}">{percentual:.0f}%</text>
        <text x="75" y="16" text-anchor="middle" font-family="Poppins, sans-serif" font-size="11" letter-spacing="1" fill="{PALETTE['muted']}">{label}</text>
    </svg>
    """
    return svg


def seletor_vendedor_logado():
    """Renderiza na sidebar um seletor de 'quem está usando' + PIN leve.
    Retorna o dict do vendedor logado (ou None)."""
    vendedores = db.get_vendedores(somente_ativos=True)
    st.sidebar.markdown("### 👤 Vendedor")

    if not vendedores:
        st.sidebar.info("Cadastre vendedores na página **Equipe**.")
        return None

    nomes = {v["id"]: v["nome"] for v in vendedores}
    vendedor_id_atual = st.session_state.get("vendedor_logado_id")

    escolhido = st.sidebar.selectbox(
        "Quem está usando agora?",
        options=list(nomes.keys()),
        format_func=lambda x: nomes[x],
        index=list(nomes.keys()).index(vendedor_id_atual) if vendedor_id_atual in nomes else 0,
    )

    if escolhido != vendedor_id_atual:
        st.session_state["vendedor_logado_id"] = escolhido

    vendedor = next(v for v in vendedores if v["id"] == escolhido)
    return vendedor
