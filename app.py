import streamlit as st
from backend import DeliveryProcessor

st.title("Planning Livraisons")

st.write("Téléchargez les fichiers pour traiter les livraisons:")

liv_file = st.file_uploader("Fichier Livraisons", type=["xlsx"])
ydlogist_file = st.file_uploader("Fichier YDLOGIST", type=["xlsx"])
wcliegps_file = st.file_uploader("Fichier Client/Ville", type=["xlsx"])

if st.button("Exécuter le traitement complet"):
    if liv_file and ydlogist_file and wcliegps_file:
        try:
            processor = DeliveryProcessor()
            df_results = processor.process_delivery_data(
                liv_file,
                ydlogist_file,
                wcliegps_file
            )
            
            st.success("Traitement terminé !")
            st.subheader("Aperçu des résultats")
            st.dataframe(df_results)

            # Exporter le fichier
            output_path = "Voyages_par_livraison.xlsx"
            processor.export_results(df_results, output_path)
            st.download_button(
                label="Télécharger le fichier Excel",
                data=open(output_path, "rb").read(),
                file_name="Voyages_par_livraison.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

        except Exception as e:
            st.error(f"Erreur : {str(e)}")
    else:
        st.warning("Veuillez télécharger tous les fichiers requis.")
