import streamlit as st
from backend import DeliveryProcessor
import os

st.set_page_config(page_title="Planning Livraisons", layout="wide")
st.title("Automatisation Planning Livraisons")

# Upload fichiers
liv_file = st.file_uploader("Fichier Livraisons", type=["xlsx"])
ydlogist_file = st.file_uploader("Fichier YDLOGIST", type=["xlsx"])
wcliegps_file = st.file_uploader("Fichier WCLIEGPS", type=["xlsx"])

if st.button("Exécuter le traitement complet"):
    if liv_file and ydlogist_file and wcliegps_file:
        try:
            processor = DeliveryProcessor()
            df_result = processor.process_delivery_data(liv_file, ydlogist_file, wcliegps_file)

            # Exporter fichier
            output_dir = "output"
            os.makedirs(output_dir, exist_ok=True)
            output_path = os.path.join(output_dir, "Planning_Livraisons_Resultats.xlsx")
            processor.export_results(df_result, output_path)

            st.success(f"Traitement terminé ! Fichier exporté : {output_path}")
            st.dataframe(df_result)  # Visualisation des résultats

        except Exception as e:
            st.error(f"Erreur : {str(e)}")
    else:
        st.warning("Merci de charger tous les fichiers requis !")
