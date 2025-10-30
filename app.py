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
# 5. TRANSFERT DES BLs ENTRE ESTAFETTES
# =====================================================
st.markdown("## 🔁 Transfert de BLs entre Estafettes")

# Récupération des DataFrames
df_voyages = st.session_state.df_voyages  # Tableau "Voyages par Estafette Optimisé"
df_client_ville_zone = st.session_state.df_grouped_zone  # Tableau des BLs avec poids/volume

# --- Constantes de capacité ---
MAX_POIDS = 1550.0  # kg
MAX_VOLUME = 4.608  # m3

# --- DEBUG : colonnes disponibles ---
st.write("Colonnes disponibles dans df_voyages :", df_voyages.columns.tolist())
st.write("Colonnes disponibles dans df_client_ville_zone :", df_client_ville_zone.columns.tolist())

# --- Sélection de la zone ---
zones_dispo = df_voyages["Zone"].dropna().unique()
zone_sel = st.selectbox("Sélectionner la zone", zones_dispo)

# --- Sélection des estafettes source et cible ---
estafettes_dispo = df_voyages[df_voyages["Zone"] == zone_sel]["Estafette N°"].dropna().astype(str).str.strip().unique().tolist()
source_estafette = st.selectbox("Estafette source", estafettes_dispo)
cible_estafette = st.selectbox("Estafette cible", [e for e in estafettes_dispo if e != source_estafette])

# --- Sélection des BLs à transférer ---
bls_source = []
row_source = df_voyages[df_voyages["Estafette N°"].astype(str).str.strip() == str(source_estafette).strip()]
if not row_source.empty:
    bls_str = str(row_source["BL inclus"].iloc[0])
    if bls_str and bls_str != 'nan':
        bls_source = [b.strip() for b in bls_str.split(";") if b.strip()]
bls_sel = st.multiselect("Sélectionner les BLs à transférer", bls_source)

# --- Bouton pour effectuer le transfert ---
if st.button("Transférer les BLs sélectionnés"):
    if not bls_sel:
        st.warning("⚠️ Sélectionnez au moins un BL à transférer.")
    else:
        # Récupération des BLs dans df_client_ville_zone
        df_transfer = df_client_ville_zone[df_client_ville_zone["No livraison"].isin(bls_sel)]
        poids_transfer = df_transfer["Poids total"].sum()
        volume_transfer = df_transfer["Volume total"].sum()

        # Poids et volume actuels de l'estafette cible
        cible_row = df_voyages[df_voyages["Estafette N°"].astype(str).str.strip() == str(cible_estafette).strip()]
        poids_cible = cible_row["Poids total chargé"].iloc[0]
        volume_cible = cible_row["Volume total chargé"].iloc[0]

        # Vérification des contraintes
        if (poids_cible + poids_transfer > MAX_POIDS) or (volume_cible + volume_transfer > MAX_VOLUME):
            st.error(f"❌ Transfert impossible : l'estafette {cible_estafette} dépasserait la capacité maximale !")
        else:
            # --- Effectuer le transfert ---
            clients_transfer = df_transfer["Client de l'estafette"].unique().tolist()
            representants_transfer = df_transfer["Représentant"].unique().tolist()

            # Retirer les BLs de l'estafette source
            df_voyages.loc[df_voyages["Estafette N°"].astype(str).str.strip() == str(source_estafette).strip(), "BL inclus"] = \
                df_voyages.loc[df_voyages["Estafette N°"].astype(str).str.strip() == str(source_estafette).strip(), "BL inclus"].apply(
                    lambda x: ";".join([b for b in str(x).split(";") if b not in bls_sel])
                )

            # Ajouter les BLs à l'estafette cible
            df_voyages.loc[df_voyages["Estafette N°"].astype(str).str.strip() == str(cible_estafette).strip(), "BL inclus"] = \
                df_voyages.loc[df_voyages["Estafette N°"].astype(str).str.strip() == str(cible_estafette).strip(), "BL inclus"].apply(
                    lambda x: ";".join([b for b in (str(x).split(";") + bls_sel) if b])
                )

            # Mise à jour poids et volume
            df_voyages.loc[df_voyages["Estafette N°"].astype(str).str.strip() == str(source_estafette).strip(), "Poids total chargé"] -= poids_transfer
            df_voyages.loc[df_voyages["Estafette N°"].astype(str).str.strip() == str(source_estafette).strip(), "Volume total chargé"] -= volume_transfer
            df_voyages.loc[df_voyages["Estafette N°"].astype(str).str.strip() == str(cible_estafette).strip(), "Poids total chargé"] += poids_transfer
            df_voyages.loc[df_voyages["Estafette N°"].astype(str).str.strip() == str(cible_estafette).strip(), "Volume total chargé"] += volume_transfer

            # Mise à jour clients et représentants
            df_voyages.loc[df_voyages["Estafette N°"].astype(str).str.strip() == str(cible_estafette).strip(), "Client(s) inclus"] = \
                ";".join(list(set(str(df_voyages.loc[df_voyages["Estafette N°"].astype(str).str.strip() == str(cible_estafette).strip(), "Client(s) inclus"].iloc[0]).split(";") + clients_transfer)))
            df_voyages.loc[df_voyages["Estafette N°"].astype(str).str.strip() == str(cible_estafette).strip(), "Représentant(s) inclus"] = \
                ";".join(list(set(str(df_voyages.loc[df_voyages["Estafette N°"].astype(str).str.strip() == str(cible_estafette).strip(), "Représentant(s) inclus"].iloc[0]).split(";") + representants_transfer)))

            st.success(f"✅ Transfert des BLs vers l'estafette {cible_estafette} effectué avec succès !")
            st.experimental_rerun()  # Rafraîchir les listes et affichages

