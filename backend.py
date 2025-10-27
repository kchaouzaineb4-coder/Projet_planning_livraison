import pandas as pd
import numpy as np

class DeliveryProcessor:
    def __init__(self):
        self.MAX_POIDS = 1550.0  # kg
        self.MAX_VOLUME = 4.608  # m3

    def process_delivery_data(self, liv_file, ydlogist_file, wcliegps_file):
        try:
            # Charger et renommer les colonnes critiques
            df_liv = pd.read_excel(liv_file)
            df_liv.rename(columns={df_liv.columns[4]: "Quantité livrée US"}, inplace=True)

            # Filtrage initial
            df_liv = self._filter_initial_data(df_liv)

            # Traitement YDLOGIST
            df_yd = self._process_ydlogist(ydlogist_file)

            # Fusion Livraisons + YDLOGIST pour volume et poids
            df_vol = self._calculate_volumes(df_liv, df_yd)
            df_vol["Poids de l'US"] = pd.to_numeric(
                df_vol["Poids de l'US"].astype(str).str.replace(",", ".").str.replace(r"[^\d.]", "", regex=True),
                errors="coerce"
            ).fillna(0)
            df_vol["Quantité livrée US"] = pd.to_numeric(df_vol["Quantité livrée US"], errors="coerce").fillna(0)
            df_vol["Poids total"] = df_vol["Quantité livrée US"] * df_vol["Poids de l'US"]

            # Supprimer colonnes inutiles et convertir volume en m³
            df_vol = df_vol.drop(columns=["Unité Volume"], errors='ignore')
            df_vol["Volume de l'US"] = pd.to_numeric(df_vol["Volume de l'US"], errors="coerce").fillna(0)
            df_vol["Volume de l'US"] = df_vol["Volume de l'US"] / 1_000_000  # cm3 -> m3
            df_vol["Volume total"] = df_vol["Volume de l'US"] * df_vol["Quantité livrée US"]

            # Ajouter info client/ville
            df_final = self._add_city_client_info(df_vol, wcliegps_file)

            # Supprimer les colonnes individuelles
            df_final = df_final.drop(columns=["Quantité livrée US", "Volume de l'US"], errors='ignore')

            # Regrouper par No livraison pour combiner les articles
            df_grouped = df_final.groupby(["No livraison", "Client", "Ville"]).agg({
                "Article": lambda x: ", ".join(x.astype(str)),
                "Poids total": "sum",
                "Volume total": "sum"
            }).reset_index()

            return df_grouped

        except Exception as e:
            raise Exception(f"Erreur lors du traitement des données: {str(e)}")

    def _filter_initial_data(self, df):
        df = df[df["Type livraison"] != "SDC"]
        clients_a_supprimer = [
            "AMECAP", "SANA", "SOPAL", "SOPALGAZ", "SOPALSERV", "SOPALTEC",
            "SOPALALG", "AQUA", "WINOX", "QUIVEM", "SANISTONE", "SOPAMAR",
            "SOPALAFR", "SOPALINTER"
        ]
        return df[~df["Client commande"].isin(clients_a_supprimer)]

    def _process_ydlogist(self, file_path):
        df = pd.read_excel(file_path)
        renommage = {
            df.columns[2]: "Catégorie",
            df.columns[5]: "Acheté",
            df.columns[6]: "Fabriqué",
            df.columns[8]: "Unité Stock",
            df.columns[9]: "Date création",
            df.columns[13]: "Unité Poids",
            df.columns[16]: "Unité Volume",
            df.columns[11] if len(df.columns) > 11 else 'Poids de l\'US': "Poids de l'US",
            df.columns[12] if len(df.columns) > 12 else 'Volume de l\'US': "Volume de l'US"
        }
        return df.rename(columns=renommage)

    def _calculate_volumes(self, df_liv, df_art):
        df_liv_sel = df_liv[["No livraison", "Article", "Quantité livrée US", "Client commande"]]
        df_art_sel = df_art[["Article", "Volume de l'US", "Poids de l'US"]]
        df_art_sel["Volume de l'US"] = pd.to_numeric(
            df_art_sel["Volume de l'US"].astype(str).str.replace(",", "."),
            errors="coerce"
        )
        return pd.merge(df_liv_sel, df_art_sel, on="Article", how="left")

    def _add_city_client_info(self, df, wcliegps_file):
        df_clients = pd.read_excel(wcliegps_file)
        df = pd.merge(
            df,
            df_clients[["Client", "Ville"]],
            left_on="Client commande",
            right_on="Client",
            how="left"
        )
        df = df[~df["Ville"].isin(["TRIPOLI"])]
        df = df[df["Client commande"] != "PERSOGSO"]
        df = df.rename(columns={"Client commande": "Client"})
        return df

    def export_results(self, df, output_path):
        df.to_excel(output_path, index=False)
        return True
