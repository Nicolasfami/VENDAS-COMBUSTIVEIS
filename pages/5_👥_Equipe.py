import streamlit as st
from datetime import date
import db
import common

st.set_page_config(page_title="Equipe", page_icon="👥", layout="wide")
db.init_db()
common.inject_css()
common.seletor_vendedor_logado()
common.header("Equipe de Vendas", "Cadastro de vendedores e metas mensais de volume")

with st.expander("➕ Novo vendedor"):
    c1, c2 = st.columns(2)
    with c1:
        nome = st.text_input("Nome")
        email = st.text_input("E-mail")
        telefone = st.text_input("Telefone")
    with c2:
        pin = st.text_input("PIN de identificação (4 dígitos)", value="0000", max_chars=4)
        meta = st.number_input("Meta mensal (litros)", min_value=0, value=50000, step=1000)
    if st.button("Cadastrar vendedor", type="primary"):
        if nome.strip():
            db.add_vendedor(nome.strip(), email.strip(), telefone.strip(), pin.strip(), meta)
            st.success(f"Vendedor {nome} cadastrado!")
            st.rerun()
        else:
            st.warning("Informe ao menos o nome.")

st.markdown("---")
st.subheader("Equipe cadastrada")

vendedores = db.get_vendedores()
if not vendedores:
    st.info("Nenhum vendedor cadastrado ainda.")
    st.stop()

mes_atual = date.today().strftime("%Y-%m")
volumes = {v["id"]: v for v in db.get_volume_por_vendedor(mes_atual)}

for v in vendedores:
    vol_info = volumes.get(v["id"], {"volume_total": 0, "valor_total": 0})
    meta = v["meta_mensal_litros"] or 0
    pct = (vol_info["volume_total"] / meta * 100) if meta > 0 else 0

    st.markdown('<div class="op-card">', unsafe_allow_html=True)
    cols = st.columns([2, 1.5, 1.5, 1.5, 1])
    with cols[0]:
        st.markdown(f"**{v['nome']}**")
        st.caption(f"{v.get('email') or '—'} · {v.get('telefone') or '—'}")
    with cols[1]:
        st.metric("Meta mensal", f"{meta:,.0f} L")
    with cols[2]:
        st.metric("Vendido no mês", f"{vol_info['volume_total']:,.0f} L")
    with cols[3]:
        cor_badge = "op-badge-green" if pct >= 100 else ("op-badge-a" if pct >= 60 else "op-badge-b")
        st.markdown(f"<span class='op-badge {cor_badge}'>{pct:.0f}% da meta</span>", unsafe_allow_html=True)
    with cols[4]:
        ativo = st.checkbox("Ativo", value=bool(v["ativo"]), key=f"ativo_{v['id']}")
        if ativo != bool(v["ativo"]):
            db.update_vendedor(v["id"], {"ativo": int(ativo)})
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)
