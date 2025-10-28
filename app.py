import streamlit as st
import pandas as pd
from backend import DeliveryProcessor
import plotly.express as px

st.set_page_config(page_title="Planning Livraisons", layout="wide")
st.title("🚚 Planning de Livraisons - Streamlit")

# Upload fichiers
liv_file = st.file_uploader("📂 Importer un fichier livraisons", type=["xlsx", "xls"])

# Instance du processor
processor = DeliveryProcessor()

if liv_file is not None:
    try:
        # Traitement principal
        df_grouped, df_city, df_grouped_zone = processor.process_all(liv_file)

        # =============================
        # ✅ Tableau 1 : Livraisons par Client & Ville (sans Zone)
        # =============================
        st.subheader("📄 Tableau original : Livraisons par Client & Ville (Sans Zone)")
        df_grouped_display = df_grouped.copy()

        if "Zone" in df_grouped_display.columns:
            df_grouped_display = df_grouped_display.drop(columns=["Zone"])

        st.dataframe(df_grouped_display)

        # Téléchargement Tableau 1
        path_grouped = "Livraisons_par_Client_Ville.xlsx"
        df_grouped_display.to_excel(path_grouped, index=False)

        with open(path_grouped, "rb") as f:
            st.download_button(
                label="⬇ Télécharger Livraisons par Client & Ville (Sans Zone)",
                data=f,
                file_name="Livraisons_par_Client_Ville.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

        st.markdown("---")

        # =============================
        # ✅ Tableau 2 : Besoin Estafette par Ville
        # =============================
        st.subheader("🏙️ Besoin Estafette par Ville")
        st.dataframe(df_city)

        # Téléchargement Tableau 2
        path_city = "Besoin_estafette_par_Ville.xlsx"
        df_city.to_excel(path_city, index=False)

        with open(path_city, "rb") as f:
            st.download_button(
                label="⬇ Télécharger Besoin Estafette par Ville",
                data=f,
                file_name="Besoin_estafette_par_Ville.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

        st.markdown("---")

        # =============================
        # ✅ Tableau 3 : Livraisons par Client & Ville + Zone (zones inconnues filtrées)
        # =============================
        st.subheader("📍 Tableau : Livraisons par Client & Ville + Zone")

        # ✅ Suppression Zone inconnue
        df_grouped_zone_clean = df_grouped_zone[df_grouped_zone["Zone"] != "Zone inconnue"]
        st.dataframe(df_grouped_zone_clean)

        # Téléchargement Tableau 3 (filtré)
        path_grouped_zone = "Livraisons_par_Client_Ville_Zone.xlsx"
        df_grouped_zone_clean.to_excel(path_grouped_zone, index=False)

        with open(path_grouped_zone, "rb") as f:
            st.download_button(
                label="⬇ Télécharger Livraisons par Client & Ville + Zone",
                data=f,
                file_name="Livraisons_par_Client_Ville_Zone.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

        st.markdown("---")

        # =============================
        # ✅ Graphiques supplémentaires (optionnels)
        # =============================
        st.subheader("📊 Graphiques")

        col1, col2 = st.columns(2)

        with col1:
            fig1 = px.bar(df_city, x="Ville", y="Total Livraisons", title="📦 Nombre de livraisons par ville")
            st.plotly_chart(fig1, use_container_width=True)

        with col2:
            fig2 = px.bar(df_city, x="Ville", y="Volume Total (m3)", title="📦 Volume total (m3) par ville")
            st.plotly_chart(fig2, use_container_width=True)

    except Exception as e:
        st.error(f"❌ Erreur lors du traitement des données : {e}")

else:
    st.info("📌 Veuillez importer un fichier Excel contenant les données de livraisons.")
