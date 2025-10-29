import streamlit as st
import pandas as pd
import plotly.express as px
# Assurez-vous que le fichier corrigé (logistic_processor.py) est nommé backend.py 
# pour que cette importation fonctionne.
from backend import DeliveryProcessor, TruckRentalProcessor, SEUIL_POIDS, SEUIL_VOLUME 

# Configuration page
st.set_page_config(page_title="Planning Livraisons", layout="wide")
st.title("🚚 Planning de Livraisons & Optimisation des Tournées")
st.markdown("---")

# SESSION STATE INIT
if 'data_processed' not in st.session_state:
    st.session_state.data_processed = False
    st.session_state.df_grouped = None
    st.session_state.df_city = None
    st.session_state.df_grouped_zone = None
    st.session_state.df_zone = None
    st.session_state.df_optimized_estafettes = None
    st.session_state.df_granular_bls = None # 🆕 Ajout du DF granulaire
    st.session_state.rental_processor = None
    st.session_state.propositions = None
    st.session_state.selected_client = None
    st.session_state.message = ""

def update_propositions_view():
    """Rafraîchit la liste des propositions de location."""
    if st.session_state.rental_processor:
        st.session_state.propositions = st.session_state.rental_processor.detecter_propositions()
    else:
        st.session_state.propositions = pd.DataFrame()

def handle_location_action(accepter):
    """Gère l'acceptation ou le refus d'une proposition de location."""
    if st.session_state.rental_processor and st.session_state.selected_client:
        client_to_process = str(st.session_state.selected_client)
        # Note: appliquer_location retourne (ok, msg, new_propositions_df)
        ok, msg, _ = st.session_state.rental_processor.appliquer_location(client_to_process, accepter=accepter)
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
# 1. UPLOAD DES FICHIERS INPUT
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
                    # 💥 CORRECTION MAJEURE: Capture de la 6ème valeur de retour (df_granular_bls)
                    df_grouped, df_city, df_grouped_zone, df_zone, df_optimized_estafettes, df_granular_bls = processor.process_delivery_data(
                        liv_file, ydlogist_file, wcliegps_file
                    )
                # store all
                st.session_state.df_grouped = df_grouped
                st.session_state.df_city = df_city
                st.session_state.df_grouped_zone = df_grouped_zone
                st.session_state.df_zone = df_zone
                st.session_state.df_optimized_estafettes = df_optimized_estafettes
                st.session_state.df_granular_bls = df_granular_bls # Stockage du DF granulaire
                
                # 💥 CORRECTION MAJEURE: Initialisation du TruckRentalProcessor avec df_granular_bls
                # Ceci est crucial pour que la fonction de transfert manuel (section 5) fonctionne.
                st.session_state.rental_processor = TruckRentalProcessor(df_optimized_estafettes, df_granular_bls)
                
                update_propositions_view()
                st.session_state.data_processed = True
                st.session_state.message = "✅ Traitement terminé avec succès !"
                st.experimental_rerun()
            except Exception as e:
                st.error(f"❌ Erreur lors du traitement : {e}")
                st.session_state.data_processed = False
        else:
            st.warning("Veuillez uploader tous les fichiers nécessaires.")
st.markdown("---")

