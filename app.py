# app.py
import streamlit as st
import pandas as pd
from backend import DeliveryProcessor

st.set_page_config(page_title="Optimisation des Livraisons", layout="wide")

st.title("Optimisation des Livraisons par Estafette")

# 1️⃣ Upload des fichiers
st.subheader("Téléversez les fichiers requis")
liv_file = st.file_uploader("Fichier des livraisons (ex: F1758623552711_LIV.xlsx)", type=["xlsx"])
clients_file = st.file_uploader("Fichier des clients (ex: F1758721675866_WCLIEGPS.xlsx)", type=["xlsx"])
volumes_file = st.file_uploader("Fichier des volumes (ex: F1758008320774_YDLOGIST.xlsx)", type=["xlsx"])

if liv_file and clients_file and volumes_file:
    st.success("✅ Tous les fichiers ont été uploadés.")
    
    try:
        # 2️⃣ Traitement backend
        processor = DeliveryProcessor()
        df_result = processor.process_delivery_data(liv_file, clients_file, volumes_file)
        
        # 3️⃣ Affichage du résultat
        st.subheader("Résultat : Voyages par estafette optimisé")
        st.dataframe(df_result)

        # 4️⃣ Bouton de téléchargement Excel
        excel_data = processor.export_to_excel(df_result)
        st.download_button(
            label="Télécharger le fichier en Excel",
            data=excel_data,
            file_name="Voyages_par_estafette_optimisé_avec_taux_clients_representants.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    except Exception as e:
        st.error(f"❌ Une erreur est survenue : {str(e)}")
else:
    st.info("Veuillez uploader les 3 fichiers pour lancer le traitement.")
