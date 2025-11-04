import streamlit as st
import pandas as pd
from backend import DeliveryProcessor, TruckRentalProcessor, TruckTransferManager, SEUIL_POIDS, SEUIL_VOLUME
import plotly.express as px

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
        # Eviter d'appeler round sur colonnes non-numériques : on essaie, sinon on ignore
        try:
            df_to_display = df_to_display.round(3)
        except Exception:
            pass
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
    st.session_state.rental_processor = None  # Objet de traitement de location
    st.session_state.propositions = None  # Dataframe de propositions
    st.session_state.selected_client = None  # Client sélectionné
    st.session_state.message = ""  # Message de résultat d'opération

# =====================================================
# Fonctions de Callback pour la Location
# =====================================================

def normalize_propositions_df(df):
    """
    Normalise le DataFrame de propositions pour garantir la colonne 'Client'
    et colonnes attendues ("Poids total (kg)", "Volume total (m³)", "Raison").
    """
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.copy()
    # Si la colonne est "Client de l'estafette", la renommer
    if "Client de l'estafette" in df.columns and "Client" not in df.columns:
        df.rename(columns={"Client de l'estafette": "Client"}, inplace=True)
    # Si colonne poids/volume sans unité, essayer de normaliser
    if "Poids total" in df.columns and "Poids total (kg)" not in df.columns:
        df.rename(columns={"Poids total": "Poids total (kg)"}, inplace=True)
    if "Volume total" in df.columns and "Volume total (m³)" not in df.columns:
        df.rename(columns={"Volume total": "Volume total (m³)"}, inplace=True)
    # Assurer les colonnes présentes
    for col in ["Client", "Poids total (kg)", "Volume total (m³)", "Raison"]:
        if col not in df.columns:
            df[col] = ""
    return df

def update_propositions_view():
    """Met à jour le DataFrame de propositions après une action."""
    if st.session_state.rental_processor is None:
        st.session_state.propositions = pd.DataFrame()
        return

    try:
        props = st.session_state.rental_processor.detecter_propositions()
        props = normalize_propositions_df(props)
        st.session_state.propositions = props
    except Exception as e:
        st.error(f"Erreur lors de la mise à jour des propositions : {e}")
        st.session_state.propositions = pd.DataFrame()

    # Réinitialiser la sélection si le client n'est plus dans les propositions ouvertes
    try:
        if (st.session_state.selected_client is not None and
            isinstance(st.session_state.propositions, pd.DataFrame) and
            st.session_state.selected_client not in st.session_state.propositions['Client'].astype(str).tolist()):
            st.session_state.selected_client = None
    except Exception:
        st.session_state.selected_client = None

def handle_location_action(accept):
    """
    Appliquer ou refuser la proposition pour le client sélectionné.
    Met à jour l'état, les propositions et le DataFrame des voyages.
    """
    client = st.session_state.selected_client
    if not client:
        st.session_state.message = "⚠️ Aucun client sélectionné."
        return

    if st.session_state.rental_processor is None:
        st.session_state.message = "⚠️ Le processeur de location n'est pas initialisé."
        return

    try:
        ok, msg, _ = st.session_state.rental_processor.appliquer_location(client, accept)
        # appliquer_location retourne (bool, message, df_propositions) dans nos implémentations précédentes
        st.session_state.message = msg if isinstance(msg, str) else str(msg)
    except Exception as e:
        st.session_state.message = f"❌ Erreur pendant l'opération de location : {e}"

    # Mettre à jour la vue des propositions et le DF des voyages affichés
    update_propositions_view()

    # Mettre à jour df_optimized_estafettes stocké (get_df_result)
    try:
        st.session_state.df_optimized_estafettes = st.session_state.rental_processor.get_df_result()
    except Exception:
        # si pb, ne pas planter l'app
        pass

    # Réinitialiser la sélection
    st.session_state.selected_client = ""

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
    st.markdown("<br>", unsafe_allow_html=True)  # Petit espace
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

                # Initialisation du processeur de location (ici on l'instancie après les DF)
                try:
                    st.session_state.rental_processor = TruckRentalProcessor(
                        df_optimized_estafettes,
                        st.session_state.df_grouped_zone
                    )
                except Exception as e:
                    st.error(f"❌ Erreur lors de l'initialisation du processeur de location : {e}")
                    st.session_state.rental_processor = None

                # Mise à jour des propositions
                update_propositions_view()

                st.session_state.data_processed = True
                st.session_state.message = "Traitement terminé avec succès ! Les résultats s'affichent ci-dessous."
                st.experimental_rerun()  # rerun pour afficher les résultats immédiatement

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

    # Récupération du DF mis à jour à chaque fois (depuis session_state)
    # On protège l'accès si la clef n'existe pas encore
    if "rental_processor" in st.session_state and st.session_state.rental_processor is not None:
        try:
            # Mettre à jour st.session_state.df_optimized_estafettes si get_df_result renvoie quelque chose de nouveau
            st.session_state.df_optimized_estafettes = st.session_state.rental_processor.get_df_result()
        except Exception:
            pass

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
    if st.session_state.df_grouped is not None:
        show_df(st.session_state.df_grouped.drop(columns=["Zone"], errors='ignore'), use_container_width=True)
        # Stockage du DataFrame pour la section 5 (transfert BLs)
        if "df_livraisons" not in st.session_state:
            st.session_state.df_livraisons = st.session_state.df_grouped.copy()
    else:
        st.info("Uploadez les fichiers et exécutez le traitement pour afficher ce tableau.")

