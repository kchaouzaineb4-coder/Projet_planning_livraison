import streamlit as st
import pandas as pd
import plotly.express as px

from backend import DeliveryProcessor

st.set_page_config(page_title="Planning Livraisons", layout="wide")
st.title("🚚 Planning de Livraisons - Streamlit")

# --- Partie 1 : Upload des fichiers ---
col1, col2, col3, col4 = st.columns([1, 1, 1, 1])
with col1:
    liv_file = st.file_uploader("Fichier Livraisons", type=["xlsx"])
with col2:
    ydlogist_file = st.file_uploader("Fichier Volumes", type=["xlsx"])
with col3:
    wcliegps_file = st.file_uploader("Fichier Clients", type=["xlsx"])
with col4:
    st.markdown("<br>", unsafe_allow_html=True)
    run_process = st.button("Exécuter le traitement complet", type="primary")

# --- Traitement des fichiers ---
if run_process:
    if not all([liv_file, ydlogist_file, wcliegps_file]):
        st.warning("Veuillez uploader tous les fichiers avant de lancer le traitement.")
    else:
        st.session_state.processor = DeliveryProcessor(liv_file, ydlogist_file, wcliegps_file)
        st.session_state.processor.process_all()
        st.session_state.data_processed = True
        st.success("✅ Traitement terminé !")

# --- Partie 2 : Analyse Livraison Détaillée ---
if st.session_state.get("data_processed", False):
    st.header("📊 Analyse de Livraison Détaillée")

    tabs = st.tabs([
        "Livraisons Client/Ville",
        "Besoin Estafette par Ville",
        "Livraisons Client/Zone",
        "Besoin Estafette par Zone",
        "Graphiques"
    ])

    # Tab 1 : Livraisons Client/Ville
    with tabs[0]:
        st.subheader("Livraisons par Client & Ville")
        df_grouped = st.session_state.processor.df_grouped.drop(columns=["Zone"], errors='ignore')
        st.dataframe(df_grouped, use_container_width=True)

        # Bouton téléchargement
        path = "Livraisons_Client_Ville.xlsx"
        df_grouped.to_excel(path, index=False)
        with open(path, "rb") as f:
            st.download_button("💾 Télécharger tableau Client/Ville", f, file_name=path)

    # Tab 2 : Besoin Estafette par Ville
    with tabs[1]:
        st.subheader("Besoin Estafette par Ville")
        df_city = st.session_state.processor.df_city
        st.dataframe(df_city, use_container_width=True)

        path = "Besoin_Estafette_Ville.xlsx"
        df_city.to_excel(path, index=False)
        with open(path, "rb") as f:
            st.download_button("💾 Télécharger Besoin Estafette Ville", f, file_name=path)

    # Tab 3 : Livraisons Client/Zone
    with tabs[2]:
        st.subheader("Livraisons par Client & Ville + Zone")
        df_grouped_zone = st.session_state.processor.df_grouped_zone
        st.dataframe(df_grouped_zone, use_container_width=True)

        path = "Livraisons_Client_Ville_Zone.xlsx"
        df_grouped_zone.to_excel(path, index=False)
        with open(path, "rb") as f:
            st.download_button("💾 Télécharger tableau Client/Ville/Zone", f, file_name=path)

    # Tab 4 : Besoin Estafette par Zone
    with tabs[3]:
        st.subheader("Besoin Estafette par Zone")
        df_zone = st.session_state.processor.df_zone
        st.dataframe(df_zone, use_container_width=True)

        path = "Besoin_Estafette_Zone.xlsx"
        df_zone.to_excel(path, index=False)
        with open(path, "rb") as f:
            st.download_button("💾 Télécharger Besoin Estafette Zone", f, file_name=path)

    # Tab 5 : Graphiques
    with tabs[4]:
        st.subheader("Statistiques par Ville")
        col1, col2 = st.columns(2)
        with col1:
            st.plotly_chart(px.bar(df_city, x="Ville", y="Poids total", title="Poids total livré par ville"), use_container_width=True)
        with col2:
            st.plotly_chart(px.bar(df_city, x="Ville", y="Volume total", title="Volume total livré par ville (m³)"), use_container_width=True)

        col3, col4 = st.columns(2)
        with col3:
            st.plotly_chart(px.bar(df_city, x="Ville", y="Nombre livraisons", title="Nombre de livraisons par ville"), use_container_width=True)
        with col4:
            st.plotly_chart(px.bar(df_city, x="Ville", y="Besoin estafette réel", title="Besoin en Estafettes par ville"), use_container_width=True)

# --- Partie 3 : Proposition de location de camion ---
if st.session_state.get("data_processed", False):
    st.header("🚚 Proposition de location de camion")
    st.markdown(f"🔸 Si un client dépasse **{st.session_state.processor.SEUIL_POIDS} kg** ou **{st.session_state.processor.SEUIL_VOLUME} m³**, une location est proposée.")

# --- Partie 4 : Voyages par Estafette Optimisé ---
if st.session_state.get("data_processed", False):
    st.subheader("Voyages par Estafette Optimisé (Inclut Camions Loués)")
    df_opt = st.session_state.processor.rental_processor.get_df_result()
    st.dataframe(df_opt.style.format({
        "Poids total chargé": "{:.2f} kg",
        "Volume total chargé": "{:.3f} m³",
        "Taux d'occupation (%)": "{:.2f}%"
    }), use_container_width=True)

    path = "Voyages_Estafette_Optimises.xlsx"
    df_opt.to_excel(path, index=False)
    with open(path, "rb") as f:
        st.download_button("💾 Télécharger Voyages Estafette Optimisés", f, file_name=path)
