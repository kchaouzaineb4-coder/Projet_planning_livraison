import streamlit as st
import pandas as pd
import numpy as np
import os

st.set_page_config(page_title="Planification des Livraisons", page_icon="🚚", layout="wide")

MAX_POIDS = 1550.0  
MAX_VOLUME = 4.608  

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

def read_excel_auto(file):
    ext = os.path.splitext(file.name)[1].lower()
    try:
        if ext == ".xlsx":
            df = pd.read_excel(file, engine="openpyxl")
        elif ext == ".xls":
            from pyexcel_xls import get_data
            data = get_data(file)
            sheet = list(data.keys())[0]
            df = pd.DataFrame(data[sheet])
            df.columns = df.iloc[0]
            df = df[1:].reset_index(drop=True)
        else:
            raise ValueError(f"Format non supporté : {ext}")

        df = df.loc[:, ~df.columns.duplicated()].copy()

        return df
    except Exception as e:
        raise ValueError(f"Impossible de lire le fichier : {e}")

def process_files(liv_file, client_file, volume_file):
    df_liv = read_excel_auto(liv_file)
    df_liv = df_liv[df_liv["Type livraison"] != "SDC"]

    clients_exclus = ["AMECAP", "SANA", "SOPAL", "SOPALGAZ", "SOPALALG", 
                      "AQUA", "WINOX", "QUIVEM", "SANISTONE"]
    df_liv = df_liv[~df_liv["Client commande"].isin(clients_exclus)]

    df_vol = read_excel_auto(volume_file)
    df_client = read_excel_auto(client_file)

    return df_liv, df_client, df_vol


def main():
    st.title("🚚 Planification des Livraisons")

    st.header("1️⃣ Téléverser les fichiers (.xls ou .xlsx)")
    col1, col2, col3 = st.columns(3)

    with col1:
        liv_file = st.file_uploader("📦 Fichier des livraisons", type=["xls", "xlsx"])
    with col2:
        client_file = st.file_uploader("👥 Fichier des clients", type=["xls", "xlsx"])
    with col3:
        volume_file = st.file_uploader("📏 Fichier des volumes", type=["xls", "xlsx"])

    if liv_file and client_file and volume_file:
        try:
            df_liv, df_client, df_vol = process_files(liv_file, client_file, volume_file)

            st.success("✅ Fichiers importés avec succès")

            st.header("📊 2️⃣ Aperçu des données")
            tab1, tab2, tab3 = st.tabs(["Livraisons", "Clients", "Volumes"])

            with tab1:
                st.dataframe(df_liv)
            with tab2:
                st.dataframe(df_client)
            with tab3:
                st.dataframe(df_vol)

            st.header("📈 3️⃣ Statistiques")
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Livraisons", len(df_liv))
                st.metric("Poids total (kg)", f"{df_liv['Poids de l\'US'].astype(float).sum():.2f}")
            with col2:
                st.metric("Clients uniques", df_liv["Client commande"].nunique())
                st.metric("Volume total (m³)", f"{df_vol['Volume de l\'US'].astype(float).sum():.2f}")

            st.header("🚦 4️⃣ Planning par zone")
            zones = sorted(df_liv['Zone'].dropna().unique().tolist())
            selected_zone = st.selectbox("Sélectionner une zone :", zones)

            if selected_zone:
                st.dataframe(df_liv[df_liv['Zone'] == selected_zone])

            st.subheader("🚚 Attribution des véhicules")
            col1, col2 = st.columns(2)
            veh = col1.selectbox("Véhicule", VEHICULES_DISPONIBLES)
            chauffeur = col2.selectbox("Chauffeur", 
                                       [f"{mat} - {n}" for mat, n in CHAUFFEURS_DETAILS.items()])

            if st.button("✅ Attribuer"):
                st.success(f"✔ {veh} attribué à {chauffeur}")

        except Exception as e:
            st.error(f"⚠️ Erreur : {e}")

if __name__ == "__main__":
    main()
