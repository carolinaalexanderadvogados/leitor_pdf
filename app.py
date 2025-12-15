import streamlit as st
import pdfplumber
import pandas as pd
import re
from io import BytesIO

# -------------------------------------------------
# CONFIGURAÇÃO DA PÁGINA
# -------------------------------------------------
st.set_page_config(page_title="Extrator Previdenciário", layout="wide")
st.title("📄 Extrator Previdenciário")

modelo = st.selectbox(
    "📂 Modelo do PDF",
    ["Selecione...", "INSS – CTC", "Prefeitura Municipal de Florianópolis"]
)

pdf_file = None
if modelo != "Selecione...":
    pdf_file = st.file_uploader("📤 Enviar PDF", type=["pdf"])

# -------------------------------------------------
# INSS – SALÁRIOS
# -------------------------------------------------
def extrair_salarios_inss(pdf):
    registros = []

    with pdfplumber.open(pdf) as pdf_doc:
        for page in pdf_doc.pages:
            texto = page.extract_text()
            if not texto:
                continue

            for linha in texto.split("\n"):
                for p in linha.split("|"):
                    m = re.search(r'(\d{2}/\d{4})\s+([\d\.]+,\d{2})', p)
                    if m:
                        registros.append({
                            "Mês": m.group(1),
                            "Salário": float(
                                m.group(2).replace(".", "").replace(",", ".")
                            )
                        })

    df = pd.DataFrame(registros)
    if not df.empty:
        df["ordem"] = pd.to_datetime(df["Mês"], format="%m/%Y")
        df = df.sort_values("ordem").drop(columns="ordem")

    return df

# -------------------------------------------------
# INSS – TEMPO DE CONTRIBUIÇÃO (TEXTO)
# -------------------------------------------------
def extrair_tempo_inss(pdf):
    registros = []
    empresa = None
    cargo = None

    with pdfplumber.open(pdf) as pdf_doc:
        for page in pdf_doc.pages:
            texto = page.extract_text()
            if not texto:
                continue

            linhas = texto.split("\n")

            for i, linha in enumerate(linhas):

                # Empresa (mesma linha ou próxima)
                if "Empregador:" in linha:
                    empresa = linha.split("Empregador:")[-1].strip()
                    if empresa == "" and i + 1 < len(linhas):
                        empresa = linhas[i + 1].strip()

                # Cargo
                if linha.strip().startswith("Função:"):
                    cargo = linha.replace("Função:", "").strip()

                # Período
                m = re.search(
                    r'Período Contribuição:\s*(\d{2}/\d{2}/\d{4})\s+a\s+(\d{2}/\d{2}/\d{4})',
                    linha
                )

                if m:
                    registros.append({
                        "Data início": m.group(1),
                        "Data final": m.group(2),
                        "Empresa": empresa,
                        "Cargo": cargo
                    })

    return pd.DataFrame(registros)

# -------------------------------------------------
# PREFEITURA – SALÁRIOS
# -------------------------------------------------
def extrair_prefeitura(pdf):
    registros = []

    with pdfplumber.open(pdf) as pdf_doc:
        for page in pdf_doc.pages:
            texto = page.extract_text()
            if not texto:
                continue

            ano_match = re.search(r'ANO:\s*(\d{4})', texto)
            if not ano_match:
                continue
            ano = ano_match.group(1)

            for linha in texto.split("\n"):
                if linha.strip().startswith("0020 VENCIMENTO ESTATUTARIO"):
                    valores = re.findall(r'[\d\.]+,\d{2}', linha)
                    for i in range(min(12, len(valores))):
                        registros.append({
                            "Mês": f"{str(i+1).zfill(2)}/{ano}",
                            "Salário": float(
                                valores[i].replace(".", "").replace(",", ".")
                            )
                        })

    df = pd.DataFrame(registros)
    if not df.empty:
        df["ordem"] = pd.to_datetime(df["Mês"], format="%m/%Y")
        df = df.sort_values("ordem").drop(columns="ordem")

    return df

# -------------------------------------------------
# PROCESSAMENTO E EXIBIÇÃO
# -------------------------------------------------
if pdf_file:

    if modelo == "INSS – CTC":
        df_sal = extrair_salarios_inss(pdf_file)
        df_tmp = extrair_tempo_inss(pdf_file)

        st.subheader("📊 Salários – INSS")
        st.dataframe(df_sal if not df_sal.empty else pd.DataFrame())

        st.subheader("🕒 Tempo de Contribuição – INSS")
        st.dataframe(df_tmp if not df_tmp.empty else pd.DataFrame())

        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df_sal.to_excel(writer, index=False, sheet_name="Salários")
            df_tmp.to_excel(writer, index=False, sheet_name="Tempo de Contribuição")
        buffer.seek(0)

        st.download_button(
            "⬇️ Baixar Excel – INSS",
            buffer,
            "INSS_completo.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    elif modelo == "Prefeitura Municipal de Florianópolis":
        df = extrair_prefeitura(pdf_file)

        st.subheader("📊 Salários – Prefeitura")
        st.dataframe(df if not df.empty else pd.DataFrame())

        buffer = BytesIO()
        df.to_excel(buffer, index=False)
        buffer.seek(0)

        st.download_button(
            "⬇️ Baixar Excel – Prefeitura",
            buffer,
            "Prefeitura_salarios.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

# -------------------------------------------------
# AVISO FINAL
# -------------------------------------------------
st.markdown("---")
st.warning(
    "⚠️ Este sistema realiza extração automática de PDFs. "
    "Diferenças de layout podem gerar erros. "
    "**Sempre confira os dados com o documento original.**"
)

