import requests
import json

BASE_URL = "https://api.plannix.com.br/public/v1"
CHAVE = "plan_live_QpKoSeMOKYWkQDNhW0ZxI-NaYnzBJAAENgpIap7zqFg"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"

HEADERS = {
    "Authorization": f"Bearer {CHAVE}",
    "Accept": "application/json",
    "User-Agent": USER_AGENT
}

def consultar_informacao_global():
    url = f"{BASE_URL}/bi/informacaoGlobalPeca"
    print(f"Consultando rota global: {url} (isso pode levar alguns segundos)...")
    
    try:
        # Timeout estendido para 120s conforme recomendado na documentação
        r = requests.get(url, headers=HEADERS, timeout=120)
        print(f"Status HTTP: {r.status_code}")
        
        if r.status_code == 200:
            dados = r.json()
            print(f"[SUCESSO!] Retornou {len(dados)} registros de peças.")
            
            # Salva o resultado completo para inspecionarmos
            with open("informacao_global_pecas.json", "w", encoding="utf-8") as f:
                json.dump(dados, f, indent=4, ensure_ascii=False)
            print("Arquivo 'informacao_global_pecas.json' salvo com sucesso!")
            
            if len(dados) > 0:
                print("\nExemplo da primeira peça (campos disponíveis):")
                print(json.dumps(dados[0], indent=2, ensure_ascii=False))
        else:
            print(f"Erro {r.status_code}: {r.text}")
            
    except Exception as e:
        print(f"Erro na requisição: {e}")

if __name__ == "__main__":
    consultar_informacao_global()