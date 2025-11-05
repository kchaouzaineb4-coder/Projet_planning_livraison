# app.py (FINAL — prêt à coller)
import streamlit as st
import pandas as pd
from io import BytesIO
import plotly.express as px

# backend.py doit être dans le même dossier
from backend import DeliveryProcessor, TruckRentalProcessor, SEUIL_POIDS, SEUIL_VOLUME, CAMION_CODE

st.set_page_config(page_title="Planning Livraisons", layout="wide")
st.title("🚚 Planning de Livraisons & Optimisation des Tournées")
st.markdown("---")


# ---------------------------
# Utilitaires
# ---------------------------
def show_df(df, **kwargs):
    """Affiche un DataFrame en arrondissant les floats."""
    if isinstance(df, pd.DataFrame):
        df_to_display = df.copy()
        for c in df_to_display.select_dtypes(include=["float", "int"]).columns:
            df_to_display[c] = df_to_display[c].round(3)
        st.dataframe(df_to_display, **kwargs)
    else:
        st.dataframe(df, **kwargs)


# ---------------------------
# Init session_state
# ---------------------------
if "initialized" not in st.session_state:
    st.session_state.initialized = True
    st.session_state.data_processed = False
    st.session_state.df_grouped = None
    st.session_state.df_city = None
    st.session_state.df_grouped_zone = None
    st.session_state.df_zone = None
    st.session_state.df_optimized_estafettes = None
    st.session_state.df_livraisons = None  # détaillé (No livraison, Poids total, Volume total, Zone, Représentant)
    st.session_state.rental_processor = None
    st.session_state.df_voyages = None
    st.session_state.propositions = pd.DataFrame()
    st.session_state.selected_client = None
    st.session_state.message = ""
    st.session_state.validations = {}
    st.session_state.df_voyages_valides = None
    st.session_state.attributions = {}

# ---------------------------
# 1️⃣ Upload des fichiers
# ---------------------------
st.header("1️⃣ Importation des fichiers")
col1, col2, col3, col4 = st.columns([3,3,3,1])
with col1:
    liv_file = st.file_uploader("Fichier Livraisons (BL)", type=["xlsx"])
with col2:
    ydlogist_file = st.file_uploader("Fichier Volumes (Articles)", type=["xlsx"])
with col3:
    wcliegps_file = st.file_uploader("Fichier Clients / Zones", type=["xlsx"])
with col4:
    st.write("")
    if st.button("▶️ Traiter les fichiers", type="primary"):
        if not (liv_file and ydlogist_file and wcliegps_file):
            st.warning("Veuillez uploader les 3 fichiers requis.")
        else:
            try:
                processor = DeliveryProcessor()
                with st.spinner("Traitement en cours..."):
                    df_grouped, df_city, df_grouped_zone, df_zone, df_optimized_estafettes = processor.process_delivery_data(
                        liv_file, ydlogist_file, wcliegps_file
                    )
                # Stockage
                st.session_state.df_grouped = df_grouped
                st.session_state.df_city = df_city
                st.session_state.df_grouped_zone = df_grouped_zone
                st.session_state.df_zone = df_zone
                st.session_state.df_optimized_estafettes = df_optimized_estafettes
                st.session_state.df_livraisons = df_grouped_zone.copy()  # utilisé pour calculs poids/volume par BL

                # Init rental processor avec DF optimisé et données brutes
                st.session_state.rental_processor = TruckRentalProcessor(df_optimized_estafettes, df_grouped_zone)
                # Initial voyages (lira rental_processor.get_df_result())
                st.session_state.df_voyages = st.session_state.rental_processor.get_df_result()
                st.session_state.data_processed = True
                st.success("✅ Traitement terminé.")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Erreur lors du traitement : {e}")

st.markdown("---")


# ---------------------------
# 2️⃣ Propositions de location
# ---------------------------
if st.session_state.data_processed and st.session_state.rental_processor is not None:
    st.header("2️⃣ Proposition de location de camion")
    propositions = st.session_state.rental_processor.detecter_propositions()
    if propositions is None or propositions.empty:
        st.success("🎉 Aucune proposition de location en attente.")
    else:
        # assurer nom 'Client'
        if "Client" not in propositions.columns and "Client de l'estafette" in propositions.columns:
            propositions = propositions.rename(columns={"Client de l'estafette": "Client"})
        show_df(propositions[["Client", "Poids total (kg)", "Volume total (m³)", "Raison"]])

        # selection client
        client_list = [""] + propositions["Client"].astype(str).tolist()
        st.session_state.selected_client = st.selectbox("Client à traiter", client_list, index=0)

        col_acc, col_ref = st.columns(2)
        with col_acc:
            if st.button("✅ Accepter la location") and st.session_state.selected_client:
                ok, msg, _ = st.session_state.rental_processor.appliquer_location(st.session_state.selected_client, accepter=True)
                if ok:
                    st.success(msg)
                    # mise à jour voyages (inclut désormais camions loués)
                    st.session_state.df_voyages = st.session_state.rental_processor.get_df_result()
                    st.rerun()
                else:
                    st.error(msg)
        with col_ref:
            if st.button("❌ Refuser la proposition") and st.session_state.selected_client:
                ok, msg, _ = st.session_state.rental_processor.appliquer_location(st.session_state.selected_client, accepter=False)
                if ok:
                    st.info(msg)
                    st.session_state.df_voyages = st.session_state.rental_processor.get_df_result()
                    st.rerun()
                else:
                    st.error(msg)
