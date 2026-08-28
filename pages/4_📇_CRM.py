import streamlit as st
from datetime import date
import db
import common
import anp_api

st.set_page_config(page_title="CRM", page_icon="📇", layout="wide")
db.init_db()
common.inject_css()
common.mostrar_logo()
vendedor = common.seletor_vendedor_logado()
common.header("CRM de Visitas", "Registro comercial, clientes e histórico de compras", icone="crm")

uf_atual = st.session_state.get("uf_atual", "SP")
municipios_atual = st.session_state.get("municipios_atual", ["Jandira"])
municipios_norm = [anp_api.normalizar_municipio(m) for m in municipios_atual]
postos = db.get_postos_by_cities(uf_atual, municipios_norm)

# ============================================================
# CLIENTES CADASTRADOS — visão geral de todos os compradores
# ============================================================

compradores = db.get_compradores()
with st.expander(f"📇 Clientes cadastrados ({len(compradores)})", expanded=False):
    if not compradores:
        st.caption("Nenhum cliente convertido ainda. Use 'Converter em comprador' abaixo, num posto.")
    else:
        for c in compradores:
            pedidos_c = db.get_pedidos(comprador_cnpj=c["cnpj"])
            volume_total = sum(pe["volume_litros"] or 0 for pe in pedidos_c)
            valor_total = sum(pe["valor_total"] or 0 for pe in pedidos_c)
            em_aberto = sum(pe["valor_total"] or 0 for pe in pedidos_c if pe["status_pagamento"] == "Em aberto")
            st.markdown(f"""
            <div class="op-card">
            <b>{c['razao_social']}</b> — {c['tipo']} · {c.get('municipio') or ''}/{c.get('uf') or ''}<br>
            <span style="color:{common.PALETTE['muted']};font-size:13px">
                CNPJ {c['cnpj']} · {len(pedidos_c)} pedido(s) · {volume_total:,.0f} L · R$ {valor_total:,.2f} faturado
                {f" · <span style='color:{common.PALETTE['red']}'>R$ {em_aberto:,.2f} em aberto</span>" if em_aberto else ""}
            </span>
            </div>
            """, unsafe_allow_html=True)

st.markdown("---")

if not postos:
    st.info("Nenhum posto carregado ainda. Vá para a página **Prospecção** primeiro.")
    st.stop()

nomes = {p["cnpj"]: f"{p['razao_social']} — {p['bairro']}" for p in postos}
cnpj_selecionado = st.selectbox("Selecione o posto", options=list(nomes.keys()), format_func=lambda x: nomes[x])
posto_atual = next(p for p in postos if p["cnpj"] == cnpj_selecionado)

ja_comprador = db.get_comprador(cnpj_selecionado) is not None

col_a, col_b = st.columns([3, 1])
with col_b:
    if ja_comprador:
        st.markdown("<span class='op-badge op-badge-green'>JÁ É COMPRADOR</span>", unsafe_allow_html=True)
    else:
        if st.button("➕ Converter em comprador", use_container_width=True):
            db.upsert_comprador(cnpj_selecionado, {
                "razao_social": posto_atual["razao_social"],
                "tipo": "Posto revendedor",
                "endereco": posto_atual["endereco"],
                "municipio": posto_atual["municipio"],
                "uf": posto_atual["uf"],
                "vendedor_id": vendedor["id"] if vendedor else None,
                "data_cadastro": str(date.today()),
            })
            st.success("Posto convertido em comprador!")
            st.rerun()

