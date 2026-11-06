import json
import pandas as pd
from collections import Counter

def processar_status_obra():
    # 1. Carrega o JSON bruto salvo da API
    print("Carregando 'informacao_global_pecas.json'...")
    with open("informacao_global_pecas.json", "r", encoding="utf-8") as f:
        pecas = json.load(f)

    dados_processados = []

    # 2. Varre cada peça aplicando a precedência das 5 cores
    for p in pecas:
        nome_obra = p.get("nomeObra", "OBRA_DESCONHECIDA")
        codigo_peca = p.get("nomePeca", "SEM_CODIGO")
        
        # Lógica de precedência (da etapa mais avançada para a inicial)
        # Roxo: Montada
        if str(p.get("montada")) == "1" or p.get("dataMontada"):
            status_final = "MONTADA"
            cor = "Roxo"
            hex_cor = "#800080"
        # Laranja: Expedida / Logística
        elif p.get("status_Logistica") == "EXPEDIDA" or p.get("data_Expedicao"):
            status_final = "EXPEDIDA"
            cor = "Laranja"
            hex_cor = "#FF8C00"
        # Verde: Produzida (Concretagem / Acabamento concluídos)
        elif p.get("status_Concretagem") == "Liberado" or p.get("data_Concretagem"):
            status_final = "PRODUZIDA"
            cor = "Verde"
            hex_cor = "#228B22"
        # Azul: Projeto Liberado
        elif p.get("status_Projeto") == "Liberado" or p.get("data_Projeto"):
            status_final = "PROJETO_LIBERADO"
            cor = "Azul"
            hex_cor = "#0066CC"
        # Cinza: Sem liberação de projeto / Inicial
        else:
            status_final = "SEM_PROJETO"
            cor = "Cinza"
            hex_cor = "#969696"

        dados_processados.append({
            "Obra": nome_obra,
            "Peca": codigo_peca,
            "Produto": p.get("produto"),
            "Grupo": p.get("grupo"),
            "PesoTeorico": p.get("pesoTeorico", 0.0),
            "StatusFinal": status_final,
            "Cor": cor,
            "Hex": hex_cor
        })

    df = pd.DataFrame(dados_processados)

    # 3. Exibe um resumo consolidado por Obra e Status
    print("\n" + "="*50)
    print(" RESUMO DE AVANÇO POR OBRA (QUANTIDADE DE PEÇAS)")
    print("="*50)
    
    resumo = df.groupby(["Obra", "Cor"]).size().unstack(fill_value=0)
    print(resumo)

    # 4. Salva um arquivo JSON otimizado por obra para o Visualizador Web e Revit
    for obra, grupo in df.groupby("Obra"):
        nome_arquivo_obra = f"status_{obra.replace(' ', '_').lower()}.json"
        
        # Garante índice único caso haja peças com o mesmo código na mesma obra
        grupo_limpo = grupo.drop_duplicates(subset=["Peca"])
        mapa_pecas = grupo_limpo.set_index("Peca")[["StatusFinal", "Cor", "Hex", "PesoTeorico"]].to_dict(orient="index")
        
        with open(nome_arquivo_obra, "w", encoding="utf-8") as out:
            json.dump(mapa_pecas, out, indent=2, ensure_ascii=False)
        print(f"Arquivo gerado para o Revit/Web: {nome_arquivo_obra}")

if __name__ == "__main__":
    processar_status_obra()