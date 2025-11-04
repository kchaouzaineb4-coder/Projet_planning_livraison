import streamlit as st
import pandas as pd
from backend import TruckRentalProcessor

# =====================================================
# 0️⃣ Initialisation des objets dans st.session_state
# =====================================================
if 'rental_processor' not in st.session_state or st.session_state.rental_processor is None:
    if 'df_optimized_estafettes' in st.session_state and st.session_state.df_optimized_estafettes is not None:
        st.session_state.rental_processor = TruckRentalProcessor(st.session_state.df_optimized_estafettes)
    else:
        st.session_state.rental_processor = None

if 'propositions' not in st.session_state:
    st.session_state.propositions = pd.DataFrame()

if 'selected_client' not in st.session_state:
    st.session_state.selected_client = None

if 'message' not in st.session_state:
    st.session_state.message = ""

# =====================================================
# 1️⃣ Mise à jour des propositions ouvertes
# =====================================================
def update_propositions_view():
    """Met à jour les propositions de location à partir du rental_processor"""
    if st.session_state.rental_processor:
        st.session_state.propositions = st.session_state.rental_processor.detecter_propositions()
        
        # Si le client sélectionné n’est plus dans les propositions, réinitialiser
        if (st.session_state.selected_client is not None and 
            st.session_state.selected_client not in st.session_state.propositions['Client'].astype(str).tolist()):
            st.session_state.selected_client = None
    else:
        st.session_state.propositions = pd.DataFrame()

# =====================================================
# 2️⃣ Appliquer ou refuser la location
# =====================================================
def handle_location_action(accepter: bool):
    """Accepte ou refuse la proposition de location pour le client sélectionné"""
    if st.session_state.rental_processor and st.session_state.selected_client:
        client_to_process = str(st.session_state.selected_client)
        ok, msg, _ = st.session_state.rental_processor.appliquer_location(
            client_to_process, accepter=accepter
        )
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
# 3️⃣ Exemple d’utilisation : afficher détails client
# =====================================================
if st.session_state.rental_processor:
    client_selectionne = "STQ"  # ou depuis un selectbox
    resume, details_df_styled = st.session_state.rental_processor.get_details_client(client_selectionne)
    st.text(resume)
    st.dataframe(details_df_styled)


# =====================================================
# 3️⃣ PROPOSITION DE LOCATION DE CAMION
# =====================================================
st.header("3. 🚚 Proposition de location de camion")
st.markdown(f"🔸 Si un client dépasse **{SEUIL_POIDS} kg** ou **{SEUIL_VOLUME} m³**, une location est proposée (si non déjà décidée).")

# --- Mettre à jour les propositions avant affichage
update_propositions_view()

if st.session_state.propositions is not None and not st.session_state.propositions.empty:
    col_prop, col_details = st.columns([2, 3])

    with col_prop:
        st.markdown("### Propositions ouvertes")
        # Affichage des propositions ouvertes
        show_df(
            st.session_state.propositions,
            use_container_width=True,
            column_order=["Client", "Poids total (kg)", "Volume total (m³)", "Raison"],
            hide_index=True
        )

        # Sélection du client à traiter
        client_options = st.session_state.propositions['Client'].astype(str).tolist()
        client_options_with_empty = [""] + client_options  # option vide par défaut

        default_index = 0
        if st.session_state.selected_client in client_options:
            default_index = client_options_with_empty.index(st.session_state.selected_client)
        elif len(client_options) > 0:
            default_index = 1  # sélection du premier client

        st.session_state.selected_client = st.selectbox(
            "Client à traiter :",
            options=client_options_with_empty,
            index=default_index,
            key='client_select'
        )

        # Boutons Accepter / Refuser
        col_btn_acc, col_btn_ref = st.columns(2)
        is_client_selected = st.session_state.selected_client != ""

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

        # Affichage du message de résultat
        if st.session_state.message:
            st.info(st.session_state.message)

    with col_details:
        st.markdown("### Détails de la commande client")
        if is_client_selected:
            try:
                resume, details_df_styled = st.session_state.rental_processor.get_details_client(
                    st.session_state.selected_client
                )
                st.text(resume)
                show_df(details_df_styled, use_container_width=True, hide_index=True)
            except Exception as e:
                st.error(f"❌ Impossible d'afficher les détails : {str(e)}")
        else:
            st.info("Sélectionnez un client pour afficher les détails de la commande/estafettes.")
else:
    st.success("🎉 Aucune proposition de location de camion en attente de décision.")

# =====================================================
# 4. VOYAGES PAR ESTAFETTE OPTIMISÉ (Section 4 - Résultat final)
# =====================================================
st.header("4. 🚐 Voyages par Estafette Optimisé (Inclut Camions Loués)")


# --- Création d'une copie pour l'affichage (avec unités) ---
df_display = df_optimized_estafettes.copy()
df_display["Poids total chargé"] = df_display["Poids total chargé"].map(lambda x: f"{x:.3f} kg")
df_display["Volume total chargé"] = df_display["Volume total chargé"].map(lambda x: f"{x:.3f} m³")
df_display["Taux d'occupation (%)"] = df_display["Taux d'occupation (%)"].map(lambda x: f"{x:.3f}%")

# --- Affichage avec show_df ---
show_df(df_display, use_container_width=True)

