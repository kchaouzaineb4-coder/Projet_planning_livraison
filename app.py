import streamlit as st
import pandas as pd
from backend import DeliveryProcessor, TruckRentalProcessor, TruckTransferManager, SEUIL_POIDS, SEUIL_VOLUME 
import plotly.express as px

# =====================================================
# 📌 Constantes pour les véhicules et chauffeurs
# =====================================================
VEHICULES_DISPONIBLES = [
    'SLG-VEH11', 'SLG-VEH14', 'SLG-VEH22', 'SLG-VEH19',
    'SLG-VEH10', 'SLG-VEH16', 'SLG-VEH23', 'SLG-VEH08', 'SLG-VEH20', 'code-Camion'
]

CHAUFFEURS_DETAILS = {
    '09254': 'DAMMAK Karim', '06002': 'MAAZOUN Bassem', '11063': 'SASSI Ramzi',
    '10334': 'BOUJELBENE Mohamed', '15144': 'GADDOUR Rami', '08278': 'DAMMAK Wissem',
    '18339': 'REKIK Ahmed', '07250': 'BARKIA Mustapha', '13321': 'BADRI Moez','Matricule': 'Chauffeur Camion'
}

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
        # --- Stockage du DataFrame pour la section 5 (transfert BLs) ---
        if "df_livraisons" not in st.session_state:
            st.session_state.df_livraisons = st.session_state.df_grouped.copy()
        
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
# Cette ligne est essentielle pour que la section 5 sache que le tableau final est prêt
st.session_state.df_voyages = df_optimized_estafettes

# =====================================================
# 5️⃣ TRANSFERT DES BLs ENTRE ESTAFETTES / CAMIONS
# =====================================================
st.markdown("## 🔁 Transfert de BLs entre Estafettes / Camions")

# --- Limites des véhicules ---
MAX_POIDS = 1550  # kg
MAX_VOLUME = 4.608  # m³

# --- Vérification : le tableau final doit être disponible ---
if "df_voyages" not in st.session_state:
    st.warning("⚠️ Vous devez d'abord exécuter la section 3 (résultat final après location).")
elif "df_livraisons" not in st.session_state:
    st.warning("⚠️ Le DataFrame des livraisons détaillées n'est pas disponible. Assurez-vous que la section 2 a été exécutée.")
