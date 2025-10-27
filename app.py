import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from backend import DeliveryProcessor

st.set_page_config(page_title="Planning Livraisons", layout="wide")
st.title("Planning de Livraisons - Streamlit")

# Upload fichiers
liv_file = st.file_uploader("Fichier Livraisons", type=["xlsx"])
ydlogist_file = st.file_uploader("Fichier YDLOGIST", type=["xlsx"])
wcliegps_file = st.file_uploader("Fichier WCLIEGPS", type=["xlsx"])

if st.button("Exécuter le traitement complet"):
    if liv_file and ydlogist_file and wcliegps_file:
        processor = DeliveryProcessor()
        try:
            df_result = processor.process_delivery_data(liv_file, ydlogist_file, wcliegps_file)
            
            # Affichage du tableau
            st.subheader("Aperçu des résultats")
            st.dataframe(df_result)
            
            # Bouton pour télécharger le fichier final
            output_path = "Livraison_finale_avec_ville_et_client.xlsx"
            processor.export_results(df_result, output_path)
            with open(output_path, "rb") as f:
                st.download_button(
                    label="Télécharger les résultats",
                    data=f,
                    file_name="Livraison_finale_avec_ville_et_client.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            
            # --- Graphique combiné par ville ---
            df_ville = df_result.groupby("Ville").agg(
                Nombre_livraisons=("No livraison", "nunique"),
                Poids_total=("Poids total", "sum"),
                Volume_total=("Volume total", "sum")
            ).reset_index()

            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=df_ville["Ville"],
                y=df_ville["Nombre_livraisons"],
                name="Nombre de livraisons",
                marker_color='steelblue'
            ))
            fig.add_trace(go.Bar(
                x=df_ville["Ville"],
                y=df_ville["Poids_total"],
                name="Poids total (kg)",
                marker_color='darkorange'
            ))
            fig.add_trace(go.Bar(
                x=df_ville["Ville"],
                y=df_ville["Volume_total"],
                name="Volume total (m³)",
                marker_color='green'
            ))

            fig.update_layout(
                title="Statistiques des livraisons par ville",
                xaxis=dict(title="Ville"),
                yaxis=dict(title="Quantité"),
                barmode='group',
                legend=dict(x=1.05, y=1)
            )

            st.plotly_chart(fig, use_container_width=True)

        except Exception as e:
            st.error(f"Erreur : {str(e)}")
    else:
        st.warning("Veuillez uploader tous les fichiers nécessaires.")
