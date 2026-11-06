import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import json
import os
import re
import math
from datetime import date, datetime, timedelta

try:
    import ifcopenshell
    import ifcopenshell.geom
    HAS_IFC = True
except ImportError:
    HAS_IFC = False

st.set_page_config(page_title="Dashboard PCP & 3D - Pré-fabricados", layout="wide")
st.title("🏗️ Gestão de PCP & Visualizador BIM 3D")
st.markdown("---")

if os.path.exists(r"C:\Plannix_BIM"):
    pasta_bim = r"C:\Plannix_BIM"
else:
    pasta_bim = os.path.dirname(os.path.abspath(__file__))
arquivo_historico = os.path.join(pasta_bim, "historico_diario_pcp.json")
arquivo_dados_3d = os.path.join(pasta_bim, "dados_3d_web.json")

# 1. Procurar os ficheiros JSON e IFC
try:
    arquivos_json = [f for f in os.listdir(pasta_bim) if f.startswith("status_") and f.endswith(".json")]
    arquivos_ifc = [f for f in os.listdir(pasta_bim) if f.lower().endswith(".ifc")]
except FileNotFoundError:
    st.error(f"A pasta {pasta_bim} não foi encontrada.")
    st.stop()

if not arquivos_json:
    st.warning("Nenhum ficheiro de status (.json) encontrado na pasta.")
    st.stop()

# 2. Barra lateral - Seleção da Obra
st.sidebar.header("📌 Seleção da Obra")
obra_selecionada = st.sidebar.selectbox("Ficheiro de Status (Plannix):", sorted(arquivos_json))
caminho_arquivo = os.path.join(pasta_bim, obra_selecionada)

ifc_selecionado = st.sidebar.selectbox("Ficheiro 3D (IFC):", ["Nenhum"] + sorted(arquivos_ifc))

with open(caminho_arquivo, "r", encoding="utf-8") as f:
    dados_obra = json.load(f)

mapa_normalizado = {
    k.strip().upper(): (v.get("StatusFinal", "DESCONHECIDO") if isinstance(v, dict) else str(v))
    for k, v in dados_obra.items()
}

registos = [{"Peça": k, "Status": v} for k, v in mapa_normalizado.items()]
df = pd.DataFrame(registos)

# 3. Cálculos de Quantidades (Discretas e Acumuladas)
total_pecas = len(df)
contagem = df["Status"].value_counts().to_dict()

sem_projeto = contagem.get("SEM_PROJETO", 0)
projeto_liberado = contagem.get("PROJETO_LIBERADO", 0)
produzida = contagem.get("PRODUZIDA", 0)
expedida = contagem.get("EXPEDIDA", 0)
montada = contagem.get("MONTADA", 0)

def pct(val):
    return (val / total_pecas * 100) if total_pecas > 0 else 0.0

acum_projeto = projeto_liberado + produzida + expedida + montada
acum_producao = produzida + expedida + montada
acum_expedicao = expedida + montada
acum_montagem = montada

saldo_producao = total_pecas - acum_producao
saldo_expedicao = total_pecas - acum_expedicao
saldo_montagem = total_pecas - acum_montagem

# 4. Gravação e Leitura Automática do Histórico Diário
hoje = date.today()
hoje_str = hoje.strftime("%Y-%m-%d")

historico_global = {}
if os.path.exists(arquivo_historico):
    try:
        with open(arquivo_historico, "r", encoding="utf-8") as fh:
            historico_global = json.load(fh)
    except Exception:
        historico_global = {}

if obra_selecionada not in historico_global:
    historico_global[obra_selecionada] = {}

historico_global[obra_selecionada][hoje_str] = {
    "total": total_pecas,
    "projeto": acum_projeto,
    "producao": acum_producao,
    "expedicao": acum_expedicao,
    "montagem": acum_montagem
}

with open(arquivo_historico, "w", encoding="utf-8") as fh:
    json.dump(historico_global, fh, indent=2, ensure_ascii=False)

df_hist = pd.DataFrame.from_dict(historico_global[obra_selecionada], orient="index")
df_hist.index.name = "Data"
df_hist = df_hist.reset_index().sort_values("Data")

# 5. Configuração de Cronograma na Barra Lateral
st.sidebar.markdown("---")
st.sidebar.header("📅 Cronograma Meta")

