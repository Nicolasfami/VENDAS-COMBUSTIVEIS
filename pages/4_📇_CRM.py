import streamlit as st
from datetime import date
import db
import common

st.set_page_config(page_title="CRM", page_icon="📇", layout="wide")
db.init_db()
common.inject_css()
vendedor = common.seletor_vendedor_logado()
common.header("CRM de Visitas", "Registro comercial posto a posto", icone="crm")

uf_atual = st.session_state.get("uf_atual", "SP")
municipio_atual = st.session_state.get("municipio_atual", "Jandira")
postos = db.get_postos_by_city(uf_atual, municipio_atual)

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
            st.success("Posto convertido em comprador! Veja na página Compradores.")
            st.rerun()

col1, col2 = st.columns(2)
with col1:
    status = st.selectbox("Status comercial",
                           ["Não visitado", "Visitado", "Sem interesse", "Interessado",
                            "Cotação enviada", "Negociando", "Retornar", "Cliente"],
                           index=["Não visitado", "Visitado", "Sem interesse", "Interessado",
                                  "Cotação enviada", "Negociando", "Retornar", "Cliente"]
                           .index(posto_atual.get("status") or "Não visitado"))
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

if st.button("💾 Salvar dados comerciais", use_container_width=True, type="primary"):
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

st.markdown("---")
st.markdown("### Histórico de contatos")
nova_nota = st.text_area("Adicionar ao histórico", key="nova_nota")
if st.button("➕ Adicionar"):
    if nova_nota.strip():
        db.add_historico(cnpj_selecionado, str(date.today()), nova_nota.strip())
        st.success("Adicionado!")
        st.rerun()

historico = db.get_historico(cnpj_selecionado)
if historico:
    for h in historico:
        st.markdown(f"<div class='op-card'><b>{h['data']}</b> — {h['nota']}</div>", unsafe_allow_html=True)
else:
    st.caption("Nenhum registro ainda.")
