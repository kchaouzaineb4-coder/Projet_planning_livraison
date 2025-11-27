import streamlit as st

# Configuration de la page
st.set_page_config(
    page_title="Planning Livraisons", 
    layout="wide",
    initial_sidebar_state="collapsed"
)

# CSS pour la navigation et le style général
st.markdown("""
<style>
    /* Navigation stylée */
    .nav-container {
        display: flex;
        justify-content: center;
        gap: 10px;
        margin-bottom: 2rem;
        padding: 1rem;
        background: linear-gradient(135deg, #1E3A8A 0%, #3B82F6 100%);
        border-radius: 10px;
    }
    .nav-button {
        padding: 12px 20px;
        border: none;
        border-radius: 8px;
        background-color: white;
        color: #1E3A8A;
        font-weight: bold;
        cursor: pointer;
        transition: all 0.3s ease;
        text-decoration: none;
        display: flex;
        align-items: center;
        gap: 8px;
        font-size: 16px;
    }
    .nav-button:hover {
        background-color: #EFF6FF;
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(0,0,0,0.2);
    }
    .nav-button.active {
        background-color: #0369A1;
        color: white;
    }
    
    /* Style pour centrer le titre */
    h1 {
        text-align: center !important;
        color: #1E3A8A;
        margin-bottom: 1rem;
    }
    
    /* Style général pour les tableaux */
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
    .table-container {
        overflow-x: auto;
        margin: 1rem 0;
        border-radius: 8px;
        border: 2px solid #4682B4;
    }
    
    /* Cacher la sidebar par défaut */
    section[data-testid="stSidebar"] {
        display: none;
    }
    
    /* Forcer l'affichage en plein écran */
    .main .block-container {
        max-width: 100%;
        padding-left: 2rem;
        padding-right: 2rem;
    }
</style>
""", unsafe_allow_html=True)

# Titre principal
st.title("🚚 Planning de Livraisons & Optimisation des Tournées")

# Navigation avec liens directs vers les pages
st.markdown("""
<div class="nav-container">
    <a href="/1_Import_et_Analyse" target="_self" class="nav-button">📥 Import & Analyse</a>
    <a href="/2_Optimisation_et_Transfert" target="_self" class="nav-button">🚚 Optimisation & Transfert</a>
    <a href="/3_Validation_et_Planning" target="_self" class="nav-button">✅ Validation & Planning</a>
    <a href="/4_KPIs_et_Dashboard" target="_self" class="nav-button">📊 KPIs & Dashboard</a>
</div>
""", unsafe_allow_html=True)

# Message d'accueil sur la page principale
st.markdown("---")
st.success("👆 **Utilisez les boutons de navigation ci-dessus pour accéder aux différentes sections de l'application**")

st.info("""
**Fonctionnalités disponibles :**
- 📥 **Page 1** : Import des données et analyse des livraisons
- 🚚 **Page 2** : Optimisation et transfert entre véhicules  
- ✅ **Page 3** : Validation des voyages et planning final
- 📊 **Page 4** : Tableau de bord et indicateurs de performance
""")

# Initialisation de l'état de session
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
    st.session_state.validations = {}
    st.session_state.attributions = {}

# Instructions pour la navigation
st.markdown("---")
st.markdown("### 🎯 Comment naviguer entre les pages :")
st.markdown("""
1. **Cliquez sur les boutons colorés en haut** pour changer de page
2. **Chaque page conserve les données** que vous avez saisies
3. **L'ordre recommandé** est de suivre les pages de 1 à 4
4. **Vous pouvez revenir** à n'importe quelle page à tout moment
""")

# Pied de page
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