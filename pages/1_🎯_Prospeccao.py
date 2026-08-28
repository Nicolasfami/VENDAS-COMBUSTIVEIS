import streamlit as st
import pandas as pd
import json
from datetime import date
import folium
from streamlit_folium import st_folium
import db
import common
import anp_api
import geo_utils

st.set_page_config(page_title="Prospecção", page_icon="🎯", layout="wide")
db.init_db()
common.inject_css()
common.mostrar_logo()
vendedor = common.seletor_vendedor_logado()
common.header("Prospecção de Postos", "Base oficial da ANP — revendedores varejistas de combustíveis automotivos", icone="prospeccao")


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


@st.cache_data(ttl=86400)
def carregar_municipios_ibge(uf):
    """Cacheia por 24h pra não ficar consultando o IBGE toda hora."""
    try:
        return anp_api.listar_municipios(uf)
    except Exception:
        return []


with st.sidebar:
    st.markdown("### 🔍 Região")
    uf = st.text_input("UF", value=st.session_state.get("uf_atual", "SP"), max_chars=2).upper()

    municipios_disponiveis = carregar_municipios_ibge(uf) if len(uf) == 2 else []

    if municipios_disponiveis:
        municipios_salvos = st.session_state.get("municipios_atual", ["Jandira"])
        default_validos = [m for m in municipios_salvos if m in municipios_disponiveis] or municipios_disponiveis[:1]
        municipios = st.multiselect(
            "Município(s)",
            options=municipios_disponiveis,
            default=default_validos,
            help="Pode selecionar várias cidades vizinhas de uma vez.",
        )
    else:
        municipio_texto = st.text_input("Município", value=", ".join(st.session_state.get("municipios_atual", ["Jandira"])))
        municipios = [m.strip() for m in municipio_texto.split(",") if m.strip()]
        st.caption("⚠️ Não consegui carregar a lista de cidades do IBGE agora — digite separado por vírgula.")

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
    with st.expander("Ajustar pesos (avançado)", expanded=False):
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
    if not municipios:
        st.sidebar.warning("Selecione ao menos uma cidade.")
    else:
        with st.spinner(f"Consultando API oficial da ANP para {', '.join(municipios)}/{uf}..."):
            total_encontrados = 0
            erros = []
            todos_postos_api = []
            for muni in municipios:
                try:
                    postos_api = anp_api.buscar_postos_por_cidade(uf, muni)
                    if postos_api:
                        todos_postos_api.extend(postos_api)
                        total_encontrados += len(postos_api)
                    else:
                        st.session_state["debug_api"] = anp_api.debug_requisicao(uf, muni)
                except Exception as e:
                    erros.append(f"{muni}: {e}")

            if todos_postos_api:
                db.upsert_postos_api(todos_postos_api)
                st.session_state["uf_atual"] = uf
                st.session_state["municipios_atual"] = municipios
                st.sidebar.success(f"{total_encontrados} posto(s) carregados via API em {len(municipios)} cidade(s).")
            else:
                st.sidebar.warning("Nenhum posto encontrado nas cidades selecionadas.")
            if erros:
                st.sidebar.error("Erros: " + " | ".join(erros))

if buscar_csv and arquivo_csv is not None:
    with st.spinner("Lendo base da ANP e filtrando região..."):
        df = carregar_csv_anp(arquivo_csv)
        municipios_norm = [anp_api.normalizar_municipio(m) for m in municipios]
        df_filtrado = df[(df["UF"] == uf) & (df["MUNICIPIO"].str.upper().isin(municipios_norm))]
        if df_filtrado.empty:
            st.sidebar.warning("Nenhum posto encontrado para essas cidades.")
        else:
            db.upsert_postos(df_filtrado)
            st.session_state["uf_atual"] = uf
            st.session_state["municipios_atual"] = municipios
            st.sidebar.success(f"{len(df_filtrado)} postos carregados via CSV.")

uf_atual = st.session_state.get("uf_atual", uf)
municipios_atual = st.session_state.get("municipios_atual", municipios or ["Jandira"])
municipios_norm_busca = [anp_api.normalizar_municipio(m) for m in municipios_atual]
postos = db.get_postos_by_cities(uf_atual, municipios_norm_busca)

