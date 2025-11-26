import streamlit as st

st.set_page_config(
    page_title="Planning Livraisons",
    page_icon="🚚",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("🚚 Système de Planning de Livraisons")
st.markdown("---")

st.markdown("""
### 📋 Navigation

Utilisez la sidebar à gauche pour naviguer entre les différentes sections :

1. **📥 Import et Analyse** - Chargement et analyse initiale des données
2. **🔄 Optimisation et Transfert** - Optimisation des tournées et transferts
3. **✅ Validation et Attribution** - Validation et attribution véhicules/chauffeurs
4. **📋 Planning Final** - Génération du planning final et rapports

### 🔄 État de la session
Toutes les données sont conservées pendant votre navigation.
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

# Afficher l'état actuel
if st.session_state.data_processed:
    st.success("✅ Données chargées et prêtes pour l'analyse")
else:
    st.info("📤 Veuillez commencer par importer les données dans la section 'Import et Analyse'")