import streamlit as st
import pandas as pd
from backend import AdvancedReportGenerator
from io import BytesIO
import openpyxl
from openpyxl.styles import Alignment
from fpdf import FPDF

# =====================================================
# CONFIGURATION DE LA PAGE
# =====================================================
st.set_page_config(page_title="Validation et Attribution", layout="wide")
st.title("✅ Validation et Attribution")

# =====================================================
# FONCTIONS UTILITAIRES
# =====================================================
def show_df(df, **kwargs):
    """Affiche un DataFrame avec arrondi à 3 décimales"""
    if isinstance(df, pd.DataFrame):
        df_to_display = df.copy()
        df_to_display = df_to_display.round(3)
        st.dataframe(df_to_display, **kwargs)
    else:
        st.dataframe(df, **kwargs)

# =====================================================
# CSS PERSONNALISÉ
# =====================================================
st.markdown("""
<style>
.voyage-card {
    border: 1px solid #e0e0e0;
    border-radius: 10px;
    padding: 20px;
    margin: 10px 0;
    background: white;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}
.voyage-header {
    background: #0369A1;
    color: white;
    padding: 15px;
    border-radius: 8px;
    margin-bottom: 15px;
}
.metric-card {
    background: #f8f9fa;
    border-left: 4px solid #0369A1;
    padding: 12px;
    margin: 8px 0;
    border-radius: 5px;
}
.bl-list {
    background: #fff3cd;
    border: 1px solid #ffeaa7;
    border-radius: 5px;
    padding: 10px;
    margin: 10px 0;
    max-height: 150px;
    overflow-y: auto;
}
.validation-buttons {
    display: flex;
    gap: 10px;
    margin-top: 15px;
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
# VÉRIFICATION DES DONNÉES
# =====================================================
st.title("✅ Validation des Voyages & Attribution")

if "df_voyages" not in st.session_state:
    st.warning("⚠️ Veuillez d'abord optimiser les voyages dans la page 'Optimisation & Transfert'")
    st.stop()

# =====================================================
# CONSTANTES POUR LES VÉHICULES ET CHAUFFEURS
# =====================================================
VEHICULES_DISPONIBLES = [
    'SLG-VEH11', 'SLG-VEH14', 'SLG-VEH22', 'SLG-VEH19',
    'SLG-VEH10', 'SLG-VEH16', 'SLG-VEH23', 'SLG-VEH08', 'SLG-VEH20', 'code-Camion'
]

CHAUFFEURS_DETAILS = {
    '09254': 'DAMMAK Karim', '06002': 'MAAZOUN Bassem', '11063': 'SASSI Ramzi',
    '10334': 'BOUJELBENE Mohamed', '15144': 'GADDOUR Rami', '08278': 'DAMMAK Wissem',
    '18339': 'REKIK Ahmed', '07250': 'BARKIA Mustapha', '13321': 'BADRI Moez','99999': 'Chauffeur Camion'
}

# =====================================================
# 7. VALIDATION DES VOYAGES APRÈS TRANSFERT
# =====================================================
st.markdown("## ✅ VALIDATION DES VOYAGES APRÈS TRANSFERT")

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

# --- Affichage amélioré des voyages ---
st.markdown("### 📋 Liste des Voyages à Valider")

for idx, row in df_validation.iterrows():
    # Création d'une carte pour chaque voyage
    with st.container():
        st.markdown(f"""
        <div class="voyage-card">
            <div class="voyage-header">
                <h4>🚚 Voyage {row['Véhicule N°']} | Zone: {row['Zone']}</h4>
            </div>
        """, unsafe_allow_html=True)
        
        # Métriques principales
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown(f"""
            <div class="metric-card">
                <strong>⚖️ Poids Total</strong><br>
                {row['Poids total chargé']:.3f} kg
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown(f"""
            <div class="metric-card">
                <strong>📏 Volume Total</strong><br>
                {row['Volume total chargé']:.3f} m³
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            taux_occupation = row.get('Taux d\'occupation (%)', 'N/A')
            if taux_occupation != 'N/A':
                taux_text = f"{taux_occupation:.1f}%"
            else:
                taux_text = "N/A"
            st.markdown(f"""
            <div class="metric-card">
                <strong>📊 Taux d'Occupation</strong><br>
                {taux_text}
            </div>
            """, unsafe_allow_html=True)
        
        # Informations détaillées
        col4, col5 = st.columns(2)
        
        with col4:
            clients = row.get('Client(s) inclus', '')
            if clients:
                st.markdown(f"**👥 Clients:** {clients}")
            
            representants = row.get('Représentant(s) inclus', '')
            if representants:
                st.markdown(f"**👨‍💼 Représentants:** {representants}")
        
        with col5:
            location = "✅ Oui" if row.get('Location_camion') else "❌ Non"
            st.markdown(f"**🚛 Location:** {location}")
            
            code_vehicule = row.get('Code Véhicule', 'N/A')
            st.markdown(f"**🔧 Code Véhicule:** {code_vehicule}")
        
        # Liste des BL avec défilement
        bls = row.get('BL inclus', '')
        if bls:
            bls_list = bls.split(';')
            bls_html = "<br>".join([f"• {bl.strip()}" for bl in bls_list])
            st.markdown(f"""
            <div class="bl-list">
                <strong>📋 BLs Inclus ({len(bls_list)}):</strong><br>
                {bls_html}
            </div>
            """, unsafe_allow_html=True)
        
        # Boutons de validation côte à côte
        st.markdown("**✅ Validation du voyage:**")
        col_oui, col_non = st.columns(2)
        
        with col_oui:
            if st.button(f"✅ Valider {row['Véhicule N°']}", key=f"btn_oui_{idx}", 
                       use_container_width=True, type="primary" if st.session_state.validations.get(idx) == "Oui" else "secondary"):
                st.session_state.validations[idx] = "Oui"
                st.rerun()
        
        with col_non:
            if st.button(f"❌ Rejeter {row['Véhicule N°']}", key=f"btn_non_{idx}",
                       use_container_width=True, type="primary" if st.session_state.validations.get(idx) == "Non" else "secondary"):
                st.session_state.validations[idx] = "Non"
                st.rerun()
        
        # Afficher le statut actuel
        statut = st.session_state.validations.get(idx)
        if statut == "Oui":
            st.success(f"✅ Voyage {row['Véhicule N°']} validé")
        elif statut == "Non":
            st.error(f"❌ Voyage {row['Véhicule N°']} rejeté")
        else:
            st.info("⏳ En attente de validation")
        
        st.markdown("</div>", unsafe_allow_html=True)
        st.markdown("---")

# --- Résumé des validations ---
st.markdown("### 📊 Résumé des Validations")
total_voyages = len(df_validation)
valides = sum(1 for v in st.session_state.validations.values() if v == "Oui")
rejetes = sum(1 for v in st.session_state.validations.values() if v == "Non")

col1, col2, col3 = st.columns(3)

with col1:
    st.metric("Total Voyages", total_voyages)
with col2:
    st.metric("✅ Validés", valides)
with col3:
    st.metric("❌ Rejetés", rejetes)

# Information supplémentaire sur l'état des validations
if valides + rejetes < total_voyages:
    st.info(f"ℹ️ {total_voyages - (valides + rejetes)} voyage(s) n'ont pas encore été validés")

# --- Bouton pour appliquer les validations ---
if st.button("🚀 Finaliser la Validation", type="primary", use_container_width=True):
    valid_indexes = [i for i, v in st.session_state.validations.items() if v == "Oui"]
    valid_indexes = [i for i in valid_indexes if i in df_validation.index]

    if valid_indexes:
        df_voyages_valides = df_validation.loc[valid_indexes].reset_index(drop=True)
        st.session_state.df_voyages_valides = df_voyages_valides

        st.success(f"✅ {len(df_voyages_valides)} voyage(s) validé(s) avec succès!")
        
        # Affichage des voyages validés
        st.markdown("### 🎉 Voyages Validés - Résumé Final")
        
        for idx, row_valide in df_voyages_valides.iterrows():
            with st.expander(f"🚚 {row_valide['Véhicule N°']} - Zone {row_valide['Zone']}", expanded=True):
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Poids", f"{row_valide['Poids total chargé']:.3f} kg")
                    st.metric("Clients", row_valide.get('Client(s) inclus', 'N/A'))
                with col2:
                    st.metric("Volume", f"{row_valide['Volume total chargé']:.3f} m³")
                    st.metric("Représentants", row_valide.get('Représentant(s) inclus', 'N/A'))

        # --- Export Excel ---
        excel_data = to_excel(df_voyages_valides)
        st.download_button(
            label="💾 Télécharger les voyages validés (XLSX)",
            data=excel_data,
            file_name="Voyages_valides.xlsx",
            mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            use_container_width=True
        )
    else:
        st.warning("⚠️ Aucun voyage n'a été validé. Veuillez valider au moins un voyage.")

st.markdown("---")

# =====================================================
# 8. ATTRIBUTION DES VÉHICULES ET CHAUFFEURS
# =====================================================
st.markdown("## 🚛 ATTRIBUTION DES VÉHICULES ET CHAUFFEURS")

if 'df_voyages_valides' in st.session_state and not st.session_state.df_voyages_valides.empty:

    df_attribution = st.session_state.df_voyages_valides.copy()

    # Fonction pour formatter les colonnes avec retours à la ligne POUR STREAMLIT
    def formater_colonnes_listes_streamlit(df):
        df_formate = df.copy()
        colonnes_a_formater = ['Client(s) inclus', 'Représentant(s) inclus', 'BL inclus']
        
        for col in colonnes_a_formater:
            if col in df_formate.columns:
                df_formate[col] = df_formate[col].apply(
                    lambda x: '\n'.join([elem.strip() for elem in str(x).replace(';', ',').split(',') if elem.strip()]) 
                    if pd.notna(x) else ""
                )
        return df_formate

    if "attributions" not in st.session_state:
        st.session_state.attributions = {}

    for idx, row in df_attribution.iterrows():
        with st.expander(f"🚚 Voyage {row['Véhicule N°']} | Zone : {row['Zone']}"):
            st.write("**Informations du voyage :**")
            
            # Créer un affichage personnalisé avec retours à ligne
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.write(f"**Zone:** {row['Zone']}")
                st.write(f"**Véhicule N°:** {row['Véhicule N°']}")
                if "Poids total chargé" in row:
                    st.write(f"**Poids total chargé:** {row['Poids total chargé']:.2f} kg")
                if "Volume total chargé" in row:
                    st.write(f"**Volume total chargé:** {row['Volume total chargé']:.3f} m³")
                if "Taux d'occupation (%)" in row:
                    st.write(f"**Taux d'occupation:** {row['Taux d\'occupation (%)']:.1f}%")
            
            with col2:
                # Afficher les clients avec retours à ligne
                if 'Client(s) inclus' in row and pd.notna(row['Client(s) inclus']):
                    st.write("**Clients:**")
                    clients = str(row['Client(s) inclus']).replace(';', ',').split(',')
                    for client in clients:
                        client_clean = client.strip()
                        if client_clean:
                            st.write(f"- {client_clean}")
                
                # Afficher les représentants avec retours à ligne
                if 'Représentant(s) inclus' in row and pd.notna(row['Représentant(s) inclus']):
                    st.write("**Représentants:**")
                    representants = str(row['Représentant(s) inclus']).replace(';', ',').split(',')
                    for rep in representants:
                        rep_clean = rep.strip()
                        if rep_clean:
                            st.write(f"- {rep_clean}")
            
            with col3:
                # Afficher les BL avec retours à ligne
                if 'BL inclus' in row and pd.notna(row['BL inclus']):
                    st.write("**BL associés:**")
                    bls = str(row['BL inclus']).replace(';', ',').split(',')
                    for bl in bls:
                        bl_clean = bl.strip()
                        if bl_clean:
                            st.write(f"- {bl_clean}")

            col_veh, col_chauf = st.columns(2)
            
            with col_veh:
                vehicule_selectionne = st.selectbox(
                    f"Véhicule pour le voyage {row['Véhicule N°']}",
                    VEHICULES_DISPONIBLES,
                    index=0 if st.session_state.attributions.get(idx, {}).get("Véhicule") else 0,
                    key=f"vehicule_{idx}"
                )
            
            with col_chauf:
                options_chauffeurs = [f"{matricule} - {nom}" for matricule, nom in CHAUFFEURS_DETAILS.items() if matricule != 'Matricule']
                
                default_index = 0
                chauffeur_actuel = st.session_state.attributions.get(idx, {}).get("Chauffeur_complet")
                if chauffeur_actuel and chauffeur_actuel in options_chauffeurs:
                    default_index = options_chauffeurs.index(chauffeur_actuel)
                
                chauffeur_selectionne_complet = st.selectbox(
                    f"Chauffeur pour le voyage {row['Véhicule N°']}",
                    options_chauffeurs,
                    index=default_index,
                    key=f"chauffeur_{idx}"
                )
                
                if chauffeur_selectionne_complet:
                    matricule_chauffeur = chauffeur_selectionne_complet.split(" - ")[0]
                    nom_chauffeur = chauffeur_selectionne_complet.split(" - ")[1]
                else:
                    matricule_chauffeur = ""
                    nom_chauffeur = ""

            st.session_state.attributions[idx] = {
                "Véhicule": vehicule_selectionne,
                "Chauffeur_complet": chauffeur_selectionne_complet,
                "Matricule_chauffeur": matricule_chauffeur,
                "Nom_chauffeur": nom_chauffeur
            }

    if st.button("✅ Appliquer les attributions"):

        df_attribution["Véhicule attribué"] = df_attribution.index.map(lambda i: st.session_state.attributions[i]["Véhicule"])
        df_attribution["Chauffeur attribué"] = df_attribution.index.map(lambda i: st.session_state.attributions[i]["Nom_chauffeur"])
        df_attribution["Matricule chauffeur"] = df_attribution.index.map(lambda i: st.session_state.attributions[i]["Matricule_chauffeur"])

        
        st.markdown("### 📦 Voyages avec Véhicule et Chauffeur")

        # --- Affichage Streamlit amélioré avec retours à ligne ---
        for idx, row in df_attribution.iterrows():
            with st.expander(f"📋 Voyage {row['Véhicule N°']} - Zone {row['Zone']} - Véhicule: {row.get('Véhicule attribué', 'N/A')} - Chauffeur: {row.get('Chauffeur attribué', 'N/A')}"):
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.write("**Informations de base:**")
                    st.write(f"**Zone:** {row['Zone']}")
                    st.write(f"**Véhicule N°:** {row['Véhicule N°']}")
                    if "Poids total chargé" in row:
                        st.write(f"**Poids total chargé:** {row['Poids total chargé']:.3f} kg")
                    if "Volume total chargé" in row:
                        st.write(f"**Volume total chargé:** {row['Volume total chargé']:.3f} m³")
                    if "Taux d'occupation (%)" in row:
                        st.write(f"**Taux d'occupation:** {row['Taux d\'occupation (%)']:.3f}%")
                    if "Véhicule attribué" in row:
                        st.write(f"**Véhicule attribué:** {row['Véhicule attribué']}")
                    if "Chauffeur attribué" in row:
                        st.write(f"**Chauffeur attribué:** {row['Chauffeur attribué']}")
                    if "Matricule chauffeur" in row:
                        st.write(f"**Matricule chauffeur:** {row['Matricule chauffeur']}")
                
                with col2:
                    # Afficher les clients avec retours à ligne
                    if 'Client(s) inclus' in row and pd.notna(row['Client(s) inclus']):
                        st.write("**📋 Clients inclus:**")
                        clients = str(row['Client(s) inclus']).replace(';', ',').split(',')
                        for client in clients:
                            client_clean = client.strip()
                            if client_clean:
                                st.write(f"• {client_clean}")
                    
                    # Afficher les représentants avec retours à ligne
                    if 'Représentant(s) inclus' in row and pd.notna(row['Représentant(s) inclus']):
                        st.write("**👤 Représentants inclus:**")
                        representants = str(row['Représentant(s) inclus']).replace(';', ',').split(',')
                        for rep in representants:
                            rep_clean = rep.strip()
                            if rep_clean:
                                st.write(f"• {rep_clean}")
                
                with col3:
                    # Afficher les BL avec retours à ligne
                    if 'BL inclus' in row and pd.notna(row['BL inclus']):
                        st.write("**📄 BL associés:**")
                        bls = str(row['BL inclus']).replace(';', ',').split(',')
                        # Afficher en colonnes si beaucoup de BL
                        if len(bls) > 5:
                            cols = st.columns(2)
                            half = len(bls) // 2
                            for i, bl in enumerate(bls):
                                bl_clean = bl.strip()
                                if bl_clean:
                                    col_idx = 0 if i < half else 1
                                    with cols[col_idx]:
                                        st.write(f"• {bl_clean}")
                        else:
                            for bl in bls:
                                bl_clean = bl.strip()
                                if bl_clean:
                                    st.write(f"• {bl_clean}")

        # --- Export Excel avec retours à ligne et CENTRAGE ---
        def to_excel(df):
            df_export = df.copy()
            
            # Formater les colonnes avec retours à ligne pour Excel
            colonnes_a_formater = ['Client(s) inclus', 'Représentant(s) inclus', 'BL inclus']
            for col in colonnes_a_formater:
                if col in df_export.columns:
                    df_export[col] = df_export[col].apply(
                        lambda x: '\n'.join([elem.strip() for elem in str(x).replace(';', ',').split(',') if elem.strip()]) 
                        if pd.notna(x) else ""
                    )
            
            if "Poids total chargé" in df_export.columns:
                df_export["Poids total chargé"] = df_export["Poids total chargé"].round(3)
            if "Volume total chargé" in df_export.columns:
                df_export["Volume total chargé"] = df_export["Volume total chargé"].round(3)
            
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_export.to_excel(writer, index=False, sheet_name='Voyages_Attribués')
                
                # Appliquer le formatage des retours à ligne et CENTRAGE dans Excel
                workbook = writer.book
                worksheet = writer.sheets['Voyages_Attribués']
                
                # Style de centrage avec retours à ligne
                center_alignment = Alignment(
                    horizontal='center', 
                    vertical='center', 
                    wrap_text=True
                )
                
                # Appliquer le centrage à TOUTES les cellules
                for row in worksheet.iter_rows(min_row=1, max_row=len(df_export) + 1, min_col=1, max_col=len(df_export.columns)):
                    for cell in row:
                        cell.alignment = center_alignment
                
                # Ajuster automatiquement la largeur des colonnes
                for column in worksheet.columns:
                    max_length = 0
                    column_letter = column[0].column_letter
                    for cell in column:
                        try:
                            if cell.value:
                                # Calculer la longueur maximale en prenant en compte les retours à ligne
                                lines = str(cell.value).split('\n')
                                max_line_length = max(len(line) for line in lines)
                                max_length = max(max_length, max_line_length)
                        except:
                            pass
                    adjusted_width = min(50, (max_length + 2))  # Limiter à 50 caractères max
                    worksheet.column_dimensions[column_letter].width = adjusted_width
                
                # Ajuster la hauteur des lignes pour les retours à ligne
                for row in range(2, len(df_export) + 2):  # Commencer à la ligne 2 (après l'en-tête)
                    worksheet.row_dimensions[row].height = 60  # Hauteur fixe pour accommoder les retours à ligne
            
            return output.getvalue()

        # --- Export PDF avec tableau ÉLARGI et ESPACES MINIMISÉS ---
        def to_pdf_better_centered(df, title="Voyages Attribués"):
            pdf = FPDF(orientation='L')  # Paysage pour plus d'espace
            pdf.add_page()
            
            # RÉDUCTION des marges pour utiliser TOUTE la largeur
            pdf.set_left_margin(5)   # Marge gauche réduite
            pdf.set_right_margin(5)  # Marge droite réduite
            pdf.set_top_margin(10)   # Marge haut réduite
            
            # Titre PLUS PETIT et PLUS HAUT
            pdf.set_font("Arial", 'B', 14)  # Taille réduite
            pdf.cell(0, 8, title, ln=True, align="C")  # Hauteur réduite
            pdf.ln(3)  # Espacement réduit après le titre
            
            # Créer une copie formatée pour le PDF
            df_pdf = df.copy()
            
            # Formater les nombres avec 3 chiffres après la virgule SAUF le taux avec 2 chiffres
            numeric_columns = {
                'Poids total chargé': ('kg', 3),
                'Volume total chargé': ('m³', 3), 
                'Taux d\'occupation (%)': ('%', 2)  # 2 chiffres après la virgule
            }
            
            for col, (unit, decimals) in numeric_columns.items():
                if col in df_pdf.columns:
                    df_pdf[col] = df_pdf[col].apply(
                        lambda x: f"{float(x):.{decimals}f} {unit}" if x and str(x).strip() and str(x).strip() != 'nan' else ""
                    )
            
            # Configuration des colonnes AVEC LARGEURS MAXIMALISÉES
            col_config = {
                'Zone': {'width': 15, 'header': 'Zone'},
                'Véhicule N°': {'width': 18, 'header': 'Véhicule'},
                'Poids total chargé': {'width': 22, 'header': 'Poids (kg)'},
                'Volume total chargé': {'width': 22, 'header': 'Volume (m³)'},
                'Client(s) inclus': {'width': 30, 'header': 'Clients'},
                'Représentant(s) inclus': {'width': 30, 'header': 'Représentants'},
                'BL inclus': {'width': 35, 'header': 'BL associés'},
                'Taux d\'occupation (%)': {'width': 18, 'header': 'Taux %'},
                'Véhicule attribué': {'width': 25, 'header': 'Véhicule Attribué'},
                'Chauffeur attribué': {'width': 25, 'header': 'Chauffeur'},
                'Matricule chauffeur': {'width': 20, 'header': 'Matricule'}
            }
            
            # Sélectionner seulement les colonnes existantes
            colonnes_existantes = [col for col in df_pdf.columns if col in col_config]
            widths = [col_config[col]['width'] for col in colonnes_existantes]
            headers = [col_config[col]['header'] for col in colonnes_existantes]
            
            # Calculer la position de départ - DÉBUT PLUS À GAUCHE
            total_width = sum(widths)
            page_width = 297  # Largeur d'une page A4 en paysage (mm)
            start_x = 5  # Commencer presque au bord gauche
            
            # Positionner le tableau AU DÉBUT
            pdf.set_x(start_x)
            
            # En-têtes CENTRÉS avec police PLUS PETITE
            pdf.set_font("Arial", 'B', 8)  # Taille réduite
            for i, header in enumerate(headers):
                pdf.cell(widths[i], 6, header, border=1, align='C')  # Hauteur réduite
            pdf.ln()
            
            # Données avec centrage VERTICAL et HORIZONTAL
            pdf.set_font("Arial", '', 7)  # Taille réduite pour les données
            
            for voyage_idx, (_, row) in enumerate(df_pdf.iterrows()):
                # Vérifier si on dépasse la hauteur de page
                if pdf.get_y() > 180:  # Si on approche du bas de page
                    pdf.add_page()  # Nouvelle page
                    pdf.set_x(start_x)
                    # Ré-afficher les en-têtes sur la nouvelle page
                    pdf.set_font("Arial", 'B', 8)
                    for i, header in enumerate(headers):
                        pdf.cell(widths[i], 6, header, border=1, align='C')
                    pdf.ln()
                    pdf.set_font("Arial", '', 7)
                
                # Déterminer le nombre de lignes nécessaires pour ce voyage
                list_columns = ['Client(s) inclus', 'Représentant(s) inclus', 'BL inclus']
                non_list_columns = [col for col in colonnes_existantes if col not in list_columns]
                
                max_lines = 1
                list_contents = {}
                
                for col in list_columns:
                    if col in colonnes_existantes:
                        content = str(row[col]) if pd.notna(row[col]) and str(row[col]) != 'nan' else ""
                        elements = content.replace(';', ',').split(',')
                        elements = [elem.strip() for elem in elements if elem.strip()]
                        list_contents[col] = elements
                        max_lines = max(max_lines, len(elements))
                
                # Pour chaque ligne du voyage
                for line_idx in range(max_lines):
                    # Vérifier si on dépasse la hauteur de page pour cette ligne
                    if pdf.get_y() > 190:  # Si on approche vraiment du bas
                        pdf.add_page()
                        pdf.set_x(start_x)
                        pdf.set_font("Arial", 'B', 8)
                        for i, header in enumerate(headers):
                            pdf.cell(widths[i], 6, header, border=1, align='C')
                        pdf.ln()
                        pdf.set_font("Arial", '', 7)
                    
                    # Positionner au DÉBUT pour chaque ligne
                    pdf.set_x(start_x)
                    
                    for i, col in enumerate(colonnes_existantes):
                        if col in list_columns:
                            # Colonnes de liste - afficher élément par élément
                            elements = list_contents.get(col, [])
                            content = elements[line_idx] if line_idx < len(elements) else ""
                        else:
                            # Colonnes non-liste - afficher sur la première ligne seulement
                            if line_idx == 0:
                                content = str(row[col]) if pd.notna(row[col]) and str(row[col]) != 'nan' else ""
                            else:
                                content = ""
                        
                        # Bordures avec hauteur RÉDUITE
                        border = 'LR'
                        if line_idx == 0: border += 'T'
                        if line_idx == max_lines - 1: border += 'B'
                        if i == 0: border += 'L'
                        if i == len(colonnes_existantes) - 1: border += 'R'
                        
                        pdf.cell(widths[i], 5, content, border=border, align='C')  # Hauteur réduite à 5
                    
                    pdf.ln()
            
            return pdf.output(dest='S').encode('latin-1')

        # Afficher les boutons de téléchargement côte à côte
        col1, col2 = st.columns(2)

        with col1:
            st.download_button(
                label="💾 Télécharger le tableau final (XLSX)",
                data=to_excel(df_attribution),
                file_name="Voyages_attribues.xlsx",
                mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )

        with col2:
            st.download_button(
                label="📄 Télécharger le tableau final (PDF)",
                data=to_pdf_better_centered(df_attribution),
                file_name="Voyages_attribues.pdf",
                mime='application/pdf'
            )
                
        # Mettre à jour le session state
        st.session_state.df_voyages_valides = df_attribution
        st.success("✅ Attributions appliquées avec succès !")
        
else:
    st.warning("⚠️ Vous devez d'abord valider les voyages dans la section 7.")

st.markdown("---")

# =====================================================
# 9. RAPPORTS AVANCÉS ET ANALYTICS
# =====================================================
st.markdown("## 📊 RAPPORTS AVANCÉS ET ANALYTICS")

if "df_voyages" in st.session_state and "df_livraisons_original" in st.session_state:
    
    # Initialiser le générateur de rapports
    from backend import AdvancedReportGenerator
    report_generator = AdvancedReportGenerator(
        st.session_state.df_voyages, 
        st.session_state.df_livraisons_original
    )
    
    tab1, tab2, tab3, tab4 = st.tabs([
        "📈 Vue d'Ensemble", 
        "🗺️ Analyse par Zone", 
        "🚚 Performance Véhicules", 
        "📋 Rapport Complet"
    ])
    
    with tab1:
        st.subheader("Vue d'Ensemble de l'Optimisation")
        
        # Métriques principales
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            total_voyages = len(st.session_state.df_voyages)
            st.metric("Nombre Total de Voyages", total_voyages)
        
        with col2:
            total_poids = st.session_state.df_voyages['Poids total chargé'].sum()
            st.metric("Poids Total Transporté", f"{total_poids:.0f} kg")
        
        with col3:
            total_volume = st.session_state.df_voyages['Volume total chargé'].sum()
            st.metric("Volume Total Transporté", f"{total_volume:.1f} m³")
        
        with col4:
            taux_moyen = st.session_state.df_voyages['Taux d\'occupation (%)'].mean()
            st.metric("Taux d'Occupation Moyen", f"{taux_moyen:.1f}%")
        
        # Graphiques principaux
        col_chart1, col_chart2 = st.columns(2)
        
        with col_chart1:
            fig_zone = report_generator.generer_graphique_repartition_zones()
            if fig_zone:
                st.plotly_chart(fig_zone, use_container_width=True)
        
        with col_chart2:
            fig_occupation = report_generator.generer_graphique_taux_occupation()
            if fig_occupation:
                st.plotly_chart(fig_occupation, use_container_width=True)
    
    with tab2:
        st.subheader("Analyse Détaillée par Zone")
        
        # Sélecteur de zone
        zones_uniques = st.session_state.df_voyages['Zone'].unique()
        zone_selectionnee = st.selectbox("Sélectionnez une zone", zones_uniques)
        
        if zone_selectionnee:
            stats_zone = report_generator.generer_statistiques_zone(zone_selectionnee)
            
            if stats_zone:
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("Voyages dans la Zone", stats_zone['nombre_voyages'])
                
                with col2:
                    st.metric("Poids Total", f"{stats_zone['poids_total']:.0f} kg")
                
                with col3:
                    st.metric("Volume Total", f"{stats_zone['volume_total']:.1f} m³")
                
                with col4:
                    st.metric("Taux Occupation Moyen", f"{stats_zone['taux_occupation_moyen']:.1f}%")
                
                # Clients et représentants de la zone
                st.subheader("Clients et Représentants")
                col_clients, col_reps = st.columns(2)
                
                with col_clients:
                    if stats_zone['clients_frequents']:
                        st.write("**Clients Fréquents:**")
                        for client, count in stats_zone['clients_frequents']:
                            st.write(f"- {client} ({count} voyages)")
                
                with col_reps:
                    if stats_zone['representants_frequents']:
                        st.write("**Représentants Fréquents:**")
                        for rep, count in stats_zone['representants_frequents']:
                            st.write(f"- {rep} ({count} voyages)")
    
    with tab3:
        st.subheader("Performance des Véhicules")
        
        # Statistiques d'utilisation des véhicules
        stats_vehicules = report_generator.generer_statistiques_vehicules()
        
        if stats_vehicules:
            st.dataframe(stats_vehicules, use_container_width=True)
            
            # Graphique de performance
            fig_perf = report_generator.generer_graphique_performance_vehicules()
            if fig_perf:
                st.plotly_chart(fig_perf, use_container_width=True)
    
    with tab4:
        st.subheader("Rapport Complet d'Optimisation")
        
        # Générer le rapport complet
        rapport_complet = report_generator.generer_rapport_complet()
        
        # Afficher le rapport section par section
        for section, contenu in rapport_complet.items():
            with st.expander(f"📄 {section}", expanded=True):
                if isinstance(contenu, dict):
                    for sous_section, donnees in contenu.items():
                        st.write(f"**{sous_section}**")
                        if isinstance(donnees, pd.DataFrame):
                            st.dataframe(donnees, use_container_width=True)
                        else:
                            st.write(donnees)
                elif isinstance(contenu, pd.DataFrame):
                    st.dataframe(contenu, use_container_width=True)
                else:
                    st.write(contenu)
        
        # Bouton d'export du rapport
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("📊 Exporter Rapport Excel", use_container_width=True):
                rapport_excel = report_generator.exporter_rapport_excel()
                st.download_button(
                    label="💾 Télécharger Rapport Excel",
                    data=rapport_excel,
                    file_name="rapport_optimisation.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
        
        with col2:
            if st.button("📄 Exporter Rapport PDF", use_container_width=True):
                rapport_pdf = report_generator.exporter_rapport_pdf()
                st.download_button(
                    label="💾 Télécharger Rapport PDF",
                    data=rapport_pdf,
                    file_name="rapport_optimisation.pdf",
                    mime="application/pdf"
                )

else:
    st.warning("⚠️ Les données nécessaires pour les rapports ne sont pas disponibles.")

st.markdown("---")
       