if not postos:
    st.info(
        "Use a **API oficial da ANP** (recomendado, mais rápido e completo) ou importe o "
        "**CSV manual** na barra lateral, informe UF e Município(s) e clique em buscar.\n\n"
        "CSV oficial disponível em: gov.br/anp → Dados Abertos → "
        "Dados Cadastrais dos Revendedores Varejistas de Combustíveis Automotivos"
    )
    if "debug_api" in st.session_state:
        with st.expander("🔧 Detalhes técnicos da última busca via API (clique pra ver)"):
            st.json(st.session_state["debug_api"])
    st.stop()

for p in postos:
    score, motivos = calcular_score(p, pesos)
    p["score"] = score
    p["motivos"] = motivos
    prioridade, badge_class = prioridade_label(score)
    p["prioridade"] = prioridade
    p["badge_class"] = badge_class

postos_ordenados = sorted(postos, key=lambda p: -p["score"])

st.subheader(f"{', '.join(municipios_atual)}/{uf_atual} — {len(postos)} posto(s) no total")

filtro_col1, filtro_col2 = st.columns(2)
with filtro_col1:
    contagem_bandeiras = {}
    for p in postos:
        b = p["bandeira"] or "Sem informação"
        contagem_bandeiras[b] = contagem_bandeiras.get(b, 0) + 1
    bandeiras_disponiveis = sorted(contagem_bandeiras.keys())
    bandeiras_selecionadas = st.multiselect(
        "Filtrar por bandeira",
        options=bandeiras_disponiveis,
        default=bandeiras_disponiveis,
        format_func=lambda b: f"{b} ({contagem_bandeiras[b]} posto{'s' if contagem_bandeiras[b] != 1 else ''})",
    )
with filtro_col2:
    contagem_bairros = {}
    for p in postos:
        b = p["bairro"] or "Sem informação"
        contagem_bairros[b] = contagem_bairros.get(b, 0) + 1
    bairros_disponiveis = sorted(contagem_bairros.keys())
    bairros_selecionados = st.multiselect(
        "Filtrar por bairro",
        options=bairros_disponiveis,
        default=bairros_disponiveis,
        format_func=lambda b: f"{b} ({contagem_bairros[b]} posto{'s' if contagem_bairros[b] != 1 else ''})",
    )
postos_ordenados = [p for p in postos_ordenados if (p["bandeira"] or "Sem informação") in bandeiras_selecionadas
                     and (p["bairro"] or "Sem informação") in bairros_selecionados]
st.caption(f"Mostrando {len(postos_ordenados)} de {len(postos)} posto(s)")

if "selecionados" not in st.session_state:
    st.session_state["selecionados"] = set()

