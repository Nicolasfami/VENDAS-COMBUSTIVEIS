import streamlit as st
from datetime import date
import db
import common

st.set_page_config(page_title="Painel de Vendas — Combustíveis", page_icon="⛽", layout="wide")
db.init_db()
common.inject_css()

vendedor = common.seletor_vendedor_logado()

common.header(
    "Painel de Vendas",
    "Prospecção e vendas de combustíveis · roda em paralelo ao Operax",
)

mes_atual = date.today().strftime("%Y-%m")
volumes = db.get_volume_por_vendedor(mes_atual)

if not volumes:
    st.info(
        "👋 Bem-vindo! Comece cadastrando sua equipe na página **Equipe** "
        "e importando os postos da região na página **Prospecção**."
    )
else:
    st.subheader(f"Metas do mês — {mes_atual}")
    cols = st.columns(len(volumes)) if len(volumes) <= 5 else st.columns(5)
    for i, v in enumerate(volumes):
        meta = v["meta_mensal_litros"] or 0
        pct = (v["volume_total"] / meta * 100) if meta > 0 else 0
        with cols[i % len(cols)]:
            st.markdown(f"<div class='op-card op-accent' style='text-align:center'>", unsafe_allow_html=True)
            st.markdown(common.gauge_svg(pct, label=v["nome"][:14].upper()), unsafe_allow_html=True)
            st.markdown(
                f"<p class='op-mono' style='text-align:center;color:{common.PALETTE['muted']};font-size:12px'>"
                f"{v['volume_total']:,.0f} L / {meta:,.0f} L</p>",
                unsafe_allow_html=True,
            )
            st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("---")

    total_volume = sum(v["volume_total"] for v in volumes)
    total_valor = sum(v["valor_total"] for v in volumes)
    todas_cotacoes = db.get_cotacoes(status="Pendente")
    todos_compradores = db.get_compradores()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Volume vendido no mês", f"{total_volume:,.0f} L")
    c2.metric("Faturamento no mês", f"R$ {total_valor:,.2f}")
    c3.metric("Cotações em aberto", len(todas_cotacoes))
    c4.metric("Compradores cadastrados", len(todos_compradores))

st.markdown("---")
st.markdown(f"""
<div class="op-card">
<b>Navegação</b><br>
<span style="color:{common.PALETTE['muted']}">
🎯 <b>Prospecção</b> — encontrar postos por região via base da ANP<br>
🗺️ <b>Mapa</b> — visualizar os postos geograficamente<br>
🚗 <b>Rota</b> — montar rota otimizada de visitas<br>
📇 <b>CRM</b> — histórico de contato posto a posto<br>
👥 <b>Equipe</b> — cadastro de vendedores e metas<br>
🏪 <b>Compradores</b> — cadastro de clientes e histórico financeiro<br>
💬 <b>Cotações</b> — propostas em aberto<br>
📦 <b>Pedidos</b> — vendas fechadas, entrega e pagamento<br>
📊 <b>Painel Geral</b> — números consolidados
</span>
</div>
""", unsafe_allow_html=True)
