# app.py
import streamlit as st
import pandas as pd
from backend import traitement_backend
from io import BytesIO

st.title("Optimisation des Voyages par Estafette")

# --- Upload des fichiers ---
liv_file = st.file_uploader("Fichier des livraisons", type=["xlsx"])
clients_file = st.file_uploader("Fichier des clients", type=["xlsx"])
volumes_file = st.file_uploader("Fichier des volumes", type=["xlsx"])

if liv_file and clients_file and volumes_file:
    try:
        # Traitement backend
        df_result = traitement_backend(liv_file, clients_file, volumes_file)

        # Affichage dans l'app
        st.subheader("Résultat du traitement")
        st.dataframe(df_result)

        # --- Téléchargement en Excel ---
        towrite = BytesIO()
        df_result.to_excel(towrite, index=False, engine='openpyxl')
        towrite.seek(0)
        st.download_button(
            label="Télécharger le fichier Excel",
            data=towrite,
            file_name="Voyages_par_estafette_optimisé_avec_taux_clients_representants.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    except Exception as e:
        st.error(f"❌ Une erreur est survenue : {str(e)}")
