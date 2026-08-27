import streamlit as st
from datetime import date
import plotly.graph_objects as go
import db
import common
import anp_api

st.set_page_config(page_title="Painel Geral", page_icon="📊", layout="wide")
db.init_db()
common.inject_css()
common.seletor_vendedor_logado()
common.header("Painel Geral", "Números consolidados de prospecção e vendas", icone="painel")

PLOTLY_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color=common.PALETTE["text"], family="Inter, sans-serif"),
    margin=dict(l=10, r=10, t=40, b=10),
    legend=dict(bgcolor="rgba(0,0,0,0)"),
)
CORES_PRIORIDADE = {"A": common.PALETTE["amber"], "B": common.PALETTE["steel"], "C": common.PALETTE["muted"]}
CORES_STATUS = {
    "Não visitado": common.PALETTE["muted"], "Visitado": common.PALETTE["steel"],
    "Sem interesse": common.PALETTE["red"], "Interessado": common.PALETTE["amber"],
    "Cotação enviada": "#9B7EDE", "Negociando": "#4FA8A0",
    "Retornar": "#C9A66B", "Cliente": common.PALETTE["green"],
}

# ============================================================
# PROSPECÇÃO
# ============================================================

uf_atual = st.session_state.get("uf_atual", "SP")
municipios_atual = st.session_state.get("municipios_atual", ["Jandira"])
municipios_norm = [anp_api.normalizar_municipio(m) for m in municipios_atual]
postos = db.get_postos_by_cities(uf_atual, municipios_norm)

st.subheader(f"Prospecção — {', '.join(municipios_atual)}/{uf_atual}")

if postos:
    total = len(postos)
    bandeira_branca = sum(1 for p in postos if (p["bandeira"] or "").upper() == "BANDEIRA BRANCA")
    visitados = sum(1 for p in postos if (p.get("status") or "Não visitado") != "Não visitado")
    clientes = sum(1 for p in postos if p.get("status") == "Cliente")
    negociando = sum(1 for p in postos if p.get("status") == "Negociando")

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total de postos", total)
    c2.metric("Bandeira branca", bandeira_branca)
    c3.metric("Visitados", visitados)
    c4.metric("Em negociação", negociando)
    c5.metric("Clientes", clientes)

    col_a, col_b = st.columns(2)

    with col_a:
        # Pizza de prioridade — recalcula score simplificado (só bandeira branca, igual peso padrão)
        contagem_prioridade = {"A": 0, "B": 0, "C": 0}
        for p in postos:
            score = 40 if (p.get("bandeira") or "").upper() == "BANDEIRA BRANCA" else 0
            if p.get("tancagem_total_m3") and p["tancagem_total_m3"] >= 60:
                score += 20
            if score >= 40:
                contagem_prioridade["A"] += 1
            elif score >= 15:
                contagem_prioridade["B"] += 1
            else:
                contagem_prioridade["C"] += 1

        fig_prioridade = go.Figure(data=[go.Pie(
            labels=[f"Prioridade {k}" for k in contagem_prioridade],
            values=list(contagem_prioridade.values()),
            hole=0.55,
            marker=dict(colors=[CORES_PRIORIDADE[k] for k in contagem_prioridade]),
            textfont=dict(color="#12181C", family="IBM Plex Mono"),
        )])
        fig_prioridade.update_layout(title="Distribuição por prioridade", **PLOTLY_LAYOUT)
        st.plotly_chart(fig_prioridade, use_container_width=True)

    with col_b:
        # Barras de status comercial
        contagem_status = {}
        for p in postos:
            s = p.get("status") or "Não visitado"
            contagem_status[s] = contagem_status.get(s, 0) + 1
        ordem = ["Não visitado", "Visitado", "Interessado", "Cotação enviada",
                 "Negociando", "Retornar", "Cliente", "Sem interesse"]
        labels = [s for s in ordem if s in contagem_status]
        valores = [contagem_status[s] for s in labels]

        fig_status = go.Figure(data=[go.Bar(
            x=valores, y=labels, orientation="h",
            marker=dict(color=[CORES_STATUS.get(s, common.PALETTE["muted"]) for s in labels]),
            text=valores, textposition="outside",
        )])
        fig_status.update_layout(title="Postos por status comercial", **PLOTLY_LAYOUT,
                                  xaxis=dict(gridcolor=common.PALETTE["border"]), yaxis=dict(autorange="reversed"))
        st.plotly_chart(fig_status, use_container_width=True)

    # Top bandeiras
    contagem_bandeira = {}
    for p in postos:
        b = p.get("bandeira") or "Sem informação"
        contagem_bandeira[b] = contagem_bandeira.get(b, 0) + 1
    top_bandeiras = sorted(contagem_bandeira.items(), key=lambda x: -x[1])[:8]

    fig_bandeiras = go.Figure(data=[go.Bar(
        x=[b[0] for b in top_bandeiras], y=[b[1] for b in top_bandeiras],
        marker=dict(color=common.PALETTE["amber"]),
        text=[b[1] for b in top_bandeiras], textposition="outside",
    )])
    fig_bandeiras.update_layout(title="Postos por bandeira", **PLOTLY_LAYOUT,
                                 yaxis=dict(gridcolor=common.PALETTE["border"]))
    st.plotly_chart(fig_bandeiras, use_container_width=True)