padrao_meta = date(hoje.year + 1, 1, 20) if hoje.month >= 10 else date(hoje.year, 12, 20)

escala_trabalho = st.sidebar.selectbox(
    "Dias de Trabalho na Semana:",
    ["Seg a Sex (5 dias)", "Seg a Sáb (6 dias)", "Seg a Dom (7 dias)"],
    index=0
)
mask_map = {
    "Seg a Sex (5 dias)": "1111100",
    "Seg a Sáb (6 dias)": "1111110",
    "Seg a Dom (7 dias)": "1111111"
}
weekmask = mask_map[escala_trabalho]

meta_prod = st.sidebar.date_input("Meta Término PRODUÇÃO:", value=padrao_meta - timedelta(days=15))
meta_exp = st.sidebar.date_input("Meta Término EXPEDIÇÃO:", value=padrao_meta - timedelta(days=5))
meta_mont = st.sidebar.date_input("Meta Término MONTAGEM (Obra):", value=padrao_meta)

def contar_dias_uteis(d_ini, d_fim, mask):
    if d_fim <= d_ini:
        return 0
    return int(np.busday_count(d_ini.strftime("%Y-%m-%d"), d_fim.strftime("%Y-%m-%d"), weekmask=mask))

def somar_dias_uteis(d_ini, dias, mask):
    if dias <= 0:
        return d_ini
    dt_np = np.busday_offset(d_ini.strftime("%Y-%m-%d"), int(dias), roll='forward', weekmask=mask)
    return datetime.strptime(str(dt_np), "%Y-%m-%d").date()

def calcular_ritmo_historico(df_h, coluna, fallback):
    if len(df_h) < 2:
        return fallback
    df_recente = df_h.tail(7)
    d_ini = datetime.strptime(df_recente.iloc[0]["Data"], "%Y-%m-%d").date()
    d_fim = datetime.strptime(df_recente.iloc[-1]["Data"], "%Y-%m-%d").date()
    dias_ut = max(1, contar_dias_uteis(d_ini, d_fim, weekmask))
    delta_pecas = df_recente.iloc[-1][coluna] - df_recente.iloc[0][coluna]
    return round(max(0.1, delta_pecas / dias_ut), 2) if delta_pecas > 0 else fallback

st.sidebar.markdown("---")
st.sidebar.header("⚡ Ritmo Diário (Peças/Dia)")

metodo_ritmo = st.sidebar.radio(
    "Origem do Ritmo:",
    ["Automático pelo Histórico (7 dias)", "Digitar Ritmo Manual", "Pela Data de Início da Etapa"]
)

if metodo_ritmo == "Automático pelo Histórico (7 dias)":
    r_p_sug = calcular_ritmo_historico(df_hist, "producao", 8.0)
    r_e_sug = calcular_ritmo_historico(df_hist, "expedicao", 5.0)
    r_m_sug = calcular_ritmo_historico(df_hist, "montagem", 5.0)
    ritmo_prod = st.sidebar.number_input("Ritmo Produção (peças/dia):", min_value=0.1, value=float(r_p_sug), step=0.5)
    ritmo_exp = st.sidebar.number_input("Ritmo Expedição (peças/dia):", min_value=0.1, value=float(r_e_sug), step=0.5)
    ritmo_mont = st.sidebar.number_input("Ritmo Montagem (peças/dia):", min_value=0.1, value=float(r_m_sug), step=0.5)
elif metodo_ritmo == "Digitar Ritmo Manual":
    ritmo_prod = st.sidebar.number_input("Ritmo Produção (peças/dia):", min_value=0.1, value=8.0, step=0.5)
    ritmo_exp = st.sidebar.number_input("Ritmo Expedição (peças/dia):", min_value=0.1, value=5.0, step=0.5)
    ritmo_mont = st.sidebar.number_input("Ritmo Montagem (peças/dia):", min_value=0.1, value=5.0, step=0.5)
else:
    ini_prod = st.sidebar.date_input("Início Real Produção:", value=hoje - timedelta(days=30))
    ini_exp = st.sidebar.date_input("Início Real Expedição:", value=hoje - timedelta(days=20))
    ini_mont = st.sidebar.date_input("Início Real Montagem:", value=hoje - timedelta(days=15))

    ritmo_prod = round(max(0.1, acum_producao / max(1, contar_dias_uteis(ini_prod, hoje, weekmask))), 2)
    ritmo_exp = round(max(0.1, acum_expedicao / max(1, contar_dias_uteis(ini_exp, hoje, weekmask))), 2)
    ritmo_mont = round(max(0.1, acum_montagem / max(1, contar_dias_uteis(ini_mont, hoje, weekmask))), 2)