st.markdown("---")


# ---------------------------
# 3️⃣ Voyages optimisés (affichage)
# ---------------------------
if st.session_state.data_processed and st.session_state.rental_processor is not None:
    st.header("3️⃣ Voyages optimisés (Estafettes + Camions loués)")
    df_voyages = st.session_state.rental_processor.get_df_result().copy()
    # formattage affichage (ne pas modifier df_voyages stocké)
    df_show = df_voyages.copy()
    if "Poids total chargé" in df_show.columns:
        df_show["Poids total chargé"] = df_show["Poids total chargé"].map(lambda x: f"{x:.3f} kg")
    if "Volume total chargé" in df_show.columns:
        df_show["Volume total chargé"] = df_show["Volume total chargé"].map(lambda x: f"{x:.3f} m³")
    if "Taux d'occupation (%)" in df_show.columns:
        df_show["Taux d'occupation (%)"] = df_show["Taux d'occupation (%)"].map(lambda x: f"{x:.3f}%")
    show_df(df_show, use_container_width=True)

    # sauvegarder l'état
    st.session_state.df_voyages = df_voyages

    # export
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df_voyages.to_excel(writer, index=False, sheet_name="Voyages_Optimises")
    st.download_button("💾 Télécharger Voyages optimisés", buf.getvalue(), "voyages_optimises.xlsx")

st.markdown("---")


# ---------------------------
# 4️⃣ Transfert de BLs entre Estafettes / Camions
# ---------------------------
st.header("4️⃣ 🔁 Transfert de BLs entre Estafettes / Camions")

if st.session_state.df_voyages is None:
    st.warning("⚠️ Exécutez d'abord l'optimisation (section 3).")
elif st.session_state.df_livraisons is None:
    st.warning("⚠️ Données détaillées des livraisons manquantes (df_livraisons).")
