import streamlit as st
import pandas as pd
# Importation de toutes les entités nécessaires
from backend import (
    DeliveryProcessor, 
    TruckRentalProcessor, 
    SEUIL_POIDS, 
    SEUIL_VOLUME
)
import plotly.express as px
from io import BytesIO # Nécessaire pour l'export Excel

# =====================================================
# CONFIGURATION ET INITIALISATION
# =====================================================
st.set_page_config(page_title="Planning Livraisons", layout="wide")
st.title("🚚 Planning et Optimisation de Livraisons")

# Initialisation de l'état de session
if 'data_processed' not in st.session_state:
    st.session_state.data_processed = False
    st.session_state.df_grouped = None
    st.session_state.df_city = None
    st.session_state.df_grouped_zone = None
    st.session_state.df_zone = None 
    st.session_state.rental_processor = None # Objet de traitement de location
    st.session_state.propositions = None # Dataframe de propositions ouvertes
    st.session_state.selected_client = "" # Client sélectionné par l'utilisateur
    st.session_state.message = "Veuillez charger les fichiers pour commencer le traitement."

# =====================================================
# FONCTIONS DE CALLBACK
# =====================================================

def update_propositions_view():
    """Met à jour le DataFrame de propositions après une action."""
    if st.session_state.rental_processor:
        st.session_state.propositions = st.session_state.rental_processor.detecter_propositions()
        # Réinitialiser la sélection si l'élément traité a disparu
        if (st.session_state.selected_client and 
            st.session_state.selected_client not in st.session_state.propositions['Client'].astype(str).tolist()):
             st.session_state.selected_client = ""
    else:
        st.session_state.propositions = pd.DataFrame()

def handle_location_action(accepter):
    """Gère l'acceptation ou le refus de la proposition de location."""
    client_to_treat = st.session_state.get('client_select') # Utiliser la clé du selectbox
    
    if st.session_state.rental_processor and client_to_treat:
        ok, msg, _ = st.session_state.rental_processor.appliquer_location(
            client_to_treat, accepter=accepter
        )
        st.session_state.message = msg
        update_propositions_view()
    elif not client_to_treat:
        st.session_state.message = "⚠️ Veuillez sélectionner un client à traiter."
    else:
        st.session_state.message = "⚠️ Le processeur de location n'est pas initialisé."
    st.session_state['client_select'] = "" # Réinitialiser la sélection après traitement
    st.rerun() # Rerun pour s'assurer que les dataframes sont mis à jour

def accept_location_callback():
    handle_location_action(True)

def refuse_location_callback():
    handle_location_action(False)

# =====================================================
# SECTIONS DE L'INTERFACE UTILISATEUR
# =====================================================

def upload_section():
    """Section de chargement des fichiers et d'exécution du traitement."""
    with st.container():
        st.subheader("Chargement des Données")
        col_file_1, col_file_2, col_file_3, col_button = st.columns([1, 1, 1, 1])
        
        with col_file_1:
            liv_file = st.file_uploader("Fichier Livraisons (Client/Ville)", type=["xlsx"])
        with col_file_2:
            ydlogist_file = st.file_uploader("Fichier Poids/Volumes", type=["xlsx"])
        with col_file_3:
            wcliegps_file = st.file_uploader("Fichier Clients (Zone)", type=["xlsx"])

        with col_button:
            st.markdown("<br>", unsafe_allow_html=True) # Petit espace
            if st.button("▶️ Exécuter le Traitement", type="primary", use_container_width=True):
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
                        
                        # Initialisation du processeur de location
                        st.session_state.rental_processor = TruckRentalProcessor(df_optimized_estafettes)
                        update_propositions_view()
                        
                        st.session_state.data_processed = True
                        st.session_state.message = "✅ Traitement terminé avec succès ! Consultez les propositions de location ci-dessous."
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Erreur lors du traitement : {str(e)}. Veuillez vérifier le format de vos fichiers.")
                        st.session_state.data_processed = False
                else:
                    st.warning("Veuillez uploader tous les fichiers nécessaires.")

