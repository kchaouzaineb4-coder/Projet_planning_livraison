import streamlit as st
import pandas as pd
import numpy as np
import os

# -------------------------------
# Configuration de la page
# -------------------------------
st.set_page_config(
    page_title="Planification des Livraisons",
    page_icon="🚚",
    layout="wide"
)

# -------------------------------
# Constantes
# -------------------------------
MAX_POIDS = 1550.0  # kg
MAX_VOLUME = 4.608  # m3
SEUIL_CAMION_POIDS = 3000.0  # kg
SEUIL_CAMION_VOLUME = 9.216  # m3

VEHICULES_DISPONIBLES = [
    'SLG-VEH11', 'SLG-VEH14', 'SLG-VEH22', 'SLG-VEH19',
    'SLG-VEH10', 'SLG-VEH16', 'SLG-VEH23', 'SLG-VEH08', 'SLG-VEH20'
]

CHAUFFEURS_DETAILS = {
    '09254': 'DAMMAK Karim',
    '06002': 'MAAZOUN Bassem',
    '11063': 'SASSI Ramzi',
    '10334': 'BOUJELBENE Mohamed',
    '15144': 'GADDOUR Rami',
    '08278': 'DAMMAK Wissem',
    '18339': 'REKIK Ahmed',
    '07250': 'BARKIA Mustapha',
    '13321': 'BADRI Moez'
}

# -------------------------------
# Initialisation des données
# -------------------------------
def load_data():
    if 'df_livraisons' not in st.session_state:
        st.session_state.df_livraisons = pd.DataFrame()
    if 'df_clients' not in st.session_state:
        st.session_state.df_clients = pd.DataFrame()
    if 'df_volumes' not in st.session_state:
        st.session_state.df_volumes = pd.DataFrame()

# -------------------------------
# Fonction pour lire Excel (.xls uniquement)
# -------------------------------
def read_excel_xls(file):
    ext = os.path.splitext(file.name)[1].lower()
    if ext != ".xls":
        raise ValueError(f"Format non supporté : {ext}. Seuls les fichiers .xls sont acceptés.")
    try:
        return pd.read_excel(file, engine='xlrd')
    except Exception as e:
        raise ValueError(f"Erreur lors de la lecture du fichier Excel : {e}")

# -------------------------------
# Traitement des fichiers
# -------------------------------
def process_files(liv_file, client_file, volume_file):
    df_liv = read_excel_xls(liv_file)
    df_liv = df_liv[df_liv["Type livraison"] != "SDC"]

    clients_a_supprimer = [
        "AMECAP", "SANA", "SOPAL", "SOPALGAZ",
        "SOPALALG", "AQUA", "WINOX", "QUIVEM", "SANISTONE"
    ]
    df_liv = df_liv[~df_liv["Client commande"].isin(clients_a_supprimer)]

    df_vol = read_excel_xls(volume_file)
    df_client = read_excel_xls(client_file)

    return df_liv, df_client, df_vol

# -------------------------------
# Interface principale
# -------------------------------
def main():
    load_data()
    st.title("🚚 Planification des Livraisons")

    st.header("1. Chargement des fichiers (.xls uniquement)")
    col1, col2, col3 = st.columns(3)

    with col1:
        liv_file = st.file_uploader("Fichier des livraisons", type=['xls'])
    with col2:
        client_file = st.file_uploader("Fichier des clients", type=['xls'])
    with col3:
        volume_file = st.file_uploader("Fichier des volumes", type=['xls'])

    if liv_file and client_file and volume_file:
        try:
            df_liv, df_client, df_vol = process_files(liv_file, client_file, volume_file)
            st.session_state.df_livraisons = df_liv
            st.session_state.df_clients = df_client
            st.session_state.df_volumes = df_vol
            st.success("Fichiers chargés avec succès!")

            # ---------------------------
            # 2. Affichage des données
            # ---------------------------
            st.header("2. Données traitées")
            tab1, tab2, tab3 = st.tabs(["Livraisons", "Clients", "Volumes"])
            with tab1:
                st.dataframe(df_liv)
            with tab2:
                st.dataframe(df_client)
            with tab3:
                st.dataframe(df_vol)

            # ---------------------------
            # 3. Statistiques
            # ---------------------------
            st.header("3. Statistiques")
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Nombre total de livraisons", len(df_liv))
                st.metric("Poids total", f"{df_liv['Poids de l\'US'].sum():.2f} kg")
            with col2:
                st.metric("Nombre de clients", len(df_liv['Client commande'].unique()))
                st.metric("Volume total", f"{df_vol['Volume de l\'US'].sum():.2f} m³")

            # ---------------------------
            # 4. Planning des livraisons
            # ---------------------------
            st.header("4. Planning des livraisons")
            zones = sorted(df_liv['Zone'].unique().tolist())
            selected_zone = st.selectbox("Sélectionner une zone", zones)
            if selected_zone:
                df_zone = df_liv[df_liv['Zone'] == selected_zone]
                st.subheader(f"Livraisons pour la zone {selected_zone}")
                st.dataframe(df_zone)

            # ---------------------------
            # Attribution des véhicules
            # ---------------------------
            st.subheader("Attribution des véhicules")
            col1, col2 = st.columns(2)
            with col1:
                selected_vehicle = st.selectbox("Sélectionner un véhicule", VEHICULES_DISPONIBLES)
            with col2:
                selected_driver = st.selectbox(
                    "Sélectionner un chauffeur",
                    [f"{mat} - {name}" for mat, name in CHAUFFEURS_DETAILS.items()]
                )
            if st.button("Attribuer"):
                st.success(f"Véhicule {selected_vehicle} attribué à {selected_driver} avec succès!")

        except Exception as e:
            st.error(f"Erreur lors du traitement des fichiers : {e}")

# -------------------------------
# Lancement de l'application
# -------------------------------
if __name__ == "__main__":
    main()
