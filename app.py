import streamlit as st
import pandas as pd
from backend import DeliveryProcessor
import plotly.express as px

st.set_page_config(page_title="Planning Livraisons", layout="wide")

st.title("📦 Planning de Livraisons - Dashboard")

# Upload fichier
uploaded_file = st.file_uploader("📄 Fichier Livraisons", type=["xlsx"])

if uploaded_file:
    try:
        df_liv = pd.read_excel(uploaded_file)
        processor = DeliveryProcessor(df_liv)

        st.success("✅ Fichier chargé avec succès !")
        st.write("### Aperçu des données")
        st.dataframe(df_liv.head())

        # ========== ANALYSE ========== #
        st.write("---")

        col1, col2 = st.columns(2)

        # ✅ Graphique : Nb livraisons par jour
        with col1:
            df_count_day = processor.count_by_day()
            fig1 = px.bar(df_count_day, x="Date", y="Nb Livraisons",
                          title="📅 Nombre de Livraisons par Jour")
            st.plotly_chart(fig1, use_container_width=True)

        # ✅ Graphique : Volume total par jour
        with col2:
            df_vol_day = processor.volume_by_day()
            fig2 = px.line(df_vol_day, x="Date", y="Volume Total (m3)",
                           title="📦 Volume Total par Jour (m3)")
            st.plotly_chart(fig2, use_container_width=True)

        st.write("---")

        col3, col4 = st.columns(2)

        # ✅ Nouveau : Nb livraisons par ville
        with col3:
            df_count_city = processor.count_by_city()
            fig3 = px.bar(df_count_city, x="ADR_LIV_VILLE", y="Nb Livraisons",
                          title="🏙️ Nombre de Livraisons par Ville")
            st.plotly_chart(fig3, use_container_width=True)

        # ✅ Nouveau : Volume total par ville
        with col4:
            df_vol_city = processor.volume_by_city()
            fig4 = px.bar(df_vol_city, x="ADR_LIV_VILLE", y="Volume Total (m3)",
                          title="🏗️ Volume Total par Ville (m3)")
            st.plotly_chart(fig4, use_container_width=True)

    except Exception as e:
        st.error(f"❌ Erreur lors du traitement : {e}")

else:
    st.info("📌 Veuillez importer votre fichier Excel pour commencer.")
