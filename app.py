import streamlit as st
import pandas as pd
from backend import DeliveryProcessor
import plotly.express as px

# Configuration page
st.set_page_config(page_title="Planning Livraisons", layout="wide")
st.title("Planning de Livraisons - Streamlit")

# =====================================================
# INITIALISATION DE L'ÉTAT DE SESSION
# =====================================================
if 'data_processed' not in st.session_state:
    st.session_state.data_processed = False
    st.session_state.df_grouped = None
    st.session_state.df_city = None
    st.session_state.df_grouped_zone = None
    st.session_state.df_zone = None # Ajout pour df_zone

# Upload fichiers
liv_file = st.file_uploader("Fichier Livraisons", type=["xlsx"])
ydlogist_file = st.file_uploader("Fichier Volumes", type=["xlsx"])
wcliegps_file = st.file_uploader("Fichier Clients", type=["xlsx"])

# =====================================================
# Logique de Traitement (Se déclenche et stocke les résultats)
# =====================================================
if st.button("Exécuter le traitement complet"):
    if liv_file and ydlogist_file and wcliegps_file:
        processor = DeliveryProcessor()
        try:
            with st.spinner("Traitement des données en cours..."):
                # Traitement complet (récupère df_zone)
                df_grouped, df_city, df_grouped_zone, df_zone = processor.process_delivery_data(
                    liv_file, ydlogist_file, wcliegps_file
                )
            
            # Stockage des résultats dans l'état de session
            st.session_state.df_grouped = df_grouped
            st.session_state.df_city = df_city
            st.session_state.df_grouped_zone = df_grouped_zone
            st.session_state.df_zone = df_zone # Stockage de df_zone
            st.session_state.data_processed = True
            st.success("Traitement terminé avec succès !")

        except Exception as e:
            st.error(f"❌ Erreur lors du traitement : {str(e)}")
            st.session_state.data_processed = False
    else:
        st.warning("Veuillez uploader tous les fichiers nécessaires.")

# =====================================================
# Logique d'Affichage (Se déclenche si les données sont dans l'état de session)
# =====================================================
if st.session_state.data_processed:
    df_grouped = st.session_state.df_grouped
    df_city = st.session_state.df_city
    df_grouped_zone = st.session_state.df_grouped_zone
    df_zone = st.session_state.df_zone # Récupération de df_zone

    # =====================================================
    # Tableau 1 - Livraisons par Client & Ville (SANS ZONE)
    # =====================================================
    df_grouped_display = df_grouped.copy()
    if "Zone" in df_grouped_display.columns:
        df_grouped_display = df_grouped_display.drop(columns=["Zone"])

    st.subheader("Livraisons par Client & Ville")
    st.dataframe(df_grouped_display)

    path_grouped = "Livraison_par_Client_Ville.xlsx"
    # Création du fichier pour le téléchargement
    df_grouped_display.to_excel(path_grouped, index=False) 

    with open(path_grouped, "rb") as f:
        st.download_button(
            label="Télécharger Tableau Client & Ville",
            data=f,
            file_name=path_grouped,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    # =====================================================
    # Tableau 2 - Besoin Estafette par Ville
    # =====================================================
    st.subheader("Besoin Estafette par Ville")
    st.dataframe(df_city)

    path_city = "Besoin_estafette_par_Ville.xlsx"
    # Création du fichier pour le téléchargement
    df_city.to_excel(path_city, index=False)
    with open(path_city, "rb") as f:
        st.download_button(
            label="Télécharger Besoin Estafette par Ville",
            data=f,
            file_name=path_city,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    # =====================================================
    # Graphiques Statistiques par Ville
    # =====================================================
    st.subheader("Statistiques par Ville")

    col1, col2 = st.columns(2)
    with col1:
        st.plotly_chart(px.bar(df_city, x="Ville", y="Poids total",
                               title="Poids total livré par ville"),
                        use_container_width=True)
    with col2:
        st.plotly_chart(px.bar(df_city, x="Ville", y="Volume total",
                               title="Volume total livré par ville (m³)"),
                        use_container_width=True)

    col3, col4 = st.columns(2)
    with col3:
        st.plotly_chart(px.bar(df_city, x="Ville", y="Nombre livraisons",
                               title="Nombre de livraisons par ville"),
                        use_container_width=True)
    with col4:
        st.plotly_chart(px.bar(df_city, x="Ville", y="Besoin estafette réel",
                               title="Besoin en Estafettes par ville"),
                        use_container_width=True)

    # =====================================================
    # Tableau 3 - Client & Ville + Zone
    # =====================================================
    st.subheader("Livraisons par Client & Ville + Zone")
    st.dataframe(df_grouped_zone)

    path_zone = "Livraison_Client_Ville_Zone.xlsx"
    # Création du fichier pour le téléchargement
    df_grouped_zone.to_excel(path_zone, index=False)
    with open(path_zone, "rb") as f:
        st.download_button(
            label="Télécharger Tableau Client & Ville + Zone",
            data=f,
            file_name=path_zone,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
    # =====================================================
    # Tableau 4 - Besoin Estafette par Zone
    # =====================================================
    st.subheader("Besoin Estafette par Zone")
    st.dataframe(df_zone)

    path_zone_summary = "Besoin_estafette_par_Zone.xlsx"
    # Création du fichier pour le téléchargement
    df_zone.to_excel(path_zone_summary, index=False)
    with open(path_zone_summary, "rb") as f:
        st.download_button(
            label="Télécharger Besoin Estafette par Zone",
            data=f,
            file_name=path_zone_summary,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
