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
            df_grouped, df_city = processor.process_delivery_data(liv_file, ydlogist_file, wcliegps_file)
            
            # Affichage du tableau détaillé
            st.subheader("Aperçu des livraisons détaillées")
            st.dataframe(df_grouped)

            # Affichage du besoin en estafette par ville
            st.subheader("Besoin en estafette par ville")
            st.dataframe(df_city)

            # Bouton pour télécharger
            output_path_grouped = "Livraison_finale_avec_ville_et_client.xlsx"
            output_path_city = "Livraison_Besoin_Estafette.xlsx"
            processor.export_results(df_grouped, df_city, output_path_grouped, output_path_city)
            with open(output_path_grouped, "rb") as f:
                st.download_button(
                    label="Télécharger livraisons détaillées",
                    data=f,
                    file_name=output_path_grouped,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            with open(output_path_city, "rb") as f:
                st.download_button(
                    label="Télécharger besoin en estafette",
                    data=f,
                    file_name=output_path_city,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
        except Exception as e:
            st.error(f"Erreur : {str(e)}")
    else:
        st.warning("Veuillez uploader tous les fichiers nécessaires.")