else:
    # --- Récupération des DataFrames ---
    df_voyages = st.session_state.df_voyages.copy()
    df_livraisons = st.session_state.df_livraisons.copy()

    # --- Colonnes requises pour l'affichage ---
    colonnes_requises = ["Zone", "Véhicule N°", "Poids total chargé", "Volume total chargé", "BL inclus"]

    if not all(col in df_voyages.columns for col in colonnes_requises):
        st.error(f"❌ Le DataFrame ne contient pas toutes les colonnes nécessaires : {', '.join(colonnes_requises)}")
    else:
        # --- Sélection de la zone ---
        zones_disponibles = sorted(df_voyages["Zone"].dropna().unique().tolist())
        zone_selectionnee = st.selectbox("🌍 Sélectionner une zone", zones_disponibles)

        if zone_selectionnee:
            df_zone = df_voyages[df_voyages["Zone"] == zone_selectionnee]
            vehicules = sorted(df_zone["Véhicule N°"].dropna().unique().tolist())

            # --- Sélection véhicule source et cible ---
            col1, col2 = st.columns(2)
            with col1:
                source = st.selectbox("🚐 Estafette / Camion source", vehicules)
            with col2:
                cible = st.selectbox("🎯 Estafette / Camion cible", [v for v in vehicules if v != source])

            if not source or not cible:
                st.info("ℹ️ Sélectionnez un véhicule source et un véhicule cible pour continuer.")
            else:
                # --- BLs du véhicule source ---
                df_source = df_zone[df_zone["Véhicule N°"] == source]
                if df_source.empty or df_source["BL inclus"].isna().all():
                    st.warning("⚠️ Aucun BL trouvé pour ce véhicule source.")
                else:
                    st.subheader(f"📦 BLs actuellement assignés à {source}")
                    st.dataframe(df_source[["Véhicule N°", "Poids total chargé", "Volume total chargé", "BL inclus"]])

                    # --- Sélection des BLs à transférer ---
                    bls_disponibles = df_source["BL inclus"].iloc[0].split(";")
                    bls_selectionnes = st.multiselect("📋 Sélectionner les BLs à transférer :", bls_disponibles)

                    if bls_selectionnes:
                        if st.button("🔁 Exécuter le transfert"):

                            # --- BLs sélectionnés depuis le DataFrame des livraisons ---
                            df_bls_selection = df_livraisons[
                                df_livraisons["No livraison"].isin(bls_selectionnes)
                            ]
    
                            poids_bls = df_bls_selection["Poids total"].sum()
                            volume_bls = df_bls_selection["Volume total"].sum()
                            # --- Vérification limites pour le véhicule cible ---
                            df_cible = df_zone[df_zone["Véhicule N°"] == cible]
                            poids_cible = df_cible["Poids total chargé"].sum()
                            volume_cible = df_cible["Volume total chargé"].sum()

                            if (poids_cible + poids_bls) > MAX_POIDS or (volume_cible + volume_bls) > MAX_VOLUME:
                                st.warning("⚠️ Le transfert dépasse les limites de poids ou volume du véhicule cible.")
                            else:
                                # --- Transfert effectif ---
                                def transfer_bl(row):
                                    bls = row["BL inclus"].split(";") if pd.notna(row["BL inclus"]) else []
                                    bls_to_move = [b for b in bls if b in bls_selectionnes]

                                    if row["Véhicule N°"] == source:
                                        new_bls = [b for b in bls if b not in bls_to_move]
                                        row["BL inclus"] = ";".join(new_bls)
                                        row["Poids total chargé"] -= poids_bls
                                        row["Volume total chargé"] -= volume_bls
                                        row["Poids total chargé"] = max(0, row["Poids total chargé"])
                                        row["Volume total chargé"] = max(0, row["Volume total chargé"])
                                    elif row["Véhicule N°"] == cible:
                                        new_bls = bls + bls_to_move
                                        row["BL inclus"] = ";".join(new_bls)
                                        row["Poids total chargé"] += poids_bls
                                        row["Volume total chargé"] += volume_bls
                                    return row

                                df_voyages = df_voyages.apply(transfer_bl, axis=1)
                                st.session_state.df_voyages = df_voyages
                                st.success(f"✅ Transfert réussi : {len(bls_selectionnes)} BL(s) déplacé(s) de {source} vers {cible}.")

                                # --- Affichage de tous les voyages mis à jour ---
                                st.subheader("📊 Voyages après transfert (toutes les zones)")
                                st.dataframe(df_voyages.sort_values(by=["Zone", "Véhicule N°"])[colonnes_requises],
                                            use_container_width=True)

                                # --- Téléchargement XLSX ---
                                from io import BytesIO
                                def to_excel(df):
                                    output = BytesIO()
                                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                                        df.to_excel(writer, index=False, sheet_name='Transfert BLs')
                                    return output.getvalue()

                                excel_data = to_excel(df_voyages)
                                st.download_button(
                                    label="💾 Télécharger le tableau mis à jour (XLSX)",
                                    data=excel_data,
                                    file_name="voyages_apres_transfert.xlsx",
                                    mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                                )
                    else:
                        st.info("ℹ️ Sélectionnez au moins un BL à transférer.")

# =====================================================
# 6️⃣ VALIDATION DES VOYAGES APRÈS TRANSFERT
# =====================================================
st.markdown("## ✅ Validation des Voyages après Transfert")

from io import BytesIO

# --- Fonction pour exporter DataFrame en Excel ---
def to_excel(df, sheet_name="Voyages Validés"):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    return output.getvalue()

# --- On crée voyages_apres_transfert à partir du df_voyages final ---
voyages_apres_transfert = st.session_state.df_voyages.copy()
df_validation = voyages_apres_transfert.copy()

# --- Création d'une clé unique pour l'état de validation ---
if "validations" not in st.session_state:
    st.session_state.validations = {}

st.markdown("### 🧾 Liste des Voyages à Valider")
st.info("👉 Pour chaque voyage, sélectionnez **Oui** pour valider ou **Non** pour supprimer.")

# --- Affichage interactif des voyages ---
for idx, row in df_validation.iterrows():
    with st.expander(f"🚚 Voyage {row['Véhicule N°']} | Zone : {row['Zone']}"):
        st.write("**Informations du voyage :**")
        st.dataframe(row.to_frame().T, use_container_width=True)

        choix = st.radio(
            f"Valider ce voyage ? (Estafette {row['Véhicule N°']})",
            ["Oui", "Non"],
            index=0 if st.session_state.validations.get(idx) == "Oui" else 1 if st.session_state.validations.get(idx) == "Non" else 0,
            key=f"validation_{idx}"
        )
        st.session_state.validations[idx] = choix

# --- Bouton pour appliquer les validations ---
if st.button("🧮 Appliquer la validation"):
    # --- Extraction des voyages validés ---
    valid_indexes = [i for i, v in st.session_state.validations.items() if v == "Oui"]
    df_voyages_valides = df_validation.loc[valid_indexes].reset_index(drop=True)

    # --- Stockage dans session_state pour qu'il soit accessible globalement ---
    st.session_state.df_voyages_valides = df_voyages_valides

    st.success(f"✅ {len(df_voyages_valides)} voyage(s) validé(s).")
    st.markdown("### 📦 Voyages Validés")
    st.dataframe(df_voyages_valides, use_container_width=True)

    # --- Téléchargement Excel ---
    excel_data = to_excel(df_voyages_valides)
    st.download_button(
        label="💾 Télécharger les voyages validés (XLSX)",
        data=excel_data,
        file_name="Voyages_valides.xlsx",
        mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )

    # --- Création du tableau des voyages validés si il n'existe pas encore ---
    if "df_voyages_valides" not in locals() and "df_voyages_valides" not in st.session_state:
        if "df_voyages" in st.session_state:
            df_voyages_valides = st.session_state.df_voyages.copy()  # copie du tableau final
        else:
            st.warning("⚠️ Aucun voyage disponible pour la validation.")