# --- Onglet Besoin Estafette par Ville ---
with tab_city:
    st.subheader("Besoin Estafette par Ville")
    if st.session_state.df_city is not None:
        show_df(st.session_state.df_city, use_container_width=True)
    else:
        st.info("Données manquantes pour afficher ce tableau.")

# --- Onglet Livraisons Client & Ville + Zone ---
with tab_zone_group:
    st.subheader("Livraisons par Client & Ville + Zone")
    if st.session_state.df_grouped_zone is not None:
        show_df(st.session_state.df_grouped_zone, use_container_width=True)
    else:
        st.info("Données manquantes pour afficher ce tableau.")

# --- Onglet Besoin Estafette par Zone ---
with tab_zone_summary:
    st.subheader("Besoin Estafette par Zone")
    if st.session_state.df_zone is not None:
        show_df(st.session_state.df_zone, use_container_width=True)
    else:
        st.info("Données manquantes pour afficher ce tableau.")

# --- Onglet Graphiques ---
with tab_charts:
    st.subheader("Statistiques par Ville")
    if st.session_state.df_city is not None:
        col1, col2 = st.columns(2)
        with col1:
            st.plotly_chart(
                px.bar(st.session_state.df_city, x="Ville", y="Poids total",
                       title="Poids total livré par ville"),
                use_container_width=True
            )
        with col2:
            st.plotly_chart(
                px.bar(st.session_state.df_city, x="Ville", y="Volume total",
                       title="Volume total livré par ville (m³)"),
                use_container_width=True
            )

        col3, col4 = st.columns(2)
        with col3:
            st.plotly_chart(
                px.bar(st.session_state.df_city, x="Ville", y="Nombre livraisons",
                       title="Nombre de livraisons par ville"),
                use_container_width=True
            )
        with col4:
            st.plotly_chart(
                px.bar(st.session_state.df_city, x="Ville", y="Besoin estafette réel",
                       title="Besoin en Estafettes par ville"),
                use_container_width=True
            )
    else:
        st.info("Données manquantes pour générer les graphiques.")

st.markdown("---")

# =====================================================
# 🔧 Initialisation du processeur de location (si nécessaire)
# =====================================================
# Si les données sont traitées mais le processeur non initialisé, on l'initialise ici
if st.session_state.data_processed and (st.session_state.rental_processor is None):
    try:
        st.session_state.rental_processor = TruckRentalProcessor(
            st.session_state.df_optimized_estafettes,
            st.session_state.df_grouped_zone
        )
        update_propositions_view()
    except Exception as e:
        st.error(f"❌ Erreur lors de l'initialisation du processeur de location : {e}")
        st.session_state.rental_processor = None

