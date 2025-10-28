import streamlit as st
import pandas as pd
from backend import DeliveryProcessor
import plotly.express as px

# Configuration de la page
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
            df_grouped, df_grouped_zone, df_city = processor.process_delivery_data(liv_file, ydlogist_file, wcliegps_file)

            # --------------------------
            # Tableau détaillé par Client & Ville
            # --------------------------
            st.subheader("Résultat : Livraisons par Client & Ville")
            st.dataframe(df_grouped)

            # --------------------------
            # Tableau détaillé par Client & Ville + Zone
            # --------------------------
            st.subheader("Résultat : Livraisons par Client & Ville + Zone")
            st.dataframe(df_grouped_zone)

            # --------------------------
            # Tableau Besoin estafette par Ville
            # --------------------------
            st.subheader("Besoin estafette par Ville")
            st.dataframe(df_city)

            # --------------------------
            # Boutons de téléchargement
            # --------------------------
            processor.export_results(
                df_grouped,
                df_grouped_zone,
                df_city,
                "Livraison_finale_avec_ville_et_client.xlsx",
                "Livraison_avec_zone.xlsx",
                "Livraison_Besoin_Estafette.xlsx"
            )

            with open("Livraison_finale_avec_ville_et_client.xlsx", "rb") as f1:
                st.download_button("Télécharger Tableau Détails Livraisons",
                                   f1, "Livraison_finale_avec_ville_et_client.xlsx",
                                   "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

            with open("Livraison_avec_zone.xlsx", "rb") as f2:
                st.download_button("Télécharger Tableau Détails Livraisons + Zone",
                                   f2, "Livraison_avec_zone.xlsx",
                                   "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

            with open("Livraison_Besoin_Estafette.xlsx", "rb") as f3:
                st.download_button("Télécharger Besoin Estafette par Ville",
                                   f3, "Livraison_Besoin_Estafette.xlsx",
                                   "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

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
            st.error(f"Erreur : {str(e)}")

    else:
        st.warning("Veuillez uploader tous les fichiers nécessaires.")
