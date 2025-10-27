import streamlit as st
import matplotlib.pyplot as plt
from backend import DeliveryProcessor

st.set_page_config(page_title="Planning Livraisons", layout="wide")
st.title("📦 Planning Livraisons & Logistique")

# --- Upload fichiers ---
liv_file = st.file_uploader("📄 Fichier Livraisons", type=["xlsx"])
ydlogist_file = st.file_uploader("📄 Fichier YDLOGIST", type=["xlsx"])
wcliegps_file = st.file_uploader("📄 Fichier WCLIEGPS", type=["xlsx"])

if st.button("🚀 Lancer le traitement"):
    if liv_file and ydlogist_file and wcliegps_file:
        try:
            processor = DeliveryProcessor()
            df_liv, df_est = processor.process_delivery_data(liv_file, ydlogist_file, wcliegps_file)

            st.success("✅ Traitement terminé avec succès !")

            # --- Affichage des livraisons ---
            st.subheader("📌 Résultats des livraisons")
            st.dataframe(df_liv)

            # --- Affichage des besoins en estafettes ---
            st.subheader("🚚 Besoin en estafettes par ville")
            st.dataframe(df_est)

            # --- Graphique combiné ---
            st.subheader("📊 Analyse logistique par ville")
            plt.figure(figsize=(12, 6))
            plt.plot(df_est["Ville"], df_est["Poids total"], marker="o", label="Poids total (kg)")
            plt.plot(df_est["Ville"], df_est["Volume total"], marker="o", label="Volume total (m³)")
            plt.bar(df_est["Ville"], df_est["Nb livraisons"], alpha=0.4, label="Nb livraisons")
            plt.xticks(rotation=45)
            plt.ylabel("Valeurs")
            plt.legend()
            plt.tight_layout()
            st.pyplot(plt)

            # --- Téléchargement Excel ---
            output_file = "Résultat_Livraisons_Estafettes.xlsx"
            processor.export_excel(df_liv, df_est, output_file)
            with open(output_file, "rb") as f:
                st.download_button(
                    label="📥 Télécharger les résultats",
                    data=f,
                    file_name=output_file,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

        except Exception as e:
            st.error(f"❌ Erreur : {str(e)}")
    else:
        st.warning("⚠️ Veuillez importer tous les fichiers !")
