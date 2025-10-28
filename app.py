import streamlit as st
import pandas as pd
import plotly.express as px
from backend import DeliveryProcessor

# Configuration de la page
st.set_page_config(page_title="Planning Livraisons", layout="wide")
st.title("🚚 Planning de Livraisons - Streamlit")

# Upload Fichiers
st.sidebar.header("📌 Fichiers requis")
liv_file = st.sidebar.file_uploader("Fichier Livraisons", type=["xlsx"])
ydlogist_file = st.sidebar.file_uploader("Fichier YDLOGIST", type=["xlsx"])
wcliegps_file = st.sidebar.file_uploader("Fichier WCLIEGPS", type=["xlsx"])

# Bouton de traitement
if st.sidebar.button("✅ Exécuter le traitement"):
    if liv_file and ydlogist_file and wcliegps_file:

        processor = DeliveryProcessor()
        try:
            df_grouped, df_city = processor.process_delivery_data(
                liv_file, ydlogist_file, wcliegps_file
            )

            st.success("✅ Traitement réussi !")

            # =======================================================================================
            # ✅ Tableaux Résultats
            # =======================================================================================
            st.subheader("📄 Tableau détaillé : Livraisons par Client & Ville")
            st.dataframe(df_grouped, use_container_width=True)

            st.subheader("🏙️ Besoin Estafette par Ville")
            st.dataframe(df_city, use_container_width=True)

            # =======================================================================================
            # ✅ Export des Résultats Excel
            # =======================================================================================
            path_grouped = "Livraison_finale_avec_ville_et_client.xlsx"
            path_city = "Livraison_Besoin_Estafette.xlsx"
            processor.export_results(df_grouped, df_city, path_grouped, path_city)

            st.write("📥 Téléchargements ⬇️")
            colA, colB = st.columns(2)

            with colA:
                with open(path_grouped, "rb") as f1:
                    st.download_button(
                        "📌 Télécharger Détails Livraisons",
                        data=f1,
                        file_name=path_grouped,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )

            with colB:
                with open(path_city, "rb") as f2:
                    st.download_button(
                        "🚐 Télécharger Besoin Estafette par Ville",
                        data=f2,
                        file_name=path_city,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )

            # =======================================================================================
            # ✅ Graphiques Statistiques
            # =======================================================================================
            st.subheader("📊 Statistiques par Ville")

            col1, col2 = st.columns(2)
            with col1:
                fig1 = px.bar(df_city, x="Ville", y="Poids total",
                              title="⚖️ Poids total livré par ville")
                st.plotly_chart(fig1, use_container_width=True)

            with col2:
                fig2 = px.bar(df_city, x="Ville", y="Volume total",
                              title="📦 Volume total par ville (m³)")
                st.plotly_chart(fig2, use_container_width=True)

            col3, col4 = st.columns(2)
            with col3:
                fig3 = px.bar(df_city, x="Ville", y="Nombre livraisons",
                              title="📍 Nombre de livraisons par ville")
                st.plotly_chart(fig3, use_container_width=True)

            with col4:
                fig4 = px.bar(df_city, x="Ville", y="Besoin estafette réel",
                              title="🚐 Nombre d'estafettes nécessaires par ville")
                st.plotly_chart(fig4, use_container_width=True)

        except Exception as e:
            st.error(f"❌ Erreur : {str(e)}")
    else:
        st.warning("⚠️ Veuillez importer tous les fichiers avant de lancer le traitement.")
