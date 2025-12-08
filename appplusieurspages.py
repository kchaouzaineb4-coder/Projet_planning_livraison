import streamlit as st
import pandas as pd
import plotly.express as px
from io import BytesIO
from backend import DeliveryProcessor, TruckRentalProcessor, TruckTransferManager, SEUIL_POIDS, SEUIL_VOLUME

# =====================================================
# CONFIGURATION DE LA PAGE ET CSS GLOBAL
# =====================================================
st.set_page_config(
    page_title="🚚 Planning de Livraisons",
    page_icon="🚚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS global pour toute l'application
st.markdown("""
<style>
    /* Navigation sidebar */
    [data-testid="stSidebarNav"] {
        padding-top: 20px;
    }
    
    /* Style des liens de navigation */
    [data-testid="stSidebarNav"] a {
        padding: 10px 15px;
        margin: 5px 0;
        border-radius: 8px;
        display: flex;
        align-items: center;
        gap: 10px;
        font-weight: 500;
        transition: all 0.3s ease;
    }
    
    [data-testid="stSidebarNav"] a:hover {
        background-color: #E6F3FF;
        color: #0369A1;
    }
    
    /* En-tête principal */
    .main-header {
        font-size: 2.5rem;
        color: #1E3A8A;
        text-align: center;
        margin-bottom: 1rem;
        padding-bottom: 1rem;
        border-bottom: 3px solid #1E3A8A;
    }
    
    /* Cartes de métriques */
    .metric-card {
        background: linear-gradient(135deg, #F8FAFC 0%, #EFF6FF 100%);
        padding: 1.5rem;
        border-radius: 10px;
        border-left: 5px solid #0369A1;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    
    /* Tables */
    .custom-table {
        width: 100%;
        border-collapse: collapse;
        font-family: Arial, sans-serif;
        font-size: 14px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        border-radius: 8px;
        overflow: hidden;
    }
    
    .custom-table th {
        background-color: #0369A1;
        color: white;
        padding: 12px 8px;
        text-align: center;
        border: 2px solid #4682B4;
        font-weight: normal;
        font-size: 13px;
        vertical-align: middle;
    }
    
    .custom-table td {
        padding: 10px 8px;
        text-align: center;
        border: 1px solid #B0C4DE;
        background-color: white;
        color: #000000;
        vertical-align: middle;
        font-weight: normal;
    }
    
    /* Onglets */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        background-color: #F0F2F6;
        border-radius: 8px 8px 0px 0px;
        gap: 8px;
        padding: 10px 16px;
        font-weight: 600;
    }
    
    .stTabs [aria-selected="true"] {
        background-color: #0369A1 !important;
        color: white !important;
    }
</style>
""", unsafe_allow_html=True)

# =====================================================
# FONCTIONS UTILITAIRES COMMUNES
# =====================================================
def show_df(df, **kwargs):
    """Affiche un DataFrame avec arrondi à 3 décimales."""
    if isinstance(df, pd.DataFrame):
        df_to_display = df.copy()
        df_to_display = df_to_display.round(3)
        st.dataframe(df_to_display, **kwargs)
    else:
        st.dataframe(df, **kwargs)

def to_excel(df, sheet_name="Données"):
    """Export DataFrame to Excel."""
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    return output.getvalue()

# =====================================================
# INITIALISATION SESSION STATE
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
    st.session_state.df_voyages_valides = None
    st.session_state.transfer_manager = None
    st.session_state.attributions = {}
    st.session_state.validations = {}

# =====================================================
# PAGE 1: IMPORTATION DES DONNÉES
# =====================================================
def page_import():
    st.markdown("<h1 class='main-header'>1. 📥 IMPORTATION DES DONNÉES</h1>", unsafe_allow_html=True)
    
    st.markdown("""
    <div style='background: linear-gradient(135deg, #1E3A8A 0%, #3B82F6 100%);
                padding: 1.5rem;
                border-radius: 10px;
                color: white;
                margin-bottom: 2rem;'>
        <h3 style='color: white; margin-bottom: 0.5rem;'>📋 Instructions d'importation</h3>
        <p style='margin-bottom: 0;'>Téléchargez les 3 fichiers requis pour commencer l'analyse des livraisons.</p>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("""
        <div class='metric-card'>
            <h4 style='color: #0369A1; margin-bottom: 10px;'>📄 Fichier Livraisons</h4>
            <p style='font-size: 14px; color: #666;'>Format Excel (.xlsx)</p>
        </div>
        """, unsafe_allow_html=True)
        liv_file = st.file_uploader("BL", type=["xlsx"], key="file1")
        
    with col2:
        st.markdown("""
        <div class='metric-card'>
            <h4 style='color: #0369A1; margin-bottom: 10px;'>📦 Fichier Volumes</h4>
            <p style='font-size: 14px; color: #666;'>Format Excel (.xlsx)</p>
        </div>
        """, unsafe_allow_html=True)
        ydlogist_file = st.file_uploader("Articles", type=["xlsx"], key="file2")
        
    with col3:
        st.markdown("""
        <div class='metric-card'>
            <h4 style='color: #0369A1; margin-bottom: 10px;'>🏢 Fichier Clients</h4>
            <p style='font-size: 14px; color: #666;'>Format Excel (.xlsx)</p>
        </div>
        """, unsafe_allow_html=True)
        wcliegps_file = st.file_uploader("Clients/Zones", type=["xlsx"], key="file3")
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Bouton de traitement
    col_btn1, col_btn2, col_btn3 = st.columns([1, 2, 1])
    with col_btn2:
        if st.button("🚀 Exécuter le traitement complet", type="primary", use_container_width=True):
            if liv_file and ydlogist_file and wcliegps_file:
                processor = DeliveryProcessor()
                try:
                    with st.spinner("🔍 Traitement des données en cours..."):
                        df_grouped, df_city, df_grouped_zone, df_zone, df_optimized_estafettes, df_livraisons_original = processor.process_delivery_data(
                            liv_file, ydlogist_file, wcliegps_file
                        )
                    
                    # Stockage dans session_state
                    st.session_state.df_grouped = df_grouped
                    st.session_state.df_city = df_city
                    st.session_state.df_grouped_zone = df_grouped_zone
                    st.session_state.df_zone = df_zone
                    st.session_state.df_optimized_estafettes = df_optimized_estafettes
                    st.session_state.df_livraisons_original = df_livraisons_original
                    st.session_state.df_livraisons = df_grouped_zone
                    
                    # Initialisation des processeurs
                    st.session_state.rental_processor = TruckRentalProcessor(
                        df_optimized_estafettes, df_livraisons_original
                    )
                    st.session_state.data_processed = True
                    
                    st.success("✅ Données importées et traitées avec succès !")
                    st.balloons()
                    
                except Exception as e:
                    st.error(f"❌ Erreur lors du traitement : {str(e)}")
            else:
                st.warning("⚠️ Veuillez télécharger les 3 fichiers requis.")
    
    # Afficher les résultats si disponibles
    if st.session_state.data_processed:
        st.markdown("---")
        st.subheader("📊 Aperçu des données importées")
        
        col_info1, col_info2, col_info3 = st.columns(3)
        with col_info1:
            if st.session_state.df_grouped is not None:
                st.metric("📦 Livraisons", f"{len(st.session_state.df_grouped)}")
        with col_info2:
            if st.session_state.df_city is not None:
                villes = st.session_state.df_city['Ville'].nunique()
                st.metric("🏙️ Villes", f"{villes}")
        with col_info3:
            if st.session_state.df_zone is not None:
                zones = st.session_state.df_zone['Zone'].nunique()
                st.metric("🌍 Zones", f"{zones}")
        
        # Boutons de navigation
        st.markdown("---")
        col_nav1, col_nav2 = st.columns(2)
        with col_nav1:
            if st.button("📋 Voir l'analyse détaillée →", use_container_width=True):
                st.session_state.page = "analyse"
                st.rerun()
        with col_nav2:
            if st.button("🚚 Passer à l'optimisation →", use_container_width=True, type="secondary"):
                st.session_state.page = "optimisation"
                st.rerun()

# =====================================================
# PAGE 2: ANALYSE DÉTAILLÉE (VERSION COMPLÈTE)
# =====================================================
def page_analyse():
    st.markdown("<h1 class='main-header'>2. 🔍 ANALYSE DÉTAILLÉE</h1>", unsafe_allow_html=True)
    
    if not st.session_state.data_processed:
        st.warning("⚠️ Veuillez d'abord importer les données dans la page 1.")
        if st.button("📥 Retour à l'importation"):
            st.session_state.page = "import"
            st.rerun()
        return
    
    # CSS PERSONNALISÉ POUR LES ONGLETS
    st.markdown("""
    <style>
        /* Style pour les onglets - COULEUR BLEUE */
        .stTabs [data-baseweb="tab-list"] {
            gap: 8px;
        }
        
        .stTabs [data-baseweb="tab"] {
            height: 50px;
            white-space: pre-wrap;
            background-color: #F0F2F6;
            border-radius: 8px 8px 0px 0px;
            gap: 8px;
            padding: 10px 16px;
            font-weight: 600;
        }
        
        .stTabs [data-baseweb="tab"]:hover {
            background-color: #E6F3FF;
            color: #0369A1;
        }
        
        /* ONGLET ACTIF - BLEU ROYAL */
        .stTabs [aria-selected="true"] {
            background-color: #0369A1 !important;
            color: white !important;
        }
        
        /* TEXTE DES ONGLETS */
        .stTabs [data-baseweb="tab"] p {
            font-size: 16px;
            font-weight: 600;
            margin: 0;
        }
        
        /* COULEUR DU TEXTE POUR ONGLET ACTIF */
        .stTabs [aria-selected="true"] p {
            color: white !important;
        }
        
        /* Style général du tableau */
        .custom-table {
            width: 100%;
            border-collapse: collapse;
            font-family: Arial, sans-serif;
            font-size: 14px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            border-radius: 8px;
            overflow: hidden;
        }
        
        /* En-têtes du tableau - BLEU ROYAL SANS DÉGRADÉ */
        .custom-table th {
            background-color: #0369A1;
            color: white;
            padding: 12px 8px;
            text-align: center;
            border: 2px solid #4682B4;
            font-weight: normal;
            font-size: 13px;
            vertical-align: middle;
        }
        
        /* Cellules du tableau - TOUTES EN BLANC */
        .custom-table td {
            padding: 10px 8px;
            text-align: center;
            border: 1px solid #B0C4DE;
            background-color: white;
            color: #000000;
            vertical-align: middle;
            font-weight: normal;
        }
        
        /* Bordures visibles pour toutes les cellules */
        .custom-table th, 
        .custom-table td {
            border: 1px solid #B0C4DE !important;
        }
        
        /* Bordures épaisses pour l'extérieur du tableau */
        .custom-table {
            border: 2px solid #4682B4 !important;
        }
        
        /* Conteneur du tableau avec défilement horizontal */
        .table-container {
            overflow-x: auto;
            margin: 1rem 0;
            border-radius: 8px;
            border: 2px solid #4682B4;
        }
        
        /* Supprimer l'alternance des couleurs - TOUTES LES LIGNES BLANCHES */
        .custom-table tr:nth-child(even) td {
            background-color: white !important;
        }
        
        /* Survol des lignes - léger effet */
        .custom-table tr:hover td {
            background-color: #F0F8FF !important;
        }
    </style>
    """, unsafe_allow_html=True)
    
    # Onglets pour différents types d'analyse
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
        
        # Créer une copie du DataFrame et FILTRER TRIPOLI
        df_liv = st.session_state.df_grouped.drop(columns=["Zone"], errors='ignore').copy()
        df_liv = df_liv[df_liv["Ville"] != "TRIPOLI"]  # ← FILTRE TRIPOLI
        
        # Vérifier si le DataFrame n'est pas vide après filtrage
        if df_liv.empty:
            st.info("ℹ️ Aucune livraison à afficher (TRIPOLI exclue)")
        else:
            # Préparer les données pour l'affichage HTML
            if "Article" in df_liv.columns:
                # Transformer les articles avec retours à la ligne HTML - SANS "•"
                df_liv["Article"] = df_liv["Article"].astype(str).apply(
                    lambda x: "<br>".join(a.strip() for a in x.split(",") if a.strip())
                )
            
            # Formater les nombres - 3 chiffres après la virgule
            if "Poids total" in df_liv.columns:
                df_liv["Poids total"] = df_liv["Poids total"].map(lambda x: f"{x:.3f} kg" if pd.notna(x) else "")
            if "Volume total" in df_liv.columns:
                df_liv["Volume total"] = df_liv["Volume total"].map(lambda x: f"{x:.3f} m³" if pd.notna(x) else "")
            
            # Afficher le tableau avec le style CSS
            html_table = df_liv.to_html(
                escape=False, 
                index=False, 
                classes="custom-table",
                border=0
            )
            
            st.markdown(f"""
            <div class="table-container">
                {html_table}
            </div>
            """, unsafe_allow_html=True)
        
        # Métriques résumées
        st.markdown("---")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            total_livraisons = len(df_liv) if not df_liv.empty else 0
            st.metric("📦 Total Livraisons", total_livraisons)
        
        with col2:
            total_clients = df_liv["Client"].nunique() if not df_liv.empty else 0
            st.metric("👥 Clients Uniques", total_clients)
        
        with col3:
            # Calculer le poids total à partir des données filtrées
            df_liv_original = st.session_state.df_grouped[st.session_state.df_grouped["Ville"] != "TRIPOLI"]
            total_poids = df_liv_original["Poids total"].sum() if not df_liv_original.empty else 0
            st.metric("⚖️ Poids Total", f"{total_poids:.3f} kg")
        
        with col4:
            # Calculer le volume total à partir des données filtrées
            total_volume = df_liv_original["Volume total"].sum() if not df_liv_original.empty else 0
            st.metric("📏 Volume Total", f"{total_volume:.3f} m³")
        
        # Bouton de téléchargement
        from io import BytesIO
        excel_buffer_grouped = BytesIO()
        with pd.ExcelWriter(excel_buffer_grouped, engine='openpyxl') as writer:
            st.session_state.df_grouped.drop(columns=["Zone"], errors='ignore').to_excel(writer, index=False, sheet_name="Livraisons Client Ville")
        excel_buffer_grouped.seek(0)
        
        st.download_button(
            label="💾 Télécharger Livraisons Client/Ville",
            data=excel_buffer_grouped,
            file_name="Livraisons_Client_Ville.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
        # Stockage pour la section transfert
        if "df_livraisons" not in st.session_state:
            st.session_state.df_livraisons = df_liv.copy()
    
    # --- Onglet Besoin Estafette par Ville ---
    with tab_city:
        st.subheader("Besoin Estafette par Ville")
        
        # Créer une copie du DataFrame et FILTRER TRIPOLI
        df_city_display = st.session_state.df_city.copy()
        df_city_display = df_city_display[df_city_display["Ville"] != "TRIPOLI"]
        
        # Formater les nombres - 3 chiffres après la virgule
        if "Poids total" in df_city_display.columns:
            df_city_display["Poids total"] = df_city_display["Poids total"].map(lambda x: f"{x:.3f} kg" if pd.notna(x) else "")
        if "Volume total" in df_city_display.columns:
            df_city_display["Volume total"] = df_city_display["Volume total"].map(lambda x: f"{x:.3f} m³" if pd.notna(x) else "")
        if "Besoin estafette réel" in df_city_display.columns:
            df_city_display["Besoin estafette réel"] = df_city_display["Besoin estafette réel"].map(lambda x: f"{x:.1f}" if pd.notna(x) else "")
        
        # Vérifier si le DataFrame n'est pas vide
        if df_city_display.empty:
            st.info("ℹ️ Aucune ville à afficher (TRIPOLI exclue)")
        else:
            # Afficher le tableau avec le style CSS
            html_table_city = df_city_display.to_html(
                escape=False, 
                index=False, 
                classes="custom-table",
                border=0
            )
            
            st.markdown(f"""
            <div class="table-container">
                {html_table_city}
            </div>
            """, unsafe_allow_html=True)
        
        # Métriques résumées
        st.markdown("---")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            total_villes = len(df_city_display)
            st.metric("🏙️ Total Villes", total_villes)
        
        with col2:
            # Calculer le total des BLs
            df_city_original_filtered = st.session_state.df_city[st.session_state.df_city["Ville"] != "TRIPOLI"]
            total_bls = df_city_original_filtered["Nombre de BLs"].sum() if "Nombre de BLs" in df_city_original_filtered.columns else 0
            st.metric("📦 Total BLs", int(total_bls))
        
        with col3:
            # Calculer le total des estafettes nécessaires
            total_estafettes = df_city_original_filtered["Besoin estafette réel"].sum() if "Besoin estafette réel" in df_city_original_filtered.columns else 0
            st.metric("🚐 Besoin Estafettes", f"{total_estafettes:.1f}")

        # Bouton de téléchargement
        excel_buffer_city = BytesIO()
        with pd.ExcelWriter(excel_buffer_city, engine='openpyxl') as writer:
            st.session_state.df_city.to_excel(writer, index=False, sheet_name="Besoin Estafette Ville")
        excel_buffer_city.seek(0)
        
        st.download_button(
            label="💾 Télécharger Besoin par Ville",
            data=excel_buffer_city,
            file_name="Besoin_Estafette_Ville.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    
    # --- Onglet Livraisons Client & Ville + Zone ---
    with tab_zone_group:
        st.subheader("Livraisons par Client & Ville + Zone")
        
        # Créer une copie du DataFrame
        df_liv_zone = st.session_state.df_grouped_zone.copy()
        
        # Préparer les données pour l'affichage HTML
        if "Article" in df_liv_zone.columns:
            # Transformer les articles avec retours à la ligne HTML - SANS "•"
            df_liv_zone["Article"] = df_liv_zone["Article"].astype(str).apply(
                lambda x: "<br>".join(a.strip() for a in x.split(",") if a.strip())
            )
        
        # Formater les nombres - 3 chiffres après la virgule
        if "Poids total" in df_liv_zone.columns:
            df_liv_zone["Poids total"] = df_liv_zone["Poids total"].map(lambda x: f"{x:.3f} kg" if pd.notna(x) else "")
        if "Volume total" in df_liv_zone.columns:
            df_liv_zone["Volume total"] = df_liv_zone["Volume total"].map(lambda x: f"{x:.3f} m³" if pd.notna(x) else "")
        
        # Afficher le tableau avec le style CSS
        html_table_zone_group = df_liv_zone.to_html(
            escape=False, 
            index=False, 
            classes="custom-table",
            border=0
        )
        
        st.markdown(f"""
        <div class="table-container">
            {html_table_zone_group}
        </div>
        """, unsafe_allow_html=True)
        
        # Métriques résumées
        st.markdown("---")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            total_livraisons_zone = len(df_liv_zone)
            st.metric("📦 Total Livraisons", total_livraisons_zone)
        
        with col2:
            zones_count = df_liv_zone["Zone"].nunique()
            st.metric("🌍 Zones", zones_count)
        
        with col3:
            villes_count = df_liv_zone["Ville"].nunique()
            st.metric("🏙️ Villes", villes_count)
        
        # Bouton de téléchargement
        excel_buffer_zone_group = BytesIO()
        with pd.ExcelWriter(excel_buffer_zone_group, engine='openpyxl') as writer:
            st.session_state.df_grouped_zone.to_excel(writer, index=False, sheet_name="Livraisons Client Ville Zone")
        excel_buffer_zone_group.seek(0)
        
        st.download_button(
            label="💾 Télécharger Livraisons Client/Ville/Zone",
            data=excel_buffer_zone_group,
            file_name="Livraisons_Client_Ville_Zone.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    
    # --- Onglet Besoin Estafette par Zone ---
    with tab_zone_summary:
        st.subheader("Besoin Estafette par Zone")
        
        # Créer une copie du DataFrame et renommer la colonne
        df_zone_display = st.session_state.df_zone.copy()
        
        # RENOMMER LA COLONNE "Nombre livraisons" en "Nombre de BLs"
        df_zone_display = df_zone_display.rename(columns={"Nombre livraisons": "Nombre de BLs"})
        
        # Formater les nombres
        if "Poids total" in df_zone_display.columns:
            df_zone_display["Poids total"] = df_zone_display["Poids total"].map(lambda x: f"{x:.3f} kg" if pd.notna(x) else "")
        if "Volume total" in df_zone_display.columns:
            df_zone_display["Volume total"] = df_zone_display["Volume total"].map(lambda x: f"{x:.3f} m³" if pd.notna(x) else "")
        if "Besoin estafette réel" in df_zone_display.columns:
            df_zone_display["Besoin estafette réel"] = df_zone_display["Besoin estafette réel"].map(lambda x: f"{x:.1f}" if pd.notna(x) else "")
        if "Nombre de BLs" in df_zone_display.columns:
            df_zone_display["Nombre de BLs"] = df_zone_display["Nombre de BLs"].map(lambda x: f"{int(x)}" if pd.notna(x) else "")
        
        # Afficher le tableau avec le style CSS
        html_table_zone = df_zone_display.to_html(
            escape=False, 
            index=False, 
            classes="custom-table",
            border=0
        )
        
        st.markdown(f"""
        <div class="table-container">
            {html_table_zone}
        </div>
        """, unsafe_allow_html=True)
        
        # Métriques résumées
        st.markdown("---")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            total_zones = len(df_zone_display)
            st.metric("🌍 Total Zones", total_zones)
        
        with col2:
            # Calculer le total des BLs
            if "Nombre livraisons" in st.session_state.df_zone.columns:
                total_bls_zone = st.session_state.df_zone["Nombre livraisons"].sum()
            else:
                total_bls_zone = 0
            st.metric("📦 Total BLs", int(total_bls_zone))
        
        with col3:
            # Calculer le total des estafettes nécessaires
            total_estafettes_zone = st.session_state.df_zone["Besoin estafette réel"].sum() if "Besoin estafette réel" in st.session_state.df_zone.columns else 0
            st.metric("🚐 Besoin Estafettes", f"{total_estafettes_zone:.1f}")
        
        # Bouton de téléchargement
        excel_buffer_zone = BytesIO()
        with pd.ExcelWriter(excel_buffer_zone, engine='openpyxl') as writer:
            st.session_state.df_zone.to_excel(writer, index=False, sheet_name="Besoin Estafette Zone")
        excel_buffer_zone.seek(0)
        
        st.download_button(
            label="💾 Télécharger Besoin par Zone",
            data=excel_buffer_zone,
            file_name="Besoin_Estafette_Zone.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    
    # --- Onglet Graphiques ---
    with tab_charts:
        st.subheader("Statistiques par Ville")
        
        # FILTRER LES DONNÉES POUR EXCLURE TRIPOLI
        df_filtered = st.session_state.df_city[st.session_state.df_city["Ville"] != "TRIPOLI"]
        
        if not df_filtered.empty:
            # Configuration commune pour tous les graphiques
            chart_config = {
                'color_discrete_sequence': ['#0369A1'],  # BLEU ROYAL
                'template': 'plotly_white',
            }
            
            col1, col2 = st.columns(2)
            with col1:
                fig1 = px.bar(df_filtered, x="Ville", y="Poids total", **chart_config)
                fig1.update_layout(title_text="Poids total livré par ville", title_x=0.5)
                st.plotly_chart(fig1, use_container_width=True)
                
            with col2:
                fig2 = px.bar(df_filtered, x="Ville", y="Volume total", **chart_config)
                fig2.update_layout(title_text="Volume total livré par ville (m³)", title_x=0.5)
                st.plotly_chart(fig2, use_container_width=True)

            col3, col4 = st.columns(2)
            with col3:
                # DIAGRAMME CORRIGÉ : Nombre de BL par ville
                df_chart = df_filtered.rename(columns={"Nombre livraisons": "Nombre de BLs"})
                fig3 = px.bar(df_chart, x="Ville", y="Nombre de BLs", **chart_config)
                fig3.update_layout(title_text="Nombre de BL par ville", title_x=0.5)
                st.plotly_chart(fig3, use_container_width=True)
                
            with col4:
                fig4 = px.bar(df_filtered, x="Ville", y="Besoin estafette réel", **chart_config)
                fig4.update_layout(title_text="Besoin en Estafettes par ville", title_x=0.5)
                st.plotly_chart(fig4, use_container_width=True)
        else:
            st.info("ℹ️ Aucune donnée disponible pour les graphiques (TRIPOLI exclue)")
    
    # Navigation entre pages
    st.markdown("---")
    col_nav1, col_nav2, col_nav3 = st.columns(3)
    
    with col_nav1:
        if st.button("← Retour à l'importation", use_container_width=True):
            st.session_state.page = "import"
            st.rerun()
    
    with col_nav2:
        if st.button("📊 Exporter toute l'analyse", use_container_width=True):
            # Créer un fichier Excel avec tous les onglets
            from io import BytesIO
            
            excel_buffer = BytesIO()
            with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                if st.session_state.df_grouped is not None:
                    st.session_state.df_grouped.drop(columns=["Zone"], errors='ignore').to_excel(writer, sheet_name="Livraisons Client Ville", index=False)
                if st.session_state.df_city is not None:
                    st.session_state.df_city.to_excel(writer, sheet_name="Besoin par Ville", index=False)
                if st.session_state.df_grouped_zone is not None:
                    st.session_state.df_grouped_zone.to_excel(writer, sheet_name="Livraisons Client Zone", index=False)
                if st.session_state.df_zone is not None:
                    st.session_state.df_zone.to_excel(writer, sheet_name="Besoin par Zone", index=False)
            
            excel_buffer.seek(0)
            
            st.download_button(
                label="💾 Télécharger l'analyse complète",
                data=excel_buffer,
                file_name="Analyse_Complete_Livraisons.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
    
    with col_nav3:
        if st.button("🚚 Passer à l'optimisation →", type="primary", use_container_width=True):
            st.session_state.page = "optimisation"
            st.rerun()

# =====================================================
# FONCTIONS DE CALLBACK POUR LA LOCATION
# =====================================================

def update_propositions_view():
    """Met à jour le DataFrame de propositions après une action."""
    if st.session_state.rental_processor:
        st.session_state.propositions = st.session_state.rental_processor.detecter_propositions()
        
        # Vérifier si le DataFrame de propositions n'est pas vide et contient la colonne 'Client'
        if (st.session_state.propositions is not None and 
            not st.session_state.propositions.empty and 
            'Client' in st.session_state.propositions.columns):
            
            # Réinitialiser la sélection si le client n'est plus dans les propositions ouvertes
            if (st.session_state.selected_client is not None and 
                st.session_state.selected_client not in st.session_state.propositions['Client'].astype(str).tolist()):
                st.session_state.selected_client = None
    else:
        st.session_state.propositions = pd.DataFrame()

def handle_location_action(accepter):
    """Gère l'acceptation ou le refus de la proposition de location."""
    if st.session_state.rental_processor and st.session_state.selected_client:
        try:
            # Assurer que le client est une chaîne valide
            client_to_process = str(st.session_state.selected_client)
            ok, msg, _ = st.session_state.rental_processor.appliquer_location(
                client_to_process, accepter=accepter
            )
            st.session_state.message = msg
            update_propositions_view()
            st.rerun()
        except Exception as e:
            st.session_state.message = f"❌ Erreur lors du traitement : {str(e)}"
    elif not st.session_state.selected_client:
        st.session_state.message = "⚠️ Veuillez sélectionner un client à traiter."
    else:
        st.session_state.message = "⚠️ Le processeur de location n'est pas initialisé."

def accept_location_callback():
    handle_location_action(True)

def refuse_location_callback():
    handle_location_action(False)

# =====================================================
# PAGE 3: OPTIMISATION ET LOCATION (VERSION COMPLÈTE)
# =====================================================
def page_optimisation():
    st.markdown("<h1 class='main-header'>3. 🚚 OPTIMISATION & LOCATION</h1>", unsafe_allow_html=True)
    
    if not st.session_state.data_processed:
        st.warning("⚠️ Veuillez d'abord importer les données dans la page 1.")
        if st.button("📥 Retour à l'importation"):
            st.session_state.page = "import"
            st.rerun()
        return
    
    # CSS POUR LES TABLEAUX DE LA SECTION 3
    st.markdown("""
    <style>
        /* Style général du tableau */
        .custom-table-rental {
            width: 100%;
            border-collapse: collapse;
            font-family: Arial, sans-serif;
            font-size: 14px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            border-radius: 8px;
            overflow: hidden;
        }
        
        /* En-têtes du tableau - BLEU ROYAL SANS DÉGRADÉ */
        .custom-table-rental th {
            background-color: #0369A1;
            color: white;
            padding: 12px 8px;
            text-align: center;
            border: 2px solid #4682B4;
            font-weight: normal;
            font-size: 13px;
            vertical-align: middle;
        }
        
        /* Cellules du tableau - TOUTES EN BLANC */
        .custom-table-rental td {
            padding: 10px 8px;
            text-align: center;
            border: 1px solid #B0C4DE;
            background-color: white;
            color: #000000;
            vertical-align: middle;
            font-weight: normal;
        }
        
        /* Bordures visibles pour toutes les cellules */
        .custom-table-rental th, 
        .custom-table-rental td {
            border: 1px solid #B0C4DE !important;
        }
        
        /* Bordures épaisses pour l'extérieur du tableau */
        .custom-table-rental {
            border: 2px solid #4682B4 !important;
        }
        
        /* Style pour les cellules numériques - SANS GRAS */
        .custom-table-rental td:nth-child(2),
        .custom-table-rental td:nth-child(3),
        .custom-table-rental td:nth-child(4),
        .custom-table-rental td:nth-child(5),
        .custom-table-rental td:nth-child(6) {
            font-weight: normal;
            color: #000000 !important;
            vertical-align: middle;
        }
        
        /* Conteneur du tableau avec défilement horizontal */
        .table-container-rental {
            overflow-x: auto;
            margin: 1rem 0;
            border-radius: 8px;
            border: 2px solid #4682B4;
        }
        
        /* Supprimer l'alternance des couleurs - TOUTES LES LIGNES BLANCHES */
        .custom-table-rental tr:nth-child(even) td {
            background-color: white !important;
        }
        
        /* Survol des lignes - léger effet */
        .custom-table-rental tr:hover td {
            background-color: #F0F8FF !important;
        }
        
        /* Style spécifique pour les cellules multilignes (BL inclus) */
        .multiline-cell {
            line-height: 1.4;
            text-align: left !important;
            padding: 8px !important;
            font-weight: normal;
        }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown(f"🔸 Si un client dépasse **{SEUIL_POIDS} kg** ou **{SEUIL_VOLUME} m³**, une location est proposée (si non déjà décidée).")
    
    # Initialiser propositions si nécessaire
    if st.session_state.propositions is None and st.session_state.rental_processor:
        update_propositions_view()
    
    # Onglets pour différentes fonctionnalités
    tab1, tab2, tab3 = st.tabs([
        "📋 Propositions Location", 
        "🔄 Transfert BLs", 
        "📦 Ajout Objets"
    ])
    
    # --- Onglet 1: Propositions de Location ---
    with tab1:
        st.subheader("Propositions de Location de Camion")
        
        if st.session_state.propositions is not None and not st.session_state.propositions.empty:
            col_prop, col_details = st.columns([2, 3])
            
            with col_prop:
                st.markdown("### Propositions ouvertes")
                
                # Vérifier si la colonne 'Client' existe
                if 'Client' in st.session_state.propositions.columns:
                    # FORMATAGE DU TABLEAU DES PROPOSITIONS AVEC STYLE CSS
                    propositions_display = st.session_state.propositions.copy()
                    
                    # Formater les nombres
                    if "Poids total (kg)" in propositions_display.columns:
                        propositions_display["Poids total (kg)"] = propositions_display["Poids total (kg)"].map(
                            lambda x: f"{float(x):.3f}" if pd.notna(x) else ""
                        )
                    if "Volume total (m³)" in propositions_display.columns:
                        propositions_display["Volume total (m³)"] = propositions_display["Volume total (m³)"].map(
                            lambda x: f"{float(x):.3f}" if pd.notna(x) else ""
                        )
                    
                    # Afficher le tableau avec le style CSS
                    html_table_propositions = propositions_display.to_html(
                        escape=False, 
                        index=False, 
                        classes="custom-table-rental",
                        border=0
                    )
                    
                    st.markdown(f"""
                    <div class="table-container-rental">
                        {html_table_propositions}
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # MÉTRIQUES RÉSUMÉES
                    st.markdown("---")
                    col_metric1, col_metric2, col_metric3 = st.columns(3)

                    with col_metric1:
                        total_propositions = len(st.session_state.propositions)
                        st.metric("📋 Propositions ouvertes", total_propositions)

                    with col_metric2:
                        # Calculer le nombre de clients dépassant le seuil de POIDS
                        clients_poids = len(st.session_state.propositions[
                            st.session_state.propositions["Poids total (kg)"] >= SEUIL_POIDS
                        ]) if "Poids total (kg)" in st.session_state.propositions.columns else 0
                        st.metric("⚖️ Dépassement poids", clients_poids)

                    with col_metric3:
                        # Calculer le nombre de clients dépassant le seuil de VOLUME
                        clients_volume = len(st.session_state.propositions[
                            st.session_state.propositions["Volume total (m³)"] >= SEUIL_VOLUME
                        ]) if "Volume total (m³)" in st.session_state.propositions.columns else 0
                        st.metric("📦 Dépassement volume", clients_volume)

                    # Sélection du client
                    client_options = st.session_state.propositions['Client'].astype(str).tolist()
                    client_options_with_empty = [""] + client_options
                    
                    # Index de sélection par défaut
                    default_index = 0
                    if st.session_state.selected_client in client_options:
                        default_index = client_options_with_empty.index(st.session_state.selected_client)
                    elif len(client_options) > 0:
                        default_index = 1

                    st.session_state.selected_client = st.selectbox(
                        "Client à traiter :", 
                        options=client_options_with_empty, 
                        index=default_index,
                        key='client_select_opt' 
                    )
                else:
                    st.warning("⚠️ Format de données incorrect dans les propositions.")
                    st.session_state.selected_client = None

                # Boutons d'action
                col_btn_acc, col_btn_ref = st.columns(2)
                is_client_selected = st.session_state.selected_client != "" and st.session_state.selected_client is not None
                
                with col_btn_acc:
                    st.button(
                        "✅ Accepter la location", 
                        on_click=accept_location_callback, 
                        disabled=not is_client_selected,
                        use_container_width=True,
                        type="primary"
                    )
                with col_btn_ref:
                    st.button(
                        "❌ Refuser la proposition", 
                        on_click=refuse_location_callback, 
                        disabled=not is_client_selected,
                        use_container_width=True,
                        type="secondary"
                    )
                
                # Afficher les messages
                if st.session_state.message:
                    if st.session_state.message.startswith("✅"):
                        st.success(st.session_state.message)
                    elif st.session_state.message.startswith("❌"):
                        st.error(st.session_state.message)
                    elif st.session_state.message.startswith("⚠️"):
                        st.warning(st.session_state.message)

            with col_details:
                st.markdown("### Détails de la commande client")
                is_client_selected = st.session_state.selected_client != "" and st.session_state.selected_client is not None
                
                if is_client_selected:
                    try:
                        resume, details_df = st.session_state.rental_processor.get_details_client(
                            st.session_state.selected_client
                        )
                        
                        # Afficher le résumé
                        st.markdown(f"**{resume}**")
                        
                        # FORMATAGE DU TABLEAU DES DÉTAILS AVEC STYLE CSS
                        if not details_df.empty:
                            details_display = details_df.copy()
                            
                            # Formatage simple et sécurisé des colonnes
                            def format_numeric_column(series, decimals, unit=""):
                                """Formate une colonne numérique avec le nombre de décimales et unité spécifiés"""
                                formatted_series = series.copy()
                                for i, value in enumerate(series):
                                    if pd.notna(value) and value != "":
                                        try:
                                            # Essayer de convertir en float
                                            if isinstance(value, str):
                                                # Nettoyer la valeur si c'est une string
                                                clean_value = value.replace(' kg', '').replace(' m³', '').replace('%', '').strip()
                                                num_value = float(clean_value)
                                            else:
                                                num_value = float(value)
                                            
                                            # Formater selon le nombre de décimales
                                            if decimals == 3:
                                                formatted_value = f"{num_value:.3f}"
                                            elif decimals == 2:
                                                formatted_value = f"{num_value:.2f}"
                                            elif decimals == 1:
                                                formatted_value = f"{num_value:.1f}"
                                            else:
                                                formatted_value = f"{num_value:.0f}"
                                            
                                            formatted_series.iloc[i] = f"{formatted_value}{unit}"
                                        except (ValueError, TypeError):
                                            # Si conversion échoue, garder la valeur originale
                                            formatted_series.iloc[i] = str(value)
                                    else:
                                        formatted_series.iloc[i] = ""
                                return formatted_series
                            
                            # Formater les colonnes numériques
                            if "Poids total" in details_display.columns:
                                details_display["Poids total"] = format_numeric_column(details_display["Poids total"], 3, " kg")
                            
                            if "Volume total" in details_display.columns:
                                details_display["Volume total"] = format_numeric_column(details_display["Volume total"], 3, " m³")
                            
                            if "Taux d'occupation (%)" in details_display.columns:
                                details_display["Taux d'occupation (%)"] = format_numeric_column(details_display["Taux d'occupation (%)"], 2, "%")
                            
                            # Gestion spéciale pour "BL inclus" - format multiligne
                            if "BL inclus" in details_display.columns:
                                details_display["BL inclus"] = details_display["BL inclus"].astype(str).apply(
                                    lambda x: "<br>".join(bl.strip() for bl in x.split(";")) if ";" in x else x
                                )
                            
                            # Afficher le tableau avec le style CSS
                            html_table_details = details_display.to_html(
                                escape=False, 
                                index=False, 
                                classes="custom-table-rental",
                                border=0
                            )
                            
                            st.markdown(f"""
                            <div class="table-container-rental">
                                {html_table_details}
                            </div>
                            """, unsafe_allow_html=True)
                            
                            # MÉTRIQUES POUR LES DÉTAILS
                            st.markdown("---")
                            col_det1, col_det2, col_det3 = st.columns(3)
                            
                            with col_det1:
                                total_camions = len(details_display)
                                st.metric("🚚 Nombre de camions", total_camions)
                            
                            with col_det2:
                                # Calculer le poids total à partir des données brutes
                                try:
                                    if "Poids total" in details_df.columns:
                                        poids_total = 0
                                        for value in details_df["Poids total"]:
                                            if pd.notna(value):
                                                try:
                                                    # Nettoyer la valeur si elle contient des unités
                                                    if isinstance(value, str):
                                                        clean_value = value.replace(' kg', '').replace('m³', '').strip()
                                                    else:
                                                        clean_value = str(value)
                                                    poids_total += float(clean_value)
                                                except (ValueError, TypeError):
                                                    continue
                                        st.metric("📦 Poids total", f"{poids_total:.1f} kg")
                                    else:
                                        st.metric("📦 Poids total", "N/A")
                                except Exception as e:
                                    st.metric("📦 Poids total", "Erreur")
                            
                            with col_det3:
                                # Calculer le volume total à partir des données brutes
                                try:
                                    if "Volume total" in details_df.columns:
                                        volume_total = 0
                                        for value in details_df["Volume total"]:
                                            if pd.notna(value):
                                                try:
                                                    # Nettoyer la valeur si elle contient des unités
                                                    if isinstance(value, str):
                                                        clean_value = value.replace(' kg', '').replace('m³', '').strip()
                                                    else:
                                                        clean_value = str(value)
                                                    volume_total += float(clean_value)
                                                except (ValueError, TypeError):
                                                    continue
                                        st.metric("📏 Volume total", f"{volume_total:.3f} m³")
                                    else:
                                        st.metric("📏 Volume total", "N/A")
                                except Exception as e:
                                    st.metric("📏 Volume total", "Erreur")
                                
                    except Exception as e:
                        st.error(f"❌ Erreur lors de la récupération des détails : {str(e)}")
                        # Debug information
                        st.write("Détails de l'erreur :")
                        if 'details_df' in locals():
                            st.write("Colonnes disponibles :", details_df.columns.tolist())
                            if not details_df.empty:
                                st.write("Aperçu des données :")
                                st.dataframe(details_df.head())
                else:
                    st.info("Sélectionnez un client pour afficher les détails de la commande/estafettes.")
        else:
            st.success("✅ Aucune proposition de location de camion en attente de décision.")
            
            # Bouton pour forcer la détection
            if st.button("🔍 Vérifier à nouveau les propositions"):
                if st.session_state.rental_processor:
                    update_propositions_view()
                    st.rerun()
    
    # --- Onglet 2: Transfert BLs ---
    with tab2:
        st.subheader("Transfert de BLs entre véhicules")
        st.info("Réorganisez les livraisons entre estafettes/camions")
        
        if st.session_state.df_voyages is None and st.session_state.rental_processor:
            # Générer les voyages optimisés si pas encore fait
            df_optimized = st.session_state.rental_processor.get_df_result()
            st.session_state.df_voyages = df_optimized
        
        if st.session_state.df_voyages is not None and st.session_state.df_livraisons is not None:
            # Interface de transfert complète
            col_trans1, col_trans2 = st.columns(2)
            
            with col_trans1:
                zones = st.session_state.df_voyages["Zone"].unique().tolist()
                selected_zone = st.selectbox("Sélectionnez une zone", zones)
            
            with col_trans2:
                if selected_zone:
                    vehicules = st.session_state.df_voyages[
                        st.session_state.df_voyages["Zone"] == selected_zone
                    ]["Véhicule N°"].unique().tolist()
                    source_veh = st.selectbox("Véhicule source", vehicules)
            
            # Afficher les BLs du véhicule source
            if selected_zone and source_veh:
                source_data = st.session_state.df_voyages[
                    (st.session_state.df_voyages["Zone"] == selected_zone) & 
                    (st.session_state.df_voyages["Véhicule N°"] == source_veh)
                ]
                
                if not source_data.empty and "BL inclus" in source_data.columns:
                    bls = source_data.iloc[0]["BL inclus"].split(";")
                    
                    # SUPPRIMÉ: L'affichage "BLs disponibles dans le véhicule source"
                    # st.write(f"**BLs disponibles dans {source_veh}:**")
                    # for bl in bls:
                    #     st.write(f"- {bl}")
                    
                    # Sélection des BLs à transférer
                    selected_bls = st.multiselect("Sélectionnez les BLs à transférer", bls)
                    
                    # Véhicule destination
                    dest_vehicles = [v for v in vehicules if v != source_veh]
                    dest_veh = st.selectbox("Véhicule destination", dest_vehicles)
                    
                    if selected_bls and dest_veh and st.button("🔄 Exécuter le transfert"):
                        st.success(f"Transfert de {len(selected_bls)} BL(s) de {source_veh} vers {dest_veh} simulé avec succès")
        else:
            st.info("ℹ️ Générez d'abord les voyages optimisés dans l'onglet 1")
        
    # --- Onglet 3: Ajout d'objets ---
    with tab3:
        st.subheader("Ajout d'objets manuels")
        st.info("Ajoutez des colis urgents aux véhicules")
        
        if st.session_state.df_voyages is not None:
            col_obj1, col_obj2, col_obj3 = st.columns(3)
            with col_obj1:
                nom_objet = st.text_input("Nom de l'objet", placeholder="Ex: Matériel urgent")
            with col_obj2:
                poids = st.number_input("Poids (kg)", min_value=0.0, value=10.0, step=0.1)
            with col_obj3:
                volume = st.number_input("Volume (m³)", min_value=0.0, value=0.1, step=0.01)
            
            # Sélection du véhicule
            if "Véhicule N°" in st.session_state.df_voyages.columns:
                vehicules = st.session_state.df_voyages["Véhicule N°"].unique().tolist()
                selected_veh = st.selectbox("Véhicule cible", vehicules)
            
            if st.button("➕ Ajouter l'objet au véhicule"):
                if nom_objet and selected_veh:
                    st.success(f"Objet '{nom_objet}' ajouté à {selected_veh}")
                else:
                    st.warning("Veuillez remplir tous les champs")
        else:
            st.info("ℹ️ Générez d'abord les voyages optimisés")
    
    # Navigation entre pages
    st.markdown("---")
    col_nav1, col_nav2, col_nav3 = st.columns(3)
    
    with col_nav1:
        if st.button("← Retour à l'analyse", use_container_width=True):
            st.session_state.page = "analyse"
            st.rerun()
    
    with col_nav2:
        if st.button("📊 Générer les voyages optimisés", use_container_width=True, type="primary"):
            # Calcul des voyages optimisés
            if st.session_state.rental_processor:
                df_optimized = st.session_state.rental_processor.get_df_result()
                st.session_state.df_voyages = df_optimized
                st.success("✅ Voyages optimisés générés avec succès !")
                st.rerun()
    
    with col_nav3:
        if st.button("✅ Passer à la validation →", use_container_width=True):
            st.session_state.page = "finalisation"
            st.rerun()

# =====================================================
# PAGE 4: VOYAGES OPTIMISÉS & VALIDATION (VERSION COMPLÈTE)
# =====================================================
def page_finalisation():
    st.markdown("<h1 class='main-header'>4. 🚐 VOYAGES OPTIMISÉS & VALIDATION</h1>", unsafe_allow_html=True)
    
    if not st.session_state.data_processed:
        st.warning("⚠️ Veuillez d'abord importer les données dans la page 1.")
        if st.button("📥 Retour à l'importation"):
            st.session_state.page = "import"
            st.rerun()
        return
    
    # Initialiser df_voyages si nécessaire
    if st.session_state.df_voyages is None and st.session_state.rental_processor:
        df_optimized = st.session_state.rental_processor.get_df_result()
        st.session_state.df_voyages = df_optimized
    
    # Onglets pour différentes fonctionnalités
    tab1, tab2, tab3, tab4 = st.tabs([
        "🚐 Voyages Optimisés", 
        "✅ Validation", 
        "🚛 Attribution", 
        "📤 Export"
    ])
    
    # --- Onglet 1: Voyages Optimisés (Section 4 originale) ---
    with tab1:
        st.subheader("Voyages par Estafette Optimisé (Inclut Camions Loués)")
        
        try:
            # Récupération sécurisée du DataFrame
            if st.session_state.rental_processor:
                df_optimized_estafettes = st.session_state.rental_processor.get_df_result()
            elif "df_voyages" in st.session_state:
                df_optimized_estafettes = st.session_state.df_voyages.copy()
            else:
                st.error("❌ Données non disponibles. Veuillez générer les voyages optimisés.")
                if st.button("🔄 Générer les voyages optimisés"):
                    if st.session_state.rental_processor:
                        df_optimized = st.session_state.rental_processor.get_df_result()
                        st.session_state.df_voyages = df_optimized
                        st.rerun()
                st.stop()
            
            # Vérifier que le DataFrame n'est pas vide
            if df_optimized_estafettes.empty:
                st.warning("⚠️ Aucune donnée à afficher.")
                st.stop()
            
            # Nettoyer les colonnes en double
            df_clean = df_optimized_estafettes.loc[:, ~df_optimized_estafettes.columns.duplicated()]
            
            # TRIER PAR ZONE D'ABORD
            if "Zone" in df_clean.columns:
                # Extraire le numéro de zone pour un tri numérique
                df_clean["Zone_Num"] = df_clean["Zone"].str.extract('(\d+)').astype(float)
                df_clean = df_clean.sort_values("Zone_Num").drop("Zone_Num", axis=1)
            
            # Définir l'ordre des colonnes pour l'affichage
            colonnes_ordre = [
                "Zone", "Véhicule N°", "Poids total chargé", "Volume total chargé",
                "Client(s) inclus", "Représentant(s) inclus", "BL inclus", 
                "Taux d'occupation (%)", "Location_camion", "Location_proposee", "Code Véhicule"
            ]
            
            # Filtrer seulement les colonnes qui existent
            colonnes_finales = [col for col in colonnes_ordre if col in df_clean.columns]
            
            # Créer le DataFrame d'affichage avec retours à la ligne POUR STREAMLIT
            df_display = df_clean[colonnes_finales].copy()
            
            # Transformer les colonnes avec retours à la ligne HTML pour l'affichage Streamlit
            if "Client(s) inclus" in df_display.columns:
                df_display["Client(s) inclus"] = df_display["Client(s) inclus"].astype(str).apply(
                    lambda x: "<br>".join(client.strip() for client in x.split(",")) if x != "nan" else ""
                )
            
            if "Représentant(s) inclus" in df_display.columns:
                df_display["Représentant(s) inclus"] = df_display["Représentant(s) inclus"].astype(str).apply(
                    lambda x: "<br>".join(rep.strip() for rep in x.split(",")) if x != "nan" else ""
                )
            
            if "BL inclus" in df_display.columns:
                df_display["BL inclus"] = df_display["BL inclus"].astype(str).apply(
                    lambda x: "<br>".join(bl.strip() for bl in x.split(";")) if x != "nan" else ""
                )
            
            # Formater les colonnes numériques pour l'affichage
            if "Poids total chargé" in df_display.columns:
                df_display["Poids total chargé"] = df_display["Poids total chargé"].map(lambda x: f"{x:.3f} kg")
            if "Volume total chargé" in df_display.columns:
                df_display["Volume total chargé"] = df_display["Volume total chargé"].map(lambda x: f"{x:.3f} m³")
            if "Taux d'occupation (%)" in df_display.columns:
                df_display["Taux d'occupation (%)"] = df_display["Taux d'occupation (%)"].map(lambda x: f"{x:.3f}%")
            
            # CSS POUR UN TABLEAU PROFESSIONNEL
            st.markdown("""
            <style>
            /* Style général du tableau */
            .custom-table-voyages {
                width: 100%;
                border-collapse: collapse;
                font-family: Arial, sans-serif;
                font-size: 14px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                border-radius: 8px;
                overflow: hidden;
            }
            
            /* En-têtes du tableau - BLEU ROYAL SANS DÉGRADÉ */
            .custom-table-voyages th {
                background-color: #0369A1;
                color: white;
                padding: 12px 8px;
                text-align: center;
                border: 2px solid #4682B4;
                font-weight: bold;
                font-size: 13px;
                vertical-align: middle;
            }
            
            /* Cellules du tableau - TOUTES EN BLANC */
            .custom-table-voyages td {
                padding: 10px 8px;
                text-align: center;
                border: 1px solid #B0C4DE;
                background-color: white;
                color: #000000;
                vertical-align: middle;
            }
            
            /* Bordures visibles pour toutes les cellules */
            .custom-table-voyages th, 
            .custom-table-voyages td {
                border: 1px solid #B0C4DE !important;
            }
            
            /* Bordures épaisses pour l'extérieur du tableau */
            .custom-table-voyages {
                border: 2px solid #4682B4 !important;
            }
            
            /* Conteneur du tableau avec défilement horizontal */
            .table-container-voyages {
                overflow-x: auto;
                margin: 1rem 0;
                border-radius: 8px;
                border: 2px solid #4682B4;
            }
            
            /* Supprimer l'alternance des couleurs - TOUTES LES LIGNES BLANCHES */
            .custom-table-voyages tr:nth-child(even) td {
                background-color: white !important;
            }
            
            /* Survol des lignes - léger effet */
            .custom-table-voyages tr:hover td {
                background-color: #F0F8FF !important;
            }
            
            /* Style pour les cellules multilignes */
            .custom-table-voyages td {
                line-height: 1.4;
            }
            </style>
            """, unsafe_allow_html=True)
            
            # Afficher le tableau avec le style CSS professionnel
            html_table = df_display.to_html(escape=False, index=False, classes="custom-table-voyages", border=0)
            
            st.markdown(f"""
            <div class="table-container-voyages">
                {html_table}
            </div>
            """, unsafe_allow_html=True)
            
            # MÉTRIQUES RÉSUMÉES
            st.markdown("---")
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                total_voyages = len(df_display)
                st.metric("🚐 Total Voyages", total_voyages)
            
            with col2:
                total_zones = df_display["Zone"].nunique() if "Zone" in df_display.columns else 0
                st.metric("🌍 Zones couvertes", total_zones)
            
            with col3:
                camions_loues = df_display["Location_camion"].sum() if "Location_camion" in df_display.columns else 0
                st.metric("🚚 Camions loués", int(camions_loues))
            
            with col4:
                estafettes = total_voyages - camions_loues
                st.metric("📦 Estafettes", estafettes)
            
            # Préparer l'export Excel avec retours à la ligne \n
            df_export = df_clean.copy()
            
            # S'assurer que l'export est aussi trié par zone
            if "Zone" in df_export.columns:
                df_export["Zone_Num"] = df_export["Zone"].str.extract('(\d+)').astype(float)
                df_export = df_export.sort_values("Zone_Num").drop("Zone_Num", axis=1)
            
            # Transformer les colonnes avec retours à la ligne \n pour Excel
            if "Client(s) inclus" in df_export.columns:
                df_export["Client(s) inclus"] = df_export["Client(s) inclus"].astype(str).apply(
                    lambda x: "\n".join(client.strip() for client in x.split(",")) if x != "nan" else ""
                )
            
            if "Représentant(s) inclus" in df_export.columns:
                df_export["Représentant(s) inclus"] = df_export["Représentant(s) inclus"].astype(str).apply(
                    lambda x: "\n".join(rep.strip() for rep in x.split(",")) if x != "nan" else ""
                )
            
            if "BL inclus" in df_export.columns:
                df_export["BL inclus"] = df_export["BL inclus"].astype(str).apply(
                    lambda x: "\n".join(bl.strip() for bl in x.split(";")) if x != "nan" else ""
                )
            
            # Formater les colonnes numériques pour l'export
            if "Poids total chargé" in df_export.columns:
                df_export["Poids total chargé"] = df_export["Poids total chargé"].round(3)
            if "Volume total chargé" in df_export.columns:
                df_export["Volume total chargé"] = df_export["Volume total chargé"].round(3)
            
            # Bouton de téléchargement avec formatage Excel
            from io import BytesIO
            import openpyxl
            from openpyxl.styles import Alignment
            
            excel_buffer = BytesIO()
            
            with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                df_export.to_excel(writer, index=False, sheet_name="Voyages Optimisés")
                
                # Récupérer le workbook et worksheet pour appliquer le formatage
                workbook = writer.book
                worksheet = writer.sheets["Voyages Optimisés"]
                
                # Appliquer le style wrap_text aux colonnes avec retours à la ligne
                wrap_columns = []
                if "Client(s) inclus" in df_export.columns:
                    wrap_columns.append("Client(s) inclus")
                if "Représentant(s) inclus" in df_export.columns:
                    wrap_columns.append("Représentant(s) inclus")
                if "BL inclus" in df_export.columns:
                    wrap_columns.append("BL inclus")
                
                # Appliquer le format wrap_text à toutes les cellules des colonnes concernées
                for col_idx, col_name in enumerate(df_export.columns):
                    if col_name in wrap_columns:
                        col_letter = openpyxl.utils.get_column_letter(col_idx + 1)
                        for row in range(2, len(df_export) + 2):  # Commence à la ligne 2 (après l'en-tête)
                            cell = worksheet[f"{col_letter}{row}"]
                            cell.alignment = Alignment(wrap_text=True, vertical='top')
                
                # Ajuster la largeur des colonnes pour une meilleure visibilité
                for column in worksheet.columns:
                    max_length = 0
                    column_letter = openpyxl.utils.get_column_letter(column[0].column)
                    for cell in column:
                        try:
                            if len(str(cell.value)) > max_length:
                                max_length = len(str(cell.value))
                        except:
                            pass
                    adjusted_width = min(max_length + 2, 50)  # Largeur max de 50
                    worksheet.column_dimensions[column_letter].width = adjusted_width
            
            excel_buffer.seek(0)
            
            st.download_button(
                label="💾 Télécharger Voyages Estafette Optimisés",
                data=excel_buffer,
                file_name="Voyages_Estafette_Optimises.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            
            # Mise à jour pour les sections suivantes
            st.session_state.df_voyages = df_clean
            
        except KeyError as e:
            st.error(f"❌ Erreur de colonne manquante : {e}")
            st.info("🔄 Tentative de récupération des données...")
            
            # Tentative de récupération
            if st.session_state.rental_processor:
                st.session_state.df_voyages = st.session_state.rental_processor.df_base.copy()
                st.rerun()
                
        except Exception as e:
            st.error(f"❌ Erreur lors de l'affichage des voyages optimisés: {str(e)}")
    
    # --- Onglet 2: Validation des voyages ---
    with tab2:
        st.subheader("Validation des voyages")
        
        if st.session_state.df_voyages is not None:
            # Afficher le tableau simplifié pour validation
            df_validation = st.session_state.df_voyages.copy()
            
            # Sélectionner les colonnes principales pour la validation
            colonnes_validation = ["Zone", "Véhicule N°", "Poids total chargé", "Volume total chargé", "BL inclus"]
            colonnes_validation = [col for col in colonnes_validation if col in df_validation.columns]
            
            st.dataframe(df_validation[colonnes_validation], use_container_width=True)
            
            col_val1, col_val2 = st.columns(2)
            
            with col_val1:
                if st.button("✅ Valider tous les voyages", type="primary", use_container_width=True):
                    st.session_state.df_voyages_valides = st.session_state.df_voyages.copy()
                    st.success("✅ Tous les voyages validés avec succès !")
                    st.rerun()
            
            with col_val2:
                if st.button("🔄 Réinitialiser la validation", type="secondary", use_container_width=True):
                    st.session_state.df_voyages_valides = None
                    st.warning("Validation réinitialisée")
                    st.rerun()
            
            # Afficher le statut de validation
            if st.session_state.df_voyages_valides is not None:
                st.info(f"✅ {len(st.session_state.df_voyages_valides)} voyages validés")
        else:
            st.info("ℹ️ Générez d'abord les voyages optimisés dans l'onglet 1")
    
    # --- Onglet 3: Attribution véhicules/chauffeurs ---
    with tab3:
        st.subheader("Attribution véhicules/chauffeurs")
        st.info("Attribuez les ressources aux voyages validés")
        
        # Liste des véhicules et chauffeurs (vous pouvez personnaliser ces listes)
        VEHICULES_DISPONIBLES = [
            'SLG-VEH11', 'SLG-VEH14', 'SLG-VEH22', 'SLG-VEH19',
            'SLG-VEH10', 'SLG-VEH16', 'SLG-VEH23', 'SLG-VEH08', 'SLG-VEH20', 'code-Camion'
        ]
        
        CHAUFFEURS_DETAILS = {
            '09254': 'DAMMAK Karim', '06002': 'MAAZOUN Bassem', '11063': 'SASSI Ramzi',
            '10334': 'BOUJELBENE Mohamed', '15144': 'GADDOUR Rami', '08278': 'DAMMAK Wissem',
            '18339': 'REKIK Ahmed', '07250': 'BARKIA Mustapha', '13321': 'BADRI Moez','99999': 'Chauffeur Camion'
        }
        
        if st.session_state.df_voyages_valides is not None:
            # Initialiser les attributions si nécessaire
            if "attributions" not in st.session_state:
                st.session_state.attributions = {}
            
            for idx, row in st.session_state.df_voyages_valides.iterrows():
                with st.expander(f"Voyage {row.get('Véhicule N°', 'N/A')} | Zone: {row.get('Zone', 'N/A')}"):
                    col_att1, col_att2 = st.columns(2)
                    
                    with col_att1:
                        # Sélection du véhicule
                        vehicule_attribue = st.selectbox(
                            "Véhicule",
                            VEHICULES_DISPONIBLES,
                            key=f"veh_{idx}",
                            index=0
                        )
                    
                    with col_att2:
                        # Sélection du chauffeur
                        options_chauffeurs = [f"{matricule} - {nom}" for matricule, nom in CHAUFFEURS_DETAILS.items()]
                        chauffeur_attribue = st.selectbox(
                            "Chauffeur",
                            options_chauffeurs,
                            key=f"chauff_{idx}",
                            index=0
                        )
                    
                    # Stocker l'attribution
                    st.session_state.attributions[idx] = {
                        "Véhicule": vehicule_attribue,
                        "Chauffeur": chauffeur_attribue
                    }
            
            # Bouton pour appliquer toutes les attributions
            if st.button("💾 Enregistrer toutes les attributions", type="primary", use_container_width=True):
                st.success("✅ Attributions enregistrées avec succès !")
        else:
            st.info("ℹ️ Validez d'abord les voyages dans l'onglet 2")
    
    # --- Onglet 4: Export final ---
    with tab4:
        st.subheader("Export final du planning")
        
        col_exp1, col_exp2 = st.columns(2)
        with col_exp1:
            nom_fichier = st.text_input("Nom du fichier", value="planning_livraisons_final")
        with col_exp2:
            format_export = st.selectbox("Format", ["Excel", "PDF"])
        
        if st.button("🚀 Générer l'export complet", type="primary", use_container_width=True):
            if st.session_state.df_voyages_valides is not None:
                # Créer un DataFrame final avec les attributions
                df_final = st.session_state.df_voyages_valides.copy()
                
                # Ajouter les attributions si disponibles
                if "attributions" in st.session_state and st.session_state.attributions:
                    df_final["Véhicule attribué"] = df_final.index.map(
                        lambda i: st.session_state.attributions.get(i, {}).get("Véhicule", "Non attribué")
                    )
                    df_final["Chauffeur attribué"] = df_final.index.map(
                        lambda i: st.session_state.attributions.get(i, {}).get("Chauffeur", "Non attribué")
                    )
                
                # Export Excel
                excel_data = to_excel(df_final, "Planning Final")
                
                st.download_button(
                    label="💾 Télécharger le planning final",
                    data=excel_data,
                    file_name=f"{nom_fichier}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
                st.success("✅ Export prêt au téléchargement !")
            else:
                st.warning("⚠️ Validez d'abord les voyages pour pouvoir exporter")
    
    # Navigation entre pages
    st.markdown("---")
    col_nav1, col_nav2, col_nav3 = st.columns(3)
    
    with col_nav1:
        if st.button("← Retour à l'optimisation", use_container_width=True):
            st.session_state.page = "optimisation"
            st.rerun()
    
    with col_nav2:
        voyages_valides = len(st.session_state.df_voyages_valides) if st.session_state.df_voyages_valides is not None else 0
        st.metric("📊 Voyages validés", voyages_valides)
    
    with col_nav3:
        if st.button("🔄 Recommencer", type="secondary", use_container_width=True):
            # Réinitialiser seulement certaines données
            keys_to_keep = ['page', 'data_processed', 'df_grouped', 'df_city', 'df_grouped_zone', 
                          'df_zone', 'df_livraisons_original', 'df_livraisons']
            
            for key in list(st.session_state.keys()):
                if key not in keys_to_keep:
                    del st.session_state[key]
            
            st.session_state.rental_processor = TruckRentalProcessor(
                st.session_state.df_optimized_estafettes, 
                st.session_state.df_livraisons_original
            )
            st.success("✅ Application réinitialisée. Vous pouvez repartir de l'optimisation.")
            st.rerun()

# =====================================================
# NAVIGATION PRINCIPALE
# =====================================================
def main():
    # Initialiser la page courante
    if 'page' not in st.session_state:
        st.session_state.page = "import"
    
    # Sidebar avec navigation
    with st.sidebar:
        st.image("https://th.bing.com/th/id/OIP.NX4XkAk56j_1bs6CiYhdxQHaHa?pid=ImgDet&rs=1", width=120)
        st.markdown("<h2 style='text-align: center; color: #1E3A8A;'>🚚 Planning Livraisons</h2>", 
                   unsafe_allow_html=True)
        
        st.markdown("---")
        
        # Boutons de navigation avec icônes
        page_options = {
            "import": {"icon": "📥", "label": "Importation Données"},
            "analyse": {"icon": "🔍", "label": "Analyse Détaillée"},
            "optimisation": {"icon": "🚚", "label": "Optimisation"},
            "finalisation": {"icon": "✅", "label": "Validation & Export"}
        }
        
        for page_key, page_info in page_options.items():
            is_active = st.session_state.page == page_key
            button_type = "primary" if is_active else "secondary"
            
            if st.button(
                f"{page_info['icon']} {page_info['label']}",
                key=f"nav_{page_key}",
                use_container_width=True,
                type=button_type
            ):
                st.session_state.page = page_key
                st.rerun()
        
        st.markdown("---")
        
        # Statut de l'application
        st.markdown("### 📊 Statut")
        if st.session_state.data_processed:
            st.success("✅ Données chargées")
            if st.session_state.df_voyages_valides is not None:
                st.success("✅ Planning validé")
        else:
            st.warning("⏳ Données requises")
        
        # Pied de page sidebar
        st.markdown("---")
        st.markdown("""
        <div style='text-align: center; font-size: 12px; color: #666;'>
            <p>Développé par Zaineb KCHAOU</p>
            <p>📧 Zaineb.KCHAOU@sopal.com</p>
        </div>
        """, unsafe_allow_html=True)
    
    # Affichage de la page sélectionnée
    if st.session_state.page == "import":
        page_import()
    elif st.session_state.page == "analyse":
        page_analyse()
    elif st.session_state.page == "optimisation":
        page_optimisation()
    elif st.session_state.page == "finalisation":
        page_finalisation()

# =====================================================
# LANCEMENT DE L'APPLICATION
# =====================================================
if __name__ == "__main__":
    main()