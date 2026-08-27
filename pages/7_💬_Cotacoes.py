import streamlit as st
from datetime import date, timedelta
import db
import common

st.set_page_config(page_title="Cotações", page_icon="💬", layout="wide")
db.init_db()
common.inject_css()
vendedor = common.seletor_vendedor_logado()
common.header("Cotações", "Propostas em aberto para compradores", icone="cotacoes")

compradores = db.get_compradores()
if not compradores:
    st.info("Cadastre compradores primeiro na página **Compradores**.")
    st.stop()

nomes_compradores = {c["cnpj"]: c["razao_social"] for c in compradores}

with st.expander("➕ Nova cotação"):
    c1, c2 = st.columns(2)
    with c1:
        comprador_cnpj = st.selectbox("Comprador", options=list(nomes_compradores.keys()),
                                       format_func=lambda x: nomes_compradores[x])
        produto = st.selectbox("Produto", ["Gasolina", "Etanol", "Diesel S10", "Diesel S500", "Outro"])
        volume_litros = st.number_input("Volume (litros)", min_value=0.0, step=100.0)
    with c2:
        preco_unitario = st.number_input("Preço unitário (R$/L)", min_value=0.0, step=0.01, format="%.2f")
        validade = st.date_input("Válida até", value=date.today() + timedelta(days=7))
        observacoes = st.text_area("Observações")

    if st.button("Registrar cotação", type="primary"):
        cotacao_id = db.add_cotacao({
            "comprador_cnpj": comprador_cnpj,
            "vendedor_id": vendedor["id"] if vendedor else None,
            "produto": produto,
            "volume_litros": volume_litros,
            "preco_unitario": preco_unitario,
            "data_cotacao": str(date.today()),
            "validade": str(validade),
            "status": "Pendente",
            "observacoes": observacoes,
        })
        st.success(f"Cotação #{cotacao_id} registrada!")
        st.rerun()

st.markdown("---")
filtro_status = st.selectbox("Filtrar por status", [None, "Pendente", "Aceita", "Recusada", "Expirada"],
                              format_func=lambda x: "Todas" if x is None else x)
cotacoes = db.get_cotacoes(status=filtro_status)

if not cotacoes:
    st.info("Nenhuma cotação registrada ainda.")
    st.stop()

BADGE_STATUS = {
    "Pendente": "op-badge-b", "Aceita": "op-badge-green",
    "Recusada": "op-badge-red", "Expirada": "op-badge-c",
}

for co in cotacoes:
    valor_total = (co["volume_litros"] or 0) * (co["preco_unitario"] or 0)
    st.markdown('<div class="op-card op-accent">', unsafe_allow_html=True)
    cols = st.columns([2.2, 1.2, 1.2, 1.2, 1.5, 1.7])
    with cols[0]:
        st.markdown(f"**{co['comprador_nome']}**")
        st.caption(f"Vendedor: {co['vendedor_nome'] or '—'} · {co['data_cotacao']}")
    with cols[1]:
        st.write(co["produto"])
    with cols[2]:
        st.write(f"{co['volume_litros']:,.0f} L")
    with cols[3]:
        st.write(f"R$ {co['preco_unitario']:.2f}/L")
    with cols[4]:
        st.markdown(f"<span class='op-badge {BADGE_STATUS.get(co['status'], 'op-badge-c')}'>{co['status']}</span> "
                     f"<br><span class='op-mono' style='font-size:12px'>R$ {valor_total:,.2f}</span>",
                     unsafe_allow_html=True)
    with cols[5]:
        if co["status"] == "Pendente":
            sub1, sub2 = st.columns(2)
            with sub1:
                if st.button("✅ Aceitar", key=f"aceitar_{co['id']}"):
                    db.update_cotacao_status(co["id"], "Aceita")
                    comissao = db.get_comissao_produto(co["produto"])
                    volume = co["volume_litros"] or 0
                    db.add_pedido({
                        "cotacao_id": co["id"], "comprador_cnpj": co["comprador_cnpj"],
                        "vendedor_id": co["vendedor_id"], "produto": co["produto"],
                        "volume_litros": volume, "preco_unitario": co["preco_unitario"],
                        "valor_total": valor_total, "data_pedido": str(date.today()),
                        "status_entrega": "Pendente", "status_pagamento": "Em aberto",
                        "comissao_vendedor_litro": comissao["comissao_vendedor_litro"],
                        "comissao_empresa_litro": comissao["comissao_empresa_litro"],
                        "comissao_vendedor_total": volume * comissao["comissao_vendedor_litro"],
                        "comissao_empresa_total": volume * comissao["comissao_empresa_litro"],
                    })
                    st.success("Cotação aceita e pedido criado!")
                    st.rerun()
            with sub2:
                if st.button("❌ Recusar", key=f"recusar_{co['id']}"):
                    db.update_cotacao_status(co["id"], "Recusada")
                    st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)
