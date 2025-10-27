import streamlit as st
import pandas as pd

st.title("Optimisation des voyages par estafette")

# Upload des fichiers
uploaded_livraisons = st.file_uploader("Fichier des livraisons", type=["xlsx"])
uploaded_clients = st.file_uploader("Fichier des clients", type=["xlsx"])
uploaded_volumes = st.file_uploader("Fichier des volumes", type=["xlsx"])

if uploaded_livraisons and uploaded_clients and uploaded_volumes:
    # Lecture des fichiers
    df_livraisons = pd.read_excel(uploaded_livraisons)
    df_clients = pd.read_excel(uploaded_clients)
    df_volumes = pd.read_excel(uploaded_volumes)

    st.success("✅ Tous les fichiers ont été uploadés.")

    # Fusion Livraisons ↔ Clients
    df_merge = df_livraisons.merge(
        df_clients,
        left_on="Client commande",
        right_on="Client",
        how="left"
    )

    # Fusion Résultat ↔ Volumes
    df_merge = df_merge.merge(
        df_volumes,
        on="Article",
        how="left"
    )

    # Exemple de traitement : ici tu mets ton calcul pour "Voyages_par_estafette_optimisé_avec_taux_clients_representants"
    df_result = df_merge  # temporaire, remplacer par ton traitement

    # Affichage du résultat final
    st.dataframe(df_result)
