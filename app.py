# app.py
import streamlit as st
import pandas as pd
from io import BytesIO
import plotly.express as px

# Importer ton backend (assure-toi que backend.py est dans le même dossier)
from backend import DeliveryProcessor, TruckRentalProcessor, TruckTransferManager, SEUIL_POIDS, SEUIL_VOLUME, CAMION_CODE

# =====================================================
# Fonctions utilitaires d'affichage
# =====================================================
def show_df(df, **kwargs):
    """Affiche un DataFrame en arrondissant les floats pour une meilleure lisibilité."""
    if isinstance(df, pd.DataFrame):
        df_to_display = df.copy()
        # arrondir les colonnes numériques
        for c in df_to_display.select_dtypes(include=["float", "int"]).columns:
            df_to_display[c] = df_to_display[c].round(3)
        st.dataframe(df_to_display, **kwargs)
    else:
        st.dataframe(df, **kwargs)

def show_df_multiline(df, column_to_multiline):
    """Affiche un DataFrame avec une colonne pouvant contenir des <br>."""
    df_display = df.copy()
    # Group by No livraison to keep unique rows if needed
    html = df_display.to_html(escape=False, index=False)
    css = """
    <style>
    table { width:100%; border-collapse: collapse; }
    th, td { border: 1px solid #555; padding: 6px; text-align:left; vertical-align: top; white-space: normal; }
    th { background-color:#222; color:white; }
    td { color:#111; }
    </style>
    """
    st.markdown(css + html, unsafe_allow_html=True)

# =====================================================
# Config page
# =====================================================
st.set_page_config(page_title="Planning Livraisons - Avec Objet Manuel", layout="wide")
st.title("🚚 Planning de Livraisons & Optimisation des Tournées")
st.markdown("---")

# =====================================================
# Initialise state
# =====================================================
if 'data_processed' not in st.session_state:
    st.session_state.data_processed = False
    st.session_state.df_grouped = None
    st.session_state.df_city = None
    st.session_state.df_grouped_zone = None
    st.session_state.df_zone = None 
    st.session_state.df_optimized_estafettes = None
    st.session_state.df_livraisons_original = None
    st.session_state.rental_processor = None
    st.session_state.propositions = None
    st.session_state.selected_client = None
    st.session_state.message = ""
    st.session_state.df_voyages = None
    st.session_state.df_livraisons = None
    st.session_state.validations = {}
    st.session_state.df_voyages_valides = None
    st.session_state.attributions = {}

# =====================================================
# Fonctions callbacks
# =====================================================
def update_propositions_view():
    if st.session_state.rental_processor:
        st.session_state.propositions = st.session_state.rental_processor.detecter_propositions()
        # normalize column name if needed (some implementations return 'Client' or 'Client de l'estafette')
        if st.session_state.propositions is not None and not st.session_state.propositions.empty:
            # try rename to 'Client' for UI convenience
            if "Client" not in st.session_state.propositions.columns:
                if "Client de l'estafette" in st.session_state.propositions.columns:
                    st.session_state.propositions = st.session_state.propositions.rename(columns={"Client de l'estafette": "Client"})
    else:
        st.session_state.propositions = pd.DataFrame()

def handle_location_action(accepter):
    if st.session_state.rental_processor and st.session_state.selected_client:
        client_to_process = str(st.session_state.selected_client)
        ok, msg, _ = st.session_state.rental_processor.appliquer_location(client_to_process, accepter=accepter)
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
# 1. Upload fichiers
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
                    df_grouped, df_city, df_grouped_zone, df_zone, df_optimized_estafettes, df_livraisons_original = processor.process_delivery_data(
                        liv_file, ydlogist_file, wcliegps_file
                    )
                # Stocker résultats
                st.session_state.df_optimized_estafettes = df_optimized_estafettes
                st.session_state.df_grouped = df_grouped
                st.session_state.df_city = df_city
                st.session_state.df_grouped_zone = df_grouped_zone
                st.session_state.df_zone = df_zone 
                st.session_state.df_livraisons_original = df_livraisons_original
                st.session_state.df_livraisons = df_grouped_zone  # pour la section transfert

                # init rental processor
                st.session_state.rental_processor = TruckRentalProcessor(df_optimized_estafettes, df_livraisons_original)
                update_propositions_view()

                # df_voyages initial (format d'affichage)
                st.session_state.df_voyages = st.session_state.rental_processor.get_df_result()
                st.session_state.data_processed = True
                st.session_state.message = "Traitement terminé avec succès !"
                st.rerun()

            except Exception as e:
                st.error(f"❌ Erreur lors du traitement : {e}")
        else:
            st.warning("Veuillez uploader tous les fichiers nécessaires.")
