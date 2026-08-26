import streamlit as st
import folium
from streamlit_folium import st_folium
import db
import geo_utils
import common

st.set_page_config(page_title="Mapa", page_icon="🗺️", layout="wide")
db.init_db()
common.inject_css()
common.seletor_vendedor_logado()
common.header("Mapa de Prospecção", "Distribuição geográfica dos postos")

CORES_STATUS = {
    "Não visitado": "gray", "Visitado": "blue", "Sem interesse": "red",
    "Interessado": "orange", "Cotação enviada": "purple", "Negociando": "cadetblue",
    "Retornar": "beige", "Cliente": "green",
}

uf_atual = st.session_state.get("uf_atual", "SP")
municipio_atual = st.session_state.get("municipio_atual", "Jandira")
postos = db.get_postos_by_city(uf_atual, municipio_atual)

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
m = folium.Map(location=[centro_lat, centro_lon], zoom_start=13, tiles="CartoDB dark_matter")

for p in postos_com_coord:
    status = p.get("status") or "Não visitado"
    cor = CORES_STATUS.get(status, "gray")
    popup_html = f"""
    <b>{p['razao_social']}</b><br>CNPJ: {p['cnpj']}<br>Bandeira: {p['bandeira']}<br>Status: {status}<br>
    <a href="https://www.google.com/maps/search/?api=1&query={p['lat']},{p['lon']}" target="_blank">Abrir no Google Maps</a>
    """
    folium.Marker(
        location=[p["lat"], p["lon"]],
        popup=folium.Popup(popup_html, max_width=250),
        tooltip=p["razao_social"],
        icon=folium.Icon(color=cor, icon="tint", prefix="fa"),
    ).add_to(m)

st_folium(m, width=None, height=560, key="mapa_postos")
st.caption("Cores indicam status comercial: cinza = não visitado, laranja = interessado, verde = cliente.")