# --- Préparer un DataFrame pour export Excel ---
df_export = df_optimized_estafettes.copy()
df_export["Poids total chargé"] = df_export["Poids total chargé"].round(3)
df_export["Volume total chargé"] = df_export["Volume total chargé"].round(3)

# --- Bouton de téléchargement Excel ---
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

# --- Mise à jour dans session_state pour la section 5 ---
st.session_state.df_voyages = df_optimized_estafettes


# =====================================================
# 5️⃣ TRANSFERT DES BLs ENTRE ESTAFETTES / CAMIONS
# =====================================================
st.markdown("## 🔁 Transfert de BLs entre Estafettes / Camions")

MAX_POIDS = 1550  # kg
MAX_VOLUME = 4.608  # m³

if "df_voyages" not in st.session_state:
    st.warning("⚠️ Vous devez d'abord exécuter la section 3 (résultat final après location).")
elif "df_livraisons" not in st.session_state:
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
                    df_source_display["Poids total chargé"] = df_source_display["Poids total chargé"].map(lambda x: f"{x:.3f} kg")
                    df_source_display["Volume total chargé"] = df_source_display["Volume total chargé"].map(lambda x: f"{x:.3f} m³")
                    show_df(df_source_display, use_container_width=True)

                    bls_disponibles = df_source["BL inclus"].iloc[0].split(";")
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
                                    row["Poids total chargé"] = max(0, row["Poids total chargé"] - poids_bls)
                                    row["Volume total chargé"] = max(0, row["Volume total chargé"] - volume_bls)
                                elif row["Véhicule N°"] == cible:
                                    new_bls = bls + bls_to_move
                                    row["BL inclus"] = ";".join(new_bls)
                                    row["Poids total chargé"] += poids_bls
                                    row["Volume total chargé"] += volume_bls
                                return row

                            df_voyages = df_voyages.apply(transfer_bl, axis=1)
                            st.session_state.df_voyages = df_voyages
                            st.success(f"✅ Transfert réussi : {len(bls_selectionnes)} BL(s) déplacé(s) de {source} vers {cible}.")

                            # --- Affichage Streamlit ---
                            st.subheader("📊 Voyages après transfert (toutes les zones)")
                            df_display = df_voyages.sort_values(by=["Zone", "Véhicule N°"]).copy()
                            df_display["Poids total chargé"] = df_display["Poids total chargé"].map(lambda x: f"{x:.3f} kg")
                            df_display["Volume total chargé"] = df_display["Volume total chargé"].map(lambda x: f"{x:.3f} m³")
                            show_df(df_display[colonnes_requises], use_container_width=True)

                            # --- Export Excel arrondi ---
                            df_export = df_voyages.copy()
                            df_export["Poids total chargé"] = df_export["Poids total chargé"].round(3)
                            df_export["Volume total chargé"] = df_export["Volume total chargé"].round(3)

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




# --- Affichage interactif des voyages ---
for idx, row in df_validation.iterrows():
    with st.expander(f"🚚 Voyage {row['Véhicule N°']} | Zone : {row['Zone']}"):
        st.write("**Informations du voyage :**")
        row_display = row.to_frame().T.copy()
        if "Poids total chargé" in row_display.columns:
            row_display["Poids total chargé"] = row_display["Poids total chargé"].map(lambda x: f"{x:.3f} kg")
        if "Volume total chargé" in row_display.columns:
            row_display["Volume total chargé"] = row_display["Volume total chargé"].map(lambda x: f"{x:.3f} m³")
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
        df_display["Poids total chargé"] = df_display["Poids total chargé"].map(lambda x: f"{x:.3f} kg")
    if "Volume total chargé" in df_display.columns:
        df_display["Volume total chargé"] = df_display["Volume total chargé"].map(lambda x: f"{x:.3f} m³")
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
                row_display["Poids total chargé"] = row_display["Poids total chargé"].map(lambda x: f"{x:.2f} kg")
            if "Volume total chargé" in row_display.columns:
                row_display["Volume total chargé"] = row_display["Volume total chargé"].map(lambda x: f"{x:.3f} m³")
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
            df_display["Poids total chargé"] = df_display["Poids total chargé"].map(lambda x: f"{x:.3f} kg")
        if "Volume total chargé" in df_display.columns:
            df_display["Volume total chargé"] = df_display["Volume total chargé"].map(lambda x: f"{x:.3f} m³")
        show_df(df_display, use_container_width=True)

        # --- Export Excel ---
        from io import BytesIO
        def to_excel(df):
            df_export = df.copy()
            if "Poids total chargé" in df_export.columns:
                df_export["Poids total chargé"] = df_export["Poids total chargé"].round(3)
            if "Volume total chargé" in df_export.columns:
                df_export["Volume total chargé"] = df_export["Volume total chargé"].round(3)
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_export.to_excel(writer, index=False, sheet_name='Voyages_Attribués')
            return output.getvalue()

        st.download_button(
            label="💾 Télécharger le tableau final (XLSX)",
            data=to_excel(df_attribution),
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
                df_pdf["Poids total chargé"] = df_pdf["Poids total chargé"].map(lambda x: f"{x:.3f} kg")
            if "Volume total chargé" in df_pdf.columns:
                df_pdf["Volume total chargé"] = df_pdf["Volume total chargé"].map(lambda x: f"{x:.3f} m³")

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


