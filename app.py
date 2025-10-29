import streamlit as st
import pandas as pd
import numpy as np
# Assurez-vous que le fichier backend.py est dans le même dossier
from backend import DeliveryProcessor, TruckRentalProcessor, SEUIL_POIDS, SEUIL_VOLUME, MAX_POIDS, MAX_VOLUME
import plotly.express as px
from typing import List, Optional

# Configuration page
st.set_page_config(page_title="Planning Livraisons", layout="wide")
st.title("🚚 Planning de Livraisons & Optimisation des Tournées")
st.markdown("---")

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
    st.session_state.df_bl_details = None # Détails des BL pour les transferts
    st.session_state.rental_processor = None # Objet de traitement de location
    st.session_state.propositions = None # Dataframe de propositions
    st.session_state.selected_client = None # Client sélectionné pour la location
    st.session_state.message = "" # Message de résultat d'opération
    st.session_state.selected_zone_transfert = None # Zone sélectionnée pour le transfert
    st.session_state.selected_source_transfert = None # Estafette source sélectionnée
    st.session_state.selected_cible_transfert = None # Estafette cible sélectionnée
    st.session_state.bls_a_transferer = [] # Liste des BLs à transférer

# =====================================================
# Fonctions de Callback pour la Location (Section 3)
# =====================================================

def update_propositions_view():
    """Met à jour le DataFrame de propositions après une action."""
    if st.session_state.rental_processor:
        st.session_state.propositions = st.session_state.rental_processor.detecter_propositions()
        
        # Réinitialiser la sélection si le client n'est plus dans les propositions ouvertes
        if (st.session_state.selected_client is not None and 
            st.session_state.propositions is not None and 
            st.session_state.selected_client not in st.session_state.propositions['Client'].astype(str).tolist()):
            st.session_state.selected_client = None
    else:
        st.session_state.propositions = pd.DataFrame()

