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
# PAGE 2: ANALYSE DÉTAILLÉE
# =====================================================
def page_analyse():
    st.markdown("<h1 class='main-header'>2. 🔍 ANALYSE DÉTAILLÉE</h1>", unsafe_allow_html=True)
    
    if not st.session_state.data_processed:
        st.warning("⚠️ Veuillez d'abord importer les données dans la page 1.")
        if st.button("📥 Retour à l'importation"):
            st.session_state.page = "import"
            st.rerun()
        return
    
    # Onglets pour différents types d'analyse
    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 Par Ville", 
        "🏢 Par Client", 
        "🌍 Par Zone", 
        "📈 Graphiques"
    ])
    
    with tab1:
        st.subheader("Analyse par Ville")
        if st.session_state.df_city is not None:
            show_df(st.session_state.df_city, use_container_width=True)
            
    with tab2:
        st.subheader("Analyse par Client")
        if st.session_state.df_grouped is not None:
            show_df(st.session_state.df_grouped, use_container_width=True)
            
    with tab3:
        st.subheader("Analyse par Zone")
        if st.session_state.df_zone is not None:
            show_df(st.session_state.df_zone, use_container_width=True)
    
    with tab4:
        st.subheader("Graphiques de distribution")
        if st.session_state.df_city is not None:
            col_chart1, col_chart2 = st.columns(2)
            
            with col_chart1:
                fig1 = px.bar(st.session_state.df_city, x="Ville", y="Poids total",
                             title="Poids total par ville")
                st.plotly_chart(fig1, use_container_width=True)
                
            with col_chart2:
                fig2 = px.bar(st.session_state.df_city, x="Ville", y="Volume total",
                             title="Volume total par ville")
                st.plotly_chart(fig2, use_container_width=True)
    
    # Navigation
    st.markdown("---")
    col_nav1, col_nav2, col_nav3 = st.columns(3)
    
    with col_nav1:
        if st.button("← Retour à l'importation"):
            st.session_state.page = "import"
            st.rerun()
    
    with col_nav2:
        if st.button("📊 Exporter l'analyse"):
            if st.session_state.df_city is not None:
                excel_data = to_excel(st.session_state.df_city, "Analyse")
                st.download_button(
                    label="💾 Télécharger Excel",
                    data=excel_data,
                    file_name="analyse_livraisons.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
    
    with col_nav3:
        if st.button("🚚 Optimisation des tournées →"):
            st.session_state.page = "optimisation"
            st.rerun()

# =====================================================
# PAGE 3: OPTIMISATION ET LOCATION
# =====================================================
def page_optimisation():
    st.markdown("<h1 class='main-header'>3. 🚚 OPTIMISATION & LOCATION</h1>", unsafe_allow_html=True)
    
    if not st.session_state.data_processed:
        st.warning("⚠️ Veuillez d'abord importer les données dans la page 1.")
        if st.button("📥 Retour à l'importation"):
            st.session_state.page = "import"
            st.rerun()
        return
    
    tab1, tab2, tab3 = st.tabs([
        "📋 Propositions Location", 
        "🔄 Transfert BLs", 
        "📦 Ajout Objets"
    ])
    
    with tab1:
        st.subheader("Propositions de Location de Camion")
        st.info(f"Seuils: {SEUIL_POIDS} kg ou {SEUIL_VOLUME} m³")
        
        if st.session_state.rental_processor:
            propositions = st.session_state.rental_processor.detecter_propositions()
            if not propositions.empty:
                show_df(propositions, use_container_width=True)
            else:
                st.success("✅ Aucune proposition de location nécessaire.")
    
    with tab2:
        st.subheader("Transfert de BLs entre véhicules")
        st.info("Réorganisez les livraisons entre estafettes")
        
        if st.session_state.df_voyages is not None:
            # Interface de transfert simplifiée
            col_trans1, col_trans2 = st.columns(2)
            with col_trans1:
                source = st.selectbox("Véhicule source", options=["Véh1", "Véh2", "Véh3"])
            with col_trans2:
                destination = st.selectbox("Véhicule destination", options=["Véh1", "Véh2", "Véh3"])
            
            if st.button("🔄 Exécuter le transfert"):
                st.success("Transfert simulé avec succès")
    
    with tab3:
        st.subheader("Ajout d'objets manuels")
        st.info("Ajoutez des colis urgents aux véhicules")
        
        col_obj1, col_obj2, col_obj3 = st.columns(3)
        with col_obj1:
            nom_objet = st.text_input("Nom de l'objet")
        with col_obj2:
            poids = st.number_input("Poids (kg)", min_value=0.0, value=10.0)
        with col_obj3:
            volume = st.number_input("Volume (m³)", min_value=0.0, value=0.1)
        
        if st.button("➕ Ajouter l'objet"):
            st.success("Objet ajouté avec succès")
    
    # Navigation
    st.markdown("---")
    col_nav1, col_nav2, col_nav3 = st.columns(3)
    
    with col_nav1:
        if st.button("← Retour à l'analyse"):
            st.session_state.page = "analyse"
            st.rerun()
    
    with col_nav2:
        if st.button("📋 Voir les voyages optimisés"):
            # Calcul des voyages optimisés
            if st.session_state.rental_processor:
                df_optimized = st.session_state.rental_processor.get_df_result()
                st.session_state.df_voyages = df_optimized
                st.success("✅ Voyages optimisés générés")
    
    with col_nav3:
        if st.button("✅ Validation & Export →"):
            st.session_state.page = "finalisation"
            st.rerun()

# =====================================================
# PAGE 4: VALIDATION ET EXPORT FINAL
# =====================================================
def page_finalisation():
    st.markdown("<h1 class='main-header'>4. ✅ VALIDATION & EXPORT FINAL</h1>", unsafe_allow_html=True)
    
    if not st.session_state.data_processed:
        st.warning("⚠️ Veuillez d'abord importer les données dans la page 1.")
        if st.button("📥 Retour à l'importation"):
            st.session_state.page = "import"
            st.rerun()
        return
    
    tab1, tab2, tab3 = st.tabs([
        "✅ Validation", 
        "🚛 Attribution", 
        "📤 Export"
    ])
    
    with tab1:
        st.subheader("Validation des voyages")
        if st.session_state.df_voyages is not None:
            st.dataframe(st.session_state.df_voyages, use_container_width=True)
            
            if st.button("✅ Valider tous les voyages"):
                st.session_state.df_voyages_valides = st.session_state.df_voyages.copy()
                st.success("✅ Tous les voyages validés avec succès !")
    
    with tab2:
        st.subheader("Attribution véhicules/chauffeurs")
        st.info("Attribuez les ressources aux voyages validés")
        
        # Liste des véhicules et chauffeurs
        VEHICULES = ["Véh1", "Véh2", "Véh3", "Camion1"]
        CHAUFFEURS = ["Jean Dupont", "Marie Martin", "Paul Durand"]
        
        if st.session_state.df_voyages_valides is not None:
            for idx, row in st.session_state.df_voyages_valides.iterrows():
                with st.expander(f"Voyage {row.get('Véhicule N°', 'N/A')}"):
                    col_att1, col_att2 = st.columns(2)
                    with col_att1:
                        st.selectbox("Véhicule", VEHICULES, key=f"veh_{idx}")
                    with col_att2:
                        st.selectbox("Chauffeur", CHAUFFEURS, key=f"chauff_{idx}")
    
    with tab3:
        st.subheader("Export final du planning")
        
        col_exp1, col_exp2 = st.columns(2)
        with col_exp1:
            nom_fichier = st.text_input("Nom du fichier", value="planning_livraisons")
        with col_exp2:
            format_export = st.selectbox("Format", ["Excel", "PDF"])
        
        if st.button("🚀 Générer l'export complet"):
            if st.session_state.df_voyages_valides is not None:
                # Export Excel
                excel_data = to_excel(st.session_state.df_voyages_valides, "Planning Final")
                
                st.download_button(
                    label="💾 Télécharger le planning",
                    data=excel_data,
                    file_name=f"{nom_fichier}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
                st.success("✅ Export prêt au téléchargement !")
    
    # Navigation et résumé
    st.markdown("---")
    col_res1, col_res2, col_res3 = st.columns(3)
    
    with col_res1:
        if st.button("← Retour à l'optimisation"):
            st.session_state.page = "optimisation"
            st.rerun()
    
    with col_res2:
        st.metric("📊 Voyages validés", 
                 f"{len(st.session_state.df_voyages_valides) if st.session_state.df_voyages_valides is not None else 0}")
    
    with col_res3:
        if st.button("🔄 Recommencer", type="secondary"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
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
        st.markdown("""
        <style>
        .logo-hover {
            transition: transform 0.3s ease;
        }
        .logo-hover:hover {
            transform: scale(1.05);
        }
        </style>
        
        <div style="text-align: center; padding: 25px 0;">
            <div class="logo-hover">
                <img src="logo.png" width="100" 
                    style="border-radius: 50%; box-shadow: 0 4px 12px rgba(30, 58, 138, 0.3);">
            </div>
            <h3 style="color: #1E3A8A; margin: 15px 0 5px 0; font-weight: 700;">SOPAL Logistics</h3>
            <p style="color: #4B5563; font-size: 13px; margin: 0;">Optimisation des tournées</p>
        </div>
        """, unsafe_allow_html=True)
            
          
        
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