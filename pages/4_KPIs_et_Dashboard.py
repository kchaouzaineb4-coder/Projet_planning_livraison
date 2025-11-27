import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.header("📊 Tableau de Bord et Indicateurs de Performance")

# Vérification des prérequis
if not st.session_state.data_processed:
    st.warning("⚠️ Veuillez d'abord importer et traiter les données dans la page 'Import & Analyse'.")
    st.stop()

# CSS pour cette page
st.markdown("""
<style>
    .kpi-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 20px;
        border-radius: 10px;
        margin: 10px 0;
        text-align: center;
    }
    .kpi-value {
        font-size: 2rem;
        font-weight: bold;
        margin: 10px 0;
    }
    .kpi-label {
        font-size: 1rem;
        opacity: 0.9;
    }
</style>
""", unsafe_allow_html=True)

# Section 12: Résumé et dashboard
st.subheader("12. 🎯 RÉSUMÉ ET TABLEAU DE BORD FINAL")

if "df_voyages" in st.session_state:
    df_final = st.session_state.df_voyages.copy()
    
    # Calcul des métriques principales
    total_vehicules = len(df_final)
    estafettes = len(df_final[df_final["Code Véhicule"] == "ESTAFETTE"]) if "Code Véhicule" in df_final.columns else 0
    camions = len(df_final[df_final["Code Véhicule"] == "CAMION-LOUE"]) if "Code Véhicule" in df_final.columns else 0
    poids_total = df_final["Poids total chargé"].sum() if "Poids total chargé" in df_final.columns else 0
    volume_total = df_final["Volume total chargé"].sum() if "Volume total chargé" in df_final.columns else 0
    taux_moyen = df_final["Taux d'occupation (%)"].mean() if "Taux d'occupation (%)" in df_final.columns else 0
    
    # Affichage des métriques en grille améliorée
    st.markdown("### 📊 Indicateurs Clés de Performance")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-value">{total_vehicules}</div>
            <div class="kpi-label">🚚 Total Véhicules</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-value">{estafettes}</div>
            <div class="kpi-label">🚐 Estafettes</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-value">{camions}</div>
            <div class="kpi-label">🚛 Camions</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-value">{poids_total:.0f}</div>
            <div class="kpi-label">⚖️ Poids Total (kg)</div>
        </div>
        """, unsafe_allow_html=True)

    col5, col6, col7, col8 = st.columns(4)
    with col5:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-value">{volume_total:.1f}</div>
            <div class="kpi-label">📦 Volume Total (m³)</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col6:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-value">{taux_moyen:.1f}%</div>
            <div class="kpi-label">📊 Taux Occupation</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col7:
        efficacite = "Bonne" if taux_moyen > 70 else "Moyenne" if taux_moyen > 50 else "Faible"
        couleur = "#28a745" if taux_moyen > 70 else "#ffc107" if taux_moyen > 50 else "#dc3545"
        st.markdown(f"""
        <div class="kpi-card" style="background: {couleur};">
            <div class="kpi-value">{efficacite}</div>
            <div class="kpi-label">🎯 Efficacité</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col8:
        status = "✅ Complet" if 'df_voyages_valides' in st.session_state else "🟡 En cours"
        couleur_status = "#28a745" if 'df_voyages_valides' in st.session_state else "#ffc107"
        st.markdown(f"""
        <div class="kpi-card" style="background: {couleur_status};">
            <div class="kpi-value">{status}</div>
            <div class="kpi-label">📋 Statut</div>
        </div>
        """, unsafe_allow_html=True)

    # Graphiques avancés
    st.markdown("---")
    st.subheader("📈 Analytics Avancés")
    
    # Répartition par zone
    if 'Zone' in df_final.columns:
        col_chart1, col_chart2 = st.columns(2)
        
        with col_chart1:
            repartition_zone = df_final.groupby("Zone").size().reset_index(name="Nombre de véhicules")
            if not repartition_zone.empty:
                fig_zone = px.bar(
                    repartition_zone, 
                    x="Zone", 
                    y="Nombre de véhicules",
                    title="Véhicules par Zone",
                    color="Nombre de véhicules",
                    color_continuous_scale="Blues",
                    text="Nombre de véhicules"
                )
                fig_zone.update_layout(coloraxis_colorbar=dict(title="Nb Véhicules"))
                st.plotly_chart(fig_zone, use_container_width=True)
        
        with col_chart2:
            # Répartition type de véhicule
            if "Code Véhicule" in df_final.columns:
                repartition_type = df_final["Code Véhicule"].value_counts().reset_index()
                repartition_type.columns = ["Type Véhicule", "Nombre"]
                fig_type = px.pie(
                    repartition_type, 
                    values="Nombre", 
                    names="Type Véhicule",
                    title="Répartition des Types de Véhicules",
                    color_discrete_sequence=px.colors.qualitative.Set3
                )
                st.plotly_chart(fig_type, use_container_width=True)
    
    # Graphique d'occupation
    if "Taux d'occupation (%)" in df_final.columns:
        col_chart3, col_chart4 = st.columns(2)
        
        with col_chart3:
            fig_occupation = px.histogram(
                df_final, 
                x="Taux d'occupation (%)",
                title="Distribution des Taux d'Occupation",
                nbins=20,
                color_discrete_sequence=['#0369A1']
            )
            fig_occupation.update_layout(
                xaxis_title="Taux d'occupation (%)",
                yaxis_title="Nombre de véhicules"
            )
            st.plotly_chart(fig_occupation, use_container_width=True)
        
        with col_chart4:
            # Scatter plot poids vs volume
            if "Poids total chargé" in df_final.columns and "Volume total chargé" in df_final.columns:
                fig_scatter = px.scatter(
                    df_final,
                    x="Poids total chargé",
                    y="Volume total chargé",
                    title="Relation Poids vs Volume",
                    color="Zone" if "Zone" in df_final.columns else None,
                    size="Taux d'occupation (%)" if "Taux d'occupation (%)" in df_final.columns else None,
                    hover_data=["Véhicule N°"]
                )
                st.plotly_chart(fig_scatter, use_container_width=True)

    # Métriques détaillées par zone
    st.markdown("---")
    st.subheader("🌍 Analyse par Zone")
    
    if 'Zone' in df_final.columns:
        analyse_zone = df_final.groupby('Zone').agg({
            'Poids total chargé': 'sum',
            'Volume total chargé': 'sum',
            'Taux d\'occupation (%)': 'mean',
            'Véhicule N°': 'count'
        }).reset_index()
        
        analyse_zone.columns = ['Zone', 'Poids Total (kg)', 'Volume Total (m³)', 'Taux Occupation Moyen (%)', 'Nb Véhicules']
        
        # Formater les nombres
        analyse_zone['Poids Total (kg)'] = analyse_zone['Poids Total (kg)'].round(1)
        analyse_zone['Volume Total (m³)'] = analyse_zone['Volume Total (m³)'].round(3)
        analyse_zone['Taux Occupation Moyen (%)'] = analyse_zone['Taux Occupation Moyen (%)'].round(1)
        
        st.dataframe(analyse_zone, use_container_width=True)

    # Alertes et recommandations
    st.markdown("---")
    st.subheader("⚠️ Alertes et Recommandations")
    
    col_alert1, col_alert2 = st.columns(2)
    
    with col_alert1:
        # Alertes de capacité
        if "Taux d'occupation (%)" in df_final.columns:
            vehicules_sous_utilises = len(df_final[df_final["Taux d'occupation (%)"] < 50])
            vehicules_surcharges = len(df_final[df_final["Taux d'occupation (%)"] > 90])
            
            if vehicules_sous_utilises > 0:
                st.warning(f"🚨 {vehicules_sous_utilises} véhicule(s) sous-utilisés (taux < 50%)")
            if vehicules_surcharges > 0:
                st.error(f"⚠️ {vehicules_surcharges} véhicule(s) presque pleins (taux > 90%)")
            if vehicules_sous_utilises == 0 and vehicules_surcharges == 0:
                st.success("✅ Tous les véhicules ont une bonne utilisation (50% ≤ taux ≤ 90%)")
    
    with col_alert2:
        # Recommandations
        if taux_moyen < 60:
            st.info("💡 **Recommandation :** Optimiser le chargement pour améliorer le taux d'occupation moyen")
        if camions > 0 and estafettes / (camions + 1) > 5:
            st.info("💡 **Recommandation :** Évaluer l'opportunité d'utiliser plus de camions pour réduire le nombre d'estafettes")

else:
    st.warning("⚠️ Le planning n'est pas encore généré.")

# Résumé de l'état du système
st.markdown("---")
st.subheader("🔍 État du Système")

col_sys1, col_sys2, col_sys3 = st.columns(3)

with col_sys1:
    st.metric("Données traitées", "✅" if st.session_state.data_processed else "❌")
    
with col_sys2:
    voyages_valides = "✅" if 'df_voyages_valides' in st.session_state else "❌"
    st.metric("Voyages validés", voyages_valides)
    
with col_sys3:
    attributions = "✅" if 'attributions' in st.session_state and st.session_state.attributions else "❌"
    st.metric("Attributions faites", attributions)

# Bouton de rafraîchissement
if st.button("🔄 Actualiser les données"):
    st.rerun()