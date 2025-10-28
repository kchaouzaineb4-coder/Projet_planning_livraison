import streamlit as st
import pandas as pd
import plotly.express as px
from backend import DeliveryProcessor

st.set_page_config(page_title="Planning Livraisons", layout="wide")
st.title("Planning de Livraisons - Streamlit")

liv_file = st.file_uploader("Fichier Livraisons", type=["xlsx"])
ydlogist_file = st.file_uploader("Fichier YDLOGIST", type=["xlsx"])
wcliegps_file = st.file_uploader("Fichier WCLIEGPS", type=["xlsx"])

if st.button("Exécuter le traitement complet"):

    if liv_file and ydlogist_file and wcliegps_file:

        processor = DeliveryProcessor()

        try:
            df_grouped, df_city = processor.process_delivery_data(
                liv_file, ydlogist_file, wcliegps_file
            )

            st.subheader("📌 Résultat : Livraisons par Client & Ville")
            st.dataframe(df_grouped)

            # Export Excel
            processor.export_results(df_grouped, df_city,
                                     "Livraison_finale_avec_ville_et_client.xlsx",
                                     "Livraison_Besoin_Estafette.xlsx")

            # ✅ Graphiques
            st.subheader("📊 Statistiques par Ville")

            col1, col2 = st.columns(2)

            with col1:
                fig1 = px.bar(df_city, x="Ville", y="Nombre livraisons",
                              title="Nombre de livraisons par ville")
                st.plotly_chart(fig1, use_container_width=True)

            with col2:
                fig2 = px.bar(df_city, x="Ville", y="Volume total",
                              title="Volume total (m³) par ville")
                st.plotly_chart(fig2, use_container_width=True)

        except Exception as e:
            st.error(f"❌ Erreur : {str(e)}")

    else:
        st.warning("⚠ Veuillez uploader tous les fichiers nécessaires.")
