import streamlit as st
import pandas as pd
from backend import DeliveryProcessor
from plotly.subplots import make_subplots
import plotly.graph_objects as go

st.set_page_config(page_title="Planning Livraisons", layout="wide")
st.title("Planning de Livraisons - Streamlit")

# Upload fichiers
liv_file = st.file_uploader("Fichier Livraisons", type=["xls", "xlsx"])
ydlogist_file = st.file_uploader("Fichier YDLOGIST", type=["xls", "xlsx"])
wcliegps_file = st.file_uploader("Fichier WCLIEGPS", type=["xls", "xlsx", "csv"])

def _pick_col(df, candidates):
    for cand in candidates:
        for c in df.columns:
            if c is None:
                continue
            if cand.lower() in str(c).lower():
                return c
    return None

if st.button("Exécuter le traitement complet"):
    if liv_file and ydlogist_file and wcliegps_file:
        processor = DeliveryProcessor()
        try:
            df_result = processor.process_delivery_data(liv_file, ydlogist_file, wcliegps_file)
            
            st.subheader("Aperçu des résultats")
            st.dataframe(df_result)
            
            # Export et téléchargement
            output_path = "Livraison_finale_avec_ville_et_client.xlsx"
            processor.export_results(df_result, output_path)
            with open(output_path, "rb") as f:
                st.download_button(
                    label="Télécharger les résultats",
                    data=f,
                    file_name="Livraison_finale_avec_ville_et_client.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

            # -------------------------
            # Graphe combiné par ville
            # -------------------------
            # Détection colonnes
            city_col = _pick_col(df_result, ["Ville", "City"])
            no_col = _pick_col(df_result, ["No livraison", "No_livraison", "No livraison", "NoLivraison", "No"])
            weight_col = _pick_col(df_result, ["Poids total", "Poids_total", "Poids", "Poids total livraison"])
            volume_col = _pick_col(df_result, ["Volume total", "Volume_total", "Volume", "Volume total livraison"])

            if city_col is None:
                st.warning("Impossible de construire le graphique : colonne 'Ville' introuvable dans les résultats.")
            else:
                # Vérifier les autres colonnes
                if weight_col is None or volume_col is None or no_col is None:
                    st.info("Les graphiques nécessitent les colonnes 'Poids total', 'Volume total' et 'No livraison'. Vérifier les en-têtes.")
                else:
                    # Agrégation par ville
                    df_city = df_result.groupby(city_col).agg({
                        no_col: pd.Series.nunique,
                        weight_col: "sum",
                        volume_col: "sum"
                    }).rename(columns={
                        no_col: "Nombre livraisons",
                        weight_col: "Poids total",
                        volume_col: "Volume total"
                    })

                    # nettoyage / conversion numérique
                    df_city["Poids total"] = pd.to_numeric(df_city["Poids total"], errors="coerce").fillna(0)
                    df_city["Volume total"] = pd.to_numeric(df_city["Volume total"], errors="coerce").fillna(0)
                    df_city["Nombre livraisons"] = df_city["Nombre livraisons"].astype(int)

                    if df_city.empty:
                        st.info("Aucune donnée agrégée pour les villes.")
                    else:
                        # Option : top N
                        max_n = min(50, len(df_city))
                        top_n = st.slider("Afficher top N villes (triées par poids total)", min_value=3, max_value=max_n, value=min(20, max_n))
                        df_city = df_city.sort_values("Poids total", ascending=False).head(top_n)

                        # Figure Plotly : bar (nombre) + bar (poids) + ligne (volume) sur axe secondaire
                        fig = make_subplots(specs=[[{"secondary_y": True}]])
                        fig.add_trace(
                            go.Bar(x=df_city.index, y=df_city["Nombre livraisons"], name="Nombre livraisons", marker_color="rgb(31,119,180)"),
                            secondary_y=False
                        )
                        fig.add_trace(
                            go.Bar(x=df_city.index, y=df_city["Poids total"], name="Poids total (kg)", marker_color="rgb(255,127,14)"),
                            secondary_y=True
                        )
                        fig.add_trace(
                            go.Scatter(x=df_city.index, y=df_city["Volume total"], name="Volume total (m³)", mode="lines+markers", marker=dict(color="green")),
                            secondary_y=True
                        )

                        fig.update_yaxes(title_text="Nombre de livraisons", secondary_y=False)
                        fig.update_yaxes(title_text="Poids (kg) / Volume (m³)", secondary_y=True)
                        fig.update_layout(
                            title_text="Nombre de livraisons, Poids et Volume par ville",
                            xaxis_tickangle=-45,
                            barmode="group",
                            height=600,
                            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                        )

                        st.plotly_chart(fig, use_container_width=True)
                        st.markdown("### Données agrégées (aperçu)")
                        st.dataframe(df_city.reset_index().rename(columns={city_col: "Ville"}))

        except Exception as e:
            st.error(f"Erreur : {str(e)}")
    else:
        st.warning("Veuillez uploader tous les fichiers nécessaires.")