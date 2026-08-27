"""
Camada de banco de dados — Postgres via Supabase.

Todas as tabelas vivem num schema PRÓPRIO ("prospeccao_vendas"), isolado de
qualquer outra tabela que já exista no seu projeto Supabase. Isso é garantido
pelo `SET search_path` logo após conectar: qualquer nome de tabela sem
prefixo (ex: "postos") sempre resolve dentro desse schema, nunca no "public"
onde outros apps possam ter suas próprias tabelas.

Requer um secret SUPABASE_DB_URL configurado em .streamlit/secrets.toml
(local) ou nas Secrets do Streamlit Community Cloud (produção). Veja o
README para instruções de onde pegar essa connection string no Supabase.

Módulos:
- postos / geocode_cache / crm / historico  -> prospecção (dados da ANP)
- vendedores                                 -> equipe comercial
- compradores                                -> clientes (postos convertidos ou cadastro manual)
- cotacoes                                   -> propostas em aberto
- pedidos                                    -> vendas fechadas / histórico financeiro
"""
import streamlit as st
import psycopg2
from psycopg2.extras import RealDictCursor

SCHEMA = "prospeccao_vendas"


def get_conn():
    """Abre uma nova conexão por chamada (padrão seguro para apps
    multiusuário — evita compartilhar uma conexão entre sessões diferentes
    do Streamlit). O pooler do Supabase foi feito exatamente para isso."""
    conn = psycopg2.connect(st.secrets["SUPABASE_DB_URL"], cursor_factory=RealDictCursor)
    with conn.cursor() as cur:
        cur.execute(f"SET search_path TO {SCHEMA}, public")
    return conn


def init_db():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")

    # ---------- PROSPECÇÃO (ANP) ----------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS postos (
            cnpj TEXT PRIMARY KEY,
            codigo_simp TEXT,
            autorizacao TEXT,
            razao_social TEXT,
            endereco TEXT,
            complemento TEXT,
            bairro TEXT,
            cep TEXT,
            uf TEXT,
            municipio TEXT,
            bandeira TEXT,
            data_vinculacao TEXT,
            latitude REAL,
            longitude REAL,
            produtos_json TEXT,
            tancagem_total_m3 REAL,
            situacao_constatada TEXT,
            origem_dado TEXT DEFAULT 'CSV'
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS geocode_cache (
            endereco_completo TEXT PRIMARY KEY,
            lat REAL,
            lon REAL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS crm (
            cnpj TEXT PRIMARY KEY,
            status TEXT DEFAULT 'Não visitado',
            responsavel TEXT,
            cargo TEXT,
            telefone TEXT,
            whatsapp TEXT,
            fornecedor_atual TEXT,
            volume_mensal TEXT,
            preco_atual TEXT,
            nossa_proposta TEXT,
            proximo_contato TEXT,
            observacoes TEXT,
            tancagem_estimada TEXT,
            comercializa_diesel INTEGER DEFAULT 0,
            comercializa_gasolina INTEGER DEFAULT 0,
            comercializa_etanol INTEGER DEFAULT 0,
            vendedor_id INTEGER,
            FOREIGN KEY (cnpj) REFERENCES postos (cnpj)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS historico (
            id SERIAL PRIMARY KEY,
            cnpj TEXT,
            data TEXT,
            nota TEXT,
            FOREIGN KEY (cnpj) REFERENCES postos (cnpj)
        )
    """)

    # ---------- EQUIPE ----------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS vendedores (
            id SERIAL PRIMARY KEY,
            nome TEXT NOT NULL,
            email TEXT,
            telefone TEXT,
            pin TEXT DEFAULT '0000',
            meta_mensal_litros REAL DEFAULT 0,
            ativo INTEGER DEFAULT 1
        )
    """)

    # ---------- COMPRADORES (clientes) ----------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS compradores (
            cnpj TEXT PRIMARY KEY,
            razao_social TEXT NOT NULL,
            tipo TEXT DEFAULT 'Posto revendedor',
            telefone TEXT,
            whatsapp TEXT,
            endereco TEXT,
            municipio TEXT,
            uf TEXT,
            vendedor_id INTEGER,
            condicao_pagamento TEXT,
            limite_credito REAL DEFAULT 0,
            observacoes TEXT,
            data_cadastro TEXT,
            FOREIGN KEY (vendedor_id) REFERENCES vendedores (id)
        )
    """)

    # ---------- COTAÇÕES ----------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS cotacoes (
            id SERIAL PRIMARY KEY,
            comprador_cnpj TEXT NOT NULL,
            vendedor_id INTEGER,
            produto TEXT,
            volume_litros REAL,
            preco_unitario REAL,
            data_cotacao TEXT,
            validade TEXT,
            status TEXT DEFAULT 'Pendente',
            observacoes TEXT,
            FOREIGN KEY (comprador_cnpj) REFERENCES compradores (cnpj),
            FOREIGN KEY (vendedor_id) REFERENCES vendedores (id)
        )
    """)

    # ---------- PEDIDOS (vendas) ----------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS pedidos (
            id SERIAL PRIMARY KEY,
            cotacao_id INTEGER,
            comprador_cnpj TEXT NOT NULL,
            vendedor_id INTEGER,
            produto TEXT,
            volume_litros REAL,
            preco_unitario REAL,
            valor_total REAL,
            data_pedido TEXT,
            data_entrega TEXT,
            status_entrega TEXT DEFAULT 'Pendente',
            status_pagamento TEXT DEFAULT 'Em aberto',
            forma_pagamento TEXT,
            observacoes TEXT,
            comissao_vendedor_litro REAL DEFAULT 0,
            comissao_empresa_litro REAL DEFAULT 0,
            comissao_vendedor_total REAL DEFAULT 0,
            comissao_empresa_total REAL DEFAULT 0,
            FOREIGN KEY (cotacao_id) REFERENCES cotacoes (id),
            FOREIGN KEY (comprador_cnpj) REFERENCES compradores (cnpj),
            FOREIGN KEY (vendedor_id) REFERENCES vendedores (id)
        )
    """)

    # ---------- TABELA DE COMISSÃO POR PRODUTO ----------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS comissoes_produto (
            produto TEXT PRIMARY KEY,
            comissao_vendedor_litro REAL DEFAULT 0,
            comissao_empresa_litro REAL DEFAULT 0
        )
    """)

    # Migração segura: adiciona colunas de comissão em bancos já existentes
    # (não apaga nem altera dados já cadastrados)
    for coluna in ["comissao_vendedor_litro", "comissao_empresa_litro",
                   "comissao_vendedor_total", "comissao_empresa_total"]:
        cur.execute(f"ALTER TABLE pedidos ADD COLUMN IF NOT EXISTS {coluna} REAL DEFAULT 0")

    conn.commit()
    conn.close()


