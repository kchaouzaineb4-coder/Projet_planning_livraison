import streamlit as st
from backend import DeliveryProcessor

st.set_page_config(page_title="Planning Livraison", layout="wide")
st.title("Planning Livraison - Traitement et Visualisation")

# Upload fichiers
liv_file = st.file_uploader("Choisir le fichier Livraisons", type=["xlsx"])
ydlogist_file = st.file_uploader("Choisir le fichier YDLOGIST", type=["xlsx"])
wcliegps_file = st.file_uploader("Choisir le fichier WCLIEGPS", type=["xlsx"])

if st.button("Exécuter le traitement complet"):
    if liv_file and ydlogist_file and wcliegps_file:
        try:
            processor = DeliveryProcessor()
            results = processor.process_delivery_data(liv_file, ydlogist_file, wcliegps_file)
            st.success("Traitement terminé avec succès !")

            # Export
            output_path = "Voyages_par_estafette.xlsx"
            processor.export_results(results, output_path)
            st.download_button(
                "Télécharger le résultat",
                data=open(output_path, "rb"),
                file_name="Voyages_par_estafette.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

            # Visualisation simple
            st.subheader("Aperçu des résultats")
            st.dataframe(results)

            st.subheader("Nombre de livraisons par ville")
            st.bar_chart(results.groupby("Ville")["No livraison"].count())

            st.subheader("Volume total par ville")
            st.bar_chart(results.groupby("Ville")["Volume total"].sum())

        except Exception as e:
            st.error(f"Erreur: {e}")
    else:
        st.warning("Veuillez uploader tous les fichiers requis.")