def handle_location_action(accepter: bool):
    """Gère l'acceptation ou le refus de la proposition de location."""
    if st.session_state.rental_processor and st.session_state.selected_client:
        client_to_process = str(st.session_state.selected_client)
        ok, msg, _ = st.session_state.rental_processor.appliquer_location(
            client_to_process, accepter=accepter
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
# Fonctions de Callback pour le Transfert (Section 4)
# =====================================================

def handle_transfert_bls():
    """Gère le clic sur le bouton de transfert de BLs."""
    proc = st.session_state.rental_processor
    
    # Vérifications de base
    if not proc:
        st.session_state.message = "❌ Le processeur de données n'est pas initialisé."
        return

    # S'assurer que les valeurs sont non nulles avant de les utiliser
    zone = st.session_state.selected_zone_transfert
    bls = st.session_state.bls_a_transferer
    source = st.session_state.selected_source_transfert
    cible = st.session_state.selected_cible_transfert

    if not zone or not source or not cible or not bls:
        st.session_state.message = "⚠️ Veuillez sélectionner la zone, les estafettes source/cible et au moins un BL à transférer."
        return
    
    # Exécuter le transfert
    ok, msg = proc.transferer_bls(zone, bls, source, cible)
    st.session_state.message = msg
    
    if ok:
        # Après un transfert réussi, mettez à jour la vue des propositions pour synchronisation
        update_propositions_view()
        
        # Réinitialiser les sélections spécifiques au transfert
        st.session_state.selected_source_transfert = None
        st.session_state.selected_cible_transfert = None
        st.session_state.bls_a_transferer = []
        # Re-exécuter pour mettre à jour les sélecteurs de voyages
        st.rerun()

# =====================================================
# 1. UPLOAD DES FICHIERS INPUT (Section 1)
# =====================================================
st.header("1. 📥 Importation des Données")

col_file_1, col_file_2, col_file_3, col_button = st.columns([1, 1, 1, 1])
with col_file_1:
    liv_file = st.file_uploader("Fichier Livraisons (BL)", type=["xlsx"])
with col_file_2:
    ydlogist_file = st.file_uploader("Fichier Volumes (Articles)", type=["xlsx"])
with col_file_3:
    wcliegps_file = st.file_uploader("Fichier Clients/Zones", type=["xlsx"])
with col_button:
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("Exécuter le traitement complet", type="primary"):
        if liv_file and ydlogist_file and wcliegps_file:
            processor = DeliveryProcessor()
            try:
                with st.spinner("Traitement des données en cours..."):
                    # Les données mock sont utilisées ici
                    df_grouped, df_city, df_grouped_zone, df_zone, df_optimized_estafettes, df_bl_details = processor.process_delivery_data(
                        liv_file, ydlogist_file, wcliegps_file
                    )
                
                # Stockage des résultats dans l'état de session
                st.session_state.df_optimized_estafettes = df_optimized_estafettes
                st.session_state.df_grouped = df_grouped
                st.session_state.df_city = df_city
                st.session_state.df_grouped_zone = df_grouped_zone
                st.session_state.df_zone = df_zone
                st.session_state.df_bl_details = df_bl_details 
                
                # Initialisation du processeur de location/voyage avec les détails BL
                st.session_state.rental_processor = TruckRentalProcessor(df_optimized_estafettes, df_bl_details)
                update_propositions_view()
                
                st.session_state.data_processed = True
                st.session_state.message = "Traitement terminé avec succès ! Les résultats s'affichent ci-dessous."
                st.rerun()

            except Exception as e:
                st.error(f"❌ Erreur lors du traitement : {str(e)}")
                st.session_state.data_processed = False
        else:
            st.warning("Veuillez uploader tous les fichiers nécessaires.")
st.markdown("---")

# =====================================================
# AFFICHAGE DES RÉSULTATS (Se déclenche si les données sont traitées)
# =====================================================
if st.session_state.data_processed:
    
    # Affichage des messages d'opération
    if st.session_state.message.startswith("✅"):
        st.success(st.session_state.message)
    elif st.session_state.message.startswith("❌"):
        st.error(st.session_state.message)
    elif st.session_state.message.startswith("⚠️"):
        st.warning(st.session_state.message)
    else:
        st.info(st.session_state.message or "Prêt à traiter les propositions de location ou à effectuer des transferts manuels.")
    
    # Récupération du DF mis à jour à chaque fois
    df_optimized_estafettes = st.session_state.rental_processor.get_df_result() 
    
    # =====================================================
    # 2. ANALYSE DE LIVRAISON DÉTAILLÉE (Section 2)
    # =====================================================
    st.header("2. 🔍 Analyse de Livraison Détaillée")
    tab_grouped, tab_city, tab_zone_group, tab_zone_summary, tab_charts = st.tabs([
        "Livraisons Client/Ville", 
        "Besoin Estafette par Ville", 
        "Livraisons Client/Zone", 
        "Besoin Estafette par Zone",
        "Graphiques"
    ])
    
    with tab_grouped:
        st.subheader("Livraisons par Client & Ville")
        st.dataframe(st.session_state.df_grouped.drop(columns=["Zone"], errors='ignore'), use_container_width=True)
        
    with tab_city:
        st.subheader("Besoin Estafette par Ville")
        st.dataframe(st.session_state.df_city, use_container_width=True)

    with tab_zone_group:
        st.subheader("Livraisons par Client & Ville + Zone")
        st.dataframe(st.session_state.df_grouped_zone, use_container_width=True)
        
    with tab_zone_summary:
        st.subheader("Besoin Estafette par Zone")
        st.dataframe(st.session_state.df_zone, use_container_width=True)
        
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

    st.markdown("---")
    
    # =====================================================
    # 3. PROPOSITION DE LOCATION DE CAMION (Section 3)
    # =====================================================
    st.header("3. 🚚 Proposition de location de camion")
    st.markdown(f"🔸 Si un client dépasse **{SEUIL_POIDS} kg** ou **{SEUIL_VOLUME} m³**, une location est proposée (si non déjà décidée).")

    if st.session_state.propositions is not None and not st.session_state.propositions.empty:
        col_prop, col_details = st.columns([2, 3])
        
        with col_prop:
            st.markdown("### Propositions ouvertes")
            st.dataframe(st.session_state.propositions, 
                          use_container_width=True,
                          column_order=["Client", "Poids total (kg)", "Volume total (m³)", "Raison"],
                          hide_index=True)
            
            client_options = st.session_state.propositions['Client'].astype(str).tolist()
            client_options_with_empty = [""] + client_options
            
            default_index = 0
            if st.session_state.selected_client in client_options:
                 default_index = client_options_with_empty.index(st.session_state.selected_client)
            elif len(client_options) > 0:
                 default_index = 1

            st.session_state.selected_client = st.selectbox(
                "Client à traiter :", 
                options=client_options_with_empty, 
                index=default_index,
                key='client_select' 
            )

            col_btn_acc, col_btn_ref = st.columns(2)
            is_client_selected = st.session_state.selected_client != ""
            
            with col_btn_acc:
                st.button("✅ Accepter la location", 
                          on_click=accept_location_callback, 
                          disabled=not is_client_selected,
                          use_container_width=True)
            with col_btn_ref:
                st.button("❌ Refuser la proposition", 
                          on_click=refuse_location_callback, 
                          disabled=not is_client_selected,
                          use_container_width=True)

        with col_details:
            st.markdown("### Détails de la commande client")
            if is_client_selected:
                resume, details_df_styled = st.session_state.rental_processor.get_details_client(st.session_state.selected_client)
                st.text(resume)
                st.dataframe(details_df_styled, use_container_width=True, hide_index=True)
            else:
                st.info("Sélectionnez un client pour afficher les détails de la commande/estafettes.")
    else:
        st.success("🎉 Aucune proposition de location de camion en attente de décision.")
        
    st.markdown("---")
    
    # =====================================================
    # 4. TRANSFERT MANUEL DES BONS DE LIVRAISON (Section 4)
    # =====================================================
    st.header("4. 🔄 Transfert Manuel des Bons de Livraison (BL)")
    st.markdown(f"**Objectif :** Déplacer des BL d'un voyage à un autre dans la **même Zone**, sans dépasser les capacités maximales (Poids: **{MAX_POIDS} kg**, Volume: **{MAX_VOLUME} m³**) de l'estafette cible.")

    df_current = st.session_state.rental_processor.get_df_result()
    all_zones = sorted(df_current['Zone'].unique().tolist())
    
    # 1. Sélecteur de Zone
    col_zone, col_source, col_cible = st.columns(3)

    with col_zone:
        # Initialiser ou conserver la zone sélectionnée
        if st.session_state.selected_zone_transfert not in all_zones:
             st.session_state.selected_zone_transfert = all_zones[0] if all_zones else None
             
        zone_select = st.selectbox(
            "Sélectionner la Zone :",
            options=all_zones,
            index=all_zones.index(st.session_state.selected_zone_transfert) if st.session_state.selected_zone_transfert in all_zones else 0,
            key='zone_select_transfer'
        )
        # Mettre à jour l'état de session si la valeur a changé
        if zone_select != st.session_state.selected_zone_transfert:
            st.session_state.selected_zone_transfert = zone_select
            st.session_state.selected_source_transfert = None
            st.session_state.selected_cible_transfert = None
            st.rerun() # Recharger pour mettre à jour les options source/cible

    
    if st.session_state.selected_zone_transfert:
        zone_filtree = df_current[df_current['Zone'] == st.session_state.selected_zone_transfert].copy()
        estafette_options = sorted(zone_filtree['Estafette N°'].unique().tolist())
        estafette_options_with_empty = [""] + estafette_options

        # 2. Sélecteur d'Estafette Source
        with col_source:
            st.session_state.selected_source_transfert = st.selectbox(
                "Estafette Source :",
                options=estafette_options_with_empty,
                index=estafette_options_with_empty.index(st.session_state.selected_source_transfert) if st.session_state.selected_source_transfert in estafette_options_with_empty else 0,
                key='source_select_transfer'
            )

        # 3. Sélecteur d'Estafette Cible
        with col_cible:
            # Assurez-vous que l'estafette source n'est pas dans la liste des options cibles
            cible_options = [e for e in estafette_options if e != st.session_state.selected_source_transfert]
            cible_options_with_empty = [""] + cible_options
            
            st.session_state.selected_cible_transfert = st.selectbox(
                "Estafette Cible :",
                options=cible_options_with_empty,
                index=cible_options_with_empty.index(st.session_state.selected_cible_transfert) if st.session_state.selected_cible_transfert in cible_options_with_empty else 0,
                key='cible_select_transfer'
            )
            
        st.markdown("---")
        
        # 4. Sélecteur de BLs (Dépend de la Source)
        if st.session_state.selected_source_transfert:
            source_match = zone_filtree[zone_filtree['Estafette N°'] == st.session_state.selected_source_transfert]
            
            if not source_match.empty:
                source_df = source_match.iloc[0]
                bls_source = source_df['BL inclus']
                
                st.markdown(f"**Estafette Source ({st.session_state.selected_source_transfert}) :** Poids {source_df['Poids total chargé']:.2f} kg, Volume {source_df['Volume total chargé']:.3f} m³")

                st.session_state.bls_a_transferer = st.multiselect(
                    "Sélectionner les Bons de Livraison (BLs) à transférer :",
                    options=bls_source,
                    default=st.session_state.bls_a_transferer,
                    key='bls_multiselect_transfer'
                )
                
                # 5. Affichage des capacités cibles et bouton de transfert
                if st.session_state.selected_cible_transfert and st.session_state.df_bl_details is not None:
                    cible_match = zone_filtree[zone_filtree['Estafette N°'] == st.session_state.selected_cible_transfert]
                    
                    if not cible_match.empty:
                        cible_df = cible_match.iloc[0]
                        
                        # Calcul rapide du potentiel de transfert pour l'affichage
                        if st.session_state.bls_a_transferer:
                            
                            df_bl_detail_lookup = st.session_state.df_bl_details.set_index('Bon de Livraison')
                            poids_transfert = sum(df_bl_detail_lookup.loc[bl, 'Poids'] for bl in st.session_state.bls_a_transferer if bl in df_bl_detail_lookup.index)
                            volume_transfert = sum(df_bl_detail_lookup.loc[bl, 'Volume'] for bl in st.session_state.bls_a_transferer if bl in df_bl_detail_lookup.index)

                            nouveau_poids = cible_df['Poids total chargé'] + poids_transfert
                            nouveau_volume = cible_df['Volume total chargé'] + volume_transfert
                            
                            transfert_possible = True
                            
                            st.info(f"**Estafette Cible ({st.session_state.selected_cible_transfert}) :** Poids actuel {cible_df['Poids total chargé']:.2f} kg, Volume actuel {cible_df['Volume total chargé']:.3f} m³")

                            if nouveau_poids > MAX_POIDS or nouveau_volume > MAX_VOLUME:
                                st.error(f"ATTENTION : Le transfert dépasserait la capacité cible.")
                                if nouveau_poids > MAX_POIDS:
                                    st.error(f"  - Dépassement Poids : {nouveau_poids:.2f} kg > {MAX_POIDS} kg max")
                                if nouveau_volume > MAX_VOLUME:
                                    st.error(f"  - Dépassement Volume : {nouveau_volume:.3f} m³ > {MAX_VOLUME} m³ max")
                                transfert_possible = False
                            else:
                                st.success(f"**ESTIMATION APRÈS TRANSFERT :** "
                                        f"Poids final : {nouveau_poids:.2f} kg / {MAX_POIDS} kg. "
                                        f"Volume final : {nouveau_volume:.3f} m³ / {MAX_VOLUME} m³.")
                                transfert_possible = True
                        else:
                            st.info("Sélectionnez les BLs à transférer pour voir l'estimation.")
                            transfert_possible = False

                        st.button(
                            "▶️ CONFIRMER ET EXÉCUTER LE TRANSFERT",
                            on_click=handle_transfert_bls,
                            disabled=not transfert_possible or len(st.session_state.bls_a_transferer) == 0,
                            type="primary"
                        )
                    else:
                        st.error("Estafette cible introuvable.")
                else:
                    st.info("Sélectionnez l'estafette cible et des BLs pour l'estimation de capacité.")
            else:
                st.error("Estafette source introuvable.")
        else:
            st.info("Sélectionnez l'estafette source pour choisir les BLs.")
    else:
        st.info("Sélectionnez une zone pour commencer le transfert.")
        
    st.markdown("---")


    # =====================================================
    # 5. VOYAGES PAR ESTAFETTE OPTIMISÉ (Section 5)
    # =====================================================
    st.header("5. Voyages par Estafette Optimisé (Inclut Camions Loués et Transferts Manuels)")
    st.info("Ce tableau représente l'ordonnancement final des livraisons, mis à jour après les décisions de location et les transferts manuels.")
    
    # Colonnes à afficher et formater
    display_df = df_optimized_estafettes.copy()
    display_df['BL inclus'] = display_df['BL inclus'].apply(lambda x: ', '.join(x))
    display_df['Clients inclus'] = display_df['Clients inclus'].apply(lambda x: ', '.join(x))
    display_df['Representants inclus'] = display_df['Representants inclus'].apply(lambda x: ', '.join(x))

    # Mise en forme
    st.dataframe(display_df.style.format({
         "Poids total chargé": "{:.2f} kg",
         "Volume total chargé": "{:.3f} m³",
         "Taux d\'occupation (%)": "{:.2f}%"
    }), use_container_width=True)

    # Bouton de téléchargement
    path_optimized = "Voyages_Estafette_Optimises.xlsx"
    df_optimized_estafettes.to_excel(path_optimized, index=False)
    with open(path_optimized, "rb") as f:
        st.download_button(
             label="💾 Télécharger Voyages Estafette Optimisés",
             data=f,
             file_name=path_optimized,
             mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
