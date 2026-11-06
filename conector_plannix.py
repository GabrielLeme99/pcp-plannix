import requests
import json

BASE_URL = "https://api.plannix.com.br/public/v1"

# Cole aqui a chave copiada direto do botao 'Copiar' do Plannix
CHAVE = "plan_live_QpKoSeMOKYWkQDNhW0ZxI-NaYnzBJAAENgpIap7zqFg"

# Simula o navegador Chrome para evitar bloqueio de firewall
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"

def validar_chave():
    url_teste = f"{BASE_URL}/test"
    
    # Testa os dois formatos oficiais separadamente
    modos = [
        ("Bearer Token", {"Authorization": f"Bearer {CHAVE}", "Accept": "application/json", "User-Agent": USER_AGENT}),
        ("X-API-Key",    {"X-API-Key": CHAVE, "Accept": "application/json", "User-Agent": USER_AGENT})
    ]
    
    for nome_modo, headers in modos:
        print(f"\nTestando modo [{nome_modo}] em {url_teste} (aguarde ate 45s)...")
        try:
            r = requests.get(url_teste, headers=headers, timeout=45)
            print(f" -> Status HTTP: {r.status_code}")
            print(f" -> Resposta: {r.text}")
            
            if r.status_code == 200:
                print("\n[SUCESSO 200!] Conexao autenticada e pronta!")
                return headers
        except requests.exceptions.Timeout:
            print(f" -> Timeout: O servidor demorou mais de 45s no modo {nome_modo}.")
        except Exception as e:
            print(f" -> Erro de conexao: {e}")

    return None

if __name__ == "__main__":
    validar_chave()