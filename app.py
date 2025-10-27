import streamlit as st
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
            df_result, df_estafettes = processor.process_delivery_data(liv_file, ydlogist_file, wcliegps_file)
            
            # Affichage du tableau principal
            st.subheader("Aperçu des livraisons")
            st.dataframe(df_result)
            
            # Affichage du besoin en estafettes par ville
            st.subheader("Besoin en estafettes par ville")
            st.dataframe(df_estafettes)
            
            # Boutons pour télécharger
            output_path_liv = "Livraison_finale.xlsx"
            processor.export_results(df_result, output_path_liv)
            with open(output_path_liv, "rb") as f:
                st.download_button(
                    label="Télécharger les résultats livraisons",
                    data=f,
                    file_name=output_path_liv,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            
            output_path_est = "Besoin_Estafette.xlsx"
            processor.export_results(df_estafettes, output_path_est)
            with open(output_path_est, "rb") as f:
                st.download_button(
                    label="Télécharger le besoin en estafettes",
                    data=f,
                    file_name=output_path_est,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

        except Exception as e:
            st.error(f"Erreur : {str(e)}")
    else:
        st.warning("Veuillez uploader tous les fichiers nécessaires.")
