import streamlit as st
import folium
from streamlit_folium import st_folium
import db
import geo_utils
import common
import anp_api

st.set_page_config(page_title="Mapa", page_icon="🗺️", layout="wide")
db.init_db()
common.inject_css()
common.seletor_vendedor_logado()
common.header("Mapa de Prospecção", "Distribuição geográfica dos postos", icone="mapa")

# Mapeia cada status comercial pro ícone de pin customizado correspondente.
# "Retornar" não tem pin próprio ainda, cai no genérico (não visitado).
PIN_POR_STATUS = {
    "Não visitado": "nao_visitado",
    "Visitado": "visitado",
    "Sem interesse": "sem_interesse",
    "Interessado": "interessado",
    "Cotação enviada": "cotacao_enviada",
    "Negociando": "negociando",
    "Retornar": "nao_visitado",
    "Cliente": "cliente",
}

uf_atual = st.session_state.get("uf_atual", "SP")
municipios_atual = st.session_state.get("municipios_atual", ["Jandira"])
municipios_norm = [anp_api.normalizar_municipio(m) for m in municipios_atual]
postos = db.get_postos_by_cities(uf_atual, municipios_norm)

if not postos:
    st.info("Nenhum posto carregado ainda. Vá para a página **Prospecção** primeiro.")
    st.stop()

with st.spinner("Geocodificando endereços..."):
    for p in postos:
        if p.get("lat") is None:
            resultado = geo_utils.geocode_endereco(p["endereco"], p["municipio"], p["uf"], p.get("cep", ""))
            if resultado:
                p["lat"], p["lon"] = resultado

postos_com_coord = [p for p in postos if p.get("lat")]
if not postos_com_coord:
    st.warning("Não foi possível geocodificar nenhum endereço ainda.")
    st.stop()

centro_lat = sum(p["lat"] for p in postos_com_coord) / len(postos_com_coord)
centro_lon = sum(p["lon"] for p in postos_com_coord) / len(postos_com_coord)
m = folium.Map(location=[centro_lat, centro_lon], zoom_start=12, tiles="CartoDB dark_matter")

for p in postos_com_coord:
    status = p.get("status") or "Não visitado"
    nome_pin = PIN_POR_STATUS.get(status, "nao_visitado")
    caminho_icone = common.pin_icon_path(nome_pin)

    popup_html = f"""
    <b>{p['razao_social']}</b><br>CNPJ: {p['cnpj']}<br>Bandeira: {p['bandeira']}<br>Status: {status}<br>
    <a href="https://www.google.com/maps/search/?api=1&query={p['lat']},{p['lon']}" target="_blank">Abrir no Google Maps</a>
    """

    if caminho_icone:
        icon = folium.CustomIcon(icon_image=caminho_icone, icon_size=(38, 47), icon_anchor=(19, 47))
    else:
        icon = folium.Icon(color="gray", icon="tint", prefix="fa")

    folium.Marker(
        location=[p["lat"], p["lon"]],
        popup=folium.Popup(popup_html, max_width=250),
        tooltip=p["razao_social"],
        icon=icon,
    ).add_to(m)

st_folium(m, width=None, height=560, key="mapa_postos")

st.markdown("##### Legenda")
legenda_cols = st.columns(len(PIN_POR_STATUS) - 1)  # -1 pra não repetir "Retornar"
status_unicos = list(dict.fromkeys(PIN_POR_STATUS.keys()))
for i, status in enumerate([s for s in status_unicos if s != "Retornar"]):
    with legenda_cols[i]:
        caminho = common.pin_icon_path(PIN_POR_STATUS[status])
        if caminho:
            st.image(caminho, width=28)
        st.caption(status)
