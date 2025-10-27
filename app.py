import streamlit as st
import pandas as pd
from io import BytesIO

st.set_page_config(page_title="Planning Livraison", layout="wide")
st.title("Application de Planning des Livraisons")

# ---- Upload des fichiers ----
st.header("📂 Upload des fichiers")
livraisons_file = st.file_uploader("Fichier des livraisons", type=["xlsx"])
clients_file = st.file_uploader("Fichier des clients", type=["xlsx"])
volumes_file = st.file_uploader("Fichier des volumes", type=["xlsx"])

if livraisons_file and clients_file and volumes_file:
    try:
        # ---- Lecture des fichiers Excel ----
        df_livraisons = pd.read_excel(livraisons_file)
        df_clients = pd.read_excel(clients_file)
        df_volumes = pd.read_excel(volumes_file)

        st.success("✅ Tous les fichiers ont été uploadés.")

        # ---- Prétraitements éventuels ----
        df_clients.rename(columns={'Client':'Client'}, inplace=True)
        df_livraisons.rename(columns={'Client commande':'Client'}, inplace=True)
        df_volumes.rename(columns={'Article':'Article'}, inplace=True)

        # ---- Fusion des données ----
        df_merge = df_livraisons.merge(df_clients[['Client','Raison sociale']], on='Client', how='left')
        df_merge = df_merge.merge(df_volumes[['Article','Volume de l\'US']], on='Article', how='left')

        # ---- Calculs backend ----
        df_result = df_merge.groupby(['Client', 'Raison sociale']).agg({
            'No livraison':'count',
            'Volume de l\'US':'sum'
        }).reset_index()
        df_result.rename(columns={'No livraison':'Nb livraisons', 'Volume de l\'US':'Volume total'}, inplace=True)

        # ---- Affichage du fichier final ----
        st.header("📊 Voyages par estafette optimisé avec taux clients/representants")
        st.dataframe(df_result)

        # ---- Téléchargement en Excel ----
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df_result.to_excel(writer, index=False, sheet_name='Voyages')
            writer.save()
        excel_data = output.getvalue()

        st.download_button(
            label="📥 Télécharger le fichier final (Excel)",
            data=excel_data,
            file_name='Voyages_par_estafette_optimisé_avec_taux_clients_representants.xlsx',
            mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )

    except Exception as e:
        st.error(f"❌ Une erreur est survenue : {e}")
else:
    st.info("⏳ Veuillez uploader les trois fichiers pour continuer.")