# ============================================================
# POSTOS (prospecção)
# ============================================================

def upsert_postos(df):
    """Insere/atualiza postos a partir de um DataFrame vindo do CSV manual da ANP."""
    conn = get_conn()
    cur = conn.cursor()
    for _, row in df.iterrows():
        cur.execute("""
            INSERT INTO postos (cnpj, codigo_simp, autorizacao, razao_social, endereco,
                                 complemento, bairro, cep, uf, municipio, bandeira, data_vinculacao)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (cnpj) DO UPDATE SET
                razao_social=excluded.razao_social, endereco=excluded.endereco,
                complemento=excluded.complemento, bairro=excluded.bairro, cep=excluded.cep,
                uf=excluded.uf, municipio=excluded.municipio, bandeira=excluded.bandeira,
                data_vinculacao=excluded.data_vinculacao
        """, (
            row["CNPJ"], row["CODIGOISIMP"], row["AUTORIZACAO"], row["RAZAOSOCIAL"],
            row["ENDERECO"], row.get("COMPLEMENTO", ""), row["BAIRRO"], row["CEP"],
            row["UF"], row["MUNICIPIO"], row["BANDEIRA"], row.get("DATAVINCULACAO", "")
        ))
        cur.execute("INSERT INTO crm (cnpj) VALUES (%s) ON CONFLICT (cnpj) DO NOTHING", (row["CNPJ"],))
    conn.commit()
    conn.close()


