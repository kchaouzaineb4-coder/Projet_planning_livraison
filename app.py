import streamlit as st
from backend import DeliveryProcessor

st.title("Planning des livraisons")

# Upload des fichiers
liv_file = st.file_uploader("Fichier livraisons", type=["xlsx"])
ydlogist_file = st.file_uploader("Fichier YDLOGIST", type=["xlsx"])
wcliegps_file = st.file_uploader("Fichier WCLIEGPS", type=["xlsx"])

# Bouton pour lancer le traitement
if st.button("Exécuter le traitement"):
    if liv_file and ydlogist_file and wcliegps_file:
        try:
            processor = DeliveryProcessor()
            results = processor.process_delivery_data(
                liv_file,
                ydlogist_file,
                wcliegps_file
            )

            # Affichage des résultats
            st.subheader("Aperçu des résultats")
            st.dataframe(results.head(20))  # Affiche les 20 premières lignes

            # Export Excel
            output_path = "Voyages_par_estafette.xlsx"
            processor.export_results(results, output_path)
            st.success(f"Traitement terminé. Fichier exporté: {output_path}")

        except Exception as e:
            st.error(f"Erreur: {str(e)}")
    else:
        st.warning("Veuillez uploader les trois fichiers nécessaires.")