# =====================================================
# 7️⃣ ATTRIBUTION DES VÉHICULES ET CHAUFFEURS
# =====================================================
st.markdown("## 🚛 Attribution des Véhicules et Chauffeurs")

# --- Vérification que df_voyages_valides existe dans st.session_state ---
if 'df_voyages_valides' in st.session_state and not st.session_state.df_voyages_valides.empty:
    
    df_attribution = st.session_state.df_voyages_valides.copy()

    # --- Création d'un dictionnaire pour stocker les attributions ---
    if "attributions" not in st.session_state:
        st.session_state.attributions = {}

    st.info("👉 Pour chaque voyage validé, sélectionnez un **Véhicule** et un **Chauffeur**.")

    # --- Affichage interactif pour chaque voyage ---
    for idx, row in df_attribution.iterrows():
        with st.expander(f"🚚 Voyage {row['Véhicule N°']} | Zone : {row['Zone']}"):
            st.write("**Informations du voyage :**")
            st.dataframe(row.to_frame().T, use_container_width=True)

            # Sélection véhicule
            vehicule_selectionne = st.selectbox(
                f"Véhicule pour le voyage {row['Véhicule N°']}",
                VEHICULES_DISPONIBLES,
                index=0 if st.session_state.attributions.get(idx, {}).get("Véhicule") else 0,
                key=f"vehicule_{idx}"
            )

            # Sélection chauffeur
            chauffeur_selectionne = st.selectbox(
                f"Chauffeur pour le voyage {row['Véhicule N°']}",
                list(CHAUFFEURS_DETAILS.values()),
                index=0 if st.session_state.attributions.get(idx, {}).get("Chauffeur") else 0,
                key=f"chauffeur_{idx}"
            )

            # Sauvegarde dans st.session_state
            st.session_state.attributions[idx] = {
                "Véhicule": vehicule_selectionne,
                "Chauffeur": chauffeur_selectionne
            }

    # --- Bouton pour appliquer les attributions ---
    if st.button("✅ Appliquer les attributions"):

        # Création des colonnes Véhicule attribué et Chauffeur attribué
        df_attribution["Véhicule attribué"] = df_attribution.index.map(lambda i: st.session_state.attributions[i]["Véhicule"])
        df_attribution["Chauffeur attribué"] = df_attribution.index.map(lambda i: st.session_state.attributions[i]["Chauffeur"])

        st.success("🚀 Attributions appliquées avec succès !")
        st.markdown("### 📦 Voyages avec Véhicule et Chauffeur")
        st.dataframe(df_attribution, use_container_width=True)

        # --- Téléchargement XLSX ---
        from io import BytesIO
        def to_excel(df):
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Voyages_Attribués')
            return output.getvalue()

        excel_data = to_excel(df_attribution)
        st.download_button(
            label="💾 Télécharger le tableau final (XLSX)",
            data=excel_data,
            file_name="Voyages_attribues.xlsx",
            mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )

else:
    st.warning("⚠️ Aucun voyage validé trouvé. Veuillez d'abord valider les voyages.")
# --- Génération PDF ---
from fpdf import FPDF
from io import BytesIO

# --- Fonction pour générer un PDF à partir d'un DataFrame ---
def to_pdf(df, title="Voyages Attribués"):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, title, ln=True, align="C")
    pdf.ln(10)
    
    # Largeurs de colonnes
    col_widths = [40] * len(df.columns)
    
    pdf.set_font("Arial", "", 12)
    # Header
    for i, col in enumerate(df.columns):
        pdf.cell(col_widths[i], 8, str(col), border=1, align="C")
    pdf.ln()
    
    # Données
    for row in df.itertuples(index=False):
        for i, value in enumerate(row):
            pdf.cell(col_widths[i], 8, str(value), border=1, align="C")
        pdf.ln()
    
    # Sauvegarde dans un buffer
    pdf_buffer = BytesIO()
    pdf.output(pdf_buffer)
    pdf_buffer.seek(0)
    return pdf_buffer

# --- Bouton pour télécharger le PDF ---
pdf_data = to_pdf(df_attribution)
st.download_button(
    label="📄 Télécharger le tableau final (PDF)",
    data=pdf_data,
    file_name="Voyages_attribues.pdf",
    mime="application/pdf"
)