def upsert_postos_api(postos_api: list):
    """Insere/atualiza postos vindos diretamente da API oficial da ANP,
    já com produtos, tancagem e coordenadas."""
    import json as _json
    conn = get_conn()
    cur = conn.cursor()
    for p in postos_api:
        produtos = p.get("produtos") or []
        tancagem_total = sum((prod.get("tancagem") or 0) for prod in produtos)
        lat = p.get("latitude") or None
        lon = p.get("longitude") or None
        lat = float(lat) if lat not in (None, "") else None
        lon = float(lon) if lon not in (None, "") else None

        cur.execute("""
            INSERT INTO postos (cnpj, codigo_simp, autorizacao, razao_social, endereco,
                                 complemento, bairro, cep, uf, municipio, bandeira, data_vinculacao,
                                 latitude, longitude, produtos_json, tancagem_total_m3,
                                 situacao_constatada, origem_dado)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'API')
            ON CONFLICT (cnpj) DO UPDATE SET
                razao_social=excluded.razao_social, endereco=excluded.endereco,
                complemento=excluded.complemento, bairro=excluded.bairro, cep=excluded.cep,
                uf=excluded.uf, municipio=excluded.municipio, bandeira=excluded.bandeira,
                data_vinculacao=excluded.data_vinculacao, latitude=excluded.latitude,
                longitude=excluded.longitude, produtos_json=excluded.produtos_json,
                tancagem_total_m3=excluded.tancagem_total_m3,
                situacao_constatada=excluded.situacao_constatada, origem_dado='API'
        """, (
            p.get("cnpj"), p.get("codigoSIMP"), p.get("autorizacao"), p.get("razaoSocial"),
            p.get("endereco"), p.get("complemento", ""), p.get("bairro"), p.get("cep"),
            p.get("uf"), p.get("municipio"), p.get("distribuidora"), p.get("dataVinculacao"),
            lat, lon, _json.dumps(produtos, ensure_ascii=False), tancagem_total,
            p.get("situacaoConstatada"),
        ))
        cur.execute("INSERT INTO crm (cnpj) VALUES (%s) ON CONFLICT (cnpj) DO NOTHING", (p.get("cnpj"),))
    conn.commit()
    conn.close()


def get_postos_by_city(uf, municipio):
    return get_postos_by_cities(uf, [municipio])


def get_postos_by_cities(uf, municipios: list):
    """Busca postos em uma ou mais cidades do mesmo estado de uma vez.
    municipios já deve vir normalizado (maiúsculo, sem acento)."""
    if not municipios:
        return []
    conn = get_conn()
    cur = conn.cursor()
    municipios_norm = [m.upper().strip() for m in municipios]
    placeholders = ", ".join(["%s"] * len(municipios_norm))
    cur.execute(f"""
        SELECT p.*,
               COALESCE(p.latitude, g.lat) as lat,
               COALESCE(p.longitude, g.lon) as lon,
               c.status, c.responsavel, c.cargo, c.telefone, c.whatsapp,
               c.fornecedor_atual, c.volume_mensal, c.preco_atual, c.nossa_proposta,
               c.proximo_contato, c.observacoes, c.tancagem_estimada,
               c.comercializa_diesel, c.comercializa_gasolina, c.comercializa_etanol,
               c.vendedor_id
        FROM postos p
        LEFT JOIN geocode_cache g ON g.endereco_completo = (p.endereco || ', ' || p.municipio || ', ' || p.uf)
        LEFT JOIN crm c ON c.cnpj = p.cnpj
        WHERE p.uf = %s AND p.municipio IN ({placeholders})
    """, [uf] + municipios_norm)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def get_geocode(endereco_completo):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT lat, lon FROM geocode_cache WHERE endereco_completo = %s", (endereco_completo,))
    row = cur.fetchone()
    conn.close()
    return (row["lat"], row["lon"]) if row else None


def save_geocode(endereco_completo, lat, lon):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO geocode_cache (endereco_completo, lat, lon) VALUES (%s, %s, %s)
        ON CONFLICT (endereco_completo) DO UPDATE SET lat=excluded.lat, lon=excluded.lon
    """, (endereco_completo, lat, lon))
    conn.commit()
    conn.close()


def update_crm(cnpj, fields: dict):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("INSERT INTO crm (cnpj) VALUES (%s) ON CONFLICT (cnpj) DO NOTHING", (cnpj,))
    set_clause = ", ".join(f"{k} = %s" for k in fields.keys())
    values = list(fields.values()) + [cnpj]
    cur.execute(f"UPDATE crm SET {set_clause} WHERE cnpj = %s", values)
    conn.commit()
    conn.close()


def add_historico(cnpj, data, nota):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("INSERT INTO historico (cnpj, data, nota) VALUES (%s, %s, %s)", (cnpj, data, nota))
    conn.commit()
    conn.close()


def get_historico(cnpj):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM historico WHERE cnpj = %s ORDER BY data DESC", (cnpj,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


# ============================================================
# VENDEDORES
# ============================================================

def add_vendedor(nome, email, telefone, pin, meta_mensal_litros):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO vendedores (nome, email, telefone, pin, meta_mensal_litros)
        VALUES (%s, %s, %s, %s, %s)
    """, (nome, email, telefone, pin, meta_mensal_litros))
    conn.commit()
    conn.close()