# --- TABS ---
tab1, tab2 = st.tabs(["📊 Dashboard & Cronograma", "🏢 Visualizador 3D"])

# ==========================================
# TAB 1: DASHBOARD, CRONOGRAMA E CURVA S
# ==========================================
with tab1:
    st.subheader("1. Status Atual das Peças (Posição Individual)")
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("📦 Total de Peças", f"{total_pecas}", "100% da Obra")
    c2.metric("⚪ Sem Projeto", f"{sem_projeto}", f"{pct(sem_projeto):.1f}%")
    c3.metric("🔵 Projeto Liberado", f"{projeto_liberado}", f"{pct(projeto_liberado):.1f}% (Fila Fábrica)")
    c4.metric("🟢 Em Estoque (Produzidas)", f"{produzida}", f"{pct(produzida):.1f}% (Aguard. Carga)")
    c5.metric("🟠 Em Trânsito/Canteiro", f"{expedida}", f"{pct(expedida):.1f}% (Aguard. Montagem)")
    c6.metric("🟣 Concluídas (Montadas)", f"{montada}", f"{pct(montada):.1f}% Finalizado")

    st.markdown("<br>", unsafe_allow_html=True)

    st.subheader("2. Avanço Acumulado Real por Etapa do Processo")
    ca1, ca2, ca3, ca4 = st.columns(4)
    with ca1:
        st.markdown(f"**📐 Projetos Liberados:** {acum_projeto} / {total_pecas} ({pct(acum_projeto):.1f}%)")
        st.progress(min(pct(acum_projeto) / 100.0, 1.0))
    with ca2:
        st.markdown(f"**🏭 Produção Acumulada:** {acum_producao} / {total_pecas} ({pct(acum_producao):.1f}%)")
        st.progress(min(pct(acum_producao) / 100.0, 1.0))
    with ca3:
        st.markdown(f"**🚚 Expedição Acumulada:** {acum_expedicao} / {total_pecas} ({pct(acum_expedicao):.1f}%)")
        st.progress(min(pct(acum_expedicao) / 100.0, 1.0))
    with ca4:
        st.markdown(f"**🏗️ Montagem Acumulada:** {acum_montagem} / {total_pecas} ({pct(acum_montagem):.1f}%)")
        st.progress(min(pct(acum_montagem) / 100.0, 1.0))

    st.markdown("---")
    st.subheader("3. Análise de Cronograma, Ritmo e Previsão de Atrasos")

    etapas_config = [
        ("🏭 Produção (Fábrica)", acum_producao, saldo_producao, ritmo_prod, meta_prod),
        ("🚚 Expedição (Logística)", acum_expedicao, saldo_expedicao, ritmo_exp, meta_exp),
        ("🏗️ Montagem (Canteiro)", acum_montagem, saldo_montagem, ritmo_mont, meta_mont),
    ]

    tabela_cronograma = []
    cols_alerta = st.columns(3)

    for idx, (nome_etapa, concluido, saldo, ritmo_atual, data_meta) in enumerate(etapas_config):
        dias_disp = contar_dias_uteis(hoje, data_meta, weekmask)
        dias_necessarios = math.ceil(saldo / ritmo_atual) if saldo > 0 else 0
        data_prevista = somar_dias_uteis(hoje, dias_necessarios, weekmask)

        atraso_dias_uteis = dias_necessarios - dias_disp
        atraso_dias_corridos = (data_prevista - data_meta).days
        ritmo_necessario = round(saldo / dias_disp, 1) if dias_disp > 0 else saldo

        if saldo == 0:
            status_prazo = "✅ CONCLUÍDO"
            cor_caixa = "success"
            msg_detalhe = "Etapa 100% finalizada."
        elif atraso_dias_uteis > 0:
            status_prazo = f"🔴 ATRASADO ({atraso_dias_uteis} dias úteis / {atraso_dias_corridos} corridos)"
            cor_caixa = "error"
            msg_detalhe = (
                f"Faltam **{saldo} peças**. No ritmo de **{ritmo_atual} pçs/dia**, precisamos de **{dias_necessarios} dias úteis** "
                f"(Término em **{data_prevista.strftime('%d/%m/%Y')}**), mas só temos **{dias_disp} dias úteis** até {data_meta.strftime('%d/%m/%Y')}. "
                f"👉 **Ritmo necessário:** `{ritmo_necessario} peças/dia`."
            )
        else:
            folga = abs(atraso_dias_uteis)
            status_prazo = f"🟢 NO PRAZO (Folga de {folga} dias úteis)"
            cor_caixa = "success"
            msg_detalhe = (
                f"Faltam **{saldo} peças**. No ritmo de **{ritmo_atual} pçs/dia**, serão necessários **{dias_necessarios} dias úteis** "
                f"(Término em **{data_prevista.strftime('%d/%m/%Y')}**), cumprindo a meta de {data_meta.strftime('%d/%m/%Y')}. "
                f"👉 **Ritmo mínimo exigido:** `{ritmo_necessario} peças/dia`."
            )

        with cols_alerta[idx]:
            st.markdown(f"#### {nome_etapa}")
            if cor_caixa == "error":
                st.error(f"**{status_prazo}**\n\n{msg_detalhe}")
            else:
                st.success(f"**{status_prazo}**\n\n{msg_detalhe}")

        tabela_cronograma.append({
            "Etapa": nome_etapa,
            "Concluído": f"{concluido} ({pct(concluido):.1f}%)",
            "Saldo Restante": f"{saldo} pçs",
            "Ritmo Atual": f"{ritmo_atual} pçs/dia",
            "Ritmo Necessário": f"{ritmo_necessario} pçs/dia",
            "Dias Úteis Disp.": f"{dias_disp} dias",
            "Dias Úteis Necess.": f"{dias_necessarios} dias",
            "Meta Término": data_meta.strftime("%d/%m/%Y"),
            "Previsão Real": data_prevista.strftime("%d/%m/%Y"),
            "Situação": status_prazo
        })

    st.dataframe(pd.DataFrame(tabela_cronograma), width='stretch', hide_index=True)
    st.markdown("---")

    col_curva, col_pizza, col_tabela = st.columns([1.5, 1.2, 1.3])
    with col_curva:
        st.subheader("📈 Evolução e Projeção (Curva S)")
        fig_curva = go.Figure()
        fig_curva.add_trace(go.Scatter(x=df_hist["Data"], y=df_hist["producao"], mode='lines+markers', name='Produção (Real)', line=dict(color='#70AD47', width=3)))
        fig_curva.add_trace(go.Scatter(x=df_hist["Data"], y=df_hist["expedicao"], mode='lines+markers', name='Expedição (Real)', line=dict(color='#ED7D31', width=3)))
        fig_curva.add_trace(go.Scatter(x=df_hist["Data"], y=df_hist["montagem"], mode='lines+markers', name='Montagem (Real)', line=dict(color='#7030A0', width=3)))

        dt_prev_prod = somar_dias_uteis(hoje, math.ceil(saldo_producao / ritmo_prod) if saldo_producao > 0 else 0, weekmask).strftime("%Y-%m-%d")
        dt_prev_exp = somar_dias_uteis(hoje, math.ceil(saldo_expedicao / ritmo_exp) if saldo_expedicao > 0 else 0, weekmask).strftime("%Y-%m-%d")
        dt_prev_mont = somar_dias_uteis(hoje, math.ceil(saldo_montagem / ritmo_mont) if saldo_montagem > 0 else 0, weekmask).strftime("%Y-%m-%d")

        fig_curva.add_trace(go.Scatter(x=[hoje_str, dt_prev_prod], y=[acum_producao, total_pecas], mode='lines', name='Projeção Prod.', line=dict(color='#70AD47', dash='dot')))
        fig_curva.add_trace(go.Scatter(x=[hoje_str, dt_prev_exp], y=[acum_expedicao, total_pecas], mode='lines', name='Projeção Exp.', line=dict(color='#ED7D31', dash='dot')))
        fig_curva.add_trace(go.Scatter(x=[hoje_str, dt_prev_mont], y=[acum_montagem, total_pecas], mode='lines', name='Projeção Mont.', line=dict(color='#7030A0', dash='dot')))

        fig_curva.update_layout(yaxis_title="Peças Acumuladas", xaxis_title="Data", legend=dict(orientation="h", y=-0.25))
        st.plotly_chart(fig_curva, width='stretch')

    with col_pizza:
        st.subheader("Distribuição Atual")
        cores_map = {
            "SEM_PROJETO": "#A6A6A6",
            "PROJETO_LIBERADO": "#5B9BD5",
            "PRODUZIDA": "#70AD47",
            "EXPEDIDA": "#ED7D31",
            "MONTADA": "#7030A0"
        }
        fig = px.pie(df, names="Status", color="Status", color_discrete_map=cores_map, hole=0.4)
        fig.update_traces(textposition='inside', textinfo='percent+label')
        fig.update_layout(showlegend=False)
        st.plotly_chart(fig, width='stretch')

    with col_tabela:
        st.subheader("Lista de Peças")
        status_filtro = st.selectbox("Filtrar por Status:", ["Todos"] + list(df["Status"].unique()))
        df_mostrar = df[df["Status"] == status_filtro] if status_filtro != "Todos" else df
        st.dataframe(df_mostrar, width='stretch', hide_index=True, height=350)

