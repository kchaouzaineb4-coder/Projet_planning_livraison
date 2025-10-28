import pandas as pd
import numpy as np
import math


class DeliveryProcessor:

    # =====================================================
    # ✅ Fonction principale : traitement complet
    # =====================================================
    def process_delivery_data(self, liv_file, ydlogist_file, wcliegps_file):
        try:
            # Lecture des fichiers
            df_liv = self._load_livraisons(liv_file)
            df_yd = self._load_ydlogist(ydlogist_file)

            # Filtrage des données
            df_liv = self._filter_initial_data(df_liv)

            # Calcul Poids & Volume
            df_poids = self._calculate_weights(df_liv)
            df_vol = self._calculate_volumes(df_liv, df_yd)

            # Fusionner poids + volume
            df_merged = self._merge_delivery_data(df_poids, df_vol)

            # Ajouter Client et Ville
            df_final = self._add_city_client_info(df_merged, wcliegps_file)

            # Calcul Volume total en m3
            df_final["Volume de l'US"] = df_final["Volume de l'US"] / 1_000_000
            df_final["Volume total"] = df_final["Volume de l'US"] * df_final["Quantité livrée US"]

            # Regroupement par ville et client
            df_grouped, df_city = self._group_data(df_final)

            # Calcul du besoin en estafette
            df_city = self._calculate_estafette_need(df_city)

            # Ajouter la colonne Zone pour le nouveau tableau
            df_grouped_zone = self._assign_zone(df_grouped)

            return df_grouped, df_grouped_zone, df_city

        except Exception as e:
            raise Exception(f"❌ Erreur lors du traitement des données : {str(e)}")


    # =====================================================
    # 🔹 Chargement des données
    # =====================================================
    def _load_livraisons(self, liv_file):
        df = pd.read_excel(liv_file)

        # Normaliser nom colonne quantité
        df.rename(columns={df.columns[4]: "Quantité livrée US"}, inplace=True)
        return df

    def _load_ydlogist(self, file_path):
        df = pd.read_excel(file_path)
        df.rename(columns={
            df.columns[16]: "Volume de l'US",
            df.columns[13]: "Poids de l'US"
        }, inplace=True)
        return df


    # =====================================================
    # 🔹 Pré-traitement : filtrage
    # =====================================================
    def _filter_initial_data(self, df):
        clients_exclus = [
            "AMECAP", "SANA", "SOPAL", "SOPALGAZ", "SOPALSERV", "SOPALTEC",
            "SOPALALG", "AQUA", "WINOX", "QUIVEM", "SANISTONE",
            "SOPAMAR", "SOPALAFR", "SOPALINTER"
        ]
        return df[
            (df["Type livraison"] != "SDC") &
            (~df["Client commande"].isin(clients_exclus))
        ]


    # =====================================================
    # 🔹 Calculs poids / volume
    # =====================================================
    def _calculate_weights(self, df):
        df = df.copy()
        df["Poids de l'US"] = pd.to_numeric(
            df["Poids de l'US"].astype(str)
            .str.replace(",", ".")
            .str.replace(r"[^\d.]", "", regex=True),
            errors="coerce"
        ).fillna(0)

        df["Quantité livrée US"] = pd.to_numeric(df["Quantité livrée US"], errors="coerce").fillna(0)
        df["Poids total"] = df["Quantité livrée US"] * df["Poids de l'US"]
        return df[["No livraison", "Article", "Client commande", "Poids total"]]


    def _calculate_volumes(self, df_liv, df_art):
        df_liv_sel = df_liv[["No livraison", "Article", "Quantité livrée US", "Client commande"]]
        df_art_sel = df_art[["Article", "Volume de l'US", "Unité Volume"]].copy()
        df_art_sel["Volume de l'US"] = pd.to_numeric(
            df_art_sel["Volume de l'US"].astype(str).str.replace(",", "."),
            errors="coerce"
        )
        return pd.merge(df_liv_sel, df_art_sel, on="Article", how="left")


    # =====================================================
    # 🔹 Fusion
    # =====================================================
    def _merge_delivery_data(self, df_poids, df_vol):
        return pd.merge(df_poids, df_vol,
                        on=["No livraison", "Article", "Client commande"],
                        how="left")


    # =====================================================
    # 🔹 Ajout Client & Ville
    # =====================================================
    def _add_city_client_info(self, df, wcliegps_file):
        df_clients = pd.read_excel(wcliegps_file)
        df = pd.merge(
            df,
            df_clients[["Client", "Ville"]],
            left_on="Client commande",
            right_on="Client",
            how="left"
        )
        return df


    # =====================================================
    # 🔹 Groupement par client et par ville
    # =====================================================
    def _group_data(self, df):
        df_grouped = df.groupby(
            ["No livraison", "Client", "Ville"], as_index=False
        ).agg({
            "Article": lambda x: ", ".join(x.astype(str)),
            "Poids total": "sum",
            "Volume total": "sum"
        })

        df_city = df_grouped.groupby(["Ville"], as_index=False).agg({
            "Poids total": "sum",
            "Volume total": "sum",
            "No livraison": "count"
        }).rename(columns={"No livraison": "Nombre livraisons"})

        return df_grouped, df_city


    # =====================================================
    # 🔹 Calcul besoin estafette par ville
    # =====================================================
    def _calculate_estafette_need(self, df_city):
        poids_max = 1550
        volume_max = 1.2 * 1.2 * 0.8 * 4  # volume véhicule
        df_city["Besoin estafette (poids)"] = df_city["Poids total"].apply(lambda p: math.ceil(p / poids_max))
        df_city["Besoin estafette (volume)"] = df_city["Volume total"].apply(lambda v: math.ceil(v / volume_max))
        df_city["Besoin estafette réel"] = df_city[["Besoin estafette (poids)", "Besoin estafette (volume)"]].max(axis=1)
        return df_city


    # =====================================================
    # 🔹 Ajouter la colonne Zone
    # =====================================================
    def _assign_zone(self, df):
        zones = {
            "Zone 1": ["TUNIS","ARIANA","MANOUBA","BEN AROUS","BIZERTE","MATEUR","MENZEL BOURGUIBA","UTIQUE"],
            "Zone 2": ["NABEUL","HAMMAMET","KORBA","MENZEL TEMIME","KELIBIA","SOLIMAN"],
            "Zone 3": ["SOUSSE","MONASTIR","MAHDIA","KAIROUAN"],
            "Zone 4": ["GABÈS","MEDENINE","ZARZIS","DJERBA"],
            "Zone 5": ["GAFSA","KASSERINE","TOZEUR","NEFTA","DOUZ"],
            "Zone 6": ["JENDOUBA","BÉJA","LE KEF","TABARKA","SILIANA"],
            "Zone 7": ["SFAX"]
        }

        def get_zone(ville):
            ville = str(ville).upper().strip()
            for zone, villes in zones.items():
                if ville in villes:
                    return zone
            return "Zone inconnue"

        df["Zone"] = df["Ville"].apply(get_zone)
        return df


    # =====================================================
    # ✅ Export des fichiers Excel
    # =====================================================
    def export_results(self, df_grouped, df_grouped_zone, df_city, path_grouped, path_grouped_zone, path_city):
        df_grouped.to_excel(path_grouped, index=False)
        df_grouped_zone.to_excel(path_grouped_zone, index=False)
        df_city.to_excel(path_city, index=False)
        return True