def update_vendedor(vendedor_id, fields: dict):
    conn = get_conn()
    cur = conn.cursor()
    set_clause = ", ".join(f"{k} = %s" for k in fields.keys())
    values = list(fields.values()) + [vendedor_id]
    cur.execute(f"UPDATE vendedores SET {set_clause} WHERE id = %s", values)
    conn.commit()
    conn.close()


def get_vendedores(somente_ativos=False):
    conn = get_conn()
    cur = conn.cursor()
    query = "SELECT * FROM vendedores"
    if somente_ativos:
        query += " WHERE ativo = 1"
    cur.execute(query + " ORDER BY nome")
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def get_vendedor(vendedor_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM vendedores WHERE id = %s", (vendedor_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


# ============================================================
# COMPRADORES
# ============================================================

def upsert_comprador(cnpj, fields: dict):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT cnpj FROM compradores WHERE cnpj = %s", (cnpj,))
    existe = cur.fetchone()
    if existe:
        set_clause = ", ".join(f"{k} = %s" for k in fields.keys())
        values = list(fields.values()) + [cnpj]
        cur.execute(f"UPDATE compradores SET {set_clause} WHERE cnpj = %s", values)
    else:
        cols = ["cnpj"] + list(fields.keys())
        placeholders = ", ".join(["%s"] * len(cols))
        values = [cnpj] + list(fields.values())
        cur.execute(f"INSERT INTO compradores ({', '.join(cols)}) VALUES ({placeholders})", values)
    conn.commit()
    conn.close()


def get_compradores(vendedor_id=None):
    conn = get_conn()
    cur = conn.cursor()
    if vendedor_id:
        cur.execute("SELECT * FROM compradores WHERE vendedor_id = %s ORDER BY razao_social", (vendedor_id,))
    else:
        cur.execute("SELECT * FROM compradores ORDER BY razao_social")
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def get_comprador(cnpj):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM compradores WHERE cnpj = %s", (cnpj,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


# ============================================================
# COTAÇÕES
# ============================================================

def add_cotacao(fields: dict):
    conn = get_conn()
    cur = conn.cursor()
    cols = list(fields.keys())
    placeholders = ", ".join(["%s"] * len(cols))
    cur.execute(f"INSERT INTO cotacoes ({', '.join(cols)}) VALUES ({placeholders}) RETURNING id",
                list(fields.values()))
    novo_id = cur.fetchone()["id"]
    conn.commit()
    conn.close()
    return novo_id


def update_cotacao_status(cotacao_id, status):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE cotacoes SET status = %s WHERE id = %s", (status, cotacao_id))
    conn.commit()
    conn.close()


def get_cotacoes(vendedor_id=None, status=None):
    conn = get_conn()
    cur = conn.cursor()
    query = """
        SELECT co.*, c.razao_social as comprador_nome, v.nome as vendedor_nome
        FROM cotacoes co
        LEFT JOIN compradores c ON c.cnpj = co.comprador_cnpj
        LEFT JOIN vendedores v ON v.id = co.vendedor_id
        WHERE 1=1
    """
    params = []
    if vendedor_id:
        query += " AND co.vendedor_id = %s"
        params.append(vendedor_id)
    if status:
        query += " AND co.status = %s"
        params.append(status)
    query += " ORDER BY co.data_cotacao DESC"
    cur.execute(query, params)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def get_cotacao(cotacao_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM cotacoes WHERE id = %s", (cotacao_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


# ============================================================
# PEDIDOS
# ============================================================

def add_pedido(fields: dict):
    conn = get_conn()
    cur = conn.cursor()
    cols = list(fields.keys())
    placeholders = ", ".join(["%s"] * len(cols))
    cur.execute(f"INSERT INTO pedidos ({', '.join(cols)}) VALUES ({placeholders}) RETURNING id",
                list(fields.values()))
    novo_id = cur.fetchone()["id"]
    conn.commit()
    conn.close()
    return novo_id


def update_pedido(pedido_id, fields: dict):
    conn = get_conn()
    cur = conn.cursor()
    set_clause = ", ".join(f"{k} = %s" for k in fields.keys())
    values = list(fields.values()) + [pedido_id]
    cur.execute(f"UPDATE pedidos SET {set_clause} WHERE id = %s", values)
    conn.commit()
    conn.close()


def get_pedidos(vendedor_id=None, comprador_cnpj=None):
    conn = get_conn()
    cur = conn.cursor()
    query = """
        SELECT pe.*, c.razao_social as comprador_nome, v.nome as vendedor_nome
        FROM pedidos pe
        LEFT JOIN compradores c ON c.cnpj = pe.comprador_cnpj
        LEFT JOIN vendedores v ON v.id = pe.vendedor_id
        WHERE 1=1
    """
    params = []
    if vendedor_id:
        query += " AND pe.vendedor_id = %s"
        params.append(vendedor_id)
    if comprador_cnpj:
        query += " AND pe.comprador_cnpj = %s"
        params.append(comprador_cnpj)
    query += " ORDER BY pe.data_pedido DESC"
    cur.execute(query, params)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def get_serie_mensal_vendas(meses=6):
    """Retorna volume/faturamento agrupado por mês (últimos N meses), em ordem
    cronológica — usado pro gráfico de tendência no Painel Geral."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT LEFT(data_pedido, 7) as mes,
               COALESCE(SUM(volume_litros), 0) as volume_total,
               COALESCE(SUM(valor_total), 0) as valor_total
        FROM pedidos
        WHERE data_pedido IS NOT NULL AND data_pedido != ''
        GROUP BY LEFT(data_pedido, 7)
        ORDER BY mes DESC
        LIMIT %s
    """, (meses,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return list(reversed(rows))


def get_comissao_produto(produto):
    """Retorna a comissão configurada (R$/L) pra um produto, ou zeros se não configurado."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM comissoes_produto WHERE produto = %s", (produto,))
    row = cur.fetchone()
    conn.close()
    if row:
        return dict(row)
    return {"produto": produto, "comissao_vendedor_litro": 0, "comissao_empresa_litro": 0}


def get_comissoes_produto():
    """Lista a tabela de comissão de todos os produtos cadastrados."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM comissoes_produto ORDER BY produto")
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def upsert_comissao_produto(produto, comissao_vendedor_litro, comissao_empresa_litro):
    """Define/atualiza a comissão (R$/L) de vendedor e empresa pra um produto."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO comissoes_produto (produto, comissao_vendedor_litro, comissao_empresa_litro)
        VALUES (%s, %s, %s)
        ON CONFLICT (produto) DO UPDATE SET
            comissao_vendedor_litro = excluded.comissao_vendedor_litro,
            comissao_empresa_litro = excluded.comissao_empresa_litro
    """, (produto, comissao_vendedor_litro, comissao_empresa_litro))
    conn.commit()
    conn.close()


def get_comissoes_por_vendedor(mes_ano=None):
    """Soma a comissão de cada vendedor (e da empresa) nos pedidos, opcionalmente
    filtrando por mês (formato 'YYYY-MM')."""
    conn = get_conn()
    cur = conn.cursor()
    query = """
        SELECT v.id, v.nome,
               COALESCE(SUM(pe.comissao_vendedor_total), 0) as comissao_vendedor,
               COALESCE(SUM(pe.comissao_empresa_total), 0) as comissao_empresa,
               COALESCE(SUM(pe.volume_litros), 0) as volume_total
        FROM vendedores v
        LEFT JOIN pedidos pe ON pe.vendedor_id = v.id
    """
    params = []
    if mes_ano:
        query += " AND LEFT(pe.data_pedido, 7) = %s"
        params.append(mes_ano)
    query += " GROUP BY v.id, v.nome ORDER BY comissao_vendedor DESC"
    cur.execute(query, params)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def get_volume_por_vendedor(mes_ano=None):
    """mes_ano no formato 'YYYY-MM'. Retorna litros vendidos (pedidos) por vendedor."""
    conn = get_conn()
    cur = conn.cursor()
    query = """
        SELECT v.id, v.nome, v.meta_mensal_litros,
               COALESCE(SUM(pe.volume_litros), 0) as volume_total,
               COALESCE(SUM(pe.valor_total), 0) as valor_total
        FROM vendedores v
        LEFT JOIN pedidos pe ON pe.vendedor_id = v.id
    """
    params = []
    if mes_ano:
        query += " AND LEFT(pe.data_pedido, 7) = %s"
        params.append(mes_ano)
    query += " GROUP BY v.id, v.nome, v.meta_mensal_litros ORDER BY volume_total DESC"
    cur.execute(query, params)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows
