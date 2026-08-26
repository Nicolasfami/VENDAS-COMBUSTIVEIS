# Painel de Vendas — Prospecção + Comercial de Combustíveis

App para representantes comerciais de refinarias/distribuidoras: encontra e
prioriza postos (prospecção via ANP), organiza rotas de visita, e gerencia
todo o ciclo comercial (vendedores, compradores, cotações e pedidos).

Roda **em paralelo** ao seu sistema operacional/faturamento (ex: Operax) —
não substitui, complementa com prospecção e gestão comercial de campo.

## Módulos

### Prospecção (fonte: ANP)
- Importa o CSV nacional de revendedores da ANP e filtra por UF/Município
- Score comercial configurável (bandeira branca, produtos, se já foi visitado)
- Prioridade A/B/C
- Mapa geocodificado automaticamente
- Geração de rota otimizada com link direto pro Google Maps
- CRM por posto: status, contato, fornecedor atual, histórico de visitas
- Botão para **converter um posto prospectado em comprador** (ponte pro módulo de vendas)

### Vendas
- **Equipe**: cadastro de vendedores, metas mensais de volume (litros), medidor visual de % da meta batida
- **Compradores**: cadastro de clientes (postos, frotas, indústrias, TRR...), vendedor responsável, condição de pagamento, limite de crédito, histórico financeiro (volume total, faturado, em aberto)
- **Cotações**: propostas com produto, volume, preço e validade; aceitar uma cotação gera um pedido automaticamente
- **Pedidos**: vendas fechadas com status de entrega e de pagamento (em aberto/pago/atrasado)
- **Painel Geral**: números consolidados de prospecção + vendas, ranking de vendedores no mês

### Login leve por vendedor
Não é autenticação forte (sem senha criptografada) — é um seletor "quem está
usando agora" na barra lateral, pra atribuir corretamente vendas e prospecção
a cada pessoa da equipe. Se quiser proteção real de acesso mais adiante,
dá pra evoluir para Streamlit Authenticator ou um provedor OAuth.

## Como rodar localmente

```bash
pip install -r requirements.txt
streamlit run app.py
```

Abra http://localhost:8501 no navegador.

## Como publicar como site (grátis, acessível do celular)

1. Crie uma conta grátis em https://share.streamlit.io (login com GitHub)
2. Suba **todos** os arquivos desta pasta num repositório GitHub, mantendo a
   estrutura de pastas (`app.py`, `db.py`, `common.py`, `geo_utils.py`,
   `requirements.txt`, a pasta `pages/` inteira, e a pasta `.streamlit/`
   com o `config.toml` — é ele que aplica o tema escuro)
3. No Streamlit Community Cloud, clique em **New app**, selecione o
   repositório e aponte pro `app.py`
4. Deploy — em 1-2 minutos você tem uma URL pública (ex:
   `https://seuapp.streamlit.app`), acessível em qualquer navegador,
   inclusive no celular

## Fluxo de uso sugerido

1. Cadastre a equipe em **Equipe** (nome, meta mensal de litros)
2. Importe o CSV da ANP em **Prospecção** e filtre pela região
3. Visite os postos, registre no **CRM** e converta os que viram clientes
   em **Compradores**
4. Registre propostas em **Cotações** — ao aceitar, vira **Pedido**
   automaticamente
5. Acompanhe entrega e pagamento em **Pedidos**
6. Veja os números de todo mundo no **Painel Geral** e a home mostra o
   medidor de meta de cada vendedor

## Limitações importantes

- **Dados da ANP**: só trazem CNPJ, razão social, endereço, bandeira e
  situação da autorização. Produtos comercializados, tancagem e contato
  são preenchidos manualmente pelo time durante a prospecção/visitas.
- **Persistência**: os dados ficam no Postgres do Supabase — permanentes,
  não resetam em redeploy. Recomendado mesmo assim manter backups periódicos
  (o próprio Supabase oferece backup automático, e a aba Exportar da
  Prospecção também gera um CSV a qualquer momento).
- **Login por PIN**: é identificação leve pra equipe pequena, não é
  segurança de verdade. Não guarde dados sensíveis assumindo proteção forte.


## Fonte de dados: API oficial vs CSV

A página **Prospecção** agora oferece duas formas de buscar os postos:

1. **API oficial da ANP (recomendado)** — consulta ao vivo em
   `revendedoresapi.anp.gov.br`, já retornando produtos comercializados
   (gasolina/etanol/diesel), tancagem por produto, quantidade de bicos e
   coordenadas geográficas prontas. O score comercial passa a ser calculado
   automaticamente com dados reais, sem depender de preenchimento manual.
2. **CSV manual** — mantido como alternativa, caso a API esteja fora do ar
   ou você prefira trabalhar offline com um arquivo baixado previamente.

Quando os dados vêm da API, o Mapa e a Rota usam as coordenadas direto —
sem precisar geocodificar endereço por endereço (mais rápido e mais preciso).


## Banco de dados: Supabase (Postgres)

O app usa **Postgres via Supabase** como banco de dados — dados permanentes,
compartilhados por toda a equipe, sem risco de reset em redeploy.

**Isolamento garantido:** todas as tabelas deste app vivem dentro de um
schema próprio chamado `prospeccao_vendas`, completamente separado do
schema `public` (onde outros apps que você já tenha no mesmo projeto
Supabase guardam suas tabelas). Isso é garantido automaticamente pelo
código — nenhuma tabela sua já existente é tocada, lida ou alterada.

### Configuração (uma vez só)

1. No [supabase.com](https://supabase.com), abra o projeto que você quer usar
2. Vá em **Project Settings** (ícone de engrenagem) → **Database**
3. Em **Connection string**, escolha o modo **Transaction pooler** (porta 6543)
4. Copie a URI e troque `[YOUR-PASSWORD]` pela senha do seu banco

**Localmente:** copie `.streamlit/secrets.toml.example` para
`.streamlit/secrets.toml` e cole sua connection string real lá dentro.
Esse arquivo já está no `.gitignore` — nunca vai pro GitHub.

**No Streamlit Community Cloud:** depois de fazer o deploy, vá nas
configurações do seu app → **Secrets**, e cole:

```toml
SUPABASE_DB_URL = "postgresql://postgres.xxxx:SUA_SENHA@aws-0-sa-east-1.pooler.supabase.com:6543/postgres"
```

Na primeira vez que o app rodar, ele cria sozinho o schema e todas as
tabelas necessárias (não precisa rodar nenhum script SQL manual).
