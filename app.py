import streamlit as st
import plotly.express as px
from backend import DeliveryProcessor

st.set_page_config(page_title="Planning Livraisons", layout="wide")
st.title("🚚 Planning de Livraisons - Streamlit")

# Upload fichier
uploaded_file = st.file_uploader("📂 Importer un fichier livraisons", type=["csv", "xlsx"])

if uploaded_file:
    try:
        # 🔹 Chargement et nettoyage
        df = DeliveryProcessor.load_data(uploaded_file)
        df = DeliveryProcessor.clean_data(df)

        st.success("✅ Fichier chargé avec succès")
        st.dataframe(df)

        # 🔹 Calcul indicateurs
        liv_ville, vol_ville = DeliveryProcessor.compute_metrics(df)

        # 🔹 Graphique : Nombre de livraisons par ville
        fig1 = px.bar(liv_ville,
                      x="Ville",
                      y="Nb Livraisons",
                      title="📦 Nombre de livraisons par ville")

        # 🔹 Graphique : Volume total (m3) par ville
        fig2 = px.bar(vol_ville,
                      x="Ville",
                      y="Volume Total",
                      title="📊 Volume total par ville (m3)")

        # Affichage côte à côte
        col1, col2 = st.columns(2)
        col1.plotly_chart(fig1, use_container_width=True)
        col2.plotly_chart(fig2, use_container_width=True)

    except Exception as e:
        st.error(f"❌ Erreur traitement : {e}")
