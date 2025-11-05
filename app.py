import streamlit as st
import pandas as pd
from backend import DeliveryProcessor, TruckRentalProcessor, TruckTransferManager, SEUIL_POIDS, SEUIL_VOLUME 
import plotly.express as px
from st_aggrid import AgGrid, GridOptionsBuilder

def show_df_aggrid(df):
    """
    Affiche un DataFrame avec st-aggrid, filtres et recherche pour chaque colonne.
    """
    gb = GridOptionsBuilder.from_dataframe(df)
    gb.configure_default_column(filter="agTextColumnFilter", sortable=True, resizable=True)
    gb.configure_selection('single')  # optionnel : sélection d'une ligne
    grid_options = gb.build()

    AgGrid(
        df,
        gridOptions=grid_options,
        enable_enterprise_modules=False,
        fit_columns_on_grid_load=True,
        update_mode="MODEL_CHANGED",
        height=400,
        width='100%',
        theme='streamlit'  # 'light', 'dark', 'streamlit', etc.
    )


# =====================================================
# === Fonction show_df pour arrondir à 3 décimales ===
# =====================================================
def show_df(df, **kwargs):
    """
    Affiche un DataFrame avec tous les nombres arrondis à 3 décimales.
    kwargs sont transmis à st.dataframe.
    """
    if isinstance(df, pd.DataFrame):
        df_to_display = df.copy()
        df_to_display = df_to_display.round(3)
        st.dataframe(df_to_display, **kwargs)
    else:
        st.dataframe(df, **kwargs)

