"""
Integração com a API oficial de Revendedores da ANP.
https://revendedoresapi.anp.gov.br/swagger/index.html

Vantagem sobre o CSV: já traz produtos comercializados, tancagem por produto,
quantidade de bicos e latitude/longitude — sem precisar geocodificar nem
preencher manualmente.
"""
import requests

BASE_URL = "https://revendedoresapi.anp.gov.br/v1/combustivel"
TIMEOUT = 20
MAX_PAGINAS = 20  # trava de segurança


def buscar_postos_por_cidade(uf, municipio):
    """Busca todos os postos de uma cidade direto na API oficial da ANP.
    Retorna lista de dicts (já no formato bruto da API) ou levanta exceção
    em caso de falha de rede."""
    todos = []
    pagina = 1
    while pagina <= MAX_PAGINAS:
        params = {"uf": uf, "municipio": municipio, "numeropagina": pagina}
        resp = requests.get(BASE_URL, params=params, timeout=TIMEOUT)
        resp.raise_for_status()
        payload = resp.json()

        if not payload.get("succeeded", True):
            break

        dados = payload.get("data") or []
        if not dados:
            break

        todos.extend(dados)

        # a API não documenta o campo de total de páginas de forma explícita;
        # paramos quando uma página vem vazia ou menor que o tamanho máximo (5000)
        if len(dados) < 5000:
            break
        pagina += 1

    return todos


def debug_requisicao(uf, municipio):
    """Faz a chamada crua pra API e devolve status/corpo da resposta,
    pra diagnosticar por que uma busca não retornou postos."""
    params = {"uf": uf, "municipio": municipio, "numeropagina": 1}
    try:
        resp = requests.get(BASE_URL, params=params, timeout=TIMEOUT)
        return {
            "url_final": resp.url,
            "status_code": resp.status_code,
            "corpo": resp.text[:2000],
        }
    except Exception as e:
        return {"erro": str(e)}


def buscar_posto_por_cnpj(cnpj):
    """Busca um único posto pelo CNPJ."""
    params = {"cnpj": cnpj}
    resp = requests.get(BASE_URL, params=params, timeout=TIMEOUT)
    resp.raise_for_status()
    payload = resp.json()
    dados = payload.get("data") or []
    return dados[0] if dados else None
