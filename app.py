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
# NOTE: Dans l'application complète, il faut s'assurer que df_voyages est bien le DF actuel optimisé
if 'df_optimized_estafettes' in st.session_state:
    df_voyages = st.session_state.df_optimized_estafettes
else:
    # Cas où la section 4 n'a pas été exécutée (seulement pour l'affichage de cette section)
    df_voyages = pd.DataFrame(columns=["Zone", "Estafette N°", "Poids total chargé", "Volume total chargé", "Client(s) inclus", "Représentant(s) inclus", "BL inclus", "Taux d'occupation (%)"])

df_client_ville_zone = st.session_state.df_grouped_zone  # Client / Ville / Zone

# Sélection des zones disponibles
zones_dispo = df_voyages["Zone"].dropna().unique()

if len(zones_dispo) == 0:
    st.warning("⚠️ Aucune donnée d'estafette disponible pour le transfert. Veuillez exécuter le traitement complet (Section 1).")
    # Sortir de la section si aucune donnée n'est chargée
    # Le reste du code ci-dessous est dans le bloc principal, donc il peut planter si df_voyages est vide.
    # On ajoute une vérification pour éviter d'autres erreurs:
    if df_voyages.empty or df_client_ville_zone is None or df_client_ville_zone.empty:
        st.stop()

zone_sel = st.selectbox("Sélectionner la zone", zones_dispo)

# Estafettes disponibles dans la zone
# CORRECTION APPLIQUÉE ICI : "Véhicule N°" -> "Estafette N°"
estafettes_dispo = df_voyages[df_voyages["Zone"] == zone_sel]["Estafette N°"].dropna().astype(str).str.strip().unique().tolist()

if len(estafettes_dispo) < 2:
    st.info("ℹ️ Au moins deux estafettes sont requises dans cette zone pour effectuer un transfert.")
    st.stop()

source_estafette = st.selectbox("Estafette source", estafettes_dispo)
cible_estafette = st.selectbox("Estafette cible", [e for e in estafettes_dispo if e != source_estafette])

# Liste des BLs de l'estafette source
# CORRECTION APPLIQUÉE ICI : "Véhicule N°" -> "Estafette N°"
source_bls_series = df_voyages.loc[df_voyages["Estafette N°"] == source_estafette, "BL inclus"]
source_bls_str = source_bls_series.values[0] if not source_bls_series.empty else None

source_bls = source_bls_str.split(";") if pd.notna(source_bls_str) and source_bls_str else []
bls_sel = st.multiselect("Sélectionner les BLs à transférer", source_bls)

# Constantes de capacité max
MAX_POIDS = 1550  # kg
MAX_VOLUME = 4.608  # m3

