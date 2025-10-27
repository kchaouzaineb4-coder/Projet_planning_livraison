import streamlit as st
import pandas as pd
from backend import DeliveryProcessor
import plotly.graph_objects as go

st.set_page_config(page_title="Planning Livraisons", layout="wide")
st.title("📦 Planning de Livraisons - Dashboard")

# Upload fichiers
liv_file = st.file_uploader("📄 Fichier Livraisons", type=["xlsx"])

if liv_file:
    try:
        processor = DeliveryProcessor(liv_file)
        df_liv = processor.process_data()

        # ✅ Affichage des données brutes
        st.subheader("🔍 Données Chargées")
        st.dataframe(df_liv, use_container_width=True)

        st.divider()

        # ==============================================================
        # 📊 DIAGRAMME 1 : Volume total par semaine
        # ==============================================================
        weekly_volume = df_liv.groupby("Semaine")["Volume de l'US"].sum().reset_index()
        fig1 = go.Figure(data=[
            go.Bar(
                x=weekly_volume["Semaine"],
                y=weekly_volume["Volume de l'US"],
                text=round(weekly_volume["Volume de l'US"], 2),
                textposition="outside"
            )
        ])
        fig1.update_layout(
            title="📊 Volume Total par Semaine (m³)",
            xaxis_title="Semaine",
            yaxis_title="Volume (m³)"
        )
        st.plotly_chart(fig1, use_container_width=True)

        # ==============================================================
        # 📊 DIAGRAMME 2 : Nombre de livraisons par semaine
        # ==============================================================
        weekly_count = df_liv.groupby("Semaine")["N° bon"].nunique().reset_index()
        fig2 = go.Figure(data=[
            go.Bar(
                x=weekly_count["Semaine"],
                y=weekly_count["N° bon"],
                text=weekly_count["N° bon"],
                textposition="outside"
            )
        ])
        fig2.update_layout(
            title="🚚 Nombre Total de Livraisons par Semaine",
            xaxis_title="Semaine",
            yaxis_title="Nombre de livraisons"
        )
        st.plotly_chart(fig2, use_container_width=True)

        st.divider()

        # ==============================================================
        # 📊 DIAGRAMME 3 : Nombre de livraisons par ville
        # ==============================================================
        livraisons_par_ville = df_liv.groupby("Ville")["N° bon"].nunique().reset_index()
        fig3 = go.Figure(data=[
            go.Bar(
                x=livraisons_par_ville["Ville"],
                y=livraisons_par_ville["N° bon"],
                text=livraisons_par_ville["N° bon"],
                textposition="outside"
            )
        ])
        fig3.update_layout(
            title="🏙️ Nombre Total de Livraisons par Ville",
            xaxis_title="Ville",
            yaxis_title="Nombre de livraisons"
        )
        st.plotly_chart(fig3, use_container_width=True)

        # ==============================================================
        # 📊 DIAGRAMME 4 : Volume total livré par ville
        # ==============================================================
        volume_ville = df_liv.groupby("Ville")["Volume de l'US"].sum().reset_index()
        fig4 = go.Figure(data=[
            go.Bar(
                x=volume_ville["Ville"],
                y=volume_ville["Volume de l'US"],
                text=round(volume_ville["Volume de l'US"], 2),
                textposition="outside"
            )
        ])
        fig4.update_layout(
            title="📦 Volume Total Livré par Ville (m³)",
            xaxis_title="Ville",
            yaxis_title="Volume (m³)"
        )
        st.plotly_chart(fig4, use_container_width=True)

    except Exception as e:
        st.error(f"🚫 Erreur : {e}")

else:
    st.info("Veuillez importer le fichier de livraisons 📄")
