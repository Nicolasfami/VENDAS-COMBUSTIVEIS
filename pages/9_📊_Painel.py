import streamlit as st
from datetime import date
import db
import common

st.set_page_config(page_title="Painel Geral", page_icon="📊", layout="wide")
db.init_db()
common.inject_css()
common.seletor_vendedor_logado()
common.header("Painel Geral", "Números consolidados de prospecção e vendas")

uf_atual = st.session_state.get("uf_atual", "SP")
municipio_atual = st.session_state.get("municipio_atual", "Jandira")
postos = db.get_postos_by_city(uf_atual, municipio_atual)

st.subheader(f"Prospecção — {municipio_atual}/{uf_atual}")
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
else:
    st.caption("Nenhum posto prospectado ainda nessa região.")

st.markdown("---")
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

st.markdown("### Ranking de vendedores no mês")
if volumes:
    for v in sorted(volumes, key=lambda x: -x["volume_total"]):
        meta = v["meta_mensal_litros"] or 0
        pct = (v["volume_total"] / meta * 100) if meta > 0 else 0
        cor = "op-badge-green" if pct >= 100 else ("op-badge-a" if pct >= 60 else "op-badge-b")
        st.markdown(f"""
        <div class="op-card">
        <b>{v['nome']}</b> — {v['volume_total']:,.0f} L — R$ {v['valor_total']:,.2f}
        &nbsp;<span class="op-badge {cor}">{pct:.0f}% da meta</span>
        </div>
        """, unsafe_allow_html=True)
else:
    st.caption("Nenhuma venda registrada ainda.")

st.markdown("### Cotações em aberto")
pendentes = [c for c in todas_cotacoes if c["status"] == "Pendente"]
if pendentes:
    valor_pendente = sum((c["volume_litros"] or 0) * (c["preco_unitario"] or 0) for c in pendentes)
    st.metric("Valor potencial em cotações pendentes", f"R$ {valor_pendente:,.2f}", f"{len(pendentes)} cotação(ões)")
else:
    st.caption("Nenhuma cotação pendente.")
