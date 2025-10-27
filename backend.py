import pandas as pd
import numpy as np

class DeliveryProcessor:
    def process_delivery_data(self, liv_file, ydlogist_file, wcliegps_file):
        try:
            # Charger le fichier Livraisons et renommer la colonne critique
            df_liv = pd.read_excel(liv_file)
            df_liv.rename(columns={df_liv.columns[4]: "Quantité livrée US"}, inplace=True)

            # Filtrage initial
            df_liv = self._filter_initial_data(df_liv)

            # Traitement YDLOGIST
            df_yd = self._process_ydlogist(ydlogist_file)

            # Calcul volumes et poids
            df_vol = self._calculate_volumes(df_liv, df_yd)
            df_poids = self._calculate_weights(df_liv)

            # Fusion volume/poids
            df_merged = pd.merge(df_poids, df_vol, on=["No livraison", "Article", "Client commande"], how="left")

            # Ajouter info client/ville
            df_final = self._add_city_client_info(df_merged, wcliegps_file)

            # Supprimer colonnes inutiles et convertir volume en m³
            df_final = df_final.drop(columns=["Client commande", "Unité Volume"], errors='ignore')
            df_final["Volume de l'US"] = df_final["Volume de l'US"] / 1_000_000  # cm3 -> m3

            # Calcul Volume total = Volume de l'US * Quantité livrée US
            df_final["Volume total"] = df_final["Volume de l'US"] * df_final["Quantité livrée US"]

            # Supprimer colonnes individuelles
            df_final = df_final.drop(columns=["Volume de l'US", "Quantité livrée US"], errors='ignore')

            # Regrouper par No livraison
            df_grouped = df_final.groupby(
                ["No livraison", "Client", "Ville"], as_index=False
            ).agg({
                "Article": lambda x: ", ".join(x.astype(str)),
                "Poids total": "sum",
                "Volume total": "sum"
            })

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
            df.columns[16]: "Unité Volume"
        }
        return df.rename(columns=renommage)

    def _calculate_volumes(self, df_liv, df_art):
        df_liv_sel = df_liv[["No livraison", "Article", "Quantité livrée US", "Client commande"]]
        df_art_sel = df_art[["Article", "Volume de l'US", "Unité Volume"]]
        df_art_sel["Volume de l'US"] = pd.to_numeric(
            df_art_sel["Volume de l'US"].astype(str).str.replace(",", "."),
            errors="coerce"
        )
        return pd.merge(df_liv_sel, df_art_sel, on="Article", how="left")

    def _calculate_weights(self, df):
        df["Poids de l'US"] = pd.to_numeric(
            df["Poids de l'US"].astype(str).str.replace(",", ".").str.replace(r"[^\d.]", "", regex=True),
            errors="coerce"
        ).fillna(0)
        df["Quantité livrée US"] = pd.to_numeric(df["Quantité livrée US"], errors="coerce").fillna(0)
        df["Poids total"] = df["Quantité livrée US"] * df["Poids de l'US"]
        return df[["No livraison", "Article", "Poids total", "Client commande"]]

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
        return df

    def export_results(self, df, output_path):
        df.to_excel(output_path, index=False)
        return True
