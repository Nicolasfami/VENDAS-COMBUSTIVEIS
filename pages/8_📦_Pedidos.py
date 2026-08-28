import streamlit as st
from datetime import date
import pandas as pd
import db
import common

st.set_page_config(page_title="Pedidos", page_icon="📦", layout="wide")
db.init_db()
common.inject_css()
common.mostrar_logo()
vendedor = common.seletor_vendedor_logado()
common.header("Pedidos", "Vendas fechadas — entrega e pagamento", icone="pedidos")

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
        comissao = db.get_comissao_produto(produto)
        pedido_id = db.add_pedido({
            "comprador_cnpj": comprador_cnpj, "vendedor_id": vendedor["id"] if vendedor else None,
            "produto": produto, "volume_litros": volume_litros, "preco_unitario": preco_unitario,
            "valor_total": valor_total, "data_pedido": str(date.today()), "data_entrega": str(data_entrega),
            "status_entrega": "Pendente", "status_pagamento": "Em aberto",
            "forma_pagamento": forma_pagamento, "observacoes": observacoes,
            "comissao_vendedor_litro": comissao["comissao_vendedor_litro"],
            "comissao_empresa_litro": comissao["comissao_empresa_litro"],
            "comissao_vendedor_total": volume_litros * comissao["comissao_vendedor_litro"],
            "comissao_empresa_total": volume_litros * comissao["comissao_empresa_litro"],
        })
        st.success(f"Pedido #{pedido_id} registrado!")
        st.rerun()

st.markdown("---")
c1, c2, c3 = st.columns(3)
with c1:
    filtro_entrega = st.selectbox("Status de entrega", [None, "Pendente", "Entregue", "Cancelado"],
                                   format_func=lambda x: "Todos" if x is None else x)
with c2:
    filtro_pagamento = st.selectbox("Status de pagamento", [None, "Em aberto", "Pago", "Atrasado"],
                                     format_func=lambda x: "Todos" if x is None else x)
with c3:
    vendedores_disponiveis = db.get_vendedores()
    nomes_vend = {v["id"]: v["nome"] for v in vendedores_disponiveis}
    filtro_vendedor = st.selectbox("Vendedor", [None] + list(nomes_vend.keys()),
                                    format_func=lambda x: "Todos" if x is None else nomes_vend[x])

pedidos = db.get_pedidos()
if filtro_entrega:
    pedidos = [p for p in pedidos if p["status_entrega"] == filtro_entrega]
if filtro_pagamento:
    pedidos = [p for p in pedidos if p["status_pagamento"] == filtro_pagamento]
if filtro_vendedor:
    pedidos = [p for p in pedidos if p["vendedor_id"] == filtro_vendedor]

if not pedidos:
    st.info("Nenhum pedido encontrado.")
    st.stop()

# ============================================================
# TABELA COLORIDA POR STATUS DE PAGAMENTO
# ============================================================

CORES_FUNDO_PAGAMENTO = {
    "Em aberto": "#4A3C12",   # amarelo escuro — aguardando pagamento
    "Pago": "#123A24",        # verde escuro — pago
    "Atrasado": "#3A1414",    # vermelho escuro — atrasado
}
CORES_TEXTO_PAGAMENTO = {
    "Em aberto": "#F2C14E",
    "Pago": "#4ADE80",
    "Atrasado": "#F87171",
}
ICONES_ENTREGA = {"Pendente": "⏳ Pendente", "Entregue": "✅ Entregue", "Cancelado": "❌ Cancelado"}

linhas = []
for p in pedidos:
    linhas.append({
        "Pedido": f"#{p['id']}",
        "Comprador": p["comprador_nome"] or "—",
        "Vendedor": p["vendedor_nome"] or "—",
        "Produto": p["produto"],
        "Volume (L)": p["volume_litros"] or 0,
        "Valor (R$)": p["valor_total"] or 0,
        "Data": p["data_pedido"] or "—",
        "Entrega": ICONES_ENTREGA.get(p["status_entrega"], p["status_entrega"]),
        "Pagamento": p["status_pagamento"],
        "Comissão vend. (R$)": p.get("comissao_vendedor_total") or 0,
    })
df = pd.DataFrame(linhas)


def colorir_linha(row):
    cor_fundo = CORES_FUNDO_PAGAMENTO.get(row["Pagamento"], "")
    cor_texto = CORES_TEXTO_PAGAMENTO.get(row["Pagamento"], "#EDF1F7")
    estilo = f"background-color: {cor_fundo}; color: {cor_texto}" if cor_fundo else ""
    return [estilo] * len(row)


styled = (
    df.style
    .apply(colorir_linha, axis=1)
    .format({"Volume (L)": "{:,.0f}", "Valor (R$)": "R$ {:,.2f}", "Comissão vend. (R$)": "R$ {:,.2f}"})
)
st.dataframe(styled, use_container_width=True, hide_index=True)

st.caption("🟡 Amarelo = aguardando pagamento · 🟢 Verde = pago · 🔴 Vermelho = atrasado")

# ============================================================
# ATUALIZAR STATUS DE UM PEDIDO
# ============================================================

st.markdown("### Atualizar status de um pedido")
opcoes_pedido = {p["id"]: f"#{p['id']} — {p['comprador_nome']} — {p['produto']} ({p['volume_litros']:,.0f} L)"
                  for p in pedidos}
pedido_escolhido_id = st.selectbox("Selecione o pedido", options=list(opcoes_pedido.keys()),
                                    format_func=lambda x: opcoes_pedido[x])
pedido_escolhido = next(p for p in pedidos if p["id"] == pedido_escolhido_id)

with st.form(key="form_atualizar_pedido"):
    fc1, fc2 = st.columns(2)
    with fc1:
        novo_status_entrega = st.selectbox(
            "Status de entrega", ["Pendente", "Entregue", "Cancelado"],
            index=["Pendente", "Entregue", "Cancelado"].index(pedido_escolhido["status_entrega"]))
    with fc2:
        novo_status_pagamento = st.selectbox(
            "Status de pagamento", ["Em aberto", "Pago", "Atrasado"],
            index=["Em aberto", "Pago", "Atrasado"].index(pedido_escolhido["status_pagamento"]))
    salvou = st.form_submit_button("💾 Salvar", type="primary")

if salvou:
    db.update_pedido(pedido_escolhido_id, {
        "status_entrega": novo_status_entrega,
        "status_pagamento": novo_status_pagamento,
    })
    st.success("Atualizado!")
    st.rerun()
