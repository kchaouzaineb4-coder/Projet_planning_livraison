import streamlit as st
import pandas as pd
from backend import DeliveryProcessor, SEUIL_POIDS, SEUIL_VOLUME 
import plotly.express as px

# =====================================================
# CONFIGURATION DE LA PAGE
# =====================================================
st.set_page_config(page_title="Import & Analyse", layout="wide")

# =====================================================
# FONCTIONS UTILITAIRES
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

def show_df_multiline(df, column_to_multiline):
    """
    Affiche un DataFrame avec les articles multilignes dans la même cellule.
    Chaque 'No livraison' reste sur une seule ligne.
    """
    df_display = df.copy()
    df_display = df_display.groupby(
        ['No livraison', 'Client', 'Ville', 'Représentant', 'Poids total', 'Volume total'],
        as_index=False
    ).agg({column_to_multiline: lambda x: "<br>".join(x.astype(str))})

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
        background-color: #EFF6FF;
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
# CSS PERSONNALISÉ
# =====================================================
st.markdown("""
<style>
/* Centrer le titre principal */
h1 {
    text-align: center !important;
    color: #1E3A8A;
    margin-bottom: 1rem;
}

/* Style pour le header de la section 1 */
section[data-testid="stVerticalBlock"] > div:has(h1:contains("1. 📥 Importation des Données")) {
    background: linear-gradient(135deg, #1E3A8A 0%, #3B82F6 100%);
    padding: 1.5rem;
    border-radius: 10px;
    margin-bottom: 1rem;
    color: white;
}

/* Style pour le titre de la section 1 */
h1:contains("1. 📥 Importation des Données") {
    color: white !important;
    margin-bottom: 0 !important;
}

/* Style pour les colonnes de fichiers */
div[data-testid="stHorizontalBlock"] {
    background-color: #F8FAFC;
    padding: 1rem;
    border-radius: 8px;
    border: 2px solid #E2E8F0;
}

/* Style pour les file uploaders */
div[data-testid="stFileUploader"] {
    background-color: white;
    padding: 1rem;
    border-radius: 8px;
    border: 4px dashed #CBD5E1;
}

/* Style pour le bouton principal */
div[data-testid="stHorizontalBlock"] button[kind="primary"] {
    background: linear-gradient(135deg, #1E3A8A 0%, #2563EB 100%);
    border: none;
    color: white;
    font-weight: bold;
}

/* Style pour les labels des file uploaders */
div[data-testid="stFileUploader"] label {
    font-weight: bold;
    color: #1E40AF;
}

/* Style pour les fichiers uploadés */
div[data-testid="stFileUploader"] div[data-testid="stMarkdownContainer"] {
    background-color: #DBEAFE;
    padding: 0.5rem;
    border-radius: 5px;
    border-left: 4px solid #3B82F6;
}

/* Style pour les onglets */
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

.stTabs [aria-selected="true"] {
    background-color: #0369A1 !important;
    color: white !important;
}

.stTabs [data-baseweb="tab"] p {
    font-size: 16px;
    font-weight: 600;
    margin: 0;
}

.stTabs [aria-selected="true"] p {
    color: white !important;
}

/* Style pour les tableaux */
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

.custom-table th, 
.custom-table td {
    border: 1px solid #B0C4DE !important;
}

.custom-table {
    border: 2px solid #4682B4 !important;
}

.custom-table td:nth-child(5) {
    text-align: center;
    max-width: 200px;
    word-wrap: break-word;
    white-space: normal;
    vertical-align: middle;
}

.custom-table td:nth-child(6),
.custom-table td:nth-child(7) {
    font-weight: normal;
    color: #000000 !important;
    vertical-align: middle;
}

.table-container {
    overflow-x: auto;
    margin: 1rem 0;
    border-radius: 8px;
    border: 2px solid #4682B4;
}

.custom-table tr:nth-child(even) td {
    background-color: white !important;
}

.custom-table tr:hover td {
    background-color: #F0F8FF !important;
}
</style>
""", unsafe_allow_html=True)

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
    st.session_state.df_livraisons_original = None
    st.session_state.df_livraisons = None

# =====================================================
# TITRE PRINCIPAL
# =====================================================
st.title("🚚 Planning de Livraisons & Optimisation des Tournées")

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
                    # Récupération des 6 valeurs
                    df_grouped, df_city, df_grouped_zone, df_zone, df_optimized_estafettes, df_livraisons_original = processor.process_delivery_data(liv_file, ydlogist_file, wcliegps_file)
                
                # Stockage des résultats dans l'état de session
                st.session_state.df_optimized_estafettes = df_optimized_estafettes
                st.session_state.df_grouped = df_grouped
                st.session_state.df_city = df_city
                st.session_state.df_grouped_zone = df_grouped_zone
                st.session_state.df_zone = df_zone 
                st.session_state.df_livraisons_original = df_livraisons_original
                st.session_state.df_livraisons = df_grouped_zone  # Pour la section transfert
                
                st.session_state.data_processed = True
                st.rerun()

            except Exception as e:
                st.error(f"❌ Erreur lors du traitement : {str(e)}")
                st.session_state.data_processed = False
        else:
            st.warning("Veuillez uploader tous les fichiers nécessaires.")
st.markdown("---")