# Bouton de transfert
if st.button("Transférer les BLs"):
    if not bls_sel:
        st.warning("⚠️ Sélectionnez au moins un BL à transférer")
    else:
        # --- Extraire les lignes des BLs à transférer pour calcul poids/volume ---
        df_bls = df_client_ville_zone[df_client_ville_zone["No livraison"].isin(bls_sel)]
        poids_transfert = df_bls["Poids total"].sum()
        volume_transfert = df_bls["Volume total"].sum()

        # Récupérer les lignes source et cible
        # CORRECTION APPLIQUÉE ICI : "Véhicule N°" -> "Estafette N°"
        source_row = df_voyages[df_voyages["Estafette N°"] == source_estafette].iloc[0]
        cible_row = df_voyages[df_voyages["Estafette N°"] == cible_estafette].iloc[0]
        
        # Copie de la ligne cible AVANT modification pour le comparatif
        cible_row_before = cible_row.copy()
        
        poids_cible = cible_row["Poids total chargé"] + poids_transfert
        volume_cible = cible_row["Volume total chargé"] + volume_transfert

        # Vérifier capacité max
        if poids_cible > MAX_POIDS or volume_cible > MAX_VOLUME:
            st.error("❌ Transfert impossible : capacité max de l'estafette cible dépassée !")
        else:
            # Récupérer les index pour la mise à jour
            source_idx = df_voyages[df_voyages["Estafette N°"] == source_estafette].index[0]
            cible_idx = df_voyages[df_voyages["Estafette N°"] == cible_estafette].index[0]

            # --- Mettre à jour df_voyages (Poids/Volume) ---
            # CORRECTION APPLIQUÉE ICI (utilisation des index pour une mise à jour fiable)
            df_voyages.loc[source_idx, "Poids total chargé"] -= poids_transfert
            df_voyages.loc[source_idx, "Volume total chargé"] -= volume_transfert

            df_voyages.loc[cible_idx, "Poids total chargé"] += poids_transfert
            df_voyages.loc[cible_idx, "Volume total chargé"] += volume_transfert
            
            # --- Mise à jour du taux d'occupation ---
            # Recalcul des taux
            df_voyages.loc[source_idx, "Taux d'occupation (%)"] = (
                (df_voyages.loc[source_idx, "Poids total chargé"] / MAX_POIDS) * 0.5 + 
                (df_voyages.loc[source_idx, "Volume total chargé"] / MAX_VOLUME) * 0.5
            ) * 100
            df_voyages.loc[cible_idx, "Taux d'occupation (%)"] = (
                (df_voyages.loc[cible_idx, "Poids total chargé"] / MAX_POIDS) * 0.5 + 
                (df_voyages.loc[cible_idx, "Volume total chargé"] / MAX_VOLUME) * 0.5
            ) * 100


            # --- Mettre à jour clients et représentants ---
            clients_transfert = df_bls["Client de l'estafette"].unique().tolist()
            representants_transfert = df_bls["Représentant"].unique().tolist()

            # Clients Cible
            cible_clients = df_voyages.loc[cible_idx, "Client(s) inclus"]
            cible_clients_list = cible_clients.split(";") if pd.notna(cible_clients) and cible_clients else []
            cible_clients_list = list(set(cible_clients_list + clients_transfert))
            df_voyages.loc[cible_idx, "Client(s) inclus"] = ";".join(filter(None, cible_clients_list))

            # Représentants Cible
            cible_reps = df_voyages.loc[cible_idx, "Représentant(s) inclus"]
            cible_reps_list = cible_reps.split(";") if pd.notna(cible_reps) and cible_reps else []
            cible_reps_list = list(set(cible_reps_list + representants_transfert))
            df_voyages.loc[cible_idx, "Représentant(s) inclus"] = ";".join(filter(None, cible_reps_list))

            # --- Mettre à jour BLs ---
            # Supprimer BLs transférés de la source
            source_bls_val = df_voyages.loc[source_idx, "BL inclus"]
            source_bls_list = source_bls_val.split(";") if pd.notna(source_bls_val) and source_bls_val else []
            source_bls_list = [bl for bl in source_bls_list if bl not in bls_sel]
            df_voyages.loc[source_idx, "BL inclus"] = ";".join(filter(None, source_bls_list))

            # Ajouter BLs à la cible
            cible_bls_val = df_voyages.loc[cible_idx, "BL inclus"]
            cible_bls_list = cible_bls_val.split(";") if pd.notna(cible_bls_val) and cible_bls_val else []
            cible_bls_list += [bl for bl in bls_sel if bl not in cible_bls_list]
            df_voyages.loc[cible_idx, "BL inclus"] = ";".join(filter(None, cible_bls_list))

            st.session_state.message = f"✅ Transfert des BLs vers l'estafette {cible_estafette} effectué avec succès !"
            # Mettre à jour la variable de session (DF principal)
            st.session_state.df_optimized_estafettes = df_voyages
            
            # Stocker les infos avant/après pour l'affichage comparatif après rerun
            st.session_state.comparatif_data = {
                'cible_estafette': cible_estafette,
                'cible_row_before': cible_row_before,
                'cible_row_after': df_voyages.loc[cible_idx].copy()
            }
            st.rerun()

# --- Affichage comparatif avant/après pour l'estafette cible ---
if st.session_state.get('comparatif_data') and st.session_state.comparatif_data['cible_estafette'] == cible_estafette:
    
    data = st.session_state.comparatif_data
    cible_row_before = data['cible_row_before']
    cible_row_after = data['cible_row_after']

    st.markdown(f"### 📊 Comparatif Estafette {cible_estafette} avant / après transfert")
    comparatif = pd.DataFrame({
        "Poids total chargé (kg)": [cible_row_before["Poids total chargé"], cible_row_after["Poids total chargé"]],
        "Volume total chargé (m3)": [cible_row_before["Volume total chargé"], cible_row_after["Volume total chargé"]],
        "Clients inclus": [cible_row_before["Client(s) inclus"], cible_row_after["Client(s) inclus"]],
        "Représentants inclus": [cible_row_before["Représentant(s) inclus"], cible_row_after["Représentant(s) inclus"]],
        "BL inclus": [cible_row_before["BL inclus"], cible_row_after["BL inclus"]],
    }, index=["Avant transfert", "Après transfert"])
    
    st.dataframe(comparatif)
    
    # Nettoyage de l'état de session pour ne pas réafficher après une nouvelle sélection
    del st.session_state.comparatif_data

# --- Affichage final de toutes les estafettes dans un tableau ---
st.markdown("### 📝 Tableau final des estafettes après transfert")
st.dataframe(df_voyages.style.format({
     "Poids total chargé": "{:.2f} kg",
     "Volume total chargé": "{:.3f} m³",
     "Taux d'occupation (%)": "{:.2f}%"
}), use_container_width=True)