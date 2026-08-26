import streamlit as st
from datetime import date
import db
import common

st.set_page_config(page_title="Pedidos", page_icon="📦", layout="wide")
db.init_db()
common.inject_css()
vendedor = common.seletor_vendedor_logado()
common.header("Pedidos", "Vendas fechadas — entrega e pagamento")

compradores = db.get_compradores()
if not compradores:
    st.info("Cadastre compradores primeiro na página **Compradores**.")
    st.stop()

nomes_compradores = {c["cnpj"]: c["razao_social"] for c in compradores}

with st.expander("➕ Novo pedido manual"):
    st.caption("Pedidos também são criados automaticamente ao aceitar uma cotação.")
    c1, c2 = st.columns(2)
    with c1:
        comprador_cnpj = st.selectbox("Comprador", options=list(nomes_compradores.keys()),
                                       format_func=lambda x: nomes_compradores[x], key="ped_comprador")
        produto = st.selectbox("Produto", ["Gasolina", "Etanol", "Diesel S10", "Diesel S500", "Outro"],
                                key="ped_produto")
        volume_litros = st.number_input("Volume (litros)", min_value=0.0, step=100.0, key="ped_volume")
        preco_unitario = st.number_input("Preço unitário (R$/L)", min_value=0.0, step=0.01, format="%.2f",
                                          key="ped_preco")
    with c2:
        data_entrega = st.date_input("Data de entrega prevista", value=date.today())
        forma_pagamento = st.text_input("Forma de pagamento", placeholder="Ex: boleto 30 dias")
        observacoes = st.text_area("Observações", key="ped_obs")

    if st.button("Registrar pedido", type="primary"):
        valor_total = volume_litros * preco_unitario
        pedido_id = db.add_pedido({
            "comprador_cnpj": comprador_cnpj, "vendedor_id": vendedor["id"] if vendedor else None,
            "produto": produto, "volume_litros": volume_litros, "preco_unitario": preco_unitario,
            "valor_total": valor_total, "data_pedido": str(date.today()), "data_entrega": str(data_entrega),
            "status_entrega": "Pendente", "status_pagamento": "Em aberto",
            "forma_pagamento": forma_pagamento, "observacoes": observacoes,
        })
        st.success(f"Pedido #{pedido_id} registrado!")
        st.rerun()

st.markdown("---")
c1, c2 = st.columns(2)
with c1:
    filtro_entrega = st.selectbox("Status de entrega", [None, "Pendente", "Entregue", "Cancelado"],
                                   format_func=lambda x: "Todos" if x is None else x)
with c2:
    filtro_pagamento = st.selectbox("Status de pagamento", [None, "Em aberto", "Pago", "Atrasado"],
                                     format_func=lambda x: "Todos" if x is None else x)

pedidos = db.get_pedidos()
if filtro_entrega:
    pedidos = [p for p in pedidos if p["status_entrega"] == filtro_entrega]
if filtro_pagamento:
    pedidos = [p for p in pedidos if p["status_pagamento"] == filtro_pagamento]

if not pedidos:
    st.info("Nenhum pedido encontrado.")
    st.stop()

BADGE_ENTREGA = {"Pendente": "op-badge-b", "Entregue": "op-badge-green", "Cancelado": "op-badge-red"}
BADGE_PAGAMENTO = {"Em aberto": "op-badge-b", "Pago": "op-badge-green", "Atrasado": "op-badge-red"}

for p in pedidos:
    st.markdown('<div class="op-card">', unsafe_allow_html=True)
    cols = st.columns([2, 1.1, 1.1, 1.3, 1.3, 1.6])
    with cols[0]:
        st.markdown(f"**{p['comprador_nome']}**")
        st.caption(f"Pedido #{p['id']} · {p['vendedor_nome'] or '—'} · {p['data_pedido']}")
    with cols[1]:
        st.write(p["produto"])
    with cols[2]:
        st.write(f"{p['volume_litros']:,.0f} L")
    with cols[3]:
        st.write(f"R$ {p['valor_total']:,.2f}")
    with cols[4]:
        st.markdown(f"<span class='op-badge {BADGE_ENTREGA.get(p['status_entrega'],'op-badge-c')}'>"
                     f"{p['status_entrega']}</span>", unsafe_allow_html=True)
    with cols[5]:
        with st.popover("Atualizar"):
            novo_status_entrega = st.selectbox("Entrega", ["Pendente", "Entregue", "Cancelado"],
                                                index=["Pendente", "Entregue", "Cancelado"].index(p["status_entrega"]),
                                                key=f"se_{p['id']}")
            novo_status_pagamento = st.selectbox("Pagamento", ["Em aberto", "Pago", "Atrasado"],
                                                  index=["Em aberto", "Pago", "Atrasado"].index(p["status_pagamento"]),
                                                  key=f"sp_{p['id']}")
            if st.button("Salvar", key=f"save_{p['id']}"):
                db.update_pedido(p["id"], {
                    "status_entrega": novo_status_entrega,
                    "status_pagamento": novo_status_pagamento,
                })
                st.success("Atualizado!")
                st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)
