import streamlit as st
import pandas as pd
# Assurez-vous que le fichier backend.py est dans le même dossier
from backend import DeliveryProcessor, TruckRentalProcessor, SEUIL_POIDS, SEUIL_VOLUME 
import plotly.express as px

# Configuration page
st.set_page_config(page_title="Planning Livraisons", layout="wide")
st.title("🚚 Planning de Livraisons & Optimisation des Tournées")
st.markdown("---")

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
    st.session_state.df_voyages = None  # <-- Ajout pour éviter l'erreur
    st.session_state.rental_processor = None
    st.session_state.propositions = None
    st.session_state.selected_client = None
    st.session_state.message = ""

# =====================================================
# Fonctions de Callback pour la Location
# =====================================================
def update_propositions_view():
    if st.session_state.rental_processor:
        st.session_state.propositions = st.session_state.rental_processor.detecter_propositions()
        if (st.session_state.selected_client is not None and 
            st.session_state.propositions is not None and 
            st.session_state.selected_client not in st.session_state.propositions['Client'].astype(str).tolist()):
            st.session_state.selected_client = None
    else:
        st.session_state.propositions = pd.DataFrame()

def handle_location_action(accepter):
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
                    df_grouped, df_city, df_grouped_zone, df_zone, df_optimized_estafettes = processor.process_delivery_data(
                        liv_file, ydlogist_file, wcliegps_file
                    )
                # Stockage des résultats dans l'état de session
                st.session_state.df_voyages = df_optimized_estafettes.copy()  # <-- initialisation df_voyages
                st.session_state.df_optimized_estafettes = df_optimized_estafettes
                st.session_state.df_grouped = df_grouped
                st.session_state.df_city = df_city
                st.session_state.df_grouped_zone = df_grouped_zone
                st.session_state.df_zone = df_zone 
                
                st.session_state.rental_processor = TruckRentalProcessor(df_optimized_estafettes)
                update_propositions_view()
                
                st.session_state.data_processed = True
                st.session_state.message = "✅ Traitement terminé avec succès ! Les résultats s'affichent ci-dessous."
                st.rerun()
            except Exception as e:
                st.error(f"❌ Erreur lors du traitement : {str(e)}")
                st.session_state.data_processed = False
        else:
            st.warning("Veuillez uploader tous les fichiers nécessaires.")

st.markdown("---")

