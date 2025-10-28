import streamlit as st
import pandas as pd
from backend import DeliveryProcessor
import plotly.express as px

st.set_page_config(page_title="Planning Livraisons", layout="wide")
st.title("🚚 Planning des Livraisons – Optimisé par Zones")

# Initialisation session_state
for key in ["data_processed", "df_grouped", "df_city", "df_grouped_zone", "df_zone", "df_estafettes"]:
    if key not in st.session_state:
        st.session_state[key] = None

# Upload fichiers
liv_file = st.file_uploader("📦 Fichier Livraisons", type=["xlsx"])
ydlogist_file = st.file_uploader("📏 Fichier Volumes", type=["xlsx"])
wcliegps_file = st.file_uploader("🏢 Fichier Clients", type=["xlsx"])

# Traitement
if st.button("🚀 Exécuter le traitement complet"):
    if liv_file and ydlogist_file and wcliegps_file:
        processor = DeliveryProcessor()
        with st.spinner("⏳ Traitement des données en cours..."):
            df_grouped, df_city, df_grouped_zone, df_zone, df_estafettes = processor.process_delivery_data(
                liv_file, ydlogist_file, wcliegps_file
            )
        st.session_state.update({
            "data_processed": True,
            "df_grouped": df_grouped,
            "df_city": df_city,
            "df_grouped_zone": df_grouped_zone,
            "df_zone": df_zone,
            "df_estafettes": df_estafettes
        })
        st.success("✅ Traitement terminé !")
    else:
        st.warning("⚠️ Veuillez importer tous les fichiers nécessaires.")

# Affichages
if st.session_state["data_processed"]:

    df_grouped = st.session_state.df_grouped
    df_city = st.session_state.df_city
    df_grouped_zone = st.session_state.df_grouped_zone
    df_zone = st.session_state.df_zone
    df_estafettes = st.session_state.df_estafettes

    # 1️⃣ Client & Ville (sans Zone)
    st.subheader("📍 Livraisons par Client & Ville")
    df1 = df_grouped.drop(columns=["Zone"], errors="ignore")
    st.dataframe(df1)
    df1.to_excel("Client_Ville.xlsx", index=False)
    st.download_button("⬇️ Télécharger", open("Client_Ville.xlsx","rb"), file_name="Client_Ville.xlsx")

    # 2️⃣ Besoin Estafette par Ville
    st.subheader("🚐 Besoin Estafette par Ville")
    st.dataframe(df_city)
    df_city.to_excel("Besoin_Ville.xlsx", index=False)
    st.download_button("⬇️ Télécharger", open("Besoin_Ville.xlsx","rb"), file_name="Besoin_Ville.xlsx")

    # Graphiques
    st.subheader("📊 Statistiques par Ville")
    st.plotly_chart(px.bar(df_city, x="Ville", y="Besoin estafette réel",
                           title="Besoin total d’Estafettes par Ville"),
                    use_container_width=True)

    # 3️⃣ Client & Ville + Zone
    st.subheader("🗺️ Livraisons par Client & Ville + Zone")
    st.dataframe(df_grouped_zone)
    df_grouped_zone.to_excel("Client_Ville_Zone.xlsx", index=False)
    st.download_button("⬇️ Télécharger", open("Client_Ville_Zone.xlsx","rb"),
                       file_name="Client_Ville_Zone.xlsx")

    # 4️⃣ Besoin Estafette par Zone
    st.subheader("📦 Besoin Estafette par Zone")
    st.dataframe(df_zone)
    df_zone.to_excel("Besoin_Zone.xlsx", index=False)
    st.download_button("⬇️ Télécharger", open("Besoin_Zone.xlsx","rb"),
                       file_name="Besoin_Zone.xlsx")

    # 🆕 5️⃣ Voyages Estafette Optimisés par Zone
    st.header("✅ Voyages Estafette Optimisés par Zone")
    st.dataframe(df_estafettes)

    df_estafettes.to_excel("Voyages_Optimises_Zone.xlsx", index=False)
    st.download_button(
        "⬇️ Télécharger Voyages Optimisés",
        open("Voyages_Optimises_Zone.xlsx","rb"),
        file_name="Voyages_Optimises_Zone.xlsx"
    )