with st.form(key="form_crm_principal"):
    col1, col2 = st.columns(2)
    with col1:
        status_opcoes = ["Não visitado", "Visitado", "Sem interesse", "Interessado",
                          "Cotação enviada", "Negociando", "Retornar", "Cliente"]
        status = st.selectbox("Status comercial", status_opcoes,
                               index=status_opcoes.index(posto_atual.get("status") or "Não visitado"))
        responsavel = st.text_input("Responsável", value=posto_atual.get("responsavel") or "")
        cargo = st.text_input("Cargo", value=posto_atual.get("cargo") or "")
        telefone = st.text_input("Telefone", value=posto_atual.get("telefone") or "")
        whatsapp = st.text_input("WhatsApp", value=posto_atual.get("whatsapp") or "")
        fornecedor_atual = st.text_input("Fornecedor atual", value=posto_atual.get("fornecedor_atual") or "")

    with col2:
        volume_mensal = st.text_input("Volume informado (L/mês)", value=posto_atual.get("volume_mensal") or "")
        preco_atual = st.text_input("Preço atual (R$)", value=posto_atual.get("preco_atual") or "")
        nossa_proposta = st.text_input("Nossa proposta (R$)", value=posto_atual.get("nossa_proposta") or "")
        tancagem_estimada = st.text_input("Tancagem estimada (L)", value=posto_atual.get("tancagem_estimada") or "")
        proximo_contato = st.date_input("Próximo contato", value=None)
        st.write("Produtos comercializados:")
        cd = st.checkbox("Diesel", value=bool(posto_atual.get("comercializa_diesel")))
        cg = st.checkbox("Gasolina", value=bool(posto_atual.get("comercializa_gasolina")))
        ce = st.checkbox("Etanol", value=bool(posto_atual.get("comercializa_etanol")))

    observacoes = st.text_area("Observações", value=posto_atual.get("observacoes") or "")
    salvou = st.form_submit_button("💾 Salvar dados comerciais", use_container_width=True, type="primary")

if salvou:
    db.update_crm(cnpj_selecionado, {
        "status": status, "responsavel": responsavel, "cargo": cargo, "telefone": telefone,
        "whatsapp": whatsapp, "fornecedor_atual": fornecedor_atual, "volume_mensal": volume_mensal,
        "preco_atual": preco_atual, "nossa_proposta": nossa_proposta, "tancagem_estimada": tancagem_estimada,
        "proximo_contato": str(proximo_contato) if proximo_contato else "", "observacoes": observacoes,
        "comercializa_diesel": int(cd), "comercializa_gasolina": int(cg), "comercializa_etanol": int(ce),
        "vendedor_id": vendedor["id"] if vendedor else None,
    })
    st.success("Dados salvos!")
    st.rerun()

# ============================================================
# HISTÓRICO DE COMPRAS (se já é comprador)
# ============================================================

if ja_comprador:
    st.markdown("---")
    st.markdown("### 📦 Histórico de compras")
    pedidos_posto = db.get_pedidos(comprador_cnpj=cnpj_selecionado)
    if pedidos_posto:
        volume_total_posto = sum(pe["volume_litros"] or 0 for pe in pedidos_posto)
        valor_total_posto = sum(pe["valor_total"] or 0 for pe in pedidos_posto)
        cpop1, cpop2, cpop3 = st.columns(3)
        cpop1.metric("Total comprado", f"{volume_total_posto:,.0f} L")
        cpop2.metric("Valor total", f"R$ {valor_total_posto:,.2f}")
        cpop3.metric("Pedidos", len(pedidos_posto))

        BADGE_ENTREGA = {"Pendente": "op-badge-b", "Entregue": "op-badge-green", "Cancelado": "op-badge-red"}
        BADGE_PAGAMENTO = {"Em aberto": "op-badge-b", "Pago": "op-badge-green", "Atrasado": "op-badge-red"}
        for pe in pedidos_posto:
            st.markdown(f"""
            <div class="op-card">
            <b>{pe['data_pedido']}</b> — {pe['produto']} — {pe['volume_litros']:,.0f} L — R$ {pe['valor_total']:,.2f}
            &nbsp;<span class="op-badge {BADGE_ENTREGA.get(pe['status_entrega'], 'op-badge-c')}">{pe['status_entrega']}</span>
            <span class="op-badge {BADGE_PAGAMENTO.get(pe['status_pagamento'], 'op-badge-c')}">{pe['status_pagamento']}</span>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.caption("Nenhuma compra registrada ainda pra esse cliente.")

st.markdown("---")
st.markdown("### Histórico de contatos")
with st.form(key="form_nova_nota"):
    nova_nota = st.text_area("Adicionar ao histórico")
    adicionou = st.form_submit_button("➕ Adicionar")

if adicionou and nova_nota.strip():
    db.add_historico(cnpj_selecionado, str(date.today()), nova_nota.strip())
    st.success("Adicionado!")
    st.rerun()

historico = db.get_historico(cnpj_selecionado)
if historico:
    for h in historico:
        st.markdown(f"<div class='op-card'><b>{h['data']}</b> — {h['nota']}</div>", unsafe_allow_html=True)
else:
    st.caption("Nenhum registro ainda.")
