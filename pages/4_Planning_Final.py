import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
from datetime import datetime
from io import BytesIO
from fpdf import FPDF
import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill
from openpyxl.utils.dataframe import dataframe_to_rows

# =====================================================
# CONFIGURATION DE LA PAGE
# =====================================================
st.set_page_config(
    page_title="Tableaux de Bord & Analytics",
    page_icon="📊",
    layout="wide"
)
st.title("📋 Planning Final")
# =====================================================
# CSS PERSONNALISÉ
# =====================================================
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
        font-weight: bold;
    }
    .section-header {
        font-size: 1.8rem;
        color: #2e86ab;
        margin: 2rem 0 1rem 0;
        padding-bottom: 0.5rem;
        border-bottom: 2px solid #2e86ab;
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 1.5rem;
        border-radius: 10px;
        text-align: center;
        margin: 0.5rem;
    }
    .kpi-value {
        font-size: 2rem;
        font-weight: bold;
        margin: 0.5rem 0;
    }
    .kpi-label {
        font-size: 1rem;
        opacity: 0.9;
    }
    .positive-trend {
        color: #00ff00;
        font-weight: bold;
    }
    .negative-trend {
        color: #ff4444;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# =====================================================
# FONCTIONS UTILITAIRES
# =====================================================
def format_number(num):
    """Formate les nombres avec séparateurs de milliers"""
    if isinstance(num, (int, float)):
        return f"{num:,.0f}".replace(",", " ")
    return num

def create_gauge_chart(value, max_value, title):
    """Crée un graphique jauge pour les KPI"""
    fig = go.Figure(go.Indicator(
        mode = "gauge+number+delta",
        value = value,
        domain = {'x': [0, 1], 'y': [0, 1]},
        title = {'text': title},
        delta = {'reference': max_value * 0.8},
        gauge = {
            'axis': {'range': [None, max_value]},
            'bar': {'color': "darkblue"},
            'steps': [
                {'range': [0, max_value*0.6], 'color': "lightgray"},
                {'range': [max_value*0.6, max_value*0.8], 'color': "gray"},
                {'range': [max_value*0.8, max_value], 'color': "darkgray"}
            ],
            'threshold': {
                'line': {'color': "red", 'width': 4},
                'thickness': 0.75,
                'value': max_value * 0.9
            }
        }
    ))
    fig.update_layout(height=300, margin=dict(l=20, r=20, t=50, b=20))
    return fig

# =====================================================
# CLASSE ANALYTICS MANAGER
# =====================================================
class AnalyticsManager:
    def __init__(self, df_voyages, df_livraisons):
        self.df_voyages = df_voyages.copy()
        self.df_livraisons = df_livraisons.copy()
        
    def calculer_kpis_principaux(self):
        """Calcule les KPI principaux"""
        kpis = {}
        
        # KPI de base
        kpis['total_voyages'] = len(self.df_voyages)
        kpis['total_poids'] = self.df_voyages['Poids total chargé'].sum()
        kpis['total_volume'] = self.df_voyages['Volume total chargé'].sum()
        kpis['taux_occupation_moyen'] = self.df_voyages['Taux d\'occupation (%)'].mean()
        
        # KPI d'efficacité
        kpis['voyages_par_zone'] = self.df_voyages['Zone'].value_counts().to_dict()
        kpis['zones_couvertes'] = len(self.df_voyages['Zone'].unique())
        
        # KPI d'optimisation
        voyages_optimaux = self.df_voyages[self.df_voyages['Taux d\'occupation (%)'] > 80]
        kpis['taux_optimisation'] = len(voyages_optimaux) / len(self.df_voyages) * 100
        
        return kpis
    
    def generer_analyse_tendances(self):
        """Génère l'analyse des tendances"""
        # Analyse par zone
        tendances_zone = self.df_voyages.groupby('Zone').agg({
            'Poids total chargé': 'sum',
            'Volume total chargé': 'sum',
            'Taux d\'occupation (%)': 'mean',
            'Véhicule N°': 'count'
        }).round(2)
        
        tendances_zone = tendances_zone.rename(columns={
            'Véhicule N°': 'Nombre de Voyages',
            'Poids total chargé': 'Poids Total (kg)',
            'Volume total chargé': 'Volume Total (m³)',
            'Taux d\'occupation (%)': 'Taux Occupation Moyen (%)'
        })
        
        return tendances_zone
    
    def generer_analyse_vehicules(self):
        """Analyse la performance des véhicules"""
        if 'Véhicule attribué' in self.df_voyages.columns:
            perf_vehicules = self.df_voyages.groupby('Véhicule attribué').agg({
                'Poids total chargé': ['sum', 'mean', 'max'],
                'Volume total chargé': ['sum', 'mean', 'max'],
                'Taux d\'occupation (%)': 'mean',
                'Véhicule N°': 'count'
            }).round(2)
            
            perf_vehicules.columns = ['_'.join(col).strip() for col in perf_vehicules.columns]
            perf_vehicules = perf_vehicules.rename(columns={
                'Véhicule N°_count': 'Nb_Voyages',
                'Poids total chargé_sum': 'Poids_Total_kg',
                'Poids total chargé_mean': 'Poids_Moyen_kg',
                'Poids total chargé_max': 'Poids_Max_kg',
                'Volume total chargé_sum': 'Volume_Total_m3',
                'Volume total chargé_mean': 'Volume_Moyen_m3',
                'Volume total chargé_max': 'Volume_Max_m3',
                'Taux d\'occupation (%)_mean': 'Taux_Occupation_Moyen_%'
            })
            
            return perf_vehicules
        return None
    
    def generer_visualisations_avancees(self):
        """Génère des visualisations avancées"""
        visualisations = {}
        
        # 1. Heatmap de corrélation
        numeric_cols = self.df_voyages.select_dtypes(include=[np.number]).columns
        if len(numeric_cols) > 1:
            corr_matrix = self.df_voyages[numeric_cols].corr()
            fig_heatmap = px.imshow(
                corr_matrix,
                title="Heatmap de Corrélation entre les Variables",
                color_continuous_scale="RdBu_r",
                aspect="auto"
            )
            visualisations['heatmap'] = fig_heatmap
        
        # 2. Distribution des taux d'occupation
        fig_distribution = px.histogram(
            self.df_voyages,
            x='Taux d\'occupation (%)',
            nbins=20,
            title="Distribution des Taux d'Occupation",
            color_discrete_sequence=['#2e86ab']
        )
        fig_distribution.update_layout(
            xaxis_title="Taux d'Occupation (%)",
            yaxis_title="Nombre de Voyages"
        )
        visualisations['distribution_occupation'] = fig_distribution
        
        # 3. Analyse comparative zones
        zone_stats = self.df_voyages.groupby('Zone').agg({
            'Poids total chargé': 'mean',
            'Volume total chargé': 'mean',
            'Taux d\'occupation (%)': 'mean'
        }).reset_index()
        
        fig_comparaison = go.Figure()
        fig_comparaison.add_trace(go.Bar(
            name='Poids Moyen (kg)',
            x=zone_stats['Zone'],
            y=zone_stats['Poids total chargé'],
            yaxis='y',
            offsetgroup=1
        ))
        fig_comparaison.add_trace(go.Bar(
            name='Volume Moyen (m³)',
            x=zone_stats['Zone'],
            y=zone_stats['Volume total chargé'],
            yaxis='y2',
            offsetgroup=2
        ))
        
        fig_comparaison.update_layout(
            title="Comparaison des Zones - Poids et Volume Moyens",
            xaxis_title="Zones",
            yaxis=dict(title="Poids Moyen (kg)", side="left"),
            yaxis2=dict(title="Volume Moyen (m³)", side="right", overlaying="y"),
            barmode="group"
        )
        visualisations['comparaison_zones'] = fig_comparaison
        
        return visualisations

# =====================================================
# INTERFACE PRINCIPALE
# =====================================================
st.markdown('<div class="main-header">📊 TABLEAUX DE BORD & ANALYTICS AVANCÉS</div>', unsafe_allow_html=True)

# Vérification des données
if "df_voyages_valides" not in st.session_state:
    st.warning("⚠️ Veuillez d'abord valider les voyages dans la page 'Validation & Attribution'")
    st.stop()

# Initialisation de l'analytics manager
analytics_manager = AnalyticsManager(
    st.session_state.df_voyages_valides,
    st.session_state.df_livraisons_original
)

# =====================================================
# 1. VUE SYNTHÈSE AVEC KPI
# =====================================================
st.markdown('<div class="section-header">📈 VUE SYNTHÈSE - INDICATEURS CLÉS</div>', unsafe_allow_html=True)

# Calcul des KPI
kpis = analytics_manager.calculer_kpis_principaux()

# Affichage des KPI en cartes
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown(f"""
    <div class="metric-card">
        <div class="kpi-label">Nombre Total de Voyages</div>
        <div class="kpi-value">{format_number(kpis['total_voyages'])}</div>
        <div>Zones couvertes: {kpis['zones_couvertes']}</div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown(f"""
    <div class="metric-card">
        <div class="kpi-label">Poids Total Transporté</div>
        <div class="kpi-value">{format_number(kpis['total_poids'])} kg</div>
        <div>Optimisation: {kpis['taux_optimisation']:.1f}%</div>
    </div>
    """, unsafe_allow_html=True)

with col3:
    st.markdown(f"""
    <div class="metric-card">
        <div class="kpi-label">Volume Total Transporté</div>
        <div class="kpi-value">{format_number(kpis['total_volume'])} m³</div>
        <div>Efficacité logistique</div>
    </div>
    """, unsafe_allow_html=True)

with col4:
    st.markdown(f"""
    <div class="metric-card">
        <div class="kpi-label">Taux d'Occupation Moyen</div>
        <div class="kpi-value">{kpis['taux_occupation_moyen']:.1f}%</div>
        <div>Performance globale</div>
    </div>
    """, unsafe_allow_html=True)

# =====================================================
# 2. ANALYSE DES TENDANCES
# =====================================================
st.markdown('<div class="section-header">📊 ANALYSE DES TENDANCES PAR ZONE</div>', unsafe_allow_html=True)

# Génération des tendances
tendances_zone = analytics_manager.generer_analyse_tendances()

if not tendances_zone.empty:
    col_graph1, col_graph2 = st.columns(2)
    
    with col_graph1:
        # Graphique de répartition par zone
        fig_repartition = px.pie(
            names=tendances_zone.index,
            values=tendances_zone['Nombre de Voyages'],
            title="Répartition des Voyages par Zone",
            color_discrete_sequence=px.colors.qualitative.Set3
        )
        st.plotly_chart(fig_repartition, use_container_width=True)
    
    with col_graph2:
        # Graphique de performance par zone
        fig_performance = px.bar(
            tendances_zone.reset_index(),
            x='Zone',
            y='Taux Occupation Moyen (%)',
            title="Taux d'Occupation Moyen par Zone",
            color='Taux Occupation Moyen (%)',
            color_continuous_scale='Viridis'
        )
        st.plotly_chart(fig_performance, use_container_width=True)
    
    # Tableau détaillé des tendances
    st.subheader("Tableau Détaillé des Performances par Zone")
    st.dataframe(tendances_zone, use_container_width=True)

# =====================================================
# 3. ANALYSE DES VÉHICULES
# =====================================================
st.markdown('<div class="section-header">🚚 ANALYSE DE LA PERFORMANCE DES VÉHICULES</div>', unsafe_allow_html=True)

analyse_vehicules = analytics_manager.generer_analyse_vehicules()

if analyse_vehicules is not None:
    col_veh1, col_veh2 = st.columns(2)
    
    with col_veh1:
        # Graphique d'utilisation des véhicules
        fig_utilisation = px.bar(
            analyse_vehicules.reset_index(),
            x='Véhicule attribué',
            y='Nb_Voyages',
            title="Nombre de Voyages par Véhicule",
            color='Nb_Voyages',
            color_continuous_scale='Blues'
        )
        st.plotly_chart(fig_utilisation, use_container_width=True)
    
    with col_veh2:
        # Graphique de performance des véhicules
        fig_perf_vehicules = px.scatter(
            analyse_vehicules.reset_index(),
            x='Poids_Moyen_kg',
            y='Taux_Occupation_Moyen_%',
            size='Nb_Voyages',
            color='Véhicule attribué',
            title="Performance des Véhicules - Poids vs Taux d'Occupation",
            hover_name='Véhicule attribué',
            size_max=60
        )
        st.plotly_chart(fig_perf_vehicules, use_container_width=True)
    
    # Tableau de performance des véhicules
    st.subheader("Tableau de Performance Détaillé des Véhicules")
    st.dataframe(analyse_vehicules, use_container_width=True)

# =====================================================
# 4. VISUALISATIONS AVANCÉES
# =====================================================
st.markdown('<div class="section-header">🔍 ANALYTICS AVANCÉS</div>', unsafe_allow_html=True)

visualisations = analytics_manager.generer_visualisations_avancees()

if visualisations:
    tab1, tab2, tab3 = st.tabs(["📈 Corrélations", "📊 Distributions", "🗺️ Comparaisons"])
    
    with tab1:
        if 'heatmap' in visualisations:
            st.plotly_chart(visualisations['heatmap'], use_container_width=True)
    
    with tab2:
        if 'distribution_occupation' in visualisations:
            st.plotly_chart(visualisations['distribution_occupation'], use_container_width=True)
    
    with tab3:
        if 'comparaison_zones' in visualisations:
            st.plotly_chart(visualisations['comparaison_zones'], use_container_width=True)

# =====================================================
# 5. RAPPORTS PERSONNALISÉS
# =====================================================
st.markdown('<div class="section-header">📋 GÉNÉRATION DE RAPPORTS</div>', unsafe_allow_html=True)

col_rapport1, col_rapport2 = st.columns(2)

with col_rapport1:
    st.subheader("Rapport de Performance")
    
    periode_rapport = st.selectbox(
        "Période d'analyse",
        ["Journalier", "Hebdomadaire", "Mensuel", "Complet"]
    )
    
    niveau_detail = st.selectbox(
        "Niveau de détail",
        ["Synthèse", "Détaillé", "Expert"]
    )

with col_rapport2:
    st.subheader("Export des Données")
    
    # Boutons d'export
    col_exp1, col_exp2 = st.columns(2)
    
    with col_exp1:
        if st.button("📊 Exporter Données Brutes", use_container_width=True):
            # Code pour exporter les données brutes
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                st.session_state.df_voyages_valides.to_excel(writer, sheet_name='Voyages_Valides', index=False)
                st.session_state.df_livraisons_original.to_excel(writer, sheet_name='Livraisons_Originales', index=False)
            
            st.download_button(
                label="💾 Télécharger Fichier Excel",
                data=output.getvalue(),
                file_name="donnees_optimisation_complete.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
    
    with col_exp2:
        if st.button("📈 Exporter Analytics", use_container_width=True):
            # Code pour exporter les analyses
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                kpis_df = pd.DataFrame([kpis])
                kpis_df.to_excel(writer, sheet_name='KPI_Principaux', index=False)
                
                if not tendances_zone.empty:
                    tendances_zone.to_excel(writer, sheet_name='Tendances_Zones')
                
                if analyse_vehicules is not None:
                    analyse_vehicules.to_excel(writer, sheet_name='Performance_Vehicules')
            
            st.download_button(
                label="💾 Télécharger Analytics",
                data=output.getvalue(),
                file_name="analytics_optimisation.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

# =====================================================
# 6. TABLEAU DE BORD INTERACTIF
# =====================================================
st.markdown('<div class="section-header">🎯 TABLEAU DE BORD INTERACTIF</div>', unsafe_allow_html=True)

# Filtres interactifs
col_filtre1, col_filtre2, col_filtre3 = st.columns(3)

with col_filtre1:
    zones_disponibles = st.session_state.df_voyages_valides['Zone'].unique()
    zone_filtre = st.multiselect(
        "Filtrer par Zone",
        options=zones_disponibles,
        default=zones_disponibles
    )

with col_filtre2:
    if 'Véhicule attribué' in st.session_state.df_voyages_valides.columns:
        vehicules_disponibles = st.session_state.df_voyages_valides['Véhicule attribué'].unique()
        vehicule_filtre = st.multiselect(
            "Filtrer par Véhicule",
            options=vehicules_disponibles,
            default=vehicules_disponibles
        )

with col_filtre3:
    min_occupation, max_occupation = st.slider(
        "Filtrer par Taux d'Occupation (%)",
        min_value=0.0,
        max_value=100.0,
        value=(0.0, 100.0)
    )

# Application des filtres
df_filtre = st.session_state.df_voyages_valides.copy()

if zone_filtre:
    df_filtre = df_filtre[df_filtre['Zone'].isin(zone_filtre)]

if 'vehicule_filtre' in locals() and vehicule_filtre:
    df_filtre = df_filtre[df_filtre['Véhicule attribué'].isin(vehicule_filtre)]

df_filtre = df_filtre[
    (df_filtre['Taux d\'occupation (%)'] >= min_occupation) & 
    (df_filtre['Taux d\'occupation (%)'] <= max_occupation)
]

# Affichage des résultats filtrés
st.subheader(f"Résultats Filtres ({len(df_filtre)} voyages)")

if not df_filtre.empty:
    col_res1, col_res2 = st.columns(2)
    
    with col_res1:
        # Métriques filtrées
        st.metric("Voyages Filtres", len(df_filtre))
        st.metric("Taux Occupation Moyen Filtre", f"{df_filtre['Taux d\'occupation (%)'].mean():.1f}%")
    
    with col_res2:
        st.metric("Poids Total Filtre", f"{df_filtre['Poids total chargé'].sum():.0f} kg")
        st.metric("Volume Total Filtre", f"{df_filtre['Volume total chargé'].sum():.1f} m³")
    
    # Graphique des données filtrées
    fig_filtre = px.scatter(
        df_filtre,
        x='Poids total chargé',
        y='Volume total chargé',
        color='Zone',
        size='Taux d\'occupation (%)',
        hover_name='Véhicule N°',
        title="Visualisation des Voyages Filtres - Poids vs Volume"
    )
    st.plotly_chart(fig_filtre, use_container_width=True)

else:
    st.warning("Aucun voyage ne correspond aux critères de filtrage.")

# =====================================================
# PIED DE PAGE
# =====================================================
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666;'>
    <p>📊 Tableaux de Bord Analytics - Optimisation Logistique | Généré le {}</p>
</div>
""".format(datetime.now().strftime("%d/%m/%Y %H:%M")), unsafe_allow_html=True)