# =====================================================
# 2. ANALYSE DE LIVRAISON DÉTAILLÉE (Section 2)
# =====================================================
if st.session_state.data_processed:
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
        
        # Créer une copie du DataFrame et FILTRER TRIPOLI
        df_liv = st.session_state.df_grouped.drop(columns=["Zone"], errors='ignore').copy()
        df_liv = df_liv[df_liv["Ville"] != "TRIPOLI"]
        
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
        
        # Métriques résumées - CORRECTION : Utiliser les données filtrées
        st.markdown("---")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            total_livraisons = len(df_liv)
            st.metric("📦 Total Livraisons", total_livraisons)
        
        with col2:
            total_clients = df_liv["Client"].nunique()
            st.metric("👥 Clients Uniques", total_clients)
        
        with col3:
            # CORRECTION : Calculer le poids total à partir des données filtrées (données originales)
            df_liv_original = st.session_state.df_grouped[st.session_state.df_grouped["Ville"] != "TRIPOLI"]
            total_poids = df_liv_original["Poids total"].sum()
            st.metric("⚖️ Poids Total", f"{total_poids:.3f} kg")
        
        with col4:
            # CORRECTION : Calculer le volume total à partir des données filtrées (données originales)
            total_volume = df_liv_original["Volume total"].sum()
            st.metric("📏 Volume Total", f"{total_volume:.3f} m³")
        
        # AJOUT DE L'IMPORT MANQUANT POUR BytesIO
        from io import BytesIO
        
        # Bouton de téléchargement (garder les données originales pour l'export)
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
        
        # Stockage pour la section 5
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
        
        # Vérifier si le DataFrame n'est pas vide après filtrage
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
        
        # Métriques résumées - CORRECTION : Utiliser les données filtrées
        st.markdown("---")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            total_villes = len(df_city_display)
            st.metric("🏙️ Total Villes", total_villes)
        
        with col2:
            # CORRECTION : Utiliser les données filtrées pour les calculs
            df_city_original_filtered = st.session_state.df_city[st.session_state.df_city["Ville"] != "TRIPOLI"]
            total_bls = df_city_original_filtered["Nombre de BLs"].sum() if "Nombre de BLs" in df_city_original_filtered.columns else 0
            st.metric("📦 Total BLs", int(total_bls))
        
        with col3:
            # CORRECTION : Utiliser les données filtrées pour les calculs
            total_estafettes = df_city_original_filtered["Besoin estafette réel"].sum() if "Besoin estafette réel" in df_city_original_filtered.columns else 0
            st.metric("🚐 Besoin Estafettes", f"{total_estafettes:.1f}")

        # Bouton de téléchargement (garder les données originales pour l'export)
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
        
        # Formater les nombres - 3 chiffres après la virgule
        if "Poids total" in df_zone_display.columns:
            df_zone_display["Poids total"] = df_zone_display["Poids total"].map(lambda x: f"{x:.3f} kg" if pd.notna(x) else "")
        if "Volume total" in df_zone_display.columns:
            df_zone_display["Volume total"] = df_zone_display["Volume total"].map(lambda x: f"{x:.3f} m³" if pd.notna(x) else "")
        if "Besoin estafette réel" in df_zone_display.columns:
            df_zone_display["Besoin estafette réel"] = df_zone_display["Besoin estafette réel"].map(lambda x: f"{x:.1f}" if pd.notna(x) else "")
        # MAINTENANT ON UTILISE "Nombre de BLs" AU LIEU DE "Nombre livraisons"
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
        
        # Métriques résumées - CORRECTION : Utiliser les données originales pour les calculs
        st.markdown("---")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            total_zones = len(df_zone_display)
            st.metric("🌍 Total Zones", total_zones)
        
        with col2:
            # Utiliser les données originales pour les calculs (avec l'ancien nom de colonne)
            if "Nombre livraisons" in st.session_state.df_zone.columns:
                total_bls_zone = st.session_state.df_zone["Nombre livraisons"].sum()
            else:
                total_bls_zone = 0
            st.metric("📦 Total BLs", int(total_bls_zone))
        
        with col3:
            # Utiliser les données originales pour les calculs
            total_estafettes_zone = st.session_state.df_zone["Besoin estafette réel"].sum() if "Besoin estafette réel" in st.session_state.df_zone.columns else 0
            st.metric("🚐 Besoin Estafettes", f"{total_estafettes_zone:.1f}")
        
        # Bouton de téléchargement
        excel_buffer_zone = BytesIO()
        with pd.ExcelWriter(excel_buffer_zone, engine='openpyxl') as writer:
            # Pour l'export Excel, on utilise les données originales
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
            st.plotly_chart(f3, use_container_width=True)
            
        with col4:
            fig4 = px.bar(df_filtered, x="Ville", y="Besoin estafette réel", **chart_config)
            fig4.update_layout(title_text="Besoin en Estafettes par ville", title_x=0.5)
            st.plotly_chart(fig4, use_container_width=True)

    st.markdown("---")

# =====================================================
# PIED DE PAGE
# =====================================================
st.markdown("---")
st.markdown(
    """
    <div style='text-align: center; color: #666;'>
        <p>🚚 <strong>Système d'Optimisation des Livraisons</strong> - Développé par Zaineb KCHAOU</p>
        <p>📧 Support : Zaineb.KCHAOU@sopal.com | 📞 Hotline : +216 23 130 088</p>
    </div>
    """,
    unsafe_allow_html=True
)