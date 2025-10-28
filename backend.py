import pandas as pd
import numpy as np
import math

class DeliveryProcessor:

    def process_delivery_data(self, liv_file, ydlogist_file, wcliegps_file):
        try:
            df_liv = pd.read_excel(liv_file)

            # Correction colonne quantité US
            df_liv.rename(columns={df_liv.columns[4]: "Quantité livrée US"}, inplace=True)

            df_liv = self._filter_initial_data(df_liv)
            df_yd = self._process_ydlogist(ydlogist_file)

            df_vol = self._calculate_volumes(df_liv, df_yd)
            df_poids = self._calculate_weights(df_liv)

            df_merged = pd.merge(
                df_poids, df_vol,
                on=["No livraison", "Article", "Client commande"],
                how="left"
            )

            df_final = self._add_city_client_info(df_merged, wcliegps_file)

            # Conversion volume en m3
            df_final["Volume de l'US"] = df_final["Volume de l'US"] / 1_000_000
            df_final["Volume total"] = df_final["Volume de l'US"] * df_final["Quantité livrée US"]

            # Résultat par livraison + ville
            df_grouped = df_final.groupby(
                ["No livraison", "Client", "Ville"], as_index=False
            ).agg({
                "Article": lambda x: ", ".join(x.astype(str)),
                "Poids total": "sum",
                "Volume total": "sum"
            })

            # Regroupement par ville
            df_city = df_grouped.groupby("Ville", as_index=False).agg({
                "Poids total": "sum",
                "Volume total": "sum",
                "No livraison": "count"
            }).rename(columns={"No livraison": "Nombre livraisons"})

            return df_grouped, df_city

        except Exception as e:
            raise Exception(f"Erreur lors du traitement des données: {str(e)}")


    def _filter_initial_data(self, df):
        clients_a_supprimer = [
            "AMECAP", "SANA", "SOPAL", "SOPALGAZ", "SOPALSERV", "SOPALTEC",
            "SOPALALG", "AQUA", "WINOX", "QUIVEM", "SANISTONE", "SOPAMAR",
            "SOPALAFR", "SOPALINTER"
        ]
        return df[(df["Type livraison"] != "SDC") & (~df["Client commande"].isin(clients_a_supprimer))]


    def _process_ydlogist(self, file_path):
        df = pd.read_excel(file_path)
        df.rename(columns={
            df.columns[16]: "Unité Volume",
            df.columns[13]: "Poids de l'US"
        }, inplace=True)
        return df


    def _calculate_volumes(self, df_liv, df_art):
        df_liv_sel = df_liv[["No livraison", "Article", "Quantité livrée US", "Client commande"]]
        df_art_sel = df_art[["Article", "Volume de l'US"]].copy()
        df_art_sel["Volume de l'US"] = pd.to_numeric(
            df_art_sel["Volume de l'US"], errors="coerce"
        )
        return pd.merge(df_liv_sel, df_art_sel, on="Article", how="left")


    def _calculate_weights(self, df):
        df["Quantité livrée US"] = pd.to_numeric(df["Quantité livrée US"], errors="coerce").fillna(0)
        df["Poids total"] = df["Quantité livrée US"] * pd.to_numeric(
            df[df.columns[13]], errors="coerce"
        ).fillna(0)
        return df[["No livraison", "Article", "Poids total", "Client commande"]]


    def _add_city_client_info(self, df, wcliegps_file):
        df_clients = pd.read_excel(wcliegps_file)
        df = pd.merge(
            df, df_clients[["Client", "Ville"]],
            left_on="Client commande",
            right_on="Client",
            how="left"
        )
        return df


    def export_results(self, df_grouped, df_city, path_grouped, path_city):
        df_grouped.to_excel(path_grouped, index=False)
        df_city.to_excel(path_city, index=False)
        return True