@st.fragment
def render_lista_postos():
    for p in postos_ordenados:
        with st.container():
            st.markdown('<div class="op-card">', unsafe_allow_html=True)
            cols = st.columns([0.3, 2, 1, 0.9, 1.1, 0.8, 0.8, 0.8, 0.9])
            with cols[0]:
                checked = st.checkbox("", key=f"chk_{p['cnpj']}",
                                       value=p["cnpj"] in st.session_state["selecionados"])
                if checked:
                    st.session_state["selecionados"].add(p["cnpj"])
                else:
                    st.session_state["selecionados"].discard(p["cnpj"])
            with cols[1]:
                st.markdown(f"**{p['razao_social']}**")
                st.caption(f"{p['endereco']}, {p['bairro']} — {p['municipio']}")
                contato_partes = []
                if p.get("responsavel"):
                    contato_partes.append(f"👤 {p['responsavel']}")
                if p.get("telefone"):
                    contato_partes.append(f"📞 {p['telefone']}")
                if p.get("whatsapp"):
                    contato_partes.append(f"💬 {p['whatsapp']}")
                if contato_partes:
                    st.caption(" · ".join(contato_partes))
                else:
                    st.caption("Sem contato cadastrado ainda (preencha no CRM após visitar)")
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
            with cols[6]:
                with st.popover("💰 Vender"):
                    st.markdown(f"**Registrar venda — {p['razao_social']}**")
                    with st.form(key=f"form_vender_{p['cnpj']}"):
                        produto_venda = st.selectbox(
                            "Produto", ["Gasolina", "Etanol", "Diesel S10", "Diesel S500", "Outro"])
                        volume_venda = st.number_input("Volume (litros)", min_value=0.0, step=100.0)
                        preco_venda = st.number_input(
                            "Preço unitário (R$/L)", min_value=0.0, step=0.01, format="%.2f")
                        confirmou_venda = st.form_submit_button("✅ Confirmar venda", type="primary")

                    if confirmou_venda:
                        if volume_venda <= 0 or preco_venda <= 0:
                            st.warning("Preencha volume e preço antes de confirmar.")
                        else:
                            if not db.get_comprador(p["cnpj"]):
                                db.upsert_comprador(p["cnpj"], {
                                    "razao_social": p["razao_social"], "tipo": "Posto revendedor",
                                    "endereco": p["endereco"], "municipio": p["municipio"], "uf": p["uf"],
                                    "vendedor_id": vendedor["id"] if vendedor else None,
                                    "data_cadastro": str(date.today()),
                                })
                            comissao = db.get_comissao_produto(produto_venda)
                            valor_total_venda = volume_venda * preco_venda
                            db.add_pedido({
                                "comprador_cnpj": p["cnpj"], "vendedor_id": vendedor["id"] if vendedor else None,
                                "produto": produto_venda, "volume_litros": volume_venda,
                                "preco_unitario": preco_venda, "valor_total": valor_total_venda,
                                "data_pedido": str(date.today()), "status_entrega": "Pendente",
                                "status_pagamento": "Em aberto",
                                "comissao_vendedor_litro": comissao["comissao_vendedor_litro"],
                                "comissao_empresa_litro": comissao["comissao_empresa_litro"],
                                "comissao_vendedor_total": volume_venda * comissao["comissao_vendedor_litro"],
                                "comissao_empresa_total": volume_venda * comissao["comissao_empresa_litro"],
                            })
                            db.update_crm(p["cnpj"], {"status": "Cliente",
                                                       "vendedor_id": vendedor["id"] if vendedor else None})
                            st.success(f"Venda de {volume_venda:,.0f} L registrada! Posto virou Cliente.")
                            st.rerun()
            with cols[7]:
                with st.popover("📇 CRM"):
                    st.markdown(f"**Dados comerciais — {p['razao_social']}**")
                    status_opcoes = ["Não visitado", "Visitado", "Sem interesse", "Interessado",
                                      "Cotação enviada", "Negociando", "Retornar", "Cliente"]

                    with st.form(key=f"form_crm_{p['cnpj']}"):
                        status_crm = st.selectbox("Status", status_opcoes,
                                                   index=status_opcoes.index(p.get("status") or "Não visitado"))
                        responsavel_crm = st.text_input("Responsável", value=p.get("responsavel") or "")
                        telefone_crm = st.text_input("Telefone", value=p.get("telefone") or "")
                        whatsapp_crm = st.text_input("WhatsApp", value=p.get("whatsapp") or "")
                        fornecedor_crm = st.text_input("Fornecedor atual", value=p.get("fornecedor_atual") or "")
                        obs_crm = st.text_area("Observações", value=p.get("observacoes") or "")
                        salvou_crm = st.form_submit_button("💾 Salvar", type="primary")

                    if salvou_crm:
                        db.update_crm(p["cnpj"], {
                            "status": status_crm, "responsavel": responsavel_crm,
                            "telefone": telefone_crm, "whatsapp": whatsapp_crm,
                            "fornecedor_atual": fornecedor_crm, "observacoes": obs_crm,
                            "vendedor_id": vendedor["id"] if vendedor else None,
                        })
                        st.success("Dados salvos!")
                        st.rerun()

                    st.markdown("---")
                    with st.form(key=f"form_nota_{p['cnpj']}"):
                        nota_rapida = st.text_area("Adicionar ao histórico", height=68)
                        adicionou_nota = st.form_submit_button("➕ Adicionar ao histórico")

                    if adicionou_nota and nota_rapida.strip():
                        db.add_historico(p["cnpj"], str(date.today()), nota_rapida.strip())
                        st.success("Adicionado!")
                        st.rerun()
            with cols[8]:
                pedidos_posto = db.get_pedidos(comprador_cnpj=p["cnpj"])
                rotulo_vendas = f"📦 Vendas ({len(pedidos_posto)})" if pedidos_posto else "📦 Vendas"
                with st.popover(rotulo_vendas):
                    st.markdown(f"**Histórico de vendas — {p['razao_social']}**")
                    if pedidos_posto:
                        volume_total_posto = sum(pe["volume_litros"] or 0 for pe in pedidos_posto)
                        valor_total_posto = sum(pe["valor_total"] or 0 for pe in pedidos_posto)
                        st.caption(f"Total: {volume_total_posto:,.0f} L · R$ {valor_total_posto:,.2f}")
                        st.markdown("---")
                        BADGE_ENTREGA = {"Pendente": "op-badge-b", "Entregue": "op-badge-green",
                                          "Cancelado": "op-badge-red"}
                        BADGE_PAGAMENTO = {"Em aberto": "op-badge-b", "Pago": "op-badge-green",
                                            "Atrasado": "op-badge-red"}
                        for pe in pedidos_posto:
                            st.markdown(f"""
                            <div class="op-card">
                            <b>{pe['data_pedido']}</b> — {pe['produto']} — {pe['volume_litros']:,.0f} L — R$ {pe['valor_total']:,.2f}<br>
                            <span class="op-badge {BADGE_ENTREGA.get(pe['status_entrega'], 'op-badge-c')}">{pe['status_entrega']}</span>
                            <span class="op-badge {BADGE_PAGAMENTO.get(pe['status_pagamento'], 'op-badge-c')}">{pe['status_pagamento']}</span>
                            </div>
                            """, unsafe_allow_html=True)
                    else:
                        st.caption("Nenhuma venda registrada pra esse posto ainda. Use o botão 💰 Vender.")
            st.markdown('</div>', unsafe_allow_html=True)
    st.caption(f"✅ {len(st.session_state['selecionados'])} posto(s) selecionado(s) para rota")

