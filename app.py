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

df_voyages = st.session_state.df_optimized_estafettes
df_client_ville_zone = st.session_state.df_grouped_zone

# --- DEBUG : afficher les colonnes pour vérifier ---
st.write("Colonnes disponibles dans df_voyages :", df_voyages.columns.tolist())
st.write("Colonnes disponibles dans df_client_ville_zone :", df_client_ville_zone.columns.tolist())

# Sélection de la zone
zones_dispo = df_voyages["Zone"].dropna().unique()
zone_sel = st.selectbox("Sélectionner la zone", zones_dispo)

# Estafettes disponibles dans la zone
estafettes_dispo = df_voyages[df_voyages["Zone"] == zone_sel]["Estafette N°"].dropna().astype(str).str.strip().unique().tolist()
source_estafette = st.selectbox("Estafette source", estafettes_dispo)
cible_estafette = st.selectbox("Estafette cible", [e for e in estafettes_dispo if e != source_estafette])

# --- DYNAMIQUE : BLs disponibles selon l'estafette source ---
bls_list = []
df_source = df_voyages[(df_voyages["Zone"] == zone_sel) & (df_voyages["Estafette N°"] == source_estafette)]

if not df_source.empty and pd.notna(df_source.iloc[0]["BL inclus"]):
    bls_list = [b.strip() for b in str(df_source.iloc[0]["BL inclus"]).split(";") if b.strip()]

bls_sel = st.multiselect("Sélectionner les BLs à transférer", bls_list)

# --- Bouton pour effectuer le transfert ---
if st.button("Transférer les BLs sélectionnés"):

    if not bls_sel:
        st.warning("⚠️ Sélectionnez au moins un BL à transférer.")
    else:
        # Copier df_voyages pour modification
        df_voyages_mod = df_voyages.copy()

        # 1️⃣ Mettre à jour BL inclus pour source et cible
        for idx, row in df_voyages_mod.iterrows():
            if row["Zone"] == zone_sel:
                veh = str(row["Estafette N°"]).strip()
                # Retirer BLs de l'estafette source
                if veh == source_estafette and pd.notna(row["BL inclus"]):
                    bls_row = [b.strip() for b in str(row["BL inclus"]).split(";") if b.strip()]
                    bls_row = [b for b in bls_row if b not in bls_sel]
                    df_voyages_mod.at[idx, "BL inclus"] = ";".join(bls_row) if bls_row else None

                # Ajouter BLs à l'estafette cible
                if veh == cible_estafette:
                    if pd.notna(row["BL inclus"]):
                        bls_row = [b.strip() for b in str(row["BL inclus"]).split(";") if b.strip()]
                        bls_row.extend(bls_sel)
                        df_voyages_mod.at[idx, "BL inclus"] = ";".join(sorted(set(bls_row)))
                    else:
                        df_voyages_mod.at[idx, "BL inclus"] = ";".join(bls_sel)

        # 2️⃣ Recalculer Poids total, Volume total, Client(s) inclus, Représentant(s) inclus
        for veh in [source_estafette, cible_estafette]:
            df_veh = df_voyages_mod[(df_voyages_mod["Zone"] == zone_sel) & (df_voyages_mod["Estafette N°"] == veh)]
            bls_veh = []
            if not df_veh.empty and pd.notna(df_veh.iloc[0]["BL inclus"]):
                bls_veh = [b.strip() for b in str(df_veh.iloc[0]["BL inclus"]).split(";") if b.strip()]

            # Filtrer df_client_ville_zone pour ces BLs
            df_bls_detail = df_client_ville_zone[df_client_ville_zone["No livraison"].isin(bls_veh)]

            # Mise à jour des totaux et listes
            df_voyages_mod.loc[(df_voyages_mod["Zone"] == zone_sel) & 
                               (df_voyages_mod["Estafette N°"] == veh), "Poids total chargé"] = df_bls_detail["Poids total"].sum()
            df_voyages_mod.loc[(df_voyages_mod["Zone"] == zone_sel) & 
                               (df_voyages_mod["Estafette N°"] == veh), "Volume total chargé"] = df_bls_detail["Volume total"].sum()
            df_voyages_mod.loc[(df_voyages_mod["Zone"] == zone_sel) & 
                               (df_voyages_mod["Estafette N°"] == veh), "Client(s) inclus"] = ";".join(sorted(df_bls_detail["Client de l'estafette"].dropna().astype(str).unique()))
            df_voyages_mod.loc[(df_voyages_mod["Zone"] == zone_sel) & 
                               (df_voyages_mod["Estafette N°"] == veh), "Représentant(s) inclus"] = ";".join(sorted(df_bls_detail["Représentant"].dropna().astype(str).unique()))

        # Mettre à jour l'état de session
        st.session_state.df_optimized_estafettes = df_voyages_mod
        st.success(f"✅ Transfert de {len(bls_sel)} BL(s) de {source_estafette} vers {cible_estafette} effectué avec succès !")

        # Rafraîchir l'interface
        st.experimental_rerun()
