import streamlit as st
import plotly.express as px
from backend import DeliveryProcessor

st.set_page_config(page_title="Planning Livraisons", layout="wide")
st.title("📦 Planning Livraisons & Logistique")

# Upload fichiers
liv_file = st.file_uploader("📄 Fichier Livraisons", type=["xlsx"])
ydlogist_file = st.file_uploader("📄 Fichier YDLOGIST", type=["xlsx"])
wcliegps_file = st.file_uploader("📄 Fichier WCLIEGPS", type=["xlsx"])

if st.button("🚀 Lancer le traitement"):
    if liv_file and ydlogist_file and wcliegps_file:
        try:
            processor = DeliveryProcessor()
            df_liv, df_est = processor.process_delivery_data(liv_file, ydlogist_file, wcliegps_file)

            st.success("✅ Traitement terminé avec succès !")

            st.subheader("📌 Résultats des livraisons")
            st.dataframe(df_liv)

            st.subheader("🚚 Besoin en estafettes par ville")
            st.dataframe(df_est)

            # Graphique combiné avec Plotly
            st.subheader("📊 Analyse logistique par ville")
            fig = px.bar(
                df_est,
                x="Ville",
                y=["Poids total", "Volume total", "Nb livraisons"],
                barmode="group",
                title="Analyse logistique par ville"
            )
            st.plotly_chart(fig)

            # Téléchargement Excel
            output_file = "Résultat_Livraisons_Estafettes.xlsx"
            processor.export_excel(df_liv, df_est, output_file)
            with open(output_file, "rb") as f:
                st.download_button(
                    label="📥 Télécharger les résultats",
                    data=f,
                    file_name=output_file,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

        except Exception as e:
            st.error(f"❌ Erreur : {str(e)}")

    else:
        st.warning("⚠️ Veuillez importer tous les fichiers !")