# ==========================================
# TAB 2: VISUALIZADOR 3D (MAPEAMENTO EXATO POR REVIT ELEMENT ID / TAG / GUID)
# ==========================================
with tab2:
    st.subheader("Visualizador 3D Sincronizado com o Revit e Plannix")

    if not HAS_IFC:
        st.error("⚠️ A biblioteca `ifcopenshell` não está instalada.")
    elif ifc_selecionado == "Nenhum":
        st.info("👈 Selecione um ficheiro IFC na barra lateral.")
    else:
        caminho_ifc = os.path.join(pasta_bim, ifc_selecionado)

        mapa_3d_web = {}
        if os.path.exists(arquivo_dados_3d):
            try:
                with open(arquivo_dados_3d, "r", encoding="utf-8") as f3d:
                    mapa_3d_web = json.load(f3d)
            except Exception:
                mapa_3d_web = {}

        cores_hex = {
            "SEM_PROJETO": "#A6A6A6",
            "PROJETO_LIBERADO": "#5B9BD5",
            "PRODUZIDA": "#70AD47",
            "EXPEDIDA": "#ED7D31",
            "MONTADA": "#7030A0",
            "NÃO MAPEADO": "#D9D9D9"
        }

        def extrair_candidatos_id_revit(elem):
            """
            No IFC exportado pelo Revit:
            - elem.Tag guarda o ElementId do Revit (ex: '3354872')
            - elem.Name termina com ':3354872' (ex: 'FAMILIA:TIPO:3354872')
            - elem.GlobalId guarda o IfcGuid
            """
            candidatos = []
            tag = getattr(elem, "Tag", None)
            if tag:
                candidatos.append(str(tag).strip())

            nome = getattr(elem, "Name", None)
            if nome and ":" in str(nome):
                sufixo = str(nome).split(":")[-1].strip()
                if sufixo.isdigit():
                    candidatos.append(sufixo)

            # Extrai qualquer numero de 5 a 9 digitos presente no Name/Tag
            texto_base = f"{nome or ''} {tag or ''}"
            for num in re.findall(r"\b\d{5,9}\b", texto_base):
                if num not in candidatos:
                    candidatos.append(num)

            return candidatos

        # Remove o @st.cache_data antigo ou usa o mtime do JSON para nunca ficar preso em cache velho!
        mtime_json = os.path.getmtime(arquivo_dados_3d) if os.path.exists(arquivo_dados_3d) else 0

        @st.cache_data(show_spinner=False)
        def carregar_geometria_revit_id(caminho, mapa_status_web, mapa_plannix_direto, _cache_buster):
            ifc_file = ifcopenshell.open(caminho)
            settings = ifcopenshell.geom.settings()
            settings.set(settings.USE_WORLD_COORDS, True)

            # Índice auxiliar por IfcGuid caso exista
            mapa_por_guid = {
                v.get("IfcGuid"): v.get("Status")
                for k, v in mapa_status_web.items()
                if isinstance(v, dict) and v.get("IfcGuid")
            }

            elementos = ifc_file.by_type("IfcBuildingElement")
            grupos = {st_key: {"x": [], "y": [], "z": [], "i": [], "j": [], "k": [], "pecas": 0} for st_key in cores_hex.keys()}
            
            mapeados_sucesso = 0
            exemplos_tags_ifc = []

            for elem in elementos:
                if elem.is_a("IfcOpeningElement") or elem.is_a("IfcSpace"):
                    continue

                candidatos_id = extrair_candidatos_id_revit(elem)
                if len(exemplos_tags_ifc) < 5 and candidatos_id:
                    exemplos_tags_ifc.append(candidatos_id[0])

                status = "NÃO MAPEADO"

                # 1. Procura pelo ElementId do Revit (extraido de elem.Tag ou elem.Name)
                for cid in candidatos_id:
                    if cid in mapa_status_web:
                        val = mapa_status_web[cid]
                        codigo_peca = val.get("Codigo", "") if isinstance(val, dict) else ""
                        # Se a peca existir no JSON da obra selecionada na barra lateral, usa o status atual dela
                        if codigo_peca and codigo_peca in mapa_plannix_direto:
                            status = mapa_plannix_direto[codigo_peca]
                        else:
                            status = val.get("Status", "NÃO MAPEADO") if isinstance(val, dict) else str(val)
                        mapeados_sucesso += 1
                        break

                # 2. Fallback pelo IfcGuid
                if status == "NÃO MAPEADO":
                    guid = getattr(elem, "GlobalId", None)
                    if guid and str(guid) in mapa_por_guid:
                        status = mapa_por_guid[str(guid)]
                        mapeados_sucesso += 1

                if status not in grupos:
                    status = "NÃO MAPEADO"

                try:
                    shape = ifcopenshell.geom.create_shape(settings, elem)
                    verts = shape.geometry.verts
                    faces = shape.geometry.faces
                    if not verts or not faces:
                        continue

                    g = grupos[status]
                    offset = len(g["x"])

                    g["x"].extend(verts[0::3])
                    g["y"].extend(verts[1::3])
                    g["z"].extend(verts[2::3])

                    g["i"].extend([f + offset for f in faces[0::3]])
                    g["j"].extend([f + offset for f in faces[1::3]])
                    g["k"].extend([f + offset for f in faces[2::3]])
                    g["pecas"] += 1
                except Exception:
                    continue

            return grupos, mapeados_sucesso, exemplos_tags_ifc

        with st.spinner("A cruzar ElementIds do Revit (Tag/Name) com o modelo IFC..."):
            grupos_3d, qtd_mapeados, tags_ifc = carregar_geometria_revit_id(
                caminho_ifc, mapa_3d_web, mapa_normalizado, mtime_json
            )

            st.info(
                f"💡 IDs do Revit no `dados_3d_web.json`: **{len(mapa_3d_web)}** | "
                f"Peças pintadas no IFC: **{qtd_mapeados}** | "
                f"Amostra de Tags lidas do IFC: `{tags_ifc}`"
            )

            status_disponiveis = [s for s, d in grupos_3d.items() if d["pecas"] > 0]
            selecao_status_3d = st.multiselect(
                "Filtrar Status Visíveis no 3D:",
                options=status_disponiveis,
                default=status_disponiveis
            )

            malhas = []
            total_renderizado = 0
            for st_nome in selecao_status_3d:
                d = grupos_3d[st_nome]
                total_renderizado += d["pecas"]
                malhas.append(go.Mesh3d(
                    x=d["x"], y=d["y"], z=d["z"],
                    i=d["i"], j=d["j"], k=d["k"],
                    color=cores_hex[st_nome],
                    opacity=1.0 if st_nome != "NÃO MAPEADO" else 0.30,
                    name=f"{st_nome} ({d['pecas']} pçs)",
                    showlegend=True,
                    flatshading=True,
                    lighting=dict(ambient=0.6, diffuse=0.8, roughness=0.5)
                ))

            if malhas:
                fig3d = go.Figure(data=malhas)
                fig3d.update_layout(
                    scene=dict(aspectmode='data', xaxis=dict(visible=False), yaxis=dict(visible=False), zaxis=dict(visible=False)),
                    margin=dict(l=0, r=0, b=0, t=0), height=720, legend=dict(orientation="h", y=1.02, x=0)
                )
                st.plotly_chart(fig3d, width='stretch')
            else:
                st.warning("Nenhuma geometria encontrada.")