render_lista_postos()

# ============================================================
# MAPA GERAL — todos os postos, clique pra selecionar/desselecionar
# ============================================================

st.markdown("---")
st.markdown("## 🗺️ Mapa de Todos os Postos")
st.caption("Clique num marcador do mapa pra marcar/desmarcar ele pra rota (mesma seleção da lista acima).")

PIN_POR_STATUS_MAPA = {
    "Não visitado": "nao_visitado", "Visitado": "visitado", "Sem interesse": "sem_interesse",
    "Interessado": "interessado", "Cotação enviada": "cotacao_enviada", "Negociando": "negociando",
    "Retornar": "nao_visitado", "Cliente": "cliente",
}


@st.fragment
def render_mapa_geral():
    postos_com_coord = [p for p in postos_ordenados if p.get("lat")]

    if not postos_com_coord:
        with st.spinner("Geocodificando endereços pro mapa (pode levar um tempinho)..."):
            for p in postos_ordenados:
                if p.get("lat") is None:
                    resultado = geo_utils.geocode_endereco(p["endereco"], p["municipio"], p["uf"], p.get("cep", ""))
                    if resultado:
                        p["lat"], p["lon"] = resultado
        postos_com_coord = [p for p in postos_ordenados if p.get("lat")]

    if not postos_com_coord:
        st.warning("Não foi possível geocodificar nenhum endereço ainda.")
        return

    centro_lat = sum(p["lat"] for p in postos_com_coord) / len(postos_com_coord)
    centro_lon = sum(p["lon"] for p in postos_com_coord) / len(postos_com_coord)
    m_geral = folium.Map(location=[centro_lat, centro_lon], zoom_start=12, tiles="CartoDB dark_matter")

    for p in postos_com_coord:
        status = p.get("status") or "Não visitado"
        nome_pin = PIN_POR_STATUS_MAPA.get(status, "nao_visitado")
        caminho_icone = common.pin_icon_path(nome_pin)
        selecionado = p["cnpj"] in st.session_state["selecionados"]
        marca = "✅ SELECIONADO<br>" if selecionado else ""
        popup_html = f"{marca}<b>{p['razao_social']}</b><br>{p['bairro']}<br>Status: {status}"

        if caminho_icone:
            icon = folium.CustomIcon(icon_image=caminho_icone, icon_size=(34, 42), icon_anchor=(17, 42))
        else:
            icon = folium.Icon(color="gray", icon="tint", prefix="fa")

        folium.Marker(
            location=[p["lat"], p["lon"]],
            tooltip=f"{'✅ ' if selecionado else ''}{p['razao_social']}",
            popup=folium.Popup(popup_html, max_width=220),
            icon=icon,
        ).add_to(m_geral)

    resultado_mapa = st_folium(m_geral, width=None, height=500, key="mapa_geral_prospeccao",
                                returned_objects=["last_object_clicked"])

    if resultado_mapa and resultado_mapa.get("last_object_clicked"):
        lat_clicado = resultado_mapa["last_object_clicked"]["lat"]
        lon_clicado = resultado_mapa["last_object_clicked"]["lng"]
        click_atual = (round(lat_clicado, 6), round(lon_clicado, 6))

        if click_atual != st.session_state.get("ultimo_click_mapa"):
            st.session_state["ultimo_click_mapa"] = click_atual
            for p in postos_com_coord:
                if abs(p["lat"] - lat_clicado) < 0.0001 and abs(p["lon"] - lon_clicado) < 0.0001:
                    if p["cnpj"] in st.session_state["selecionados"]:
                        st.session_state["selecionados"].discard(p["cnpj"])
                    else:
                        st.session_state["selecionados"].add(p["cnpj"])
                    st.rerun()