# =====================================================
# AFFICHAGE DES RÉSULTATS
# =====================================================
if st.session_state.data_processed:

    # messages
    if st.session_state.message:
        if st.session_state.message.startswith("✅"):
            st.success(st.session_state.message)
        elif st.session_state.message.startswith("❌"):
            st.error(st.session_state.message)
        elif st.session_state.message.startswith("⚠️"):
            st.warning(st.session_state.message)
        else:
            st.info(st.session_state.message)

    # get current optimized df (affichage final)
    df_optimized_estafettes = st.session_state.rental_processor.get_df_result()

    # =====================================================
    # 2. ANALYSE DE LIVRAISON DÉTAILLÉE
    # =====================================================
    st.header("2. 🔍 Analyse de Livraison Détaillée")
    tab_grouped, tab_city, tab_zone_group, tab_zone_summary, tab_charts = st.tabs([
        "Livraisons Client/Ville",
        "Besoin Estafette par Ville",
        "Livraisons Client/Zone",
        "Besoin Estafette par Zone",
        "Graphiques"
    ])

    with tab_grouped:
        st.subheader("Livraisons par Client & Ville")
        df_disp = st.session_state.df_grouped.copy()
        st.dataframe(df_disp, use_container_width=True)

    with tab_city:
        st.subheader("Besoin Estafette par Ville")
        st.dataframe(st.session_state.df_city, use_container_width=True)

    with tab_zone_group:
        st.subheader("Livraisons par Client & Ville + Zone")
        st.dataframe(st.session_state.df_grouped_zone, use_container_width=True)

    with tab_zone_summary:
        st.subheader("Besoin Estafette par Zone")
        st.dataframe(st.session_state.df_zone, use_container_width=True)

    with tab_charts:
        st.subheader("Statistiques par Ville")
        col1, col2 = st.columns(2)
        with col1:
            st.plotly_chart(px.bar(st.session_state.df_city, x="Ville", y="Poids total",
                                   title="Poids total livré par ville"), use_container_width=True)
        with col2:
            st.plotly_chart(px.bar(st.session_state.df_city, x="Ville", y="Volume total",
                                   title="Volume total livré par ville (m³)"), use_container_width=True)

    st.markdown("---")

    # =====================================================
    # 3. PROPOSITION DE LOCATION DE CAMION
    # =====================================================
    st.header("3. 🚚 Proposition de location de camion")
    st.markdown(f"🔸 Si un client dépasse **{SEUIL_POIDS} kg** ou **{SEUIL_VOLUME} m³**, une location est proposée.")
    update_propositions_view()
    if st.session_state.propositions is not None and not st.session_state.propositions.empty:
        col_prop, col_details = st.columns([2, 3])
        with col_prop:
            st.markdown("### Propositions ouvertes")
            st.dataframe(st.session_state.propositions, use_container_width=True)
            client_options = st.session_state.propositions['Client'].astype(str).tolist()
            client_options = [""] + client_options
            st.session_state.selected_client = st.selectbox("Client à traiter :", options=client_options, index=0)
            col_btn_acc, col_btn_ref = st.columns(2)
            is_client_selected = st.session_state.selected_client != ""
            with col_btn_acc:
                st.button("✅ Accepter la location", on_click=accept_location_callback, disabled=not is_client_selected)
            with col_btn_ref:
                st.button("❌ Refuser la proposition", on_click=refuse_location_callback, disabled=not is_client_selected)
        with col_details:
            st.markdown("### Détails de la commande client")
            if is_client_selected:
                resume, details_df_styled = st.session_state.rental_processor.get_details_client(st.session_state.selected_client)
                st.text(resume)
                try:
                    # Afficher le DataFrame non stylé pour Streamlit
                    if hasattr(details_df_styled, "data"):
                        st.dataframe(details_df_styled.data, use_container_width=True)
                    else:
                        st.dataframe(details_df_styled, use_container_width=True)
                except Exception:
                    st.info("Détails (formatage) non affichables, vérifiez la console.")
    else:
        st.success("🎉 Aucune proposition de location de camion en attente de décision.")
    st.markdown("---")

    # =====================================================
    # 4. VOYAGES PAR ESTAFETTE OPTIMISÉ (Section 4)
    # =====================================================
    st.header("4. Voyages par Estafette Optimisé (Inclut Camions Loués)")
    st.info("Tableau final : Zone | Véhicule N° | Poids total chargé | Volume total chargé | Client(s) inclus | Représentant(s) inclus | BL inclus | Taux d'occupation (%) | Location_camion | Location_proposee | Code Véhicule")
    st.dataframe(df_optimized_estafettes, use_container_width=True)

    # =====================================================
    # 5. INTERFACE DE TRANSFERT DES BL ENTRE ESTAFETTES
    # =====================================================
    st.header("5. 🔁 Transfert de Bons de Livraison (BL) entre estafettes")
    st.markdown("Sélectionnez la zone, l'estafette source, l'estafette cible et les BLs à transférer. **Seules les Estafettes sont disponibles pour le transfert.**")

    # Utilisation du df granulaire stocké
    df_bls_details = st.session_state.df_granular_bls.copy()
    
    # garantir noms et indexation
    bl_index_name = "No livraison"
    poids_col_name = "Poids total"
    vol_col_name = "Volume total"
    df_bls_details[bl_index_name] = df_bls_details[bl_index_name].astype(str)
    df_bl_details = df_bls_details[[bl_index_name, poids_col_name, vol_col_name]].set_index(bl_index_name).rename(columns={poids_col_name: "Poids", vol_col_name: "Volume"})

    rp = st.session_state.rental_processor
    df_base = rp.df_base.copy()
    
    # Fonction pour normaliser les BLs (utilisée pour extraire la liste des BLs d'une estafette)
    def split_bls_safe(x):
        if pd.isna(x): return []
        if isinstance(x, list): return [str(i).strip() for i in x]
        s = str(x)
        s = s.replace(",", ";")
        return [p.strip() for p in s.split(";") if p.strip()]
    df_base['BL_list'] = df_base['BL inclus'].apply(split_bls_safe)

    # zone selector
    zones = sorted(df_base['Zone'].dropna().unique().tolist())
    zone_choice = st.selectbox("Zone :", options=[""] + zones, index=0)

    # --- SÉLECTEURS DE VÉHICULE ---
    if zone_choice:
        # Filtrer uniquement les Estafettes actives pour le transfert manuel (Code Véhicule ESTAFETTE)
        df_zone_estafettes = df_base[(df_base['Zone'] == zone_choice) & (df_base['Code Véhicule'] == 'ESTAFETTE')].copy()
        
        vehs = sorted(df_zone_estafettes['Camion N°'].astype(str).tolist())
        col_src, col_tgt = st.columns(2)
        with col_src:
            src_vehicle = st.selectbox("Estafette source (Véhicule N°) :", options=[""] + vehs, index=0, help="Indice Camion N° tel que E1, E2, C1...")
        with col_tgt:
            tgt_vehicle = st.selectbox("Estafette cible (Véhicule N°) :", options=[""] + vehs, index=0)

        # BL multiselect populated from source
        bl_options = []
        if src_vehicle:
            row_src = df_zone_estafettes[df_zone_estafettes['Camion N°'].astype(str) == str(src_vehicle)]
            if not row_src.empty:
                bl_options = row_src.iloc[0]['BL_list']
        bl_selected = st.multiselect("BLs à transférer :", options=bl_options)

        # Buttons: vérifier puis confirmer
        col_check, col_confirm = st.columns([1, 1])
        with col_check:
            if st.button("Vérifier transfert", key="check_transfer"):
                if not src_vehicle or not tgt_vehicle or not bl_selected:
                    st.warning("Sélectionnez zone, source, cible et au moins un BL.")
                elif src_vehicle == tgt_vehicle:
                    st.error("Source et cible identiques — choisissez une cible différente.")
                else:
                    missing = [b for b in bl_selected if b not in df_bl_details.index]
                    if missing:
                        st.error(f"Détails Poids/Volume manquants pour BL(s): {missing}")
                    else:
                        poids_transf = float(df_bl_details.loc[bl_selected, "Poids"].sum())
                        vol_transf = float(df_bl_details.loc[bl_selected, "Volume"].sum())
                        
                        # target current (extraction depuis le DF filtré)
                        row_tgt = df_zone_estafettes[df_zone_estafettes['Camion N°'].astype(str) == str(tgt_vehicle)].iloc[0]
                        tgt_poids_cur = float(row_tgt["Poids total"])
                        tgt_vol_cur = float(row_tgt["Volume total"])
                        
                        new_poids = tgt_poids_cur + poids_transf
                        new_vol = tgt_vol_cur + vol_transf
                        
                        # Constantes de capacité Estafette (pour la vérification UX)
                        MAX_P = 1550 
                        MAX_V = 4.608
                        
                        st.write(f"Poids à transférer : **{poids_transf:.2f} kg** — Volume à transférer : **{vol_transf:.3f} m³**")
                        st.write(f"Après transfert la cible **{tgt_vehicle}** aura : Poids = **{new_poids:.2f} kg** / Volume = **{new_vol:.3f} m³**")
                        
                        if new_poids > MAX_P or new_vol > MAX_V:
                            st.error(f"Transfert **REFUSÉ** : capacité cible dépassée ({MAX_P} kg ou {MAX_V} m³).")
                        else:
                            st.success("Transfert **POSSIBLE** — vous pouvez confirmer.")
        with col_confirm:
            if st.button("Confirmer transfert", key="confirm_transfer"):
                if not src_vehicle or not tgt_vehicle or not bl_selected:
                    st.warning("Sélectionnez zone, source, cible et au moins un BL.")
                elif src_vehicle == tgt_vehicle:
                    st.error("Source et cible identiques — annulation.")
                else:
                    # Appel de la fonction backend corrigée qui gère le recalcul
                    try:
                        ok, msg, _ = rp.transfer_bl_between_estafettes(src_vehicle, tgt_vehicle, bl_selected)
                        if ok:
                            st.session_state.message = msg
                            # Re-charger les données et les propositions après modification
                            update_propositions_view()
                            st.experimental_rerun() # Rerun pour mettre à jour les sélecteurs et le tableau
                        else:
                            st.error(msg)
                    except Exception as e:
                        st.error(f"Erreur lors du transfert : {e}")
    else:
        st.info("Sélectionnez une zone pour activer le transfert.")

    st.markdown("---")

    # =====================================================
    # DOWNLOAD optimized result
    # =====================================================
    st.markdown("### Export des voyages optimisés")
    path_optimized = "Voyages_Estafette_Optimises.xlsx"
    # S'assurer d'utiliser le dernier DataFrame mis à jour
    st.session_state.df_optimized_estafettes = df_optimized_estafettes 
    
    # Créer le fichier avant le téléchargement
    df_optimized_estafettes.to_excel(path_optimized, index=False)
    
    with open(path_optimized, "rb") as f:
        st.download_button(
            label="💾 Télécharger Voyages Estafette Optimisés",
            data=f,
            file_name=path_optimized,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
else:
    st.info("Importer les fichiers et exécuter le traitement pour afficher les résultats.")
