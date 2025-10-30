import streamlit as st
import pandas as pd
# Assurez-vous que le fichier backend.py est dans le même dossier
from backend import DeliveryProcessor, TruckRentalProcessor, TruckTransferManager, SEUIL_POIDS, SEUIL_VOLUME 
import plotly.express as px


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
    st.session_state.rental_processor = None # Objet de traitement de location
    st.session_state.propositions = None # Dataframe de propositions
    st.session_state.selected_client = None # Client sélectionné
    st.session_state.message = "" # Message de résultat d'opération

# =====================================================
# Fonctions de Callback pour la Location
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

def handle_location_action(accepter):
    """Gère l'acceptation ou le refus de la proposition de location."""
    if st.session_state.rental_processor and st.session_state.selected_client:
        # Assurer que le client est une chaîne valide
        client_to_process = str(st.session_state.selected_client)
        ok, msg, _ = st.session_state.rental_processor.appliquer_location(
            client_to_process, accepter=accepter
        )
        st.session_state.message = msg
        update_propositions_view()
        # st.rerun() # Pas besoin de rerun ici car le on_click est déjà dans un bloc de rerender
    elif not st.session_state.selected_client:
        st.session_state.message = "⚠️ Veuillez sélectionner un client à traiter."
    else:
        st.session_state.message = "⚠️ Le processeur de location n'est pas initialisé."

def accept_location_callback():
    handle_location_action(True)