# =====================================================
# 2. AFFICHAGE DES RÉSULTATS
# =====================================================
if st.session_state.data_processed:
    
    if st.session_state.message.startswith("✅"):
        st.success(st.session_state.message)
    elif st.session_state.message.startswith("❌"):
        st.error(st.session_state.message)
    elif st.session_state.message.startswith("⚠️"):
        st.warning(st.session_state.message)
    else:
        st.info(st.session_state.message or "Prêt à traiter les propositions de location.")
    
    df_optimized_estafettes = st.session_state.rental_processor.get_df_result()
    
    # --- Analyse détaillée
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
        st.dataframe(st.session_state.df_grouped.drop(columns=["Zone"], errors='ignore'), use_container_width=True)
        
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
                                   title="Poids total livré par ville"),
                            use_container_width=True)
        with col2:
            st.plotly_chart(px.bar(st.session_state.df_city, x="Ville", y="Volume total",
                                   title="Volume total livré par ville (m³)"),
                            use_container_width=True)

        col3, col4 = st.columns(2)
        with col3:
            st.plotly_chart(px.bar(st.session_state.df_city, x="Ville", y="Nombre livraisons",
                                   title="Nombre de livraisons par ville"),
                            use_container_width=True)
        with col4:
            st.plotly_chart(px.bar(st.session_state.df_city, x="Ville", y="Besoin estafette réel",
                                   title="Besoin en Estafettes par ville"),
                            use_container_width=True)

    st.markdown("---")
    
    # --- Proposition Location Camion
    st.header("3. 🚚 Proposition de location de camion")
    st.markdown(f"🔸 Si un client dépasse **{SEUIL_POIDS} kg** ou **{SEUIL_VOLUME} m³**, une location est proposée (si non déjà décidée).")
    if st.session_state.propositions is not None and not st.session_state.propositions.empty:
        col_prop, col_details = st.columns([2, 3])
        with col_prop:
            st.markdown("### Propositions ouvertes")
            st.dataframe(st.session_state.propositions, 
                         use_container_width=True,
                         column_order=["Client", "Poids total (kg)", "Volume total (m³)", "Raison"],
                         hide_index=True)
            client_options = st.session_state.propositions['Client'].astype(str).tolist()
            client_options_with_empty = [""] + client_options
            default_index = 0
            if st.session_state.selected_client in client_options:
                 default_index = client_options_with_empty.index(st.session_state.selected_client)
            elif len(client_options) > 0:
                 default_index = 1
            st.session_state.selected_client = st.selectbox(
                "Client à traiter :", 
                options=client_options_with_empty, 
                index=default_index,
                key='client_select' 
            )
            col_btn_acc, col_btn_ref = st.columns(2)
            is_client_selected = st.session_state.selected_client != ""
            with col_btn_acc:
                st.button("✅ Accepter la location", 
                          on_click=accept_location_callback, 
                          disabled=not is_client_selected,
                          use_container_width=True)
            with col_btn_ref:
                st.button("❌ Refuser la proposition", 
                          on_click=refuse_location_callback, 
                          disabled=not is_client_selected,
                          use_container_width=True)
        with col_details:
            st.markdown("### Détails de la commande client")
            if is_client_selected:
                resume, details_df_styled = st.session_state.rental_processor.get_details_client(st.session_state.selected_client)
                st.text(resume)
                st.dataframe(details_df_styled, use_container_width=True, hide_index=True)
            else:
                st.info("Sélectionnez un client pour afficher les détails de la commande/estafettes.")
    else:
        st.success("🎉 Aucune proposition de location de camion en attente de décision.")
        
    st.markdown("---")
    
    # --- Voyages par Estafette Optimisé
    st.header("4. Voyages par Estafette Optimisé (Inclut Camions Loués)")
    st.info("Ce tableau représente l'ordonnancement final des livraisons, y compris les commandes pour lesquelles un camion loué (Code Véhicule : CAMION-LOUE) a été accepté ou refusé.")
    st.dataframe(df_optimized_estafettes.style.format({
         "Poids total chargé": "{:.2f} kg",
         "Volume total chargé": "{:.3f} m³",
         "Taux d'occupation (%)": "{:.2f}%"
    }), use_container_width=True)
    path_optimized = "Voyages_Estafette_Optimises.xlsx"
    df_optimized_estafettes.to_excel(path_optimized, index=False)
    with open(path_optimized, "rb") as f:
        st.download_button(
             label="💾 Télécharger Voyages Estafette Optimisés",
             data=f,
             file_name=path_optimized,
             mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

# =====================================================
# 5. TRANSFERT DES BLs ENTRE ESTAFETTES
# =====================================================
st.markdown("## 🔁 Transfert de BLs entre Estafettes")

df_voyages = st.session_state.df_voyages  # <-- Corrigé
df_client_ville_zone = st.session_state.df_grouped_zone

zones_dispo = df_voyages["Zone"].dropna().unique()
zone_sel = st.selectbox("Sélectionner la zone", zones_dispo)

estafettes_dispo = df_voyages[df_voyages["Zone"] == zone_sel]["Véhicule N°"].dropna().astype(str).str.strip().unique().tolist()
source_estafette = st.selectbox("Estafette source", estafettes_dispo)
cible_estafette = st.selectbox("Estafette cible", [e for e in estafettes_dispo if e != source_estafette])

source_bls_str = df_voyages.loc[df_voyages["Véhicule N°"] == source_estafette, "BL inclus"].values[0]
source_bls = source_bls_str.split(";") if pd.notna(source_bls_str) else []
bls_sel = st.multiselect("Sélectionner les BLs à transférer", source_bls)

MAX_POIDS = 1550
MAX_VOLUME = 4.608

if st.button("Transférer les BLs"):
    if not bls_sel:
        st.warning("⚠️ Sélectionnez au moins un BL à transférer")
    else:
        df_bls = df_client_ville_zone[df_client_ville_zone["No livraison"].isin(bls_sel)]
        poids_transfert = df_bls["Poids total"].sum()
        volume_transfert = df_bls["Volume total"].sum()
        source_row = df_voyages[df_voyages["Véhicule N°"] == source_estafette]
        cible_row = df_voyages[df_voyages["Véhicule N°"] == cible_estafette]

        poids_cible = cible_row["Poids total chargé"].values[0] + poids_transfert
        volume_cible = cible_row["Volume total chargé"].values[0] + volume_transfert

        if poids_cible > MAX_POIDS or volume_cible > MAX_VOLUME:
            st.error("❌ Transfert impossible : capacité max de l'estafette cible dépassée !")
        else:
            # --- Mettre à jour poids/volume
            df_voyages.loc[df_voyages["Véhicule N°"] == source_estafette, "Poids total chargé"] -= poids_transfert
            df_voyages.loc[df_voyages["Véhicule N°"] == source_estafette, "Volume total chargé"] -= volume_transfert
            df_voyages.loc[df_voyages["Véhicule N°"] == cible_estafette, "Poids total chargé"] += poids_transfert
            df_voyages.loc[df_voyages["Véhicule N°"] == cible_estafette, "Volume total chargé"] += volume_transfert

            # --- Clients & Représentants (suppression doublons)
            clients_transfert = df_bls["Client de l'estafette"].unique().tolist()
            reps_transfert = df_bls["Représentant"].unique().tolist()

            cible_clients_list = cible_row["Client(s) inclus"].values[0].split(";") if pd.notna(cible_row["Client(s) inclus"].values[0]) else []
            cible_clients_list += clients_transfert
            cible_clients_list = list(dict.fromkeys([cl.strip() for cl in cible_clients_list if cl.strip() != ""]))

            cible_reps_list = cible_row["Représentant(s) inclus"].values[0].split(";") if pd.notna(cible_row["Représentant(s) inclus"].values[0]) else []
            cible_reps_list += reps_transfert
            cible_reps_list = list(dict.fromkeys([r.strip() for r in cible_reps_list if r.strip() != ""]))

            df_voyages.loc[df_voyages["Véhicule N°"] == cible_estafette, "Client(s) inclus"] = "; ".join(cible_clients_list)
            df_voyages.loc[df_voyages["Véhicule N°"] == cible_estafette, "Représentant(s) inclus"] = "; ".join(cible_reps_list)

            st.success(f"✅ BLs transférés de {source_estafette} vers {cible_estafette} avec succès !")
            st.session_state.df_voyages = df_voyages
