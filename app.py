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
    st.session_state.rental_processor = None # 🆕 Objet de traitement de location
    st.session_state.propositions = None # 🆕 Dataframe de propositions
    st.session_state.selected_client = None # 🆕 Client sélectionné
    st.session_state.message = "" # 🆕 Message de résultat d'opération

# =====================================================
# Fonctions de Callback pour la Location
# =====================================================

def update_propositions_view():
    """Met à jour le DataFrame de propositions après une action."""
    if st.session_state.rental_processor:
        st.session_state.propositions = st.session_state.rental_processor.detecter_propositions()
        # Réinitialiser la sélection si le client n'est plus dans les propositions ouvertes
        if st.session_state.selected_client and st.session_state.selected_client not in st.session_state.propositions['Client'].tolist():
             st.session_state.selected_client = None
    else:
        st.session_state.propositions = pd.DataFrame()

def handle_location_action(accepter):
    """Gère l'acceptation ou le refus de la proposition de location."""
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

def accept_location_callback():
    handle_location_action(True)

def refuse_location_callback():
    handle_location_action(False)

# =====================================================
# Logique de Traitement (Upload)
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

                # Stockage des résultats dans l'état de session
                st.session_state.df_optimized_estafettes = df_optimized_estafettes
                st.session_state.df_grouped = df_grouped
                st.session_state.df_city = df_city
                st.session_state.df_grouped_zone = df_grouped_zone
                st.session_state.df_zone = df_zone

                # 🆕 Initialisation du processeur de location et des propositions
                st.session_state.rental_processor = TruckRentalProcessor(df_optimized_estafettes)
                update_propositions_view()

                st.session_state.data_processed = True
                st.session_state.message = "Traitement terminé avec succès !"
                st.rerun() # Rerun pour mettre à jour l'interface

            except Exception as e:
                st.error(f"❌ Erreur lors du traitement : {str(e)}")
                st.session_state.data_processed = False
        else:
            st.warning("Veuillez uploader tous les fichiers nécessaires.")

# =====================================================
# AFFICHAGE (ordre demandé)
# 1) Analyse Livraison Détaillée
# 2) Proposition de location de camion
# 3) Voyages par Estafette Optimisé (Inclut Camions Loués)
# =====================================================

