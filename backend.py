import pandas as pd
import numpy as np
import math

class DeliveryProcessor:

    def process_delivery_data(self, liv_file, ydlogist_file, wcliegps_file):
        try:
            df_liv = pd.read_excel(liv_file)
            df_liv.rename(columns={df_liv.columns[4]: "Quantité livrée US"}, inplace=True)

            df_liv = self._filter_initial_data(df_liv)
            df_yd = self._process_ydlogist(ydlogist_file)

            df_vol = self._calculate_volumes(df_liv, df_yd)
            df_poids = self._calculate_weights(df_liv)

            df_merged = pd.merge(df_poids, df_vol, on=["No livraison", "Article", "Client commande"], how="left")

            df_final = self._add_city_client_info(df_merged, wcliegps_file)

            df_final = df_final.drop(columns=["Client commande", "Unité Volume"], errors="ignore")
            df_final["Volume de l'US"] = df_final["Volume de l'US"] / 1_000_000

            df_final["Volume total"] = df_final["Volume de l'US"] * df_final["Quantité livrée US"]

            df_final = df_final.drop(columns=["Volume de l'US", "Quantité livrée US"], errors="ignore")

            df_grouped = df_final.groupby(
                ["No livraison", "Client", "Ville"], as_index=False
            ).agg({
                "Article": lambda x: ", ".join(x.astype(str)),
                "Poids total": "sum",
                "Volume total": "sum"
            })

            # Ajout du calcul besoin estafettes
            df_estafettes = self._calculate_estafette_per_city(df_grouped)

            return df_grouped, df_estafettes

        except Exception as e:
            raise Exception(f"Erreur traitement : {str(e)}")

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
        return df.rename(columns={
            df.columns[2]: "Catégorie",
            df.columns[5]: "Acheté",
            df.columns[6]: "Fabriqué",
            df.columns[8]: "Unité Stock",
            df.columns[9]: "Date création",
            df.columns[13]: "Unité Poids",
            df.columns[16]: "Unité Volume",
            df.columns[17]: "Volume de l'US",
        })

    def _calculate_volumes(self, df_liv, df_art):
        df_liv_sel = df_liv[["No livraison", "Article", "Quantité livrée US", "Client commande"]]
        df_art_sel = df_art[["Article", "Volume de l'US", "Unité Volume"]]
        df_art_sel["Volume de l'US"] = pd.to_numeric(df_art_sel["Volume de l'US"].astype(str).str.replace(",", "."), errors="coerce")
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
            df, df_clients[["Client", "Ville"]],
            left_on="Client commande", right_on="Client", how="left"
        )
        df = df[~df["Ville"].isin(["TRIPOLI"])]
        df = df[df["Client commande"] != "PERSOGSO"]
        return df

    def _calculate_estafette_per_city(self, df):
        poids_cap = 1550
        vol_cap = 1.2 * 1.2 * 0.8 * 4

        df_city = df.groupby("Ville", as_index=False).agg({
            "Poids total": "sum",
            "Volume total": "sum",
            "No livraison": "count"
        })
        df_city.rename(columns={"No livraison": "Nb livraisons"}, inplace=True)

        df_city["Estafettes Poids"] = df_city["Poids total"].apply(lambda x: math.ceil(x / poids_cap))
        df_city["Estafettes Volume"] = df_city["Volume total"].apply(lambda x: math.ceil(x / vol_cap))

        df_city["Estafettes Réelles"] = df_city[["Estafettes Poids", "Estafettes Volume"]].max(axis=1)

        return df_city

    def export_excel(self, df1, df2, file_path):
        with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
            df1.to_excel(writer, sheet_name="Livraisons", index=False)
            df2.to_excel(writer, sheet_name="Estafettes", index=False)
        return True
