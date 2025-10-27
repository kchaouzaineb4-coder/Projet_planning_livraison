import streamlit as st
import pandas as pd

st.set_page_config(page_title="Planning Livraisons", layout="wide")

st.title("Optimisation Planning de Livraisons")

# ---------------------- Upload des fichiers ----------------------
st.header("1️⃣ Upload des fichiers Excel")

livraisons_file = st.file_uploader("Fichier des livraisons (F1758623552711_LIV.xlsx)", type="xlsx")
clients_file = st.file_uploader("Fichier des clients (F1758721675866_WCLIEGPS.xlsx)", type="xlsx")
volumes_file = st.file_uploader("Fichier des volumes (F1758008320774_YDLOGIST.xlsx)", type="xlsx")

# ---------------------- Vérifier si tous les fichiers sont uploadés ----------------------
if livraisons_file and clients_file and volumes_file:
    st.success("✅ Tous les fichiers ont été uploadés.")

    # ---------------------- Lecture des fichiers ----------------------
    df_livraisons = pd.read_excel(livraisons_file)
    df_clients = pd.read_excel(clients_file)
    df_volumes = pd.read_excel(volumes_file)

    # ---------------------- Exemple de nettoyage et conversion ----------------------
    # Ici, tu définis les colonnes numériques selon tes fichiers
    colonnes_num_livraisons = ['Qté', 'Poids', 'Volume']  # À adapter
    for col in colonnes_num_livraisons:
        if col in df_livraisons.columns:
            df_livraisons[col] = pd.to_numeric(df_livraisons[col], errors='coerce').fillna(0)

    colonnes_num_volumes = ['Volume']  # À adapter
    for col in colonnes_num_volumes:
        if col in df_volumes.columns:
            df_volumes[col] = pd.to_numeric(df_volumes[col], errors='coerce').fillna(0)

    # ---------------------- Traitement backend ----------------------
    # Exemple : fusion des fichiers (à adapter selon ton traitement réel)
    df_merge = df_livraisons.merge(df_clients, on='Client', how='left')
    df_merge = df_merge.merge(df_volumes, on='Produit', how='left')

    # Exemple : calcul fictif du voyage optimisé (à remplacer par ton vrai code)
    df_merge['Qté_optimisée'] = df_merge['Qté']  # Ici tu mets tes calculs

    # ---------------------- Affichage du résultat ----------------------
    st.header("2️⃣ Résultat : Voyages par estafette optimisé")
    st.dataframe(df_merge)  # Affiche le DataFrame complet

    # Option pour télécharger le résultat
    st.download_button(
        label="📥 Télécharger le résultat",
        data=df_merge.to_excel(index=False, engine='openpyxl'),
        file_name="Voyages_par_estafette_optimisé.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

else:
    st.info("📌 Merci d'uploader les 3 fichiers pour commencer le traitement.")
