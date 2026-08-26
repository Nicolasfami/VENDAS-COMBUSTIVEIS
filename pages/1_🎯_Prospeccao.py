import streamlit as st
import pandas as pd
import json
import db
import common
import anp_api

st.set_page_config(page_title="Prospecção", page_icon="🎯", layout="wide")
db.init_db()
common.inject_css()
vendedor = common.seletor_vendedor_logado()
common.header("Prospecção de Postos", "Base oficial da ANP — revendedores varejistas de combustíveis automotivos")


@st.cache_data
def carregar_csv_anp(caminho_ou_arquivo):
    df = pd.read_csv(caminho_ou_arquivo, sep=";", encoding="latin1", dtype=str)
    df.columns = [c.strip() for c in df.columns]
    return df


def extrair_produtos(posto):
    """Lê produtos_json (vindo da API) e detecta diesel/gasolina/etanol automaticamente."""
    produtos_raw = posto.get("produtos_json")
    if not produtos_raw:
        return {"diesel": bool(posto.get("comercializa_diesel")),
                "gasolina": bool(posto.get("comercializa_gasolina")),
                "etanol": bool(posto.get("comercializa_etanol")),
                "lista": []}
    try:
        lista = json.loads(produtos_raw)
    except (TypeError, json.JSONDecodeError):
        lista = []
    nomes = " ".join((p.get("produto") or "").upper() for p in lista)
    return {
        "diesel": "DIESEL" in nomes,
        "gasolina": "GASOLINA" in nomes,
        "etanol": "ETANOL" in nomes,
        "lista": lista,
    }


def calcular_score(posto, pesos):
    score = 0
    motivos = []
    produtos = extrair_produtos(posto)
    if (posto.get("bandeira") or "").upper() == "BANDEIRA BRANCA":
        score += pesos["bandeira_branca"]
        motivos.append(f"Bandeira branca (+{pesos['bandeira_branca']})")
    if produtos["diesel"]:
        score += pesos["diesel"]
        motivos.append(f"Comercializa diesel (+{pesos['diesel']})")
    if produtos["diesel"] and produtos["gasolina"] and produtos["etanol"]:
        score += pesos["linha_completa"]
        motivos.append(f"Linha completa (+{pesos['linha_completa']})")
    if posto.get("tancagem_total_m3") and posto["tancagem_total_m3"] >= 60:
        score += pesos["alta_tancagem"]
        motivos.append(f"Alta tancagem: {posto['tancagem_total_m3']:.0f} m³ (+{pesos['alta_tancagem']})")
    if (posto.get("status") or "Não visitado") == "Não visitado":
        score += pesos["nunca_visitado"]
        motivos.append(f"Nunca visitado (+{pesos['nunca_visitado']})")
    return score, motivos


def prioridade_label(score):
    if score >= 40:
        return "A", "op-badge-a"
    elif score >= 15:
        return "B", "op-badge-b"
    return "C", "op-badge-c"


with st.sidebar:
    st.markdown("### 🔍 Região")
    uf = st.text_input("UF", value=st.session_state.get("uf_atual", "SP"), max_chars=2).upper()
    municipio = st.text_input("Município", value=st.session_state.get("municipio_atual", "Jandira"))

    fonte = st.radio("Fonte dos dados", ["API oficial da ANP (recomendado)", "Importar CSV manual"])

    if fonte.startswith("API"):
        buscar_api = st.button("🔎 Buscar via API", use_container_width=True, type="primary")
        arquivo_csv = None
        buscar_csv = False
    else:
        arquivo_csv = st.file_uploader("CSV da ANP", type=["csv"])
        buscar_csv = st.button("Buscar postos (CSV)", use_container_width=True, type="primary")
        buscar_api = False

    st.markdown("### ⚖️ Pesos do score")
    peso_bandeira_branca = st.slider("Bandeira branca", 0, 60, 40)
    peso_diesel = st.slider("Comercializa diesel", 0, 30, 15)
    peso_linha_completa = st.slider("Linha completa", 0, 30, 10)
    peso_alta_tancagem = st.slider("Alta tancagem (≥60m³)", 0, 30, 20)
    peso_nunca_visitado = st.slider("Nunca visitado", 0, 20, 5)

pesos = {
    "bandeira_branca": peso_bandeira_branca,
    "diesel": peso_diesel,
    "linha_completa": peso_linha_completa,
    "alta_tancagem": peso_alta_tancagem,
    "nunca_visitado": peso_nunca_visitado,
}