def refuse_location_callback():
    handle_location_action(False)

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
    # Espace pour le bouton
    st.markdown("<br>", unsafe_allow_html=True) # Petit espace
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
                st.session_state.message = "Traitement terminé avec succès ! Les résultats s'affichent ci-dessous."
                st.rerun() # Rerun pour mettre à jour l'interface

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
        st.info(st.session_state.message or "Prêt à traiter les propositions de location.")
    
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
            # Affichage des propositions ouvertes
            st.dataframe(st.session_state.propositions, 
                         use_container_width=True,
                         column_order=["Client", "Poids total (kg)", "Volume total (m³)", "Raison"],
                         hide_index=True)
            
            # Sélection du client (assure qu'un client non None est sélectionné par défaut si possible)
            client_options = st.session_state.propositions['Client'].astype(str).tolist()
            client_options_with_empty = [""] + client_options
            
            # Index de sélection par défaut
            default_index = 0
            if st.session_state.selected_client in client_options:
                 default_index = client_options_with_empty.index(st.session_state.selected_client)
            elif len(client_options) > 0:
                 default_index = 1 # Sélectionne le premier client par défaut s'il y en a

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
                # Affichage du DataFrame stylisé
                st.dataframe(details_df_styled, use_container_width=True, hide_index=True)
            else:
                st.info("Sélectionnez un client pour afficher les détails de la commande/estafettes.")
    else:
        st.success("🎉 Aucune proposition de location de camion en attente de décision.")
        
    st.markdown("---")
    
    # =====================================================
    # 4. VOYAGES PAR ESTAFETTE OPTIMISÉ (Section 4 - Résultat final)
    # =====================================================
    st.header("4.Voyages par Estafette Optimisé (Inclut Camions Loués)")
    st.info("Ce tableau représente l'ordonnancement final des livraisons, y compris les commandes pour lesquelles un camion loué (Code Véhicule : CAMION-LOUE) a été accepté ou refusé.")
    
    # Affichage du DataFrame avec formatage
    st.dataframe(df_optimized_estafettes.style.format({
         "Poids total chargé": "{:.2f} kg",
         "Volume total chargé": "{:.3f} m³",
         "Taux d'occupation (%)": "{:.2f}%"
    }), use_container_width=True)

    # Bouton de téléchargement
    path_optimized = "Voyages_Estafette_Optimises.xlsx"
    # Note: On utilise le DataFrame non formaté en string pour l'export Excel
    df_optimized_estafettes.to_excel(path_optimized, index=False)
    with open(path_optimized, "rb") as f:
        st.download_button(
             label="💾 Télécharger Voyages Estafette Optimisés",
             data=f,
             file_name=path_optimized,
             mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
# ===================================================== 
# 5️⃣ TRANSFERT DES BLs ENTRE ESTAFETTES
# ===================================================== 
st.markdown("## 🔁 Transfert de BLs entre Estafettes")

# ✅ Recherche automatique du DataFrame final (résultat Section 3 / 4)
df_voyages = None
if "df_rental_final" in st.session_state:
    df_voyages = st.session_state.df_rental_final.copy()
elif "df_voyages" in st.session_state:
    df_voyages = st.session_state.df_voyages.copy()
elif "df_optimized_estafettes" in st.session_state:
    df_voyages = st.session_state.df_optimized_estafettes.copy()

if df_voyages is None:
    st.warning("⚠️ Impossible de trouver le tableau final. Veuillez exécuter la section 3 (Location / Résultat final).")
else:
    df_client_ville_zone = st.session_state.df_grouped_zone.copy()  # Détails BLs

    # --- Sélection de la zone
    zones_dispo = sorted(df_voyages["Zone"].dropna().unique().tolist())
    zone_sel = st.selectbox("🌍 Sélectionner une zone", zones_dispo)

    if zone_sel:
        # --- Filtrer les estafettes/camions de cette zone
        df_zone = df_voyages[df_voyages["Zone"] == zone_sel].copy()
        estafettes_dispo = sorted(df_zone["Estafette N°"].astype(str).unique().tolist())

        # --- Sélection source et cible
        col1, col2 = st.columns(2)
        with col1:
            source_estafette = st.selectbox("🚐 Estafette / Camion source", estafettes_dispo)
        with col2:
            cible_estafette = st.selectbox("🎯 Estafette / Camion cible", estafettes_dispo)

        # --- Empêcher transfert vers soi-même
        if source_estafette == cible_estafette:
            st.error("❌ Source et cible doivent être différentes.")
        else:
            # --- BLs de la source
            source_bls_str = df_zone.loc[df_zone["Estafette N°"] == source_estafette, "BL inclus"].values
            if len(source_bls_str) == 0 or pd.isna(source_bls_str[0]):
                st.warning("⚠️ Aucun BL trouvé pour cette estafette source.")
            else:
                source_bls_list = [b.strip() for b in source_bls_str[0].split(";") if b.strip()]
                selected_bls = st.multiselect(
                    f"📦 Sélectionnez les BLs à transférer de {source_estafette} vers {cible_estafette}",
                    options=source_bls_list,
                )

                if selected_bls:
                    # --- Détails des BLs sélectionnés
                    df_selected_bls = df_client_ville_zone[df_client_ville_zone["BL"].isin(selected_bls)]
                    poids_transfert = df_selected_bls["Poids (kg)"].sum()
                    volume_transfert = df_selected_bls["Volume (m3)"].sum()

                    # --- Capacité actuelle de la cible
                    poids_cible = df_zone.loc[df_zone["Estafette N°"] == cible_estafette, "Poids total (kg)"].values[0]
                    volume_cible = df_zone.loc[df_zone["Estafette N°"] == cible_estafette, "Volume total (m3)"].values[0]

                    # --- Seuils max (identiques à la location)
                    SEUIL_POIDS = 3000.0
                    SEUIL_VOLUME = 9.216

                    # --- Vérification des capacités
                    if poids_cible + poids_transfert > SEUIL_POIDS or volume_cible + volume_transfert > SEUIL_VOLUME:
                        st.error("🚫 Dépassement de capacité ! (Poids ou volume)")
                        st.info(f"Capacité actuelle : {poids_cible:.0f} kg / {volume_cible:.2f} m³")
                        st.info(f"Transfert : +{poids_transfert:.0f} kg / +{volume_transfert:.2f} m³")
                    else:
                        # --- Comparatif avant / après
                        colA, colB = st.columns(2)
                        with colA:
                            st.markdown("### 📊 Avant transfert")
                            st.dataframe(df_zone[
                                ["Estafette N°", "Poids total (kg)", "Volume total (m3)", "BL inclus"]
                            ])

                        # --- Mise à jour des BLs
                        df_voyages.loc[df_voyages["Estafette N°"] == source_estafette, "BL inclus"] = df_voyages.loc[
                            df_voyages["Estafette N°"] == source_estafette, "BL inclus"
                        ].apply(lambda x: ";".join([b for b in str(x).split(";") if b.strip() not in selected_bls]))

                        df_voyages.loc[df_voyages["Estafette N°"] == cible_estafette, "BL inclus"] = df_voyages.loc[
                            df_voyages["Estafette N°"] == cible_estafette, "BL inclus"
                        ].apply(lambda x: ";".join(
                            list(set([b.strip() for b in (str(x) + ";" + ";".join(selected_bls)).split(";") if b.strip()]))
                        ))

                        # --- Recalcul des poids / volumes
                        def recalculer_poids_volume(bl_str):
                            if not isinstance(bl_str, str) or not bl_str.strip():
                                return (0.0, 0.0)
                            bl_list = [b.strip() for b in bl_str.split(";") if b.strip()]
                            df_temp = df_client_ville_zone[df_client_ville_zone["BL"].isin(bl_list)]
                            return (df_temp["Poids (kg)"].sum(), df_temp["Volume (m3)"].sum())

                        df_voyages[["Poids total (kg)", "Volume total (m3)"]] = df_voyages["BL inclus"].apply(
                            recalculer_poids_volume
                        ).apply(pd.Series)

                        # --- Taux d’occupation
                        df_voyages["Taux_occupation_poids_%"] = (
                            df_voyages["Poids total (kg)"] / SEUIL_POIDS * 100
                        ).round(1)
                        df_voyages["Taux_occupation_vol_%"] = (
                            df_voyages["Volume total (m3)"] / SEUIL_VOLUME * 100
                        ).round(1)

                        with colB:
                            st.markdown("### ✅ Après transfert")
                            st.dataframe(df_voyages[df_voyages["Zone"] == zone_sel][
                                ["Estafette N°", "Poids total (kg)", "Volume total (m3)",
                                 "Taux_occupation_poids_%", "Taux_occupation_vol_%", "BL inclus"]
                            ])

                        # --- Sauvegarde mise à jour
                        st.session_state.df_rental_final = df_voyages
                        st.success("✅ Transfert effectué et tableau mis à jour avec succès.")
                else:
                    st.info("Sélectionnez au moins un BL pour effectuer un transfert.")