# =====================================================
# 3. PROPOSITION DE LOCATION DE CAMION (Section 3)
# =====================================================
st.header("3. 🚚 Proposition de location de camion")
st.markdown(f"🔸 Si un client dépasse **{SEUIL_POIDS} kg** ou **{SEUIL_VOLUME} m³**, une location est proposée (si non déjà décidée).")

# On protège l'accès à st.session_state.propositions
props = st.session_state.propositions if "propositions" in st.session_state else pd.DataFrame()
props = normalize_propositions_df(props)

if not props.empty:
    col_prop, col_details = st.columns([2, 3])

    with col_prop:
        st.markdown("### Propositions ouvertes")

        # Affichage des propositions
        show_df(
            props[["Client", "Poids total (kg)", "Volume total (m³)", "Raison"]]
            .drop_duplicates(subset=["Client"], keep="first").reset_index(drop=True),
            use_container_width=True,
            hide_index=True
        )

        # Liste des clients à décider (unique)
        client_options = props['Client'].astype(str).unique().tolist()
        client_options_with_empty = [""] + list(client_options)

        default_index = 0
        if st.session_state.selected_client in client_options:
            default_index = client_options_with_empty.index(st.session_state.selected_client)
        elif len(client_options) > 0:
            default_index = 1

        st.session_state.selected_client = st.selectbox(
            "Client à traiter :",
            options=client_options_with_empty,
            index=default_index,
            key="client_select"
        )

        is_client_selected = st.session_state.selected_client != ""

        col_btn_acc, col_btn_ref = st.columns(2)
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

    # Détails du client sélectionné
    with col_details:
        st.markdown("### Détails de la commande client")

        if is_client_selected:
            try:
                resume, details_df = st.session_state.rental_processor.get_details_client(
                    st.session_state.selected_client
                )
                st.text(resume)
                # Affichage sécurisé
                if isinstance(details_df, pd.DataFrame) and not details_df.empty:
                    show_df(details_df, use_container_width=True, hide_index=True)
                else:
                    st.info("Pas de détails disponibles pour ce client.")
            except Exception as e:
                st.error(f"Erreur lors de la récupération des détails client : {e}")
        else:
            st.info("Sélectionnez un client pour afficher les détails de la commande/estafettes.")
else:
    st.success("🎉 Aucune proposition de location de camion en attente de décision.")

st.markdown("---")

# =====================================================
# 4. VOYAGES PAR ESTAFETTE OPTIMISÉ (Section 4 - Résultat final)
# =====================================================
st.header("4. 🚐 Voyages par Estafette Optimisé (Inclut Camions Loués)")

# --- Utiliser st.session_state.df_optimized_estafettes (protégé) ---
if "df_optimized_estafettes" in st.session_state and st.session_state.df_optimized_estafettes is not None:
    df_display = st.session_state.df_optimized_estafettes.copy()

    # Normaliser noms de colonnes possibles
    if "Poids total" in df_display.columns and "Poids total chargé" not in df_display.columns:
        df_display.rename(columns={"Poids total": "Poids total chargé"}, inplace=True)
    if "Volume total" in df_display.columns and "Volume total chargé" not in df_display.columns:
        df_display.rename(columns={"Volume total": "Volume total chargé"}, inplace=True)
    if "Client commande" in df_display.columns and "Client(s) inclus" not in df_display.columns:
        df_display.rename(columns={"Client commande": "Client(s) inclus"}, inplace=True)

    # ajouter formats si colonnes présentes
    if "Poids total chargé" in df_display.columns:
        try:
            df_display["Poids total chargé"] = df_display["Poids total chargé"].map(lambda x: f"{float(x):.3f} kg")
        except Exception:
            pass
    if "Volume total chargé" in df_display.columns:
        try:
            df_display["Volume total chargé"] = df_display["Volume total chargé"].map(lambda x: f"{float(x):.3f} m³")
        except Exception:
            pass
    if "Taux d'occupation (%)" in df_display.columns:
        try:
            df_display["Taux d'occupation (%)"] = df_display["Taux d'occupation (%)"].map(lambda x: f"{float(x):.3f}%")
        except Exception:
            pass

    show_df(df_display, use_container_width=True)
else:
    st.info("Aucun voyage optimisé disponible — exécutez d'abord le traitement (Section 1).")

