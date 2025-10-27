# app.py
import streamlit as st
import pandas as pd
from backend import process_delivery_files
from io import BytesIO

st.set_page_config(page_title="Planning Livraisons", layout="wide")

st.title("📦 Optimisation des Livraisons par Estafette")

# --- Upload fichiers ---
st.subheader("Uploader les fichiers input :")
liv_file = st.file_uploader("Fichier des livraisons (F1758623552711_LIV.xlsx)", type=["xlsx"])
clients_file = st.file_uploader("Fichier des clients (F1758721675866_WCLIEGPS.xlsx)", type=["xlsx"])
volumes_file = st.file_uploader("Fichier des volumes (F1758008320774_YDLOGIST.xlsx)", type=["xlsx"])

if liv_file and clients_file and volumes_file:
    try:
        # --- Traitement backend ---
        df_result = process_delivery_files(liv_file, clients_file, volumes_file)

        # --- Affichage du résultat ---
        st.subheader("📊 Voyages par estafette optimisé avec taux clients / représentants")
        st.dataframe(df_result)

        # --- Téléchargement Excel ---
        output = BytesIO()
        df_result.to_excel(output, index=False, engine='openpyxl')
        output.seek(0)

        st.download_button(
            label="📥 Télécharger le fichier Excel",
            data=output,
            file_name="Voyages_par_estafette_optimisé.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    except Exception as e:
        st.error(f"❌ Une erreur est survenue : {str(e)}")
