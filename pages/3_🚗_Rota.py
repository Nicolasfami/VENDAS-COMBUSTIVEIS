import streamlit as st
import db
import geo_utils
import common

st.set_page_config(page_title="Rota", page_icon="🚗", layout="wide")
db.init_db()
common.inject_css()
common.seletor_vendedor_logado()
common.header("Rota de Visitas", "Sequência otimizada + link direto pro Google Maps")

uf_atual = st.session_state.get("uf_atual", "SP")
municipio_atual = st.session_state.get("municipio_atual", "Jandira")
postos = db.get_postos_by_city(uf_atual, municipio_atual)
selecionados_cnpj = st.session_state.get("selecionados", set())
postos_selecionados = [p for p in postos if p["cnpj"] in selecionados_cnpj]

if not postos_selecionados:
    st.info("Selecione postos na página **Prospecção** para gerar uma rota.")
    st.stop()

st.markdown(f"<div class='op-card'>{len(postos_selecionados)} posto(s) selecionado(s).</div>", unsafe_allow_html=True)

usar_origem = st.checkbox("Definir ponto de partida (ex: seu endereço)")
origem_coord = None
if usar_origem:
    endereco_origem = st.text_input("Endereço de partida", placeholder="Ex: Rua Exemplo, 100, Jandira, SP")
    if endereco_origem:
        origem_coord = geo_utils.geocode_endereco(endereco_origem, municipio_atual, uf_atual)
        if not origem_coord:
            st.warning("Não foi possível localizar esse endereço.")

if st.button("🚗 Gerar rota otimizada", type="primary"):
    with st.spinner("Geocodificando e otimizando..."):
        for p in postos_selecionados:
            if p.get("lat") is None:
                resultado = geo_utils.geocode_endereco(p["endereco"], p["municipio"], p["uf"], p.get("cep", ""))
                if resultado:
                    p["lat"], p["lon"] = resultado

        pontos_validos = [p for p in postos_selecionados if p.get("lat")]
        faltando = len(postos_selecionados) - len(pontos_validos)
        if faltando:
            st.warning(f"{faltando} posto(s) não geocodificados foram ignorados.")

        if pontos_validos:
            rota = geo_utils.otimizar_rota(pontos_validos, origem=origem_coord)
            st.session_state["rota_gerada"] = rota
            st.session_state["rota_origem"] = origem_coord

if "rota_gerada" in st.session_state:
    rota = st.session_state["rota_gerada"]
    origem_coord = st.session_state.get("rota_origem")

    st.markdown("### Sequência de visitas")
    for i, p in enumerate(rota, 1):
        st.markdown(f"""
        <div class="op-card op-accent">
        <span class="op-badge op-badge-a">PARADA {i}</span>
        &nbsp;&nbsp;<b>{p['razao_social']}</b> — {p['bairro']}
        </div>
        """, unsafe_allow_html=True)

    link = geo_utils.gerar_link_google_maps_rota(rota, origem=origem_coord)
    st.link_button("📲 Abrir rota no Google Maps", link, use_container_width=True)