def rental_section():
    """Section dédiée à la gestion des propositions de location de camion."""
    
    if st.session_state.rental_processor is None:
        return # Ne rien afficher si le processeur n'est pas prêt

    st.divider()
    st.header("🚚 Gestion des Propositions de Location")
    st.info(st.session_state.message)

    df_optimized_estafettes = st.session_state.rental_processor.get_df_result()
    
    propositions = st.session_state.propositions

    if propositions is not None and not propositions.empty:
        col_prop, col_details = st.columns([2, 3])
        
        with col_prop:
            st.markdown(f"### Propositions Ouvertes ({len(propositions)})")
            st.markdown(f"🔸 Seuil de proposition : **{SEUIL_POIDS} kg** ou **{SEUIL_VOLUME} m³**.")
            
            # Affichage des propositions ouvertes
            st.dataframe(propositions, 
                         use_container_width=True,
                         column_order=["Client", "Poids total chargé", "Volume total chargé", "Raison"],
                         hide_index=True)
            
            # Sélection du client. Note: Utilise une clé 'client_select' pour la session state
            client_options = [""] + propositions['Client'].astype(str).tolist()
            
            # Mise à jour de la sélection pour persister la valeur si possible
            initial_index = 0
            if st.session_state.selected_client in client_options:
                 initial_index = client_options.index(st.session_state.selected_client)

            st.session_state.selected_client = st.selectbox(
                "Client à traiter :", 
                options=client_options, 
                index=initial_index,
                key='client_select' 
            )

            col_btn_acc, col_btn_ref = st.columns(2)
            is_client_selected = bool(st.session_state.selected_client)
            
            with col_btn_acc:
                st.button("✅ Accepter la location", 
                          on_click=accept_location_callback, 
                          disabled=not is_client_selected,
                          use_container_width=True, type="primary")
            with col_btn_ref:
                st.button("❌ Refuser la proposition", 
                          on_click=refuse_location_callback, 
                          disabled=not is_client_selected,
                          use_container_width=True)

        with col_details:
            st.markdown("### Détails de la commande client")
            client_to_show = st.session_state.get('client_select')
            
            if client_to_show:
                resume, details_df_styled = st.session_state.rental_processor.get_details_client(client_to_show)
                st.code(resume, language='')
                # Affichage du DataFrame stylisé (le processeur retourne déjà un style.Styler)
                st.dataframe(details_df_styled, use_container_width=True, hide_index=True)
            else:
                st.info("Sélectionnez un client dans la liste pour afficher les détails.")
    else:
        st.success("🎉 Aucune proposition de location de camion détectée. Toutes les commandes sont conformes ou ont été traitées.")
        
    # Affichage du tableau final optimisé
    st.subheader("Synthèse de l'Optimisation par Client")
    st.dataframe(df_optimized_estafettes.style.format({
        "Poids total chargé": "{:.2f} kg",
        "Volume total chargé": "{:.3f} m³",
        "Taux d\'occupation (%)": "{:.2f}%",
        "Capacité Poids (kg)": "{:.0f}",
        "Capacité Volume (m³)": "{:.1f}"
    }), use_container_width=True)

    # Bouton de téléchargement
    path_optimized = "Voyages_Estafette_Optimises_Final.xlsx"
    # Utilisation de BytesIO pour éviter les accès disques
    output = BytesIO()
    df_optimized_estafettes.to_excel(output, index=False)
    output.seek(0)

    st.download_button(
        label="💾 Télécharger Synthèse Optimisée (Excel)",
        data=output,
        file_name=path_optimized,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

def analysis_section():
    """Section d'affichage des tableaux de données brutes et des graphiques."""
    
    st.divider() 
    st.header("Analyse Détaillée et Statistiques")
    
    df_city = st.session_state.df_city
    df_grouped = st.session_state.df_grouped
    df_grouped_zone = st.session_state.df_grouped_zone
    df_zone = st.session_state.df_zone
    
    tab_grouped, tab_city, tab_zone_group, tab_zone_summary, tab_charts = st.tabs([
        "Livraisons Client/Ville", 
        "Besoin Estafette par Ville", 
        "Livraisons Client/Zone", 
        "Besoin Estafette par Zone",
        "Graphiques"
    ])
    
    with tab_grouped:
        st.subheader("Livraisons par Client & Ville")
        st.dataframe(df_grouped.drop(columns=["Zone"], errors='ignore'), use_container_width=True)
        
    with tab_city:
        st.subheader("Besoin Estafette par Ville")
        st.dataframe(df_city.style.format({
            "Poids total (kg)": "{:.2f}", 
            "Volume total (m³)": "{:.3f}"
        }), use_container_width=True)

    with tab_zone_group:
        st.subheader("Livraisons par Client & Zone")
        st.dataframe(df_grouped_zone, use_container_width=True)
        
    with tab_zone_summary:
        st.subheader("Besoin Estafette par Zone")
        st.dataframe(df_zone.style.format({
            "Poids total (kg)": "{:.2f}", 
            "Volume total (m³)": "{:.3f}"
        }), use_container_width=True)
        
    with tab_charts:
        st.subheader("Statistiques par Ville")
        col1, col2 = st.columns(2)
        with col1:
            st.plotly_chart(px.bar(df_city, x="Ville", y="Poids total (kg)",
                                   title="Poids total livré par ville"),
                            use_container_width=True)
        with col2:
            st.plotly_chart(px.bar(df_city, x="Ville", y="Volume total (m³)",
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
# FLUX PRINCIPAL DE L'APPLICATION
# =====================================================
upload_section()

if st.session_state.data_processed:
    rental_section()
    analysis_section()