st.markdown("---")

# =====================================================
# 2. Analyse de livraison détaillée
# =====================================================
if st.session_state.data_processed:
    if st.session_state.message.startswith("✅"):
        st.success(st.session_state.message)
    elif st.session_state.message.startswith("❌"):
        st.error(st.session_state.message)
    elif st.session_state.message.startswith("⚠️"):
        st.warning(st.session_state.message)
    else:
        st.info(st.session_state.message or "Prêt.")

    df_optimized_estafettes = st.session_state.rental_processor.get_df_result()

# Affichage onglets
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
    if st.session_state.df_grouped is not None:
        show_df(st.session_state.df_grouped.drop(columns=["Zone"], errors='ignore'), use_container_width=True)
        # téléchargement
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            st.session_state.df_grouped.drop(columns=["Zone"], errors='ignore').to_excel(writer, index=False, sheet_name="Livraisons Client Ville")
        buffer.seek(0)
        st.download_button("💾 Télécharger Livraisons Client/Ville", data=buffer, file_name="Livraisons_Client_Ville.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

with tab_city:
    st.subheader("Besoin Estafette par Ville")
    if st.session_state.df_city is not None:
        show_df(st.session_state.df_city, use_container_width=True)
        buf = BytesIO()
        with pd.ExcelWriter(buf, engine='openpyxl') as writer:
            st.session_state.df_city.to_excel(writer, index=False, sheet_name="Besoin Estafette Ville")
        buf.seek(0)
        st.download_button("💾 Télécharger Besoin par Ville", data=buf, file_name="Besoin_Estafette_Ville.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

with tab_zone_group:
    st.subheader("Livraisons par Client & Ville + Zone")
    if st.session_state.df_grouped_zone is not None:
        show_df(st.session_state.df_grouped_zone, use_container_width=True)
        buf = BytesIO()
        with pd.ExcelWriter(buf, engine='openpyxl') as writer:
            st.session_state.df_grouped_zone.to_excel(writer, index=False, sheet_name="Livraisons Client Ville Zone")
        buf.seek(0)
        st.download_button("💾 Télécharger Livraisons Client/Ville/Zone", data=buf, file_name="Livraisons_Client_Ville_Zone.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

with tab_zone_summary:
    st.subheader("Besoin Estafette par Zone")
    if st.session_state.df_zone is not None:
        show_df(st.session_state.df_zone, use_container_width=True)
        buf = BytesIO()
        with pd.ExcelWriter(buf, engine='openpyxl') as writer:
            st.session_state.df_zone.to_excel(writer, index=False, sheet_name="Besoin Estafette Zone")
        buf.seek(0)
        st.download_button("💾 Télécharger Besoin par Zone", data=buf, file_name="Besoin_Estafette_Zone.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

with tab_charts:
    st.subheader("Graphiques")
    if st.session_state.df_city is not None and not st.session_state.df_city.empty:
        col1, col2 = st.columns(2)
        with col1:
            st.plotly_chart(px.bar(st.session_state.df_city, x="Ville", y="Poids total", title="Poids total livré par ville"), use_container_width=True)
        with col2:
            st.plotly_chart(px.bar(st.session_state.df_city, x="Ville", y="Volume total", title="Volume total livré par ville (m³)"), use_container_width=True)

st.markdown("---")

# =====================================================
# 3. Proposition de location de camion
# =====================================================
st.header("3. 🚚 Proposition de location de camion")
st.markdown(f"🔸 Si un client dépasse **{SEUIL_POIDS} kg** ou **{SEUIL_VOLUME} m³**, une location est proposée (si non déjà décidée).")

if st.session_state.rental_processor:
    update_propositions_view()

if st.session_state.propositions is not None and not st.session_state.propositions.empty:
    col_prop, col_details = st.columns([2, 3])
    with col_prop:
        st.markdown("### Propositions ouvertes")
        # show_df expects dataframe; ensure column 'Client' exists
        df_props = st.session_state.propositions.copy()
        if "Client" not in df_props.columns and "Client de l'estafette" in df_props.columns:

            df_props = df_props.rename(columns={"Client de l'estafette": "Client"})
        show_df(df_props[["Client", "Poids total (kg)" , "Volume total (m³)", "Raison"]], use_container_width=True)
        client_options = [""] + df_props['Client'].astype(str).tolist()
        default_index = 0
        if st.session_state.selected_client in client_options:
            default_index = client_options.index(st.session_state.selected_client)
        else:
            if len(client_options) > 1:
                default_index = 1
        st.session_state.selected_client = st.selectbox("Client à traiter :", client_options, index=default_index, key='client_select')

        col_btn_acc, col_btn_ref = st.columns(2)
        is_client_selected = st.session_state.selected_client not in (None, "", [])
        with col_btn_acc:
            st.button("✅ Accepter la location", on_click=accept_location_callback, disabled=not is_client_selected, use_container_width=True)
        with col_btn_ref:
            st.button("❌ Refuser la proposition", on_click=refuse_location_callback, disabled=not is_client_selected, use_container_width=True)

    with col_details:
        st.markdown("### Détails de la commande client")
        if is_client_selected:
            try:
                resume, details_df = st.session_state.rental_processor.get_details_client(st.session_state.selected_client)
                st.text(resume)
                show_df(details_df, use_container_width=True)
            except Exception as e:
                st.error(f"❌ Erreur lors de la récupération des détails : {str(e)}")
        else:
            st.info("Sélectionnez un client pour afficher les détails.")
else:
    st.success("🎉 Aucune proposition de location de camion en attente de décision.")

st.markdown("---")

# =====================================================
# 4. Voyages par Estafette Optimisé (inclut camions loués)
# =====================================================
st.header("4. 🚐 Voyages par Estafette Optimisé (Inclut Camions Loués)")

if st.session_state.df_optimized_estafettes is not None:
    df_clean = st.session_state.df_optimized_estafettes.loc[:, ~st.session_state.df_optimized_estafettes.columns.duplicated()]
    # s'assurer que c'est le format d'affichage 'Véhicule N°'
    df_display = st.session_state.rental_processor.get_df_result()
    # formatter pour l'affichage
    if "Poids total chargé" in df_display.columns:
        df_display["Poids total chargé"] = df_display["Poids total chargé"].map(lambda x: f"{x:.3f} kg")
    if "Volume total chargé" in df_display.columns:
        df_display["Volume total chargé"] = df_display["Volume total chargé"].map(lambda x: f"{x:.3f} m³")
    if "Taux d'occupation (%)" in df_display.columns:
        df_display["Taux d'occupation (%)"] = df_display["Taux d'occupation (%)"].map(lambda x: f"{x:.3f}%")
    show_df(df_display, use_container_width=True)

    # sauvegarder df_voyages dans session_state si pas déjà
    if "df_voyages" not in st.session_state or st.session_state.df_voyages is None:
        st.session_state.df_voyages = df_display.copy()


    # Export
    df_export = st.session_state.rental_processor.get_df_result().copy()
    # convertir colonnes numériques si présentes
    for col in ["Poids total chargé", "Volume total chargé"]:
        if col in df_export.columns:
            df_export[col] = df_export[col].apply(lambda v: round(float(v), 3) if v != "" and pd.notna(v) else v)
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine='openpyxl') as writer:
        df_export.to_excel(writer, index=False, sheet_name="Voyages Optimisés")
    buf.seek(0)
    st.download_button("💾 Télécharger Voyages Estafette Optimisés", data=buf, file_name="Voyages_Estafette_Optimises.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
else:
    st.info("Exécutez d'abord le traitement des fichiers pour obtenir les voyages optimisés.")

st.markdown("---")

# =====================================================
# 5. TRANSFERT DES BLs ENTRE ESTAFETTES / CAMIONS
# =====================================================
st.markdown("## 🔁 Transfert de BLs entre Estafettes / Camions")

MAX_POIDS = 1550  # kg (estafette)
MAX_VOLUME = 4.608  # m³

if st.session_state.df_voyages is None:
    st.warning("⚠️ Vous devez d'abord exécuter la section 4 (Voyages par Estafette Optimisé).")
elif st.session_state.df_livraisons is None:
    st.warning("⚠️ Le DataFrame des livraisons détaillées n'est pas disponible.")
else:
    df_voyages = st.session_state.df_voyages.copy()
    df_livraisons = st.session_state.df_livraisons.copy()

    colonnes_requises = ["Zone", "Véhicule N°", "Poids total chargé", "Volume total chargé", "BL inclus"]
    if not all(col in df_voyages.columns for col in colonnes_requises):
        st.error(f"❌ Le DataFrame ne contient pas toutes les colonnes nécessaires : {', '.join(colonnes_requises)}")
    else:
        zones_disponibles = sorted(df_voyages["Zone"].dropna().unique().tolist())
        zone_selectionnee = st.selectbox("🌍 Sélectionner une zone", zones_disponibles, index=0 if zones_disponibles else None)

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

                    bls_disponibles = str(df_source["BL inclus"].iloc[0]).split(";")
                    bls_selectionnes = st.multiselect("📋 Sélectionner les BLs à transférer :", bls_disponibles)

                    if bls_selectionnes and st.button("🔁 Exécuter le transfert"):
                        # calcul poids/volume selectionnés
                        df_bls_selection = df_livraisons[df_livraisons["No livraison"].isin(bls_selectionnes)]
                        poids_bls = float(df_bls_selection["Poids total"].sum())
                        volume_bls = float(df_bls_selection["Volume total"].sum())

                        df_cible = df_zone[df_zone["Véhicule N°"] == cible]
                        poids_cible = float(df_cible["Poids total chargé"].sum())
                        volume_cible = float(df_cible["Volume total chargé"].sum())

                        if (poids_cible + poids_bls) > MAX_POIDS or (volume_cible + volume_bls) > MAX_VOLUME:
                            st.warning("⚠️ Le transfert dépasse les limites de poids ou volume du véhicule cible.")
                        else:
                            # appliquer transfert
                            def transfer_bl(row):
                                bls = str(row["BL inclus"]).split(";") if pd.notna(row["BL inclus"]) else []
                                bls_to_move = [b for b in bls if b in bls_selectionnes]
                                if row["Véhicule N°"] == source:
                                    new_bls = [b for b in bls if b not in bls_to_move]
                                    row["BL inclus"] = ";".join(new_bls)
                                    row["Poids total chargé"] = max(0, float(row["Poids total chargé"]) - poids_bls)
                                    row["Volume total chargé"] = max(0, float(row["Volume total chargé"]) - volume_bls)
                                elif row["Véhicule N°"] == cible:
                                    new_bls = bls + bls_to_move
                                    row["BL inclus"] = ";".join(new_bls)
                                    row["Poids total chargé"] = float(row["Poids total chargé"]) + poids_bls
                                    row["Volume total chargé"] = float(row["Volume total chargé"]) + volume_bls
                                return row

                            df_voyages = df_voyages.apply(transfer_bl, axis=1)
                            st.session_state.df_voyages = df_voyages
                            st.success(f"✅ Transfert réussi : {len(bls_selectionnes)} BL(s) déplacé(s) de {source} vers {cible}.")

                            # affichage résultat
                            st.subheader("📊 Voyages après transfert (toutes les zones)")
                            df_display_after = df_voyages.sort_values(by=["Zone", "Véhicule N°"]).copy()
                            df_display_after["Poids total chargé"] = df_display_after["Poids total chargé"].map(lambda x: f"{x:.3f} kg")
                            df_display_after["Volume total chargé"] = df_display_after["Volume total chargé"].map(lambda x: f"{x:.3f} m³")
                            show_df(df_display_after[["Zone", "Véhicule N°", "Poids total chargé", "Volume total chargé", "BL inclus"]], use_container_width=True)

                            # export
                            buf = BytesIO()
                            df_export = df_voyages.copy()
                            with pd.ExcelWriter(buf, engine='openpyxl') as writer:
                                df_export.to_excel(writer, index=False, sheet_name='Transfert BLs')
                            buf.seek(0)
                            st.download_button("💾 Télécharger le tableau mis à jour (XLSX)", data=buf, file_name="voyages_apres_transfert.xlsx", mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

st.markdown("---")

# =====================================================
# 5.5 AJOUT D'UN OBJET MANUEL (nouvelle section)
# =====================================================
st.markdown("## ➕ Ajouter un objet manuel dans un véhicule (machine / colis / BL manuel)")
st.markdown("Ajoutez un objet (désignation, poids, volume) dans un véhicule existant. **L'objet restera dans le véhicule**. L'ajout est refusé si capacité dépassée.")

if st.session_state.df_voyages is None:
    st.info("⚠️ Exécutez d'abord le traitement pour obtenir la liste des voyages (section 4).")
else:
    df_v = st.session_state.df_voyages.copy()
    # Normaliser colonnes pour être sûr d'avoir 'Véhicule N°' et 'Zone'
    if "Véhicule N°" not in df_v.columns and "Camion N°" in df_v.columns:
        df_v = df_v.rename(columns={"Camion N°": "Véhicule N°"})
    if "Zone" not in df_v.columns:
        st.error("Le DataFrame des voyages ne contient pas la colonne 'Zone'.")

    zones = sorted(df_v["Zone"].dropna().unique().tolist())
    col_z, col_v = st.columns([1, 1])
    with col_z:
        zone_for_obj = st.selectbox("🌍 Zone", options=zones) if zones else None
    with col_v:
        vehicles_in_zone = sorted(df_v[df_v["Zone"] == zone_for_obj]["Véhicule N°"].dropna().unique().tolist()) if zone_for_obj else []
        vehicle_for_obj = st.selectbox("🚐 Véhicule cible", options=vehicles_in_zone) if vehicles_in_zone else None

    name_obj = st.text_input("🏷️ Désignation de l'objet (ex: Machine X)")
    weight_obj = st.number_input("⚖️ Poids (kg)", min_value=0.0, step=0.1, format="%.3f")
    volume_obj = st.number_input("📦 Volume (m³)", min_value=0.0, step=0.001, format="%.3f")

    if st.button("✅ Ajouter l'objet dans le véhicule"):
        if not zone_for_obj or not vehicle_for_obj:
            st.warning("⚠️ Sélectionnez la zone et le véhicule cible.")
        elif not name_obj or weight_obj <= 0 or volume_obj <= 0:
            st.warning("⚠️ Remplissez correctement la désignation, le poids et le volume (supérieurs à 0).")
        else:
            # Appeler la méthode backend
            try:
                # appeler via rental_processor pour bénéficier de la synchronisation automatique
                rp = st.session_state.rental_processor
                if rp is None:
                    st.error("❌ rental_processor non initialisé.")
                else:
                    success, message, df_updated = rp.add_manual_object(st.session_state.df_voyages, vehicle_for_obj, zone_for_obj, name_obj, weight_obj, volume_obj)
                    if success:
                        # Mettre à jour st.session_state.df_voyages avec le df retourné
                        st.session_state.df_voyages = df_updated.copy()
                        # essayer de synchroniser rental_processor.df_base si nécessaire (déjà tenté dans la fonction)
                        # Mettre message de succès
                        st.success(message)
                    else:
                        st.error(message)
            except Exception as e:
                st.error(f"❌ Erreur lors de l'ajout : {e}")

# Afficher un tableau minimal des objets ajoutés (recherche OBJ- prefix)
if st.session_state.df_voyages is not None:
    df_check = st.session_state.df_voyages.copy()
    # chercher BLs contenant OBJ-
    df_check["Objects Added"] = df_check["BL inclus"].apply(lambda s: ";".join([b for b in str(s).split(";") if b.startswith("OBJ-")]) if pd.notna(s) else "")
    # afficher lignes avec objets
    df_objs = df_check[df_check["Objects Added"].astype(str).str.strip() != ""]
    if not df_objs.empty:
        st.markdown("### 📦 Objets manuels présents dans les véhicules")
        df_show_objs = df_objs[["Zone", "Véhicule N°", "Objects Added", "Poids total chargé", "Volume total chargé", "Taux d'occupation (%)"]].copy()
        if "Poids total chargé" in df_show_objs.columns:
            df_show_objs["Poids total chargé"] = df_show_objs["Poids total chargé"].map(lambda x: f"{x:.3f} kg")
        if "Volume total chargé" in df_show_objs.columns:
            df_show_objs["Volume total chargé"] = df_show_objs["Volume total chargé"].map(lambda x: f"{x:.3f} m³")
        show_df(df_show_objs, use_container_width=True)

st.markdown("---")

# =====================================================
# 6. VALIDATION DES VOYAGES APRÈS TRANSFERT
# =====================================================
st.markdown("## ✅ VALIDATION DES VOYAGES APRÈS TRANSFERT")

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

if "df_voyages" in st.session_state and st.session_state.df_voyages is not None:
    voyages_apres_transfert = st.session_state.df_voyages.copy()
    df_validation = voyages_apres_transfert.copy()

    # initialiser validations si besoin
    if "validations" not in st.session_state:
        st.session_state.validations = {}

    for idx, row in df_validation.reset_index().iterrows():
        # utiliser 'index' réel pour mapping
        real_idx = row['index']
        with st.expander(f"🚚 Voyage {row['Véhicule N°']} | Zone : {row['Zone']}"):
            row_display = row.drop(labels=["index"]).to_frame().T.copy()
            if "Poids total chargé" in row_display.columns:
                row_display["Poids total chargé"] = row_display["Poids total chargé"].map(lambda x: f"{x:.3f} kg")
            if "Volume total chargé" in row_display.columns:
                row_display["Volume total chargé"] = row_display["Volume total chargé"].map(lambda x: f"{x:.3f} m³")
            show_df(row_display, use_container_width=True)

            choix = st.radio(
                f"Valider ce voyage ? (Véhicule {row['Véhicule N°']})",
                ["Oui", "Non"],
                index=0 if st.session_state.validations.get(real_idx) == "Oui" else 1 if st.session_state.validations.get(real_idx) == "Non" else 0,
                key=f"validation_{real_idx}"
            )
            st.session_state.validations[real_idx] = choix

    if st.button("🧮 Appliquer la validation"):
        valid_indexes = [i for i, v in st.session_state.validations.items() if v == "Oui"]
        valid_indexes = [i for i in valid_indexes if i in df_validation.reset_index()["index"].tolist()]
        df_voyages_valides = df_validation.reset_index().set_index("index").loc[valid_indexes].reset_index(drop=True)
        st.session_state.df_voyages_valides = df_voyages_valides
        st.success(f"✅ {len(df_voyages_valides)} voyage(s) validé(s).")
        st.markdown("### 📦 Voyages Validés")
        df_show = df_voyages_valides.copy()
        if "Poids total chargé" in df_show.columns:
            df_show["Poids total chargé"] = df_show["Poids total chargé"].map(lambda x: f"{x:.3f} kg")
        if "Volume total chargé" in df_show.columns:
            df_show["Volume total chargé"] = df_show["Volume total chargé"].map(lambda x: f"{x:.3f} m³")
        show_df(df_show, use_container_width=True)
        excel_data = to_excel(df_voyages_valides)
        st.download_button("💾 Télécharger les voyages validés (XLSX)", data=excel_data, file_name="Voyages_valides.xlsx", mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
else:
    st.warning("⚠️ Vous devez d'abord exécuter la section 4 (Voyages par Estafette Optimisé).")

st.markdown("---")

# =====================================================
# 7. Attribution des véhicules et chauffeurs
# =====================================================
st.markdown("## 🚛 ATTRIBUTION DES VÉHICULES ET CHAUFFEURS")

VEHICULES_DISPONIBLES = [
    'SLG-VEH11', 'SLG-VEH14', 'SLG-VEH22', 'SLG-VEH19',
    'SLG-VEH10', 'SLG-VEH16', 'SLG-VEH23', 'SLG-VEH08', 'SLG-VEH20', 'code-Camion'
]
CHAUFFEURS_DETAILS = {
    '09254': 'DAMMAK Karim', '06002': 'MAAZOUN Bassem', '11063': 'SASSI Ramzi',
    '10334': 'BOUJELBENE Mohamed', '15144': 'GADDOUR Rami', '08278': 'DAMMAK Wissem',
    '18339': 'REKIK Ahmed', '07250': 'BARKIA Mustapha', '13321': 'BADRI Moez', 'Matricule': 'Chauffeur Camion'
}

if 'df_voyages_valides' in st.session_state and st.session_state.df_voyages_valides is not None and not st.session_state.df_voyages_valides.empty:
    df_attribution = st.session_state.df_voyages_valides.copy()

    if "attributions" not in st.session_state:
        st.session_state.attributions = {}

    for idx, row in df_attribution.reset_index().iterrows():
        real_idx = row['index']
        with st.expander(f"🚚 Voyage {row['Véhicule N°']} | Zone : {row['Zone']}"):
            row_display = row.drop(labels=["index"]).to_frame().T.copy()
            if "Poids total chargé" in row_display.columns:
                row_display["Poids total chargé"] = row_display["Poids total chargé"].map(lambda x: f"{x:.2f} kg")
            if "Volume total chargé" in row_display.columns:
                row_display["Volume total chargé"] = row_display["Volume total chargé"].map(lambda x: f"{x:.3f} m³")
            show_df(row_display, use_container_width=True)

            vehicule_selectionne = st.selectbox(f"Véhicule pour le voyage {row['Véhicule N°']}", VEHICULES_DISPONIBLES, key=f"vehicule_{real_idx}")
            chauffeur_selectionne = st.selectbox(f"Chauffeur pour le voyage {row['Véhicule N°']}", list(CHAUFFEURS_DETAILS.values()), key=f"chauffeur_{real_idx}")

            st.session_state.attributions[real_idx] = {
                "Véhicule": vehicule_selectionne,
                "Chauffeur": chauffeur_selectionne
            }

    if st.button("✅ Appliquer les attributions"):
        df_attrib_copy = df_attribution.copy().reset_index(drop=True)
        df_attrib_copy["Véhicule attribué"] = df_attrib_copy.index.map(lambda i: st.session_state.attributions.get(i, {}).get("Véhicule"))
        df_attrib_copy["Chauffeur attribué"] = df_attrib_copy.index.map(lambda i: st.session_state.attributions.get(i, {}).get("Chauffeur"))
        st.markdown("### 📦 Voyages avec Véhicule et Chauffeur")
        df_display = df_attrib_copy.copy()
        if "Poids total chargé" in df_display.columns:
            df_display["Poids total chargé"] = df_display["Poids total chargé"].map(lambda x: f"{x:.3f} kg")
        if "Volume total chargé" in df_display.columns:
            df_display["Volume total chargé"] = df_display["Volume total chargé"].map(lambda x: f"{x:.3f} m³")
        show_df(df_display, use_container_width=True)

        # download xlsx & pdf
        buf = BytesIO()
        with pd.ExcelWriter(buf, engine='openpyxl') as writer:
            df_display.to_excel(writer, index=False, sheet_name='Voyages_Attribués')
        buf.seek(0)
        st.download_button("💾 Télécharger le tableau final (XLSX)", data=buf, file_name="Voyages_attribues.xlsx", mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

else:
    st.info("Validez des voyages pour activer l'attribution de véhicules et chauffeurs.")

st.markdown("---")
st.info("Fichier app.py chargé — interface prête. Teste avec un petit jeu de données pour vérifier l'ajout d'objets manuels et les contrôles de capacité.")