else:
    df_v = st.session_state.rental_processor.get_df_result().copy()  # IMPORTANT: lire la source à jour
    st.session_state.df_voyages = df_v.copy()

    # colonnes attendues
    needed = ["Zone", "Véhicule N°", "Poids total chargé", "Volume total chargé", "BL inclus"]
    if not all(c in df_v.columns for c in needed):
        st.error("❌ DataFrame voyages manque des colonnes requises.")
    else:
        zones = sorted(df_v["Zone"].dropna().unique().tolist())
        zone_sel = st.selectbox("🌍 Zone", zones)

        if zone_sel:
            df_zone = df_v[df_v["Zone"] == zone_sel]
            vehs = sorted(df_zone["Véhicule N°"].dropna().unique().tolist())

            col1, col2 = st.columns(2)
            with col1:
                src = st.selectbox("🚐 Véhicule source", vehs)
            with col2:
                dst = st.selectbox("🎯 Véhicule cible", [v for v in vehs if v != src])

            if src and dst:
                row_src = df_zone[df_zone["Véhicule N°"] == src].iloc[0]
                bls_src = str(row_src["BL inclus"]).split(";") if pd.notna(row_src["BL inclus"]) else []
                bls_src = [b for b in bls_src if b != ""]  # nettoyer
                st.subheader(f"BLs du véhicule {src}")
                st.write(bls_src)

                bls_to_move = st.multiselect("Sélectionner BLs à transférer", bls_src)

                if st.button("🔁 Exécuter le transfert"):
                    if not bls_to_move:
                        st.warning("Sélectionnez au moins un BL.")
                    else:
                        # calcul poids/volume des BL sélectionnés depuis df_livraisons (source détaillée)
                        df_liv = st.session_state.df_livraisons
                        sel = df_liv[df_liv["No livraison"].astype(str).isin([str(x) for x in bls_to_move])]
                        poids_sel = float(sel["Poids total"].sum())
                        vol_sel = float(sel["Volume total"].sum())

                        # capacites (estafette)
                        estaf_poids = 1550.0
                        estaf_vol = 4.608

                        # poids/vol cible
                        row_dst = df_zone[df_zone["Véhicule N°"] == dst].iloc[0]
                        poids_dst = float(row_dst["Poids total chargé"])
                        vol_dst = float(row_dst["Volume total chargé"])

                        if (poids_dst + poids_sel) > estaf_poids or (vol_dst + vol_sel) > estaf_vol:
                            st.warning("⚠️ Le transfert dépasse la capacité du véhicule cible.")
                        else:
                            # appliquer au DataFrame df_v (local) puis sauvegarder dans rental_processor.df_base
                            def apply_transfer(df_rows):
                                dfr = df_rows.copy()
                                # source
                                if dfr["Véhicule N°"] == src and dfr["Zone"] == zone_sel:
                                    current = [b for b in str(dfr["BL inclus"]).split(";") if b]
                                    new = [b for b in current if b not in bls_to_move]
                                    dfr["BL inclus"] = ";".join(new)
                                    dfr["Poids total chargé"] = max(0.0, float(dfr["Poids total chargé"]) - poids_sel)
                                    dfr["Volume total chargé"] = max(0.0, float(dfr["Volume total chargé"]) - vol_sel)
                                # destination
                                if dfr["Véhicule N°"] == dst and dfr["Zone"] == zone_sel:
                                    current = [b for b in str(dfr["BL inclus"]).split(";") if b]
                                    new = current + bls_to_move
                                    dfr["BL inclus"] = ";".join(new)
                                    dfr["Poids total chargé"] = float(dfr["Poids total chargé"]) + poids_sel
                                    dfr["Volume total chargé"] = float(dfr["Volume total chargé"]) + vol_sel
                                return dfr

                            df_v_updated = df_v.apply(apply_transfer, axis=1)
                            # Mettre à jour rental_processor.df_base si possible (synchronisation)
                            try:
                                # overwrite df_base with compatible columns where possible
                                rp = st.session_state.rental_processor
                                rp.df_base = rp.df_base.copy()
                                # Map by 'Véhicule N°' <-> 'Camion N°' or 'Camion N°' column
                                # To be safe, replace by matching 'Camion N°' values if present, else by 'Véhicule N°'
                                if "Camion N°" in rp.df_base.columns:
                                    rp.df_base["Camion N°"] = rp.df_base["Camion N°"].astype(str)
                                    for idx, r in df_v_updated.iterrows():
                                        mask = rp.df_base["Camion N°"] == str(r["Véhicule N°"])
                                        if mask.any():
                                            rp.df_base.loc[mask, "BL inclus"] = r["BL inclus"]
                                            # try update poids/volume columns if exist
                                            if "Poids total chargé" in rp.df_base.columns:
                                                rp.df_base.loc[mask, "Poids total chargé"] = r["Poids total chargé"]
                                            if "Volume total chargé" in rp.df_base.columns:
                                                rp.df_base.loc[mask, "Volume total chargé"] = r["Volume total chargé"]
                                else:
                                    # fallback: try 'Véhicule N°' column
                                    if "Véhicule N°" in rp.df_base.columns:
                                        for idx, r in df_v_updated.iterrows():
                                            mask = rp.df_base["Véhicule N°"] == r["Véhicule N°"]
                                            if mask.any():
                                                rp.df_base.loc[mask, "BL inclus"] = r["BL inclus"]
                                                if "Poids total chargé" in rp.df_base.columns:
                                                    rp.df_base.loc[mask, "Poids total chargé"] = r["Poids total chargé"]
                                                if "Volume total chargé" in rp.df_base.columns:
                                                    rp.df_base.loc[mask, "Volume total chargé"] = r["Volume total chargé"]
                            except Exception:
                                # ne pas bloquer l'UI si la sync échoue
                                pass

                            # sauvegarde état UI
                            st.session_state.df_voyages = df_v_updated.copy()
                            st.success(f"✅ Transfert effectué : {len(bls_to_move)} BL(s).")
                            st.rerun()

st.markdown("---")


# ---------------------------
# 5️⃣ Ajouter un objet manuel (machine / colis / BL manuel)
# ---------------------------
st.header("5️⃣ ➕ Ajouter un objet manuel dans un véhicule")
if st.session_state.df_voyages is None:
    st.info("Exécutez d'abord l'optimisation (section 3).")