# --- Préparer un DataFrame pour export Excel (protégé) ---
if "df_optimized_estafettes" in st.session_state and st.session_state.df_optimized_estafettes is not None:
    df_export = st.session_state.df_optimized_estafettes.copy()
    if "Poids total chargé" not in df_export.columns and "Poids total" in df_export.columns:
        df_export = df_export.rename(columns={"Poids total": "Poids total chargé"})
    if "Volume total chargé" not in df_export.columns and "Volume total" in df_export.columns:
        df_export = df_export.rename(columns={"Volume total": "Volume total chargé"})

    try:
        df_export["Poids total chargé"] = df_export["Poids total chargé"].astype(float).round(3)
    except Exception:
        pass
    try:
        df_export["Volume total chargé"] = df_export["Volume total chargé"].astype(float).round(3)
    except Exception:
        pass

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

    # Mise à jour dans session_state pour la section 5
    st.session_state.df_voyages = st.session_state.df_optimized_estafettes
else:
    # sécurité : pas de df_voyages si pas de df_optimized_estafettes
    st.session_state.df_voyages = st.session_state.get("df_voyages", pd.DataFrame())

# =====================================================
# 5️⃣ TRANSFERT DES BLs ENTRE ESTAFETTES / CAMIONS
# =====================================================
st.markdown("## 🔁 Transfert de BLs entre Estafettes / Camions")

MAX_POIDS = 1550  # kg
MAX_VOLUME = 4.608  # m³

if "df_voyages" not in st.session_state or st.session_state.df_voyages is None or st.session_state.df_voyages.empty:
    st.warning("⚠️ Vous devez d'abord exécuter la section 3 (résultat final après location).")
elif "df_livraisons" not in st.session_state or st.session_state.df_livraisons is None:
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

                    # --- Affichage formaté pour Streamlit ---
                    df_source_display = df_source[["Véhicule N°", "Poids total chargé", "Volume total chargé", "BL inclus"]].copy()
                    try:
                        df_source_display["Poids total chargé"] = df_source_display["Poids total chargé"].map(lambda x: f"{float(x):.3f} kg")
                    except Exception:
                        pass
                    try:
                        df_source_display["Volume total chargé"] = df_source_display["Volume total chargé"].map(lambda x: f"{float(x):.3f} m³")
                    except Exception:
                        pass
                    show_df(df_source_display, use_container_width=True)

                    bls_disponibles = []
                    try:
                        bls_disponibles = df_source["BL inclus"].iloc[0].split(";")
                    except Exception:
                        bls_disponibles = []
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
                                    try:
                                        row["Poids total chargé"] = max(0, float(row["Poids total chargé"]) - poids_bls)
                                    except Exception:
                                        pass
                                    try:
                                        row["Volume total chargé"] = max(0, float(row["Volume total chargé"]) - volume_bls)
                                    except Exception:
                                        pass
                                elif row["Véhicule N°"] == cible:
                                    new_bls = bls + bls_to_move
                                    row["BL inclus"] = ";".join(new_bls)
                                    try:
                                        row["Poids total chargé"] = float(row["Poids total chargé"]) + poids_bls
                                    except Exception:
                                        pass
                                    try:
                                        row["Volume total chargé"] = float(row["Volume total chargé"]) + volume_bls
                                    except Exception:
                                        pass
                                return row

                            df_voyages = df_voyages.apply(transfer_bl, axis=1)
                            st.session_state.df_voyages = df_voyages
                            st.success(f"✅ Transfert réussi : {len(bls_selectionnes)} BL(s) déplacé(s) de {source} vers {cible}.")

                            # --- Affichage Streamlit ---
                            st.subheader("📊 Voyages après transfert (toutes les zones)")
                            df_display = df_voyages.sort_values(by=["Zone", "Véhicule N°"]).copy()
                            try:
                                df_display["Poids total chargé"] = df_display["Poids total chargé"].map(lambda x: f"{float(x):.3f} kg")
                            except Exception:
                                pass
                            try:
                                df_display["Volume total chargé"] = df_display["Volume total chargé"].map(lambda x: f"{float(x):.3f} m³")
                            except Exception:
                                pass
                            show_df(df_display[colonnes_requises], use_container_width=True)

                            # --- Export Excel arrondi ---
                            df_export = df_voyages.copy()
                            try:
                                df_export["Poids total chargé"] = df_export["Poids total chargé"].astype(float).round(3)
                            except Exception:
                                pass
                            try:
                                df_export["Volume total chargé"] = df_export["Volume total chargé"].astype(float).round(3)
                            except Exception:
                                pass

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
        try:
            df_export["Poids total chargé"] = df_export["Poids total chargé"].astype(float).round(3)
        except Exception:
            pass
    if "Volume total chargé" in df_export.columns:
        try:
            df_export["Volume total chargé"] = df_export["Volume total chargé"].astype(float).round(3)
        except Exception:
            pass

    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_export.to_excel(writer, index=False, sheet_name=sheet_name)
    return output.getvalue()

