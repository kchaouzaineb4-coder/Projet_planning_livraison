import streamlit as st
import pandas as pd
import plotly.express as px
from backend import DeliveryProcessor

st.set_page_config(page_title="Planning Livraisons", layout="wide")
st.title("Planning de Livraisons - Dashboard 📦")

liv_file = st.file_uploader("📄 Fichier Livraisons", type=["xlsx"])
ydlogist_file = st.file_uploader("📄 Fichier YDLOGIST", type=["xlsx"])
wcliegps_file = st.file_uploader("📄 Fichier WCLIEGPS", type=["xlsx"])

if st.button("🚀 Exécuter le traitement"):
    if liv_file and ydlogist_file and wcliegps_file:

        processor = DeliveryProcessor()

        try:
            df_grouped, df_city = processor.process_delivery_data(
                liv_file, ydlogist_file, wcliegps_file
            )

            st.subheader("📌 Tableau Livraisons par Client & Ville")
            st.dataframe(df_grouped)

            # ✅ Téléchargement
            path_grouped = "Livraison_finale_avec_ville_et_client.xlsx"
            path_city = "Livraison_Besoin_Estafette.xlsx"
            processor.export_results(df_grouped, df_city, path_grouped, path_city)

            st.download_button("⬇ Télécharger Tableau Détail",
                               data=open(path_grouped, "rb"), file_name=path_grouped)

            st.download_button("⬇ Télécharger Tableau Estafette par Ville",
                               data=open(path_city, "rb"), file_name=path_city)

            st.subheader("📊 Statistiques Graphiques par Ville")

            col1, col2 = st.columns(2)
            col3, col4 = st.columns(2)

            # 4 Graphiques demandés ✅✅✅✅

            with col1:
                st.plotly_chart(px.bar(df_city, x="Ville", y="Nombre livraisons",
                                       title="📦 Nombre de livraisons par ville"),
                                use_container_width=True)

            with col2:
                st.plotly_chart(px.bar(df_city, x="Ville", y="Volume total",
                                       title="📦 Volume total livré (m³) par ville"),
                                use_container_width=True)

            with col3:
                st.plotly_chart(px.bar(df_city, x="Ville", y="Poids total",
                                       title="⚖ Poids total livré par ville"),
                                use_container_width=True)

            with col4:
                st.plotly_chart(px.bar(df_city, x="Ville", y="Besoin estafette réel",
                                       title="🚐 Besoin en Estafettes par ville"),
                                use_container_width=True)

        except Exception as e:
            st.error(f"❌ Erreur : {str(e)}")

    else:
        st.warning("⚠ Veuillez uploader les 3 fichiers Excel.")