if buscar_api:
    with st.spinner(f"Consultando API oficial da ANP para {municipio}/{uf}..."):
        try:
            postos_api = anp_api.buscar_postos_por_cidade(uf, municipio)
            if not postos_api:
                st.sidebar.warning("Nenhum posto encontrado para essa região.")
            else:
                db.upsert_postos_api(postos_api)
                st.session_state["uf_atual"] = uf
                st.session_state["municipio_atual"] = municipio
                st.sidebar.success(f"{len(postos_api)} postos carregados via API (com produtos, tancagem e coordenadas).")
        except Exception as e:
            st.sidebar.error(f"Erro ao consultar a API da ANP: {e}")

if buscar_csv and arquivo_csv is not None:
    with st.spinner("Lendo base da ANP e filtrando região..."):
        df = carregar_csv_anp(arquivo_csv)
        df_filtrado = df[(df["UF"] == uf) & (df["MUNICIPIO"].str.upper() == municipio.upper())]
        if df_filtrado.empty:
            st.sidebar.warning("Nenhum posto encontrado para essa região.")
        else:
            db.upsert_postos(df_filtrado)
            st.session_state["uf_atual"] = uf
            st.session_state["municipio_atual"] = municipio
            st.sidebar.success(f"{len(df_filtrado)} postos carregados via CSV.")

uf_atual = st.session_state.get("uf_atual", uf)
municipio_atual = st.session_state.get("municipio_atual", municipio)
postos = db.get_postos_by_city(uf_atual, municipio_atual)

if not postos:
    st.info(
        "Envie o CSV da ANP na barra lateral, informe UF e Município e clique em **Buscar postos**.\n\n"
        "Baixe o CSV oficial em: gov.br/anp → Dados Abertos → "
        "Dados Cadastrais dos Revendedores Varejistas de Combustíveis Automotivos"
    )
    st.stop()

for p in postos:
    score, motivos = calcular_score(p, pesos)
    p["score"] = score
    p["motivos"] = motivos
    prioridade, badge_class = prioridade_label(score)
    p["prioridade"] = prioridade
    p["badge_class"] = badge_class

postos_ordenados = sorted(postos, key=lambda p: -p["score"])

st.subheader(f"{municipio_atual}/{uf_atual} — {len(postos)} posto(s)")

if "selecionados" not in st.session_state:
    st.session_state["selecionados"] = set()

for p in postos_ordenados:
    with st.container():
        st.markdown('<div class="op-card">', unsafe_allow_html=True)
        cols = st.columns([0.4, 3, 1.3, 1.3, 1.4, 1.2])
        with cols[0]:
            checked = st.checkbox("", key=f"chk_{p['cnpj']}",
                                   value=p["cnpj"] in st.session_state["selecionados"])
            if checked:
                st.session_state["selecionados"].add(p["cnpj"])
            else:
                st.session_state["selecionados"].discard(p["cnpj"])
        with cols[1]:
            st.markdown(f"**{p['razao_social']}**")
            st.caption(f"{p['endereco']}, {p['bairro']}")
        with cols[2]:
            st.markdown(f"<span class='op-badge op-badge-b'>{p['bandeira']}</span>", unsafe_allow_html=True)
        with cols[3]:
            st.caption(f"Status: {p.get('status') or 'Não visitado'}")
        with cols[4]:
            st.markdown(
                f"<span class='op-badge {p['badge_class']}'>PRIORIDADE {p['prioridade']} · {p['score']} pts</span>",
                unsafe_allow_html=True)
        with cols[5]:
            with st.popover("Detalhes"):
                st.write(f"CNPJ: {p['cnpj']}")
                st.write(f"Autorização: {p['autorizacao']}")
                st.write(f"CEP: {p['cep']}")
                if p.get("origem_dado") == "API":
                    st.write(f"Tancagem total: {p.get('tancagem_total_m3') or 0:.0f} m³")
                    produtos = extrair_produtos(p)
                    if produtos["lista"]:
                        st.write("Produtos comercializados:")
                        for prod in produtos["lista"]:
                            st.write(f"- {prod['produto']}: {prod['tancagem']} {prod.get('unidMedidaTancagem','')} "
                                     f"· {prod.get('qtdeBicos', 0)} bico(s)")
                if p["motivos"]:
                    st.write("Motivos do score:")
                    for m in p["motivos"]:
                        st.write(f"- {m}")
        st.markdown('</div>', unsafe_allow_html=True)

st.caption(f"✅ {len(st.session_state['selecionados'])} posto(s) selecionado(s) para rota (aba Rota)")