else:
    st.caption("Nenhum posto prospectado ainda nessa região.")

st.markdown("---")

# ============================================================
# VENDAS
# ============================================================

st.subheader("Vendas")

mes_atual = date.today().strftime("%Y-%m")
volumes = db.get_volume_por_vendedor(mes_atual)
todos_pedidos = db.get_pedidos()
todas_cotacoes = db.get_cotacoes()

volume_total_mes = sum(v["volume_total"] for v in volumes)
valor_total_mes = sum(v["valor_total"] for v in volumes)
em_aberto = sum(p["valor_total"] or 0 for p in todos_pedidos if p["status_pagamento"] == "Em aberto")
atrasado = sum(p["valor_total"] or 0 for p in todos_pedidos if p["status_pagamento"] == "Atrasado")

c1, c2, c3, c4 = st.columns(4)
c1.metric(f"Volume vendido — {mes_atual}", f"{volume_total_mes:,.0f} L")
c2.metric(f"Faturamento — {mes_atual}", f"R$ {valor_total_mes:,.2f}")
c3.metric("Em aberto (todos os meses)", f"R$ {em_aberto:,.2f}")
c4.metric("Atrasado", f"R$ {atrasado:,.2f}")

col_c, col_d = st.columns(2)

with col_c:
    volumes_com_vendas = [v for v in volumes if v["volume_total"] > 0]
    if volumes_com_vendas:
        volumes_ordenados = sorted(volumes_com_vendas, key=lambda x: x["volume_total"])
        fig_ranking = go.Figure(data=[go.Bar(
            x=[v["volume_total"] for v in volumes_ordenados],
            y=[v["nome"] for v in volumes_ordenados],
            orientation="h",
            marker=dict(color=common.PALETTE["steel"]),
            text=[f"{v['volume_total']:,.0f} L" for v in volumes_ordenados], textposition="outside",
        )])
        fig_ranking.update_layout(title=f"Ranking de vendedores — {mes_atual}", **PLOTLY_LAYOUT,
                                   xaxis=dict(gridcolor=common.PALETTE["border"]))
        st.plotly_chart(fig_ranking, use_container_width=True)
    else:
        st.caption("Nenhuma venda registrada no mês ainda.")

with col_d:
    serie = db.get_serie_mensal_vendas(meses=6)
    serie_com_dados = [s for s in serie if s["volume_total"] > 0]
    if serie_com_dados:
        fig_tendencia = go.Figure(data=[go.Scatter(
            x=[s["mes"] for s in serie], y=[s["volume_total"] for s in serie],
            mode="lines+markers", line=dict(color=common.PALETTE["amber"], width=3),
            marker=dict(size=8, color=common.PALETTE["amber"]),
            fill="tozeroy", fillcolor="rgba(242,169,59,0.12)",
        )])
        fig_tendencia.update_layout(title="Volume vendido — últimos 6 meses", **PLOTLY_LAYOUT,
                                     xaxis=dict(gridcolor=common.PALETTE["border"]),
                                     yaxis=dict(gridcolor=common.PALETTE["border"]))
        st.plotly_chart(fig_tendencia, use_container_width=True)
    else:
        st.caption("Ainda não há histórico de vendas suficiente pra mostrar tendência.")

# Funil de cotações
if todas_cotacoes:
    contagem_cotacao = {}
    for c in todas_cotacoes:
        contagem_cotacao[c["status"]] = contagem_cotacao.get(c["status"], 0) + 1
    ordem_cotacao = ["Pendente", "Aceita", "Recusada", "Expirada"]
    cores_cotacao = {"Pendente": common.PALETTE["steel"], "Aceita": common.PALETTE["green"],
                      "Recusada": common.PALETTE["red"], "Expirada": common.PALETTE["muted"]}
    labels_cot = [s for s in ordem_cotacao if s in contagem_cotacao]
    valores_cot = [contagem_cotacao[s] for s in labels_cot]

    fig_cotacoes = go.Figure(data=[go.Bar(
        x=labels_cot, y=valores_cot,
        marker=dict(color=[cores_cotacao[s] for s in labels_cot]),
        text=valores_cot, textposition="outside",
    )])
    fig_cotacoes.update_layout(title="Cotações por status", **PLOTLY_LAYOUT,
                                yaxis=dict(gridcolor=common.PALETTE["border"]))
    st.plotly_chart(fig_cotacoes, use_container_width=True)

st.markdown("### Cotações em aberto")
pendentes = [c for c in todas_cotacoes if c["status"] == "Pendente"]
if pendentes:
    valor_pendente = sum((c["volume_litros"] or 0) * (c["preco_unitario"] or 0) for c in pendentes)
    st.metric("Valor potencial em cotações pendentes", f"R$ {valor_pendente:,.2f}", f"{len(pendentes)} cotação(ões)")
else:
    st.caption("Nenhuma cotação pendente.")
