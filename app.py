import streamlit as st
import pandas as pd
import plotly.express as px
from backend import DeliveryProcessor, TruckTransferManager

st.set_page_config(page_title="🚚 Planning de Livraisons", layout="wide")

st.title("🚚 Planning de Livraisons")

# ================================
# 📂 IMPORT DES FICHIERS
# ================================
st.header("📦 Importer les fichiers de livraisons et volumes")

uploaded_livraisons = st.file_uploader("Fichier Livraisons", type=["csv", "xlsx"])
uploaded_volumes = st.file_uploader("Fichier Volumes", type=["csv", "xlsx"])

if uploaded_livraisons and uploaded_volumes:
    try:
        processor = DeliveryProcessor()

        df_livraisons = processor.load_data(uploaded_livraisons)
        df_volumes = processor.load_data(uploaded_volumes)

        (
            df_detaillé,
            df_client_ville_zone,
            df_besoin_estafette
        ) = processor.traiter_donnees(df_livraisons, df_volumes)

        # ================================
        # 🧾 TABLEAU 1 : DÉTAILLÉ
        # ================================
        st.subheader("📋 Détails des livraisons")
        st.dataframe(df_detaillé, use_container_width=True)

        st.download_button(
            label="⬇️ Télécharger le tableau détaillé",
            data=processor.to_excel(df_detaillé),
            file_name="Livraisons_Detail.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        # ================================
        # 📦 TABLEAU 2 : CLIENT & VILLE + ZONE
        # ================================
        st.subheader("🏙️ Livraisons par Client & Ville + Zone (hors Zone inconnue)")
        st.dataframe(df_client_ville_zone, use_container_width=True)

        st.download_button(
            label="⬇️ Télécharger Livraisons par Client & Ville + Zone",
            data=processor.to_excel(df_client_ville_zone),
            file_name="Livraisons_Client_Ville_Zone.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        # ================================
        # 🚐 TABLEAU 3 : Besoin Estafette
        # ================================
        st.subheader("🚐 Besoin en Estafettes par Ville")
        st.dataframe(df_besoin_estafette, use_container_width=True)

        st.download_button(
            label="⬇️ Télécharger Besoin Estafette par Ville",
            data=processor.to_excel(df_besoin_estafette),
            file_name="Besoin_Estafette.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        # ================================
        # 📊 GRAPHIQUES
        # ================================
        st.header("📊 Visualisation des livraisons")

        col1, col2 = st.columns(2)

        with col1:
            fig1 = px.bar(df_client_ville_zone.groupby("Ville").size().reset_index(name="Nombre de livraisons"),
                          x="Ville", y="Nombre de livraisons", title="Nombre de livraisons par ville")
            st.plotly_chart(fig1, use_container_width=True)

        with col2:
            fig2 = px.bar(df_client_ville_zone.groupby("Ville")["Volume (m3)"].sum().reset_index(),
                          x="Ville", y="Volume (m3)", title="Volume total par ville (m³)")
            st.plotly_chart(fig2, use_container_width=True)

        # ================================
        # 🔁 INTERFACE DE TRANSFERT DE BLS
        # ================================
        st.header("🔁 Transfert des BLs entre estafettes")

        manager = TruckTransferManager(df_client_ville_zone)

        # Sélection zone
        zones = sorted(df_client_ville_zone["Zone"].dropna().unique())
        selected_zone = st.selectbox("🌍 Sélectionnez la zone :", zones)

        if selected_zone:
            estafettes_zone = manager.get_estafettes_in_zone(selected_zone)
            if estafettes_zone:
                col1, col2 = st.columns(2)

                with col1:
                    source = st.selectbox("🚚 Estafette source :", estafettes_zone)
                with col2:
                    cible = st.selectbox("🎯 Estafette cible :", [e for e in estafettes_zone if e != source])

                if source:
                    bls_source = manager.get_bls_of_estafette(selected_zone, source)
                    selected_bls = st.multiselect("📦 Sélectionnez les BLs à transférer :", bls_source)

                    if selected_bls and cible:
                        if st.button("✅ Vérifier le transfert"):
                            result, details = manager.check_transfer(selected_zone, source, cible, selected_bls)
                            if result:
                                st.success("✅ TRANSFERT AUTORISÉ (En attente de validation)")
                            else:
                                st.error("❌ TRANSFERT REFUSÉ : CAPACITÉ DÉPASSÉE ❌")
                            st.write("📘 Détails :", details)

            else:
                st.warning("⚠️ Aucune estafette trouvée dans cette zone.")

    except Exception as e:
        st.error(f"❌ Erreur lors du traitement des données: {e}")
else:
    st.info("📥 Veuillez importer les deux fichiers pour commencer.")
