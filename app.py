import streamlit as st
import pandas as pd
from backend import DeliveryProcessor
import os
import plotly.express as px

# Configuration page
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
            # Traitement complet
            df_grouped, df_city, df_grouped_zone = processor.process_delivery_data(
                liv_file, ydlogist_file, wcliegps_file
            )

            # --------------------------
            # 1️⃣ Tableau original par Client & Ville (sans Zone)
            # --------------------------
            st.subheader("Tableau original : Livraisons par Client & Ville")
            st.dataframe(df_grouped)

            # --------------------------
            # 2️⃣ Besoin estafette par Ville
            # --------------------------
            st.subheader("Besoin estafette par Ville")
            st.dataframe(df_city)

            # --------------------------
            # 3️⃣ Tableau Client & Ville + Zone
            # --------------------------
            st.subheader("Tableau : Livraisons par Client & Ville + Zone")
            st.dataframe(df_grouped_zone)

            # --------------------------
            # Boutons de téléchargement
            # --------------------------
            path_grouped = "Livraison_par_Client_Ville.xlsx"
            path_city = "Besoin_estafette_par_Ville.xlsx"
            path_zone = "Livraison_Client_Ville_Zone.xlsx"

            processor.export_results(df_grouped, df_city, df_grouped_zone, path_grouped, path_city, path_zone)

            with open(path_grouped, "rb") as f:
                st.download_button(
                    label="Télécharger Tableau Client & Ville",
                    data=f,
                    file_name=path_grouped,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

            with open(path_city, "rb") as f:
                st.download_button(
                    label="Télécharger Besoin Estafette par Ville",
                    data=f,
                    file_name=path_city,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

            with open(path_zone, "rb") as f:
                st.download_button(
                    label="Télécharger Tableau Client & Ville + Zone",
                    data=f,
                    file_name=path_zone,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

            # --------------------------
            # Graphiques statistiques par ville
            # --------------------------
            st.subheader("Statistiques par Ville")
            col1, col2 = st.columns(2)
            with col1:
                fig1 = px.bar(df_city, x="Ville", y="Poids total", title="Poids total livré par ville")
                st.plotly_chart(fig1, use_container_width=True)
            with col2:
                fig2 = px.bar(df_city, x="Ville", y="Volume total", title="Volume total par ville (m³)")
                st.plotly_chart(fig2, use_container_width=True)

            col3, col4 = st.columns(2)
            with col3:
                fig3 = px.bar(df_city, x="Ville", y="Nombre livraisons", title="Nombre de livraisons par ville")
                st.plotly_chart(fig3, use_container_width=True)
            with col4:
                fig4 = px.bar(df_city, x="Ville", y="Besoin estafette réel", title="Nombre d'estafettes nécessaires par ville")
                st.plotly_chart(fig4, use_container_width=True)

        except Exception as e:
            st.error(f"❌ Erreur lors du traitement : {str(e)}")
    else:
        st.warning("Veuillez uploader tous les fichiers nécessaires.")