if st.session_state.data_processed:

    # Message d'état
    if st.session_state.message.startswith("✅"):
        st.success(st.session_state.message)
    elif st.session_state.message.startswith("❌"):
        st.error(st.session_state.message)
    elif st.session_state.message.startswith("⚠️"):
        st.warning(st.session_state.message)
    else:
        st.info(st.session_state.message or "Prêt à traiter les propositions de location.")

    # ----------------------------
    # 1) Analyse de Livraison Détaillée
    # ----------------------------
    st.header("2️⃣ Analyse de Livraison Détaillée")

    tab_grouped, tab_city, tab_zone_group, tab_zone_summary, tab_charts = st.tabs([
        "Livraisons Client/Ville",
        "Besoin Estafette par Ville",
        "Livraisons Client/Zone",
        "Besoin Estafette par Zone",
        "Graphiques"
    ])

    # Livraisons Client/Ville
    with tab_grouped:
        st.subheader("Livraisons par Client & Ville")
        df_display = st.session_state.df_grouped.drop(columns=["Zone"], errors='ignore') if st.session_state.df_grouped is not None else pd.DataFrame()
        st.dataframe(df_display, use_container_width=True)
        # Bouton de téléchargement placé juste en dessous
        if not df_display.empty:
            towrite = io.BytesIO()
            df_display.to_excel(towrite, index=False, sheet_name="Livraisons_Client_Ville")
            towrite.seek(0)
            st.download_button("💾 Télécharger Livraisons Client & Ville", data=towrite, file_name="Livraisons_Client_Ville.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    # Besoin Estafette par Ville
    with tab_city:
        st.subheader("Besoin Estafette par Ville")
        df_city = st.session_state.df_city if st.session_state.df_city is not None else pd.DataFrame()
        st.dataframe(df_city, use_container_width=True)
        if not df_city.empty:
            towrite = io.BytesIO()
            df_city.to_excel(towrite, index=False, sheet_name="Besoin_Estafette_Ville")
            towrite.seek(0)
            st.download_button("💾 Télécharger Besoin Estafette par Ville", data=towrite, file_name="Besoin_Estafette_Ville.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    # Livraisons Client/Zone
    with tab_zone_group:
        st.subheader("Livraisons par Client & Ville + Zone")
        st.dataframe(st.session_state.df_grouped_zone, use_container_width=True)

    # Besoin Estafette par Zone
    with tab_zone_summary:
        st.subheader("Besoin Estafette par Zone")
        st.dataframe(st.session_state.df_zone, use_container_width=True)

    # Graphiques
    with tab_charts:
        st.subheader("Statistiques par Ville")
        col1, col2 = st.columns(2)
        with col1:
            st.plotly_chart(px.bar(st.session_state.df_city, x="Ville", y="Poids total",
                                   title="Poids total livré par ville"),
                            use_container_width=True)
        with col2:
            st.plotly_chart(px.bar(st.session_state.df_city, x="Ville", y="Volume total",
                                   title="Volume total livré par ville (m³)"),
                            use_container_width=True)

        col3, col4 = st.columns(2)
        with col3:
            st.plotly_chart(px.bar(st.session_state.df_city, x="Ville", y="Nombre livraisons",
                                   title="Nombre de livraisons par ville"),
                            use_container_width=True)
        with col4:
            st.plotly_chart(px.bar(st.session_state.df_city, x="Ville", y="Besoin estafette réel",
                                   title="Besoin en Estafettes par ville"),
                            use_container_width=True)

    st.divider()

    # ----------------------------
    # 2) Proposition de location de camion
    # ----------------------------
    st.header("3️⃣ Proposition de location de camion")
    st.markdown(f"🔸 Si un client dépasse **{SEUIL_POIDS} kg** ou **{SEUIL_VOLUME} m³**, une location est proposée.")

    if st.session_state.propositions is not None and not st.session_state.propositions.empty:
        col_prop, col_details = st.columns([2, 3])

        with col_prop:
            st.markdown("### Propositions ouvertes")
            st.dataframe(st.session_state.propositions,
                         use_container_width=True,
                         column_order=["Client", "Poids total (kg)", "Volume total (m³)", "Raison"],
                         hide_index=True)

            # Sélection du client
            client_options = [""] + st.session_state.propositions['Client'].astype(str).tolist()
            st.session_state.selected_client = st.selectbox(
                "Client à traiter :",
                options=client_options,
                index=client_options.index(st.session_state.selected_client) if st.session_state.selected_client in client_options else 0,
                key='client_select'
            )

            col_btn_acc, col_btn_ref = st.columns(2)
            with col_btn_acc:
                st.button("✅ Accepter la location",
                          on_click=accept_location_callback,
                          disabled=not st.session_state.selected_client,
                          use_container_width=True)
            with col_btn_ref:
                st.button("❌ Refuser la proposition",
                          on_click=refuse_location_callback,
                          disabled=not st.session_state.selected_client,
                          use_container_width=True)

        with col_details:
            st.markdown("### Détails de la commande client")
            if st.session_state.selected_client:
                resume, details_df_styled = st.session_state.rental_processor.get_details_client(st.session_state.selected_client)
                st.text(resume)
                # Affichage du DataFrame stylisé
                st.dataframe(details_df_styled, use_container_width=True, hide_index=True)
            else:
                st.info("Sélectionnez un client pour afficher les détails de la commande/estafettes.")
    else:
        st.success("🎉 Aucune proposition de location de camion détectée pour le moment.")

    st.divider()

    # ----------------------------
    # 3) Voyages par Estafette Optimisé (Inclut Camions Loués)
    # ----------------------------
    st.header("4️⃣ Voyages par Estafette Optimisé (Inclut Camions Loués)")

    # Récupérer le DF final depuis le processeur de location s'il existe (pour prendre en compte les acceptations)
    df_optimized_estafettes = st.session_state.rental_processor.get_df_result() if st.session_state.rental_processor else st.session_state.df_optimized_estafettes

    if df_optimized_estafettes is None or df_optimized_estafettes.empty:
        st.info("Aucun voyage optimisé disponible.")
    else:
        # Mise en évidence visuelle : ligne camions loués (Camion N° commence par 'C' ou Location_camion True)
        def highlight_camion_row(row):
            # row is a Series
            try:
                val = str(row.get("Camion N°", "")).strip()
                loc = row.get("Location_camion", False)
                if loc or (val and val.startswith("C")):
                    return ['background-color: #ffdede'] * len(row)
            except:
                pass
            return [''] * len(row)

        styled = df_optimized_estafettes.style.format({
            "Poids total chargé": "{:.2f} kg",
            "Volume total chargé": "{:.3f} m³",
            "Taux d'occupation (%)": "{:.2f}%"
        }).apply(highlight_camion_row, axis=1)

        st.dataframe(styled, use_container_width=True)

        # Bouton de téléchargement sous le tableau
        towrite = io.BytesIO()
        df_optimized_estafettes.to_excel(towrite, index=False, sheet_name="Voyages_Estafette_Optimises")
        towrite.seek(0)
        st.download_button(
            label="💾 Télécharger Voyages Estafette Optimisés",
            data=towrite,
            file_name="Voyages_Estafette_Optimises.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

else:
    st.info("Uploadez les fichiers puis cliquez sur 'Exécuter le traitement complet' pour afficher les résultats.")