render_mapa_geral()

# ============================================================
# ROTA + MAPA (direto na Prospecção, sem precisar trocar de tela)
# ============================================================

st.markdown("---")
st.markdown("## 🚗 Gerar Rota")

PIN_POR_STATUS = {
    "Não visitado": "nao_visitado", "Visitado": "visitado", "Sem interesse": "sem_interesse",
    "Interessado": "interessado", "Cotação enviada": "cotacao_enviada", "Negociando": "negociando",
    "Retornar": "nao_visitado", "Cliente": "cliente",
}

@st.fragment
def render_secao_rota():
    selecionados_cnpj = st.session_state["selecionados"]
    postos_selecionados = [p for p in postos if p["cnpj"] in selecionados_cnpj]

    if not postos_selecionados:
        st.info("Marque o checkbox dos postos que quer visitar (na lista acima) pra gerar a rota.")
    else:
        st.markdown(
            f"<div class='op-card op-accent'>{len(postos_selecionados)} posto(s) selecionado(s) pra rota</div>",
            unsafe_allow_html=True)

        usar_origem = st.checkbox("Definir ponto de partida (ex: seu endereço)")
        origem_coord = None
        if usar_origem:
            endereco_origem = st.text_input("Endereço de partida", placeholder="Ex: Rua Exemplo, 100, Jandira, SP")
            if endereco_origem:
                origem_coord = geo_utils.geocode_endereco(endereco_origem, municipios_atual[0], uf_atual)
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
                    st.warning(f"{faltando} posto(s) não geocodificados foram ignorados na rota.")

                if pontos_validos:
                    rota = geo_utils.otimizar_rota(pontos_validos, origem=origem_coord)
                    st.session_state["rota_gerada"] = rota
                    st.session_state["rota_origem"] = origem_coord

        if st.session_state.get("rota_gerada"):
            rota = st.session_state["rota_gerada"]
            origem_coord = st.session_state.get("rota_origem")

            st.markdown("#### Sequência de visitas")
            for i, p in enumerate(rota, 1):
                st.markdown(f"""
                <div class="op-card op-accent">
                <span class="op-badge op-badge-a">PARADA {i}</span>
                &nbsp;&nbsp;<b>{p['razao_social']}</b> — {p['bairro']}
                </div>
                """, unsafe_allow_html=True)

            link = geo_utils.gerar_link_google_maps_rota(rota, origem=origem_coord)
            st.link_button("📲 Abrir rota no Google Maps", link, use_container_width=True)

            st.markdown("#### Mapa da rota")
            centro_lat = sum(p["lat"] for p in rota) / len(rota)
            centro_lon = sum(p["lon"] for p in rota) / len(rota)
            m = folium.Map(location=[centro_lat, centro_lon], zoom_start=12, tiles="CartoDB dark_matter")

            for i, p in enumerate(rota, 1):
                status = p.get("status") or "Não visitado"
                nome_pin = PIN_POR_STATUS.get(status, "nao_visitado")
                caminho_icone = common.pin_icon_path(nome_pin)
                popup_html = f"<b>{i}. {p['razao_social']}</b><br>{p['bairro']}<br>Status: {status}"

                if caminho_icone:
                    icon = folium.CustomIcon(icon_image=caminho_icone, icon_size=(36, 45), icon_anchor=(18, 45))
                else:
                    icon = folium.Icon(color="gray", icon="tint", prefix="fa")

                folium.Marker(
                    location=[p["lat"], p["lon"]],
                    popup=folium.Popup(popup_html, max_width=220),
                    tooltip=f"{i}. {p['razao_social']}",
                    icon=icon,
                ).add_to(m)

            st_folium(m, width=None, height=460, key="mapa_rota_prospeccao")


render_secao_rota()
