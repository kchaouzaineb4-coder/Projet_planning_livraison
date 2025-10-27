import streamlit as st
import pandas as pd
import numpy as np
import math
import re

st.title("Optimisation des voyages par estafette")

st.markdown("""
**Instructions :**  
1. Uploadez vos 3 fichiers :  
   - Fichier des livraisons (`F1758623552711_LIV.xlsx`)  
   - Fichier des clients (`F1758721675866_WCLIEGPS.xlsx`)  
   - Fichier des volumes (`F1758008320774_YDLOGIST.xlsx`)  
2. Cliquez sur *Lancer le traitement* pour générer le fichier final.
""")

# ====== Upload des fichiers ======
livraisons_file = st.file_uploader("Fichier des livraisons", type=["xlsx"])
clients_file = st.file_uploader("Fichier des clients", type=["xlsx"])
volumes_file = st.file_uploader("Fichier des volumes", type=["xlsx"])

# ====== Lancer le traitement ======
if st.button("Lancer le traitement"):

    if not livraisons_file or not clients_file or not volumes_file:
        st.error("Merci d'uploader les 3 fichiers.")
    else:
        st.info("Traitement en cours... ⏳")

        # ====== Lire les fichiers ======
        df_livraison = pd.read_excel(livraisons_file)
        df_clients = pd.read_excel(clients_file)
        df_volume = pd.read_excel(volumes_file)

        # ====== Nettoyage des colonnes numériques ======
        for col in ["Quantité livrée US", "Poids de l'US"]:
            if col in df_livraison.columns:
                df_livraison[col] = (
                    df_livraison[col].astype(str).str.replace(",", ".")
                ).astype(float).fillna(0)
        for col in ["Quantité livrée US", "Volume de l'US"]:
            if col in df_volume.columns:
                df_volume[col] = (
                    df_volume[col].astype(str).str.replace(",", ".")
                ).astype(float).fillna(0)

        # ====== Calcul poids total par BL ======
        df_livraison["Poids calculé"] = df_livraison["Quantité livrée US"] * df_livraison["Poids de l'US"]
        df_poids = df_livraison.groupby(["No livraison", "Client commande"], as_index=False).agg({"Poids calculé":"sum"})
        df_articles = df_livraison.groupby("No livraison")["Article"].apply(lambda x: ", ".join(x.unique())).reset_index()
        df_poids = pd.merge(df_poids, df_articles, on="No livraison")
        df_poids.rename(columns={"Poids calculé":"Poids total"}, inplace=True)

        # ====== Calcul volume total par BL ======
        df_volume["Volume calculé"] = df_volume["Quantité livrée US"] * df_volume["Volume de l'US"]
        df_volume_total = df_volume.groupby("No livraison", as_index=False).agg({"Volume calculé":"sum"})
        df_volume_total["Volume calculé"] = df_volume_total["Volume calculé"] / 1_000_000  # cm3 -> m3
        df_articles_vol = df_volume.groupby("No livraison")["Article"].apply(lambda x: ", ".join(x.unique())).reset_index()
        df_volume_total = pd.merge(df_volume_total, df_articles_vol, on="No livraison")
        df_volume_total.rename(columns={"Volume calculé":"Volume total (m³)"}, inplace=True)

        # ====== Fusion poids + volume ======
        df_merge = pd.merge(df_poids, df_volume_total, on="No livraison", how="outer")
        # Fusion articles
        def fusion_articles(row):
            articles = [str(row["Article_x"]), str(row["Article_y"])]
            articles = [a for a in articles if a != "nan" and a.strip() != ""]
            return ", ".join(sorted(set(articles)))
        df_merge["Article"] = df_merge.apply(fusion_articles, axis=1)
        df_merge = df_merge.drop(columns=["Article_x","Article_y"])
        df_merge = df_merge[["No livraison","Article","Client commande","Poids total","Volume total (m³)"]]

        # ====== Optimisation voyages par estafette ======
        MAX_POIDS = 1550
        MAX_VOLUME = 4.608

        # Ajouter une colonne région par ville (exemple simplifié)
        zones = {
            "Zone 1":["TUNIS","ARIANA","MANOUBA","BEN AROUS","BIZERTE","MATEUR","MENZEL BOURGUIBA","UTIQUE"],
            "Zone 2":["NABEUL","HAMMAMET","KORBA","MENZEL TEMIME","KELIBIA","SOLIMAN"],
            "Zone 3":["SOUSSE","MONASTIR","MAHDIA","KAIROUAN"],
            "Zone 4":["GABÈS","MEDENINE","ZARZIS","DJERBA"],
            "Zone 5":["GAFSA","KASSERINE","TOZEUR","NEFTA","DOUZ"],
            "Zone 6":["JENDOUBA","BEJA","LE KEF","TABARKA","SILIANA"],
            "Zone 7":["SFAX"]
        }
        def trouver_zone(ville):
            ville_upper = str(ville).strip().upper()
            for zone, villes in zones.items():
                if ville_upper in [v.upper() for v in villes]:
                    return zone
            return "Zone inconnue"
        if "Ville" in df_livraison.columns:
            df_merge["région"] = df_livraison["Ville"].apply(trouver_zone)
        else:
            df_merge["région"] = "Zone inconnue"

        # Boucle pour créer les estafettes
        resultats = []
        estafette_num = 1
        for zone, group in df_merge.groupby("région"):
            group_sorted = group.sort_values(by="Poids total", ascending=False)
            estafettes = []
            for idx, row in group_sorted.iterrows():
                bl = row["No livraison"]
                poids = row["Poids total"]
                volume = row["Volume total (m³)"]
                placed = False
                for e in estafettes:
                    if e["poids"]+poids<=MAX_POIDS and e["volume"]+volume<=MAX_VOLUME:
                        e["poids"] += poids
                        e["volume"] += volume
                        e["bls"].append(bl)
                        placed = True
                        break
                if not placed:
                    estafettes.append({"poids":poids,"volume":volume,"bls":[bl]})
            for e in estafettes:
                resultats.append([zone, estafette_num, e["poids"], e["volume"], ";".join(e["bls"])])
                estafette_num += 1

        df_estafettes = pd.DataFrame(resultats, columns=["Zone","Estafette N°","Poids total","Volume total","BL inclus"])

        # ====== Calcul taux d'occupation ======
        df_estafettes["taux d'occupation (%)"] = df_estafettes.apply(
            lambda row: max(row['Poids total']/MAX_POIDS, row['Volume total']/MAX_VOLUME)*100, axis=1
        ).round(2)

        # ====== Ajout clients ======
        mapping_client = dict(zip(df_livraison["No livraison"], df_livraison["Client commande"]))
        def extraire_clients(bls):
            bl_list = [b.strip() for b in str(bls).split(";")]
            clients = [mapping_client.get(b,"??") for b in bl_list]
            return "; ".join(clients)
        df_estafettes["Client commande"] = df_estafettes["BL inclus"].apply(extraire_clients)

        # ====== Ajout représentant ======
        mapping_rep = dict(zip(df_clients["Client"], df_clients.iloc[:,16]))
        def extraire_reps(clients_str):
            clients = [c.strip() for c in str(clients_str).split(";")]
            reps = [mapping_rep.get(c,"Client inconnu") for c in clients]
            return "; ".join(list(dict.fromkeys(reps)))
        df_estafettes["Représentant"] = df_estafettes["Client commande"].apply(extraire_reps)

        # ====== Affichage du résultat final ======
        st.success("✅ Traitement terminé ! Voici un aperçu du fichier final :")
        st.dataframe(df_estafettes)

        # Option de téléchargement
        st.download_button(
            label="Télécharger le fichier final",
            data=df_estafettes.to_excel(index=False, engine='openpyxl'),
            file_name="Voyages_par_estafette_final.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
