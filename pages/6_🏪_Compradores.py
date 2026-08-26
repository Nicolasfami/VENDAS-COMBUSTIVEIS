import streamlit as st
from datetime import date
import db
import common

st.set_page_config(page_title="Compradores", page_icon="🏪", layout="wide")
db.init_db()
common.inject_css()
vendedor = common.seletor_vendedor_logado()
common.header("Compradores", "Cadastro de clientes e histórico financeiro")

vendedores = db.get_vendedores()
nomes_vendedores = {v["id"]: v["nome"] for v in vendedores}

with st.expander("➕ Novo comprador (cadastro manual)"):
    st.caption("Postos vindos da Prospecção também podem ser convertidos direto na página CRM.")
    c1, c2 = st.columns(2)
    with c1:
        cnpj = st.text_input("CNPJ (só números)")
        razao_social = st.text_input("Razão social")
        tipo = st.selectbox("Tipo", ["Posto revendedor", "Frota", "Indústria", "TRR", "Outro"])
        endereco = st.text_input("Endereço")
        municipio = st.text_input("Município")
        uf_c = st.text_input("UF", max_chars=2)
    with c2:
        telefone = st.text_input("Telefone")
        whatsapp = st.text_input("WhatsApp")
        vendedor_responsavel = st.selectbox(
            "Vendedor responsável", options=list(nomes_vendedores.keys()) or [None],
            format_func=lambda x: nomes_vendedores.get(x, "—"))
        condicao_pagamento = st.text_input("Condição de pagamento", placeholder="Ex: 30 dias, à vista...")
        limite_credito = st.number_input("Limite de crédito (R$)", min_value=0.0, step=1000.0)
    observacoes = st.text_area("Observações")

    if st.button("Cadastrar comprador", type="primary"):
        if cnpj.strip() and razao_social.strip():
            db.upsert_comprador(cnpj.strip(), {
                "razao_social": razao_social.strip(), "tipo": tipo, "endereco": endereco,
                "municipio": municipio, "uf": uf_c.upper(), "telefone": telefone, "whatsapp": whatsapp,
                "vendedor_id": vendedor_responsavel, "condicao_pagamento": condicao_pagamento,
                "limite_credito": limite_credito, "observacoes": observacoes,
                "data_cadastro": str(date.today()),
            })
            st.success(f"{razao_social} cadastrado!")
            st.rerun()
        else:
            st.warning("Informe ao menos CNPJ e razão social.")

st.markdown("---")
st.subheader("Compradores cadastrados")

compradores = db.get_compradores()
if not compradores:
    st.info("Nenhum comprador cadastrado ainda.")
    st.stop()

filtro_vendedor = st.selectbox(
    "Filtrar por vendedor", options=[None] + list(nomes_vendedores.keys()),
    format_func=lambda x: "Todos" if x is None else nomes_vendedores.get(x, "—"))

lista = db.get_compradores(vendedor_id=filtro_vendedor) if filtro_vendedor else compradores

for c in lista:
    pedidos_c = db.get_pedidos(comprador_cnpj=c["cnpj"])
    volume_total = sum(p["volume_litros"] or 0 for p in pedidos_c)
    valor_total = sum(p["valor_total"] or 0 for p in pedidos_c)
    em_aberto = sum(p["valor_total"] or 0 for p in pedidos_c if p["status_pagamento"] == "Em aberto")

    with st.container():
        st.markdown('<div class="op-card">', unsafe_allow_html=True)
        cols = st.columns([2.5, 1.3, 1.3, 1.3, 1.3])
        with cols[0]:
            st.markdown(f"**{c['razao_social']}**")
            st.caption(f"{c['tipo']} · {c.get('municipio') or ''}/{c.get('uf') or ''} · CNPJ {c['cnpj']}")
        with cols[1]:
            st.metric("Volume total", f"{volume_total:,.0f} L")
        with cols[2]:
            st.metric("Faturado", f"R$ {valor_total:,.2f}")
        with cols[3]:
            cor = "op-badge-red" if em_aberto > 0 else "op-badge-green"
            st.markdown(f"<span class='op-badge {cor}'>Em aberto: R$ {em_aberto:,.2f}</span>", unsafe_allow_html=True)
        with cols[4]:
            with st.popover("Histórico"):
                if pedidos_c:
                    for p in pedidos_c:
                        st.write(
                            f"{p['data_pedido']} — {p['produto']} — {p['volume_litros']:,.0f} L — "
                            f"R$ {p['valor_total']:,.2f} — {p['status_pagamento']}"
                        )
                else:
                    st.caption("Nenhum pedido registrado ainda.")
        st.markdown('</div>', unsafe_allow_html=True)