else:
    df_v = st.session_state.rental_processor.get_df_result().copy()
    # garantir la colonne 'Véhicule N°' existe
    if "Véhicule N°" not in df_v.columns:
        st.error("Le DataFrame voyages ne contient pas la colonne 'Véhicule N°'.")
    else:
        zones = sorted(df_v["Zone"].dropna().unique().tolist())
        zone_obj = st.selectbox("Zone", zones)
        vehicles = sorted(df_v[df_v["Zone"] == zone_obj]["Véhicule N°"].dropna().unique().tolist())
        vehicle_obj = st.selectbox("Véhicule cible", vehicles)

        name_obj = st.text_input("Désignation de l'objet")
        weight_obj = st.number_input("Poids (kg)", min_value=0.0, step=0.1, format="%.3f")
        volume_obj = st.number_input("Volume (m³)", min_value=0.0, step=0.001, format="%.3f")

        if st.button("✅ Ajouter l'objet dans le véhicule"):
            if not name_obj or weight_obj <= 0 or volume_obj <= 0:
                st.warning("Remplissez correctement la désignation, le poids et le volume (> 0).")
            else:
                rp = st.session_state.rental_processor
                ok, msg, df_updated = rp.add_manual_object(st.session_state.df_voyages, vehicle_obj, zone_obj, name_obj, weight_obj, volume_obj)
                if ok:
                    # mettre à jour l'état avec la source officielle
                    st.session_state.df_voyages = rp.get_df_result()
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)

    # afficher objets manuels présents
    df_check = st.session_state.rental_processor.get_df_result().copy()
    df_check["ObjectsAdded"] = df_check["BL inclus"].apply(lambda s: ";".join([b for b in str(s).split(";") if str(b).startswith("OBJ-")]) if pd.notna(s) else "")
    df_objs = df_check[df_check["ObjectsAdded"].astype(str).str.strip() != ""]
    if not df_objs.empty:
        st.markdown("### 📦 Objets manuels présents")
        show_df(df_objs[["Zone", "Véhicule N°", "ObjectsAdded", "Poids total chargé", "Volume total chargé", "Taux d'occupation (%)"]])

st.markdown("---")


# ---------------------------
# 6️⃣ Validation des voyages après transfert
# ---------------------------
st.header("6️⃣ ✅ Validation des voyages après transfert")
if st.session_state.df_voyages is None:
    st.info("Aucun voyage à valider (exécutez l'optimisation).")
else:
    df_val = st.session_state.df_voyages.copy().reset_index(drop=True)
    # interface simple : afficher et permettre choix
    validated = []
    for i, r in df_val.iterrows():
        col1, col2 = st.columns([4,1])
        with col1:
            st.write(f"Véhicule: **{r['Véhicule N°']}**  — Zone: **{r['Zone']}**")
            st.write(f"BLs: {r.get('BL inclus','')}")
        with col2:
            ans = st.radio("", ["Oui", "Non"], index=0, key=f"validate_{i}")
            if ans == "Oui":
                validated.append(i)
    if st.button("🧾 Confirmer voyages validés"):
        df_valid = df_val.loc[validated].reset_index(drop=True)
        st.session_state.df_voyages_valides = df_valid
        st.success(f"{len(df_valid)} voyage(s) validé(s).")
        # export XLSX
        out = BytesIO()
        with pd.ExcelWriter(out, engine="openpyxl") as w:
            df_valid.to_excel(w, index=False, sheet_name="Voyages_valides")
        st.download_button("💾 Télécharger voyages validés", out.getvalue(), "voyages_valides.xlsx")

st.markdown("---")


# ---------------------------
# 7️⃣ Attribution véhicules/chauffeurs (optionnel)
# ---------------------------
st.header("7️⃣ 🚛 Attribution Véhicules et Chauffeurs (optionnel)")
if "df_voyages_valides" in st.session_state and st.session_state.df_voyages_valides is not None:
    df_attr = st.session_state.df_voyages_valides.copy()
    VEHICULES_DISP = ['SLG-VEH11','SLG-VEH14','SLG-VEH22','SLG-VEH19','SLG-VEH10']
    CHAUFFEURS = ['DAMMAK Karim','MAAZOUN Bassem','SASSI Ramzi']
    atts = {}
    for i, r in df_attr.iterrows():
        veh_sel = st.selectbox(f"Véhicule pour {r['Véhicule N°']}", VEHICULES_DISP, key=f"att_veh_{i}")
        chf_sel = st.selectbox(f"Chauffeur pour {r['Véhicule N°']}", CHAUFFEURS, key=f"att_chf_{i}")
        atts[i] = {"Véhicule": veh_sel, "Chauffeur": chf_sel}
    if st.button("📤 Appliquer attributions"):
        st.session_state.attributions = atts
        st.success("Attributions enregistrées.")
else:
    st.info("Validez des voyages pour activer l'attribution (section 6).")

st.markdown("---")
st.info("app.py chargé — teste les actions : accepter location → vérifier camions dans Transfert / Ajout objet.")
