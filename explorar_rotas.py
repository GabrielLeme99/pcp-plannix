import requests
import json

BASE_URL = "https://api.plannix.com.br/public/v1"
CHAVE = "plan_live_QpKoSeMOKYWkQDNhW0ZxI-NaYnzBJAAENgpIap7zqFg"

# Cabeçalho padrão exato exigido pela documentação pública
HEADERS = {
    "Authorization": f"Bearer {CHAVE}",
    "Accept": "application/json"
}

# Rotas base da API do Plannix
ROTAS_PARA_TESTAR = [
    "/obra", "/obras",
    "/peca", "/pecas",
    "/projeto", "/projetos",
    "/producao", "/fabricacao",
    "/logistica", "/expedicao",
    "/montagem"
]

def mapear_endpoints():
    print("=== TESTANDO ROTAS COM BEARER TOKEN CORRETO ===\n")
    
    for rota in ROTAS_PARA_TESTAR:
        url = f"{BASE_URL}{rota}"
        try:
            r = requests.get(url, headers=HEADERS, timeout=20)
            print(f"Rota {rota:<15} -> Status: {r.status_code}")
            
            if r.status_code == 200:
                dados = r.json()
                print(f"   [SUCESSO!] Retornou dados. Amostra:")
                print(json.dumps(dados, indent=2, ensure_ascii=False)[:400])
                with open(f"resposta_{rota.replace('/', '')}.json", "w", encoding="utf-8") as f:
                    json.dump(dados, f, indent=4, ensure_ascii=False)
            elif r.status_code == 401:
                # Tenta alternar para o header X-API-Key caso o Bearer falhe nesta rota
                r2 = requests.get(url, headers={"X-API-Key": CHAVE, "Accept": "application/json"}, timeout=20)
                if r2.status_code == 200:
                    print(f"   [SUCESSO com X-API-Key!] Retornou dados.")
        except Exception as e:
            print(f"Rota {rota:<15} -> Erro: {e}")

if __name__ == "__main__":
    mapear_endpoints()