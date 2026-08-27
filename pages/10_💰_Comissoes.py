import streamlit as st
from datetime import date
import plotly.graph_objects as go
import db
import common

st.set_page_config(page_title="Comissões", page_icon="💰", layout="wide")
db.init_db()
common.inject_css()
common.seletor_vendedor_logado()
common.header("Comissões", "Tabela de comissão por produto e totais por vendedor/empresa")

PLOTLY_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color=common.PALETTE["text"], family="Inter, sans-serif"),
    margin=dict(l=10, r=10, t=40, b=10),
)

# ============================================================
# TABELA DE COMISSÃO POR PRODUTO
# ============================================================

st.subheader("Tabela de comissão por produto")
st.caption(
    "Defina quanto vale cada litro vendido — separado entre o que vai pro vendedor "
    "e o que fica de margem pra empresa/refinaria. Ex: R$ 0,01/L de comissão do "
    "vendedor + R$ 0,03/L de margem da empresa."
)

produtos_padrao = ["Gasolina", "Etanol", "Diesel S10", "Diesel S500", "Outro"]
comissoes_existentes = {c["produto"]: c for c in db.get_comissoes_produto()}

with st.expander("➕ Configurar / atualizar comissão de um produto", expanded=not comissoes_existentes):
    col1, col2, col3 = st.columns(3)
    with col1:
        produto_edit = st.selectbox("Produto", produtos_padrao)
    with col2:
        valor_vendedor = st.number_input(
            "Comissão do vendedor (R$/L)", min_value=0.0, step=0.001, format="%.4f",
            value=float(comissoes_existentes.get(produto_edit, {}).get("comissao_vendedor_litro", 0) or 0),
        )
    with col3:
        valor_empresa = st.number_input(
            "Margem da empresa/refinaria (R$/L)", min_value=0.0, step=0.001, format="%.4f",
            value=float(comissoes_existentes.get(produto_edit, {}).get("comissao_empresa_litro", 0) or 0),
        )
    if st.button("💾 Salvar comissão deste produto", type="primary"):
        db.upsert_comissao_produto(produto_edit, valor_vendedor, valor_empresa)
        st.success(f"Comissão de {produto_edit} atualizada!")
        st.rerun()

comissoes_lista = db.get_comissoes_produto()
if comissoes_lista:
    for c in comissoes_lista:
        st.markdown(f"""
        <div class="op-card">
        <b>{c['produto']}</b>
        &nbsp;<span class="op-badge op-badge-a">Vendedor: R$ {c['comissao_vendedor_litro']:.4f}/L</span>
        &nbsp;<span class="op-badge op-badge-b">Empresa: R$ {c['comissao_empresa_litro']:.4f}/L</span>
        </div>
        """, unsafe_allow_html=True)
else:
    st.info("Nenhuma comissão configurada ainda. Use o formulário acima pra cadastrar por produto.")

st.markdown("---")

# ============================================================
# TOTAIS
# ============================================================

st.subheader("Totais de comissão")

periodo = st.radio("Período", ["Mês atual", "Todos os períodos"], horizontal=True)
mes_ano = date.today().strftime("%Y-%m") if periodo == "Mês atual" else None

comissoes_vendedor = db.get_comissoes_por_vendedor(mes_ano)
total_comissao_vendedores = sum(v["comissao_vendedor"] for v in comissoes_vendedor)
total_comissao_empresa = sum(v["comissao_empresa"] for v in comissoes_vendedor)
volume_total = sum(v["volume_total"] for v in comissoes_vendedor)

c1, c2, c3 = st.columns(3)
c1.metric("Volume vendido no período", f"{volume_total:,.0f} L")
c2.metric("💰 Comissão total dos vendedores", f"R$ {total_comissao_vendedores:,.2f}")
c3.metric("🏢 Margem total da empresa/refinaria", f"R$ {total_comissao_empresa:,.2f}")

vendedores_com_comissao = [v for v in comissoes_vendedor if v["comissao_vendedor"] > 0 or v["volume_total"] > 0]

if vendedores_com_comissao:
    col_a, col_b = st.columns(2)

    with col_a:
        vendedores_ordenados = sorted(vendedores_com_comissao, key=lambda x: x["comissao_vendedor"])
        fig_comissao = go.Figure(data=[go.Bar(
            x=[v["comissao_vendedor"] for v in vendedores_ordenados],
            y=[v["nome"] for v in vendedores_ordenados],
            orientation="h",
            marker=dict(color=common.PALETTE["amber"]),
            text=[f"R$ {v['comissao_vendedor']:,.2f}" for v in vendedores_ordenados],
            textposition="outside",
        )])
        fig_comissao.update_layout(title="Comissão por vendedor", **PLOTLY_LAYOUT,
                                    xaxis=dict(gridcolor=common.PALETTE["border"]))
        st.plotly_chart(fig_comissao, use_container_width=True)

    with col_b:
        fig_split = go.Figure(data=[go.Pie(
            labels=["Comissão vendedores", "Margem empresa/refinaria"],
            values=[total_comissao_vendedores, total_comissao_empresa],
            hole=0.55,
            marker=dict(colors=[common.PALETTE["amber"], common.PALETTE["steel"]]),
            textfont=dict(color="#0B1220", family="IBM Plex Mono"),
        )])
        fig_split.update_layout(title="Divisão vendedor × empresa", **PLOTLY_LAYOUT)
        st.plotly_chart(fig_split, use_container_width=True)

    st.markdown("### Detalhamento por vendedor")
    for v in sorted(vendedores_com_comissao, key=lambda x: -x["comissao_vendedor"]):
        st.markdown(f"""
        <div class="op-card">
        <b>{v['nome']}</b> — {v['volume_total']:,.0f} L vendidos
        &nbsp;<span class="op-badge op-badge-a">Comissão: R$ {v['comissao_vendedor']:,.2f}</span>
        &nbsp;<span class="op-badge op-badge-b">Margem empresa: R$ {v['comissao_empresa']:,.2f}</span>
        </div>
        """, unsafe_allow_html=True)
else:
    st.caption("Nenhuma venda com comissão registrada nesse período ainda.")
