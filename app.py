import streamlit as st
import pandas as pd
from backend import DeliveryProcessor, TruckRentalProcessor, SEUIL_POIDS, SEUIL_VOLUME
import plotly.express as px
import io

# Configuration page
st.set_page_config(page_title="Planning Livraisons", layout="wide")
st.title("🚚 Planning de Livraisons")

# =====================================================
# INITIALISATION DE L'ÉTAT DE SESSION
# =====================================================
if 'data_processed' not in st.session_state:
    st.session_state.data_processed = False
    st.session_state.df_grouped = None
    st.session_state.df_city = None
    st.session_state.df_grouped_zone = None
    st.session_state.df_zone = None
    st.session_state.df_optimized_estafettes = None
    st.session_state.rental_processor = None
    st.session_state.propositions = None
    st.session_state.selected_client = None
    st.session_state.message = ""

# =====================================================
# Fonctions de Callback pour la Location
# =====================================================
def update_propositions_view():
    if st.session_state.rental_processor:
        st.session_state.propositions = st.session_state.rental_processor.detecter_propositions()
        if st.session_state.selected_client and st.session_state.selected_client not in st.session_state.propositions['Client'].tolist():
             st.session_state.selected_client = None
    else:
        st.session_state.propositions = pd.DataFrame()

def handle_location_action(accepter):
    if st.session_state.rental_processor and st.session_state.selected_client:
        ok, msg, _ = st.session_state.rental_processor.appliquer_location(
            st.session_state.selected_client, accepter=accepter
        )
        st.session_state.message = msg
        update_propositions_view()
    elif not st.session_state.selected_client:
        st.session_state.message = "⚠️ Veuillez sélectionner un client à traiter."
    else:
        st.session_state.message = "⚠️ Le processeur de location n'est pas initialisé."

def accept_location_callback(): handle_location_action(True)
def refuse_location_callback(): handle_location_action(False)

# =====================================================
# Upload et Traitement
# =====================================================
st.header("1️⃣ Import des fichiers d'entrée")
col_file_1, col_file_2, col_file_3, col_button = st.columns([1, 1, 1, 1])
with col_file_1:
    liv_file = st.file_uploader("Fichier Livraisons (xlsx)", type=["xlsx"], key="liv_file")
with col_file_2:
    ydlogist_file = st.file_uploader("Fichier Volumes (ydlogist) (xlsx)", type=["xlsx"], key="yd_file")
with col_file_3:
    wcliegps_file = st.file_uploader("Fichier Clients (wcliegps) (xlsx)", type=["xlsx"], key="clients_file")
with col_button:
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("Exécuter le traitement complet", type="primary"):
        if liv_file and ydlogist_file and wcliegps_file:
            processor = DeliveryProcessor()
            try:
                with st.spinner("Traitement des données en cours..."):
                    df_grouped, df_city, df_grouped_zone, df_zone, df_optimized_estafettes = processor.process_delivery_data(
                        liv_file, ydlogist_file, wcliegps_file
                    )

                st.session_state.df_optimized_estafettes = df_optimized_estafettes
                st.session_state.df_grouped = df_grouped
                st.session_state.df_city = df_city
                st.session_state.df_grouped_zone = df_grouped_zone
                st.session_state.df_zone = df_zone

                st.session_state.rental_processor = TruckRentalProcessor(df_optimized_estafettes)
                update_propositions_view()

                st.session_state.data_processed = True
                st.session_state.message = "✅ Traitement terminé avec succès !"
                st.rerun()

            except Exception as e:
                st.error(f"❌ Erreur lors du traitement : {str(e)}")

        else:
            st.warning("Veuillez uploader tous les fichiers nécessaires.")

# =====================================================
# AFFICHAGE DES RESULTATS
# =====================================================
if st.session_state.data_processed:

    if st.session_state.message:
        if "✅" in st.session_state.message:
            st.success(st.session_state.message)
        elif "⚠️" in st.session_state.message:
            st.warning(st.session_state.message)
        else:
            st.info(st.session_state.message)

    # ----------------------------
    # Analyse Livraison Détaillée
    # ----------------------------
    st.header("2️⃣ Analyse de Livraison Détaillée")

    tab_grouped, tab_city, tab_zone_group, tab_zone_summary, tab_charts = st.tabs([
        "Livraisons Client/Ville",
        "Besoin Estafette par Ville",
        "Livraisons Client/Zone",
        "Besoin Estafette par Zone",
        "Graphiques"
    ])

    with tab_grouped:
        st.subheader("Livraisons par Client & Ville")
        df_display = st.session_state.df_grouped.drop(columns=["Zone"], errors='ignore')
        st.dataframe(df_display, use_container_width=True)

    with tab_city:
        st.subheader("Besoin Estafette par Ville")
        st.dataframe(st.session_state.df_city, use_container_width=True)

    with tab_zone_group:
        st.subheader("Livraisons par Client & Ville + Zone")
        st.dataframe(st.session_state.df_grouped_zone, use_container_width=True)

    with tab_zone_summary:
        st.subheader("Besoin Estafette par Zone")
        st.dataframe(st.session_state.df_zone, use_container_width=True)

    # Graphiques
    with tab_charts:
        st.subheader("Statistiques par Ville")
        col1, col2 = st.columns(2)
        with col1: st.plotly_chart(px.bar(st.session_state.df_city, x="Ville", y="Poids total"))
        with col2: st.plotly_chart(px.bar(st.session_state.df_city, x="Ville", y="Volume total"))

    st.divider()

    # ----------------------------
    # Proposition de location
    # ----------------------------
    st.header("3️⃣ Proposition de location de camion")
    st.markdown(f"🔸 Si un client dépasse **{SEUIL_POIDS} kg** ou **{SEUIL_VOLUME} m³**, une location est proposée.")

    propositions = st.session_state.propositions
    if propositions is not None and not propositions.empty:
        st.dataframe(propositions, use_container_width=True)
    else:
        st.success("🎉 Aucune proposition de location de camion détectée.")

    st.divider()

    # ----------------------------
    # Voyages par Estafette Optimisé
    # ----------------------------
    st.header("4️⃣ Voyages par Estafette Optimisé (Inclut Camions Loués)")

    df_optimized = st.session_state.rental_processor.get_df_result()

    if df_optimized is not None and not df_optimized.empty:

        # ✅ Nouvelle coloration claire
        def highlight_voyage(row):
            val = str(row.get("Voyage", "")).strip()
            if val.startswith("C"):  # Camion loué
                return ['background-color: #ff4d4d; color: white; font-weight: bold;'] * len(row)
            else:  # Estafette
                return ['background-color: #cce6ff; color: black;'] * len(row)

        styled = df_optimized.style.apply(highlight_voyage, axis=1)
        st.dataframe(styled, use_container_width=True)

    else:
        st.info("Aucun voyage optimisé disponible.")

else:
    st.info("Uploadez les fichiers puis lancez le traitement ✅")
