import streamlit as st
import pandas as pd
from backend import DeliveryProcessor

st.set_page_config(page_title="Planning Livraisons", layout="wide")

st.title("Planning de Livraisons - Streamlit")

# Upload fichiers
liv_file = st.file_uploader("Fichier Livraisons", type=["xlsx"])
ydlogist_file = st.file_uploader("Fichier YDLOGIST", type=["xlsx"])
wcliegps_file = st.file_uploader("Fichier WCLIEGPS", type=["xlsx"])

if st.button("Exécuter le traitement complet"):
    if liv_file and ydlogist_file and wcliegps_file:
        processor = DeliveryProcessor()
        try:
            df_result = processor.process_delivery_data(liv_file, ydlogist_file, wcliegps_file)
            
            # Affichage du tableau
            st.subheader("Aperçu des résultats")
            st.dataframe(df_result)
            
            # Bouton pour télécharger
            output_path = "Voyages_par_estafette.xlsx"
            processor.export_results(df_result, output_path)
            with open(output_path, "rb") as f:
                st.download_button(
                    label="Télécharger les résultats",
                    data=f,
                    file_name="Voyages_par_estafette.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
        except Exception as e:
            st.error(f"Erreur : {str(e)}")
    else:
        st.warning("Veuillez uploader tous les fichiers nécessaires.")