# =====================================================
# === Fonction show_df_multiline avec affichage HTML ===
# =====================================================
def show_df_multiline(df, column_to_multiline):
    """
    Affiche un DataFrame avec les articles multilignes dans la même cellule.
    Chaque 'No livraison' reste sur une seule ligne.
    """
    df_display = df.copy()

    # Grouper les lignes par livraison et concaténer les articles avec des <br>
    df_display = df_display.groupby(
        ['No livraison', 'Client', 'Ville', 'Représentant', 'Poids total', 'Volume total'],
        as_index=False
    ).agg({column_to_multiline: lambda x: "<br>".join(x.astype(str))})

    # CSS pour forcer l’affichage des <br> sur plusieurs lignes
    css = """
    <style>
    table {
        width: 100%;
        border-collapse: collapse;
    }
    th, td {
        border: 1px solid #555;
        padding: 8px;
        text-align: left;
        vertical-align: top;
        white-space: normal;
        word-wrap: break-word;
    }
    th {
        background-color: #222;
        color: white;
    }
    td {
        color: #ddd;
    }
    </style>
    """

    html = df_display.to_html(escape=False, index=False)
    st.markdown(css + html, unsafe_allow_html=True)
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
                st.session_state.rental_processor = TruckRentalProcessor(df_optimized_estafettes, df_grouped_zone)
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

    # --- Onglet Livraisons Client/Ville ---
    with tab_grouped:
        st.subheader("Livraisons par Client & Ville")
        if st.session_state.df_grouped is not None and not st.session_state.df_grouped.empty:
            cols_to_display = [c for c in st.session_state.df_grouped.columns if c != "Zone"]
            show_df(st.session_state.df_grouped[cols_to_display], width="stretch")
            if "df_livraisons" not in st.session_state or st.session_state.df_livraisons is None:
                st.session_state.df_livraisons = st.session_state.df_grouped.copy()
        else:
            st.info("⚠️ Aucun DataFrame disponible. Veuillez uploader les fichiers et exécuter le traitement.")

    # --- Onglet Besoin Estafette par Ville ---
    with tab_city:
        st.subheader("Besoin Estafette par Ville")
        show_df(st.session_state.df_city, use_container_width=True)

    # --- Onglet Livraisons Client & Ville + Zone ---
    with tab_zone_group:
        st.subheader("Livraisons par Client & Ville + Zone")
        show_df(st.session_state.df_grouped_zone, use_container_width=True)

    # --- Onglet Besoin Estafette par Zone ---
    with tab_zone_summary:
        st.subheader("Besoin Estafette par Zone")
        show_df(st.session_state.df_zone, use_container_width=True)

    # --- Onglet Graphiques ---
    with tab_charts:
        st.subheader("Statistiques par Ville")
        
        # Check if data is available
        if st.session_state.df_city is None or st.session_state.df_city.empty:
            st.warning("⚠️ Aucune donnée disponible pour les graphiques.")
        else:
            # Verify required columns exist
            required_cols = ["Ville", "Poids total", "Volume total", "Nombre livraisons", "Besoin estafette réel"]
            missing_cols = [col for col in required_cols if col not in st.session_state.df_city.columns]
            
            if missing_cols:
                st.error(f"❌ Colonnes manquantes: {', '.join(missing_cols)}")
            else:
                col1, col2 = st.columns(2)
                with col1:
                    try:
                        fig1 = px.bar(
                            data_frame=st.session_state.df_city,
                            x="Ville", 
                            y="Poids total",
                            title="Poids total livré par ville"
                        )
                        st.plotly_chart(fig1, use_container_width=True)
                    except Exception as e:
                        st.error(f"Erreur graphique Poids: {str(e)}")
                
                with col2:
                    try:
                        fig2 = px.bar(
                            data_frame=st.session_state.df_city,
                            x="Ville", 
                            y="Volume total",
                            title="Volume total livré par ville (m³)"
                        )
                        st.plotly_chart(fig2, use_container_width=True)
                    except Exception as e:
                        st.error(f"Erreur graphique Volume: {str(e)}")

                col3, col4 = st.columns(2)
                with col3:
                    try:
                        fig3 = px.bar(
                            data_frame=st.session_state.df_city,
                            x="Ville", 
                            y="Nombre livraisons",
                            title="Nombre de livraisons par ville"
                        )
                        st.plotly_chart(fig3, use_container_width=True)
                    except Exception as e:
                        st.error(f"Erreur graphique Livraisons: {str(e)}")
                
                with col4:
                    try:
                        fig4 = px.bar(
                            data_frame=st.session_state.df_city,
                            x="Ville", 
                            y="Besoin estafette réel",
                            title="Besoin en Estafettes par ville"
                        )
                        st.plotly_chart(fig4, use_container_width=True)
                    except Exception as e:
                        st.error(f"Erreur graphique Estafettes: {str(e)}")

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
            show_df(
                st.session_state.propositions,
                use_container_width=True,
                column_order=["Client", "Poids total (kg)", "Volume total (m³)", "Raison"],
                hide_index=True
            )
            
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
                st.button(
                    "✅ Accepter la location", 
                    on_click=accept_location_callback, 
                    disabled=not is_client_selected,
                    use_container_width=True
                )
            with col_btn_ref:
                st.button(
                    "❌ Refuser la proposition", 
                    on_click=refuse_location_callback, 
                    disabled=not is_client_selected,
                    use_container_width=True
                )

        with col_details:
            st.markdown("### Détails de la commande client")
            if is_client_selected:
                resume, details_df_styled = st.session_state.rental_processor.get_details_client(
                    st.session_state.selected_client
                )
                st.text(resume)
                show_df(details_df_styled, use_container_width=True, hide_index=True)
            else:
                st.info("Sélectionnez un client pour afficher les détails de la commande/estafettes.")
    else:
        st.success("🎉 Aucune proposition de location de camion en attente de décision.")

    st.markdown("---")

    # =====================================================
    # 4. VOYAGES PAR ESTAFETTE OPTIMISÉ (Section 4 - Résultat final)
    # =====================================================
    st.header("4. 🚐 Voyages par Estafette Optimisé (Inclut Camions Loués)")

    # --- Création d'une copie pour l'affichage (avec unités) ---
    df_display = df_optimized_estafettes.copy()
    df_display["Poids total chargé"] = df_display["Poids total chargé"].map(lambda x: f"{x:.3f} kg")
    df_display["Volume total chargé"] = df_display["Volume total chargé"].map(lambda x: f"{x:.3f} m³")
    df_display["Taux d'occupation (%)"] = df_display["Taux d'occupation (%)"].map(lambda x: f"{x:.3f}%")

    # --- Affichage avec show_df ---
    show_df(df_display, use_container_width=True)

    # --- Préparer un DataFrame pour export Excel ---
    df_export = df_optimized_estafettes.copy()
    df_export["Poids total chargé"] = df_export["Poids total chargé"].round(3)
    df_export["Volume total chargé"] = df_export["Volume total chargé"].round(3)

    # --- Bouton de téléchargement Excel ---
    from io import BytesIO
    path_optimized = "Voyages_Estafette_Optimises.xlsx"
    excel_buffer = BytesIO()
    with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
        df_export.to_excel(writer, index=False, sheet_name="Voyages Optimisés")
    excel_buffer.seek(0)

    st.download_button(
        label="💾 Télécharger Voyages Estafette Optimisés",
        data=excel_buffer,
        file_name=path_optimized,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    # --- Mise à jour dans session_state pour la section 5 ---
    st.session_state.df_voyages = df_optimized_estafettes

    # =====================================================
    # 5️⃣ TRANSFERT DES BLs ENTRE ESTAFETTES / CAMIONS
    # =====================================================
    st.markdown("## 🔁 Transfert de BLs entre Estafettes / Camions")

    MAX_POIDS = 1550  # kg
    MAX_VOLUME = 4.608  # m³

    if "df_voyages" not in st.session_state:
        st.warning("⚠️ Vous devez d'abord exécuter la section 3 (résultat final après location).")
    elif "df_livraisons" not in st.session_state:
        st.warning("⚠️ Le DataFrame des livraisons détaillées n'est pas disponible.")
    else:
        df_voyages = st.session_state.df_voyages.copy()
        df_livraisons = st.session_state.df_livraisons.copy()

        colonnes_requises = ["Zone", "Véhicule N°", "Poids total chargé", "Volume total chargé", "BL inclus"]

        if not all(col in df_voyages.columns for col in colonnes_requises):
            st.error(f"❌ Le DataFrame ne contient pas toutes les colonnes nécessaires : {', '.join(colonnes_requises)}")
        else:
            zones_disponibles = sorted(df_voyages["Zone"].dropna().unique().tolist())
            zone_selectionnee = st.selectbox("🌍 Sélectionner une zone", zones_disponibles)

            if zone_selectionnee:
                df_zone = df_voyages[df_voyages["Zone"] == zone_selectionnee]
                vehicules = sorted(df_zone["Véhicule N°"].dropna().unique().tolist())

                col1, col2 = st.columns(2)
                with col1:
                    source = st.selectbox("🚐 Estafette / Camion source", vehicules)
                with col2:
                    cible = st.selectbox("🎯 Estafette / Camion cible", [v for v in vehicules if v != source])

                if source and cible:
                    df_source = df_zone[df_zone["Véhicule N°"] == source]
                    if df_source.empty or df_source["BL inclus"].isna().all():
                        st.warning("⚠️ Aucun BL trouvé pour ce véhicule source.")
                    else:
                        st.subheader(f"📦 BLs actuellement assignés à {source}")
                        df_source_display = df_source[["Véhicule N°", "Poids total chargé", "Volume total chargé", "BL inclus"]].copy()
                        df_source_display["Poids total chargé"] = df_source_display["Poids total chargé"].map(lambda x: f"{x:.3f} kg")
                        df_source_display["Volume total chargé"] = df_source_display["Volume total chargé"].map(lambda x: f"{x:.3f} m³")
                        show_df(df_source_display, use_container_width=True)

                        bls_disponibles = df_source["BL inclus"].iloc[0].split(";")
                        bls_selectionnes = st.multiselect("📋 Sélectionner les BLs à transférer :", bls_disponibles)

                        if bls_selectionnes and st.button("🔁 Exécuter le transfert"):
                            df_bls_selection = df_livraisons[df_livraisons["No livraison"].isin(bls_selectionnes)]
                            poids_bls = df_bls_selection["Poids total"].sum()
                            volume_bls = df_bls_selection["Volume total"].sum()

                            df_cible = df_zone[df_zone["Véhicule N°"] == cible]
                            poids_cible = df_cible["Poids total chargé"].sum()
                            volume_cible = df_cible["Volume total chargé"].sum()

                            if (poids_cible + poids_bls) > MAX_POIDS or (volume_cible + volume_bls) > MAX_VOLUME:
                                st.warning("⚠️ Le transfert dépasse les limites de poids ou volume du véhicule cible.")
                            else:
                                def transfer_bl(row):
                                    bls = row["BL inclus"].split(";") if pd.notna(row["BL inclus"]) else []
                                    bls_to_move = [b for b in bls if b in bls_selectionnes]

                                    if row["Véhicule N°"] == source:
                                        new_bls = [b for b in bls if b not in bls_to_move]
                                        row["BL inclus"] = ";".join(new_bls)
                                        row["Poids total chargé"] = max(0, row["Poids total chargé"] - poids_bls)
                                        row["Volume total chargé"] = max(0, row["Volume total chargé"] - volume_bls)
                                    elif row["Véhicule N°"] == cible:
                                        new_bls = bls + bls_to_move
                                        row["BL inclus"] = ";".join(new_bls)
                                        row["Poids total chargé"] += poids_bls
                                        row["Volume total chargé"] += volume_bls
                                    return row

                                df_voyages = df_voyages.apply(transfer_bl, axis=1)
                                st.session_state.df_voyages = df_voyages
                                st.success(f"✅ Transfert réussi : {len(bls_selectionnes)} BL(s) déplacé(s) de {source} vers {cible}.")

                                # --- Affichage Streamlit ---
                                st.subheader("📊 Voyages après transfert (toutes les zones)")
                                df_display = df_voyages.sort_values(by=["Zone", "Véhicule N°"]).copy()
                                df_display["Poids total chargé"] = df_display["Poids total chargé"].map(lambda x: f"{x:.3f} kg")
                                df_display["Volume total chargé"] = df_display["Volume total chargé"].map(lambda x: f"{x:.3f} m³")
                                show_df(df_display[colonnes_requises], use_container_width=True)

                                # --- Export Excel arrondi ---
                                df_export = df_voyages.copy()
                                df_export["Poids total chargé"] = df_export["Poids total chargé"].round(3)
                                df_export["Volume total chargé"] = df_export["Volume total chargé"].round(3)

                                from io import BytesIO
                                excel_buffer = BytesIO()
                                with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                                    df_export.to_excel(writer, index=False, sheet_name='Transfert BLs')
                                excel_buffer.seek(0)

                                st.download_button(
                                    label="💾 Télécharger le tableau mis à jour (XLSX)",
                                    data=excel_buffer,
                                    file_name="voyages_apres_transfert.xlsx",
                                    mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                                )

    # =====================================================
    # 6️⃣ VALIDATION DES VOYAGES APRÈS TRANSFERT
    # =====================================================
    st.markdown("## ✅ VALIDATION DES VOYAGES APRÈS TRANSFERT")

    from io import BytesIO

    # --- Fonction pour exporter DataFrame en Excel avec arrondi ---
    def to_excel(df, sheet_name="Voyages Validés"):
        df_export = df.copy()
        if "Poids total chargé" in df_export.columns:
            df_export["Poids total chargé"] = df_export["Poids total chargé"].round(3)
        if "Volume total chargé" in df_export.columns:
            df_export["Volume total chargé"] = df_export["Volume total chargé"].round(3)

        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_export.to_excel(writer, index=False, sheet_name=sheet_name)
        return output.getvalue()

    # --- Création du DataFrame de validation à partir du df_voyages ---
    voyages_apres_transfert = st.session_state.df_voyages.copy()
    df_validation = voyages_apres_transfert.copy()

    if "validations" not in st.session_state:
        st.session_state.validations = {}

    # --- Affichage interactif des voyages ---
    for idx, row in df_validation.iterrows():
        with st.expander(f"🚚 Voyage {row['Véhicule N°']} | Zone : {row['Zone']}"):
            st.write("**Informations du voyage :**")
            row_display = row.to_frame().T.copy()
            if "Poids total chargé" in row_display.columns:
                row_display["Poids total chargé"] = row_display["Poids total chargé"].map(lambda x: f"{x:.3f} kg")
            if "Volume total chargé" in row_display.columns:
                row_display["Volume total chargé"] = row_display["Volume total chargé"].map(lambda x: f"{x:.3f} m³")
            show_df(row_display, use_container_width=True)

            choix = st.radio(
                f"Valider ce voyage ? (Estafette {row['Véhicule N°']})",
                ["Oui", "Non"],
                index=0 if st.session_state.validations.get(idx) == "Oui" 
                      else 1 if st.session_state.validations.get(idx) == "Non" 
                      else 0,
                key=f"validation_{idx}"
            )
            st.session_state.validations[idx] = choix

    # --- Bouton pour appliquer les validations ---
    if st.button("🧮 Appliquer la validation"):
        valid_indexes = [i for i, v in st.session_state.validations.items() if v == "Oui"]
        valid_indexes = [i for i in valid_indexes if i in df_validation.index]

        df_voyages_valides = df_validation.loc[valid_indexes].reset_index(drop=True)
        st.session_state.df_voyages_valides = df_voyages_valides

        st.success(f"✅ {len(df_voyages_valides)} voyage(s) validé(s).")
        st.markdown("### 📦 Voyages Validés")

        # --- Affichage Streamlit avec unités ---
        df_display = df_voyages_valides.copy()
        if "Poids total chargé" in df_display.columns:
            df_display["Poids total chargé"] = df_display["Poids total chargé"].map(lambda x: f"{x:.3f} kg")
        if "Volume total chargé" in df_display.columns:
            df_display["Volume total chargé"] = df_display["Volume total chargé"].map(lambda x: f"{x:.3f} m³")
        show_df(df_display, use_container_width=True)

        # --- Export Excel arrondi ---
        excel_data = to_excel(df_voyages_valides)
        st.download_button(
            label="💾 Télécharger les voyages validés (XLSX)",
            data=excel_data,
            file_name="Voyages_valides.xlsx",
            mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )

    # =====================================================
    # 7️⃣ ATTRIBUTION DES VÉHICULES ET CHAUFFEURS
    # =====================================================
    st.markdown("## 🚛 ATTRIBUTION DES VÉHICULES ET CHAUFFEURS")

    if 'df_voyages_valides' in st.session_state and not st.session_state.df_voyages_valides.empty:
        df_attribution = st.session_state.df_voyages_valides.copy()

        if "attributions" not in st.session_state:
            st.session_state.attributions = {}

        for idx, row in df_attribution.iterrows():
            with st.expander(f"🚚 Voyage {row['Véhicule N°']} | Zone : {row['Zone']}"):
                st.write("**Informations du voyage :**")
                row_display = row.to_frame().T.copy()
                if "Poids total chargé" in row_display.columns:
                    row_display["Poids total chargé"] = row_display["Poids total chargé"].map(lambda x: f"{x:.2f} kg")
                if "Volume total chargé" in row_display.columns:
                    row_display["Volume total chargé"] = row_display["Volume total chargé"].map(lambda x: f"{x:.3f} m³")
                show_df(row_display, use_container_width=True)

                vehicule_selectionne = st.selectbox(
                    f"Véhicule pour le voyage {row['Véhicule N°']}",
                    VEHICULES_DISPONIBLES,
                    index=0 if st.session_state.attributions.get(idx, {}).get("Véhicule") else 0,
                    key=f"vehicule_{idx}"
                )
                chauffeur_selectionne = st.selectbox(
                    f"Chauffeur pour le voyage {row['Véhicule N°']}",
                    list(CHAUFFEURS_DETAILS.values()),
                    index=0 if st.session_state.attributions.get(idx, {}).get("Chauffeur") else 0,
                    key=f"chauffeur_{idx}"
                )

                st.session_state.attributions[idx] = {
                    "Véhicule": vehicule_selectionne,
                    "Chauffeur": chauffeur_selectionne
                }

        if st.button("✅ Appliquer les attributions"):
            df_attribution["Véhicule attribué"] = df_attribution.index.map(lambda i: st.session_state.attributions[i]["Véhicule"])
            df_attribution["Chauffeur attribué"] = df_attribution.index.map(lambda i: st.session_state.attributions[i]["Chauffeur"])

            st.markdown("### 📦 Voyages avec Véhicule et Chauffeur")

            # --- Affichage formaté ---
            df_display = df_attribution.copy()
            if "Poids total chargé" in df_display.columns:
                df_display["Poids total chargé"] = df_display["Poids total chargé"].map(lambda x: f"{x:.3f} kg")
            if "Volume total chargé" in df_display.columns:
                df_display["Volume total chargé"] = df_display["Volume total chargé"].map(lambda x: f"{x:.3f} m³")
            show_df(df_display, use_container_width=True)

            # --- Export Excel ---
            from io import BytesIO
            def to_excel(df):
                df_export = df.copy()
                if "Poids total chargé" in df_export.columns:
                    df_export["Poids total chargé"] = df_export["Poids total chargé"].round(3)
                if "Volume total chargé" in df_export.columns:
                    df_export["Volume total chargé"] = df_export["Volume total chargé"].round(3)
                output = BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df_export.to_excel(writer, index=False, sheet_name='Voyages_Attribués')
                return output.getvalue()

            st.download_button(
                label="💾 Télécharger le tableau final (XLSX)",
                data=to_excel(df_attribution),
                file_name="Voyages_attribues.xlsx",
                mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )

            # --- Export PDF corrigé ---
            from fpdf import FPDF

            def to_pdf(df, title="Voyages Attribués"):
                pdf = FPDF()
                pdf.add_page()
                pdf.set_font("Arial", 'B', 14)
                pdf.cell(0, 10, title, ln=True, align="C")
                pdf.ln(5)

                pdf.set_font("Arial", '', 10)

                # Créer une copie formatée pour le PDF avec unités
                df_pdf = df.copy()
                if "Poids total chargé" in df_pdf.columns:
                    df_pdf["Poids total chargé"] = df_pdf["Poids total chargé"].map(lambda x: f"{x:.3f} kg")
                if "Volume total chargé" in df_pdf.columns:
                    df_pdf["Volume total chargé"] = df_pdf["Volume total chargé"].map(lambda x: f"{x:.3f} m³")

                col_widths = [pdf.get_string_width(col)+6 for col in df_pdf.columns]

                # En-têtes
                for i, col in enumerate(df_pdf.columns):
                    pdf.cell(col_widths[i], 8, str(col), border=1, align='C')
                pdf.ln()

                # Lignes
                for _, row in df_pdf.iterrows():
                    for i, col in enumerate(df_pdf.columns):
                        pdf.cell(col_widths[i], 8, str(row[col]), border=1)
                    pdf.ln()

                return pdf.output(dest='S').encode('latin1')

            st.download_button(
                label="📄 Télécharger le tableau final (PDF)",
                data=to_pdf(df_attribution),
                file_name="Voyages_attribues.pdf",
                mime='application/pdf'
            )

# =====================================================
# MESSAGE SI DONNÉES NON TRAITÉES
# =====================================================
else:
    st.info("📊 Veuillez uploader les fichiers et exécuter le traitement complet pour afficher les résultats.")