# --- Création du DataFrame de validation à partir du df_voyages ---
voyages_apres_transfert = st.session_state.get("df_voyages", pd.DataFrame()).copy()
df_validation = voyages_apres_transfert.copy()

if "validations" not in st.session_state:
    st.session_state.validations = {}

# --- Affichage interactif des voyages ---
for idx, row in df_validation.iterrows():
    with st.expander(f"🚚 Voyage {row['Véhicule N°']} | Zone : {row['Zone']}"):
        st.write("**Informations du voyage :**")
        row_display = row.to_frame().T.copy()
        if "Poids total chargé" in row_display.columns:
            try:
                row_display["Poids total chargé"] = row_display["Poids total chargé"].map(lambda x: f"{float(x):.3f} kg")
            except Exception:
                pass
        if "Volume total chargé" in row_display.columns:
            try:
                row_display["Volume total chargé"] = row_display["Volume total chargé"].map(lambda x: f"{float(x):.3f} m³")
            except Exception:
                pass
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
        try:
            df_display["Poids total chargé"] = df_display["Poids total chargé"].map(lambda x: f"{float(x):.3f} kg")
        except Exception:
            pass
    if "Volume total chargé" in df_display.columns:
        try:
            df_display["Volume total chargé"] = df_display["Volume total chargé"].map(lambda x: f"{float(x):.3f} m³")
        except Exception:
            pass
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
                try:
                    row_display["Poids total chargé"] = row_display["Poids total chargé"].map(lambda x: f"{float(x):.2f} kg")
                except Exception:
                    pass
            if "Volume total chargé" in row_display.columns:
                try:
                    row_display["Volume total chargé"] = row_display["Volume total chargé"].map(lambda x: f"{float(x):.3f} m³")
                except Exception:
                    pass
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
            try:
                df_display["Poids total chargé"] = df_display["Poids total chargé"].map(lambda x: f"{float(x):.3f} kg")
            except Exception:
                pass
        if "Volume total chargé" in df_display.columns:
            try:
                df_display["Volume total chargé"] = df_display["Volume total chargé"].map(lambda x: f"{float(x):.3f} m³")
            except Exception:
                pass
        show_df(df_display, use_container_width=True)

        # --- Export Excel ---
        from io import BytesIO
        def to_excel_final(df):
            df_export = df.copy()
            if "Poids total chargé" in df_export.columns:
                try:
                    df_export["Poids total chargé"] = df_export["Poids total chargé"].astype(float).round(3)
                except Exception:
                    pass
            if "Volume total chargé" in df_export.columns:
                try:
                    df_export["Volume total chargé"] = df_export["Volume total chargé"].astype(float).round(3)
                except Exception:
                    pass
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_export.to_excel(writer, index=False, sheet_name='Voyages_Attribués')
            return output.getvalue()

        st.download_button(
            label="💾 Télécharger le tableau final (XLSX)",
            data=to_excel_final(df_attribution),
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
                try:
                    df_pdf["Poids total chargé"] = df_pdf["Poids total chargé"].map(lambda x: f"{float(x):.3f} kg")
                except Exception:
                    pass
            if "Volume total chargé" in df_pdf.columns:
                try:
                    df_pdf["Volume total chargé"] = df_pdf["Volume total chargé"].map(lambda x: f"{float(x):.3f} m³")
                except Exception:
                    pass

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
