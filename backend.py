import pandas as pd
import math

class DeliveryProcessor:

    def process_delivery_data(self, liv_file, ydlogist_file, wcliegps_file):
        try:
            df_liv = self._load_livraisons(liv_file)
            df_yd = self._load_ydlogist(ydlogist_file)
            df_liv = self._filter_initial_data(df_liv)

            df_poids = self._calculate_weights(df_liv, df_yd)
            df_vol = self._calculate_volumes(df_liv, df_yd)

            df_merged = self._merge_delivery_data(df_poids, df_vol)
            df_final = self._add_city_client_info(df_merged, wcliegps_file)

            df_final["Quantité livrée US"] = pd.to_numeric(df_final["Quantité livrée US"], errors="coerce").fillna(0)
            if "Volume de l'US" in df_final.columns:
                df_final["Volume de l'US"] = pd.to_numeric(df_final["Volume de l'US"], errors="coerce").fillna(0)
                df_final["Volume de l'US"] = df_final["Volume de l'US"] / 1_000_000
            else:
                df_final["Volume de l'US"] = 0
            df_final["Volume total"] = df_final["Quantité livrée US"] * df_final["Volume de l'US"]

            df_grouped, df_city = self._group_data(df_final)
            df_city = self._calculate_estafette_need(df_city)
            df_grouped_zone = self._assign_zone(df_grouped)

            return df_grouped, df_city, df_grouped_zone

        except Exception as e:
            raise Exception(f"❌ Erreur lors du traitement des données : {str(e)}")


    def _load_livraisons(self, liv_file):
        df = pd.read_excel(liv_file)
        df.rename(columns={df.columns[4]: "Quantité livrée US"}, inplace=True)
        return df

    def _load_ydlogist(self, file_path):
        df = pd.read_excel(file_path)
        # Sélectionne explicitement les colonnes utiles
        cols_needed = ["Article", "Poids de l'US", "Volume de l'US"]
        for col in cols_needed:
            if col not in df.columns:
                df[col] = 0
        return df[cols_needed]

    def _filter_initial_data(self, df):
        clients_exclus = [
            "AMECAP", "SANA", "SOPAL", "SOPALGAZ", "SOPALSERV", "SOPALTEC",
            "SOPALALG", "AQUA", "WINOX", "QUIVEM", "SANISTONE",
            "SOPAMAR", "SOPALAFR", "SOPALINTER"
        ]
        return df[(df["Type livraison"] != "SDC") & (~df["Client commande"].isin(clients_exclus))]

    def _calculate_weights(self, df_liv, df_yd):
        df = pd.merge(df_liv, df_yd[["Article", "Poids de l'US"]], on="Article", how="left")
        if "Poids de l'US" in df.columns:
            df["Poids de l'US"] = pd.to_numeric(df["Poids de l'US"].astype(str).str.replace(",", "."),
                                               errors="coerce").fillna(0)
        else:
            df["Poids de l'US"] = 0
        df["Quantité livrée US"] = pd.to_numeric(df["Quantité livrée US"], errors="coerce").fillna(0)
        df["Poids total"] = df["Quantité livrée US"] * df["Poids de l'US"]
        return df[["No livraison", "Article", "Client commande", "Poids total"]]

    def _calculate_volumes(self, df_liv, df_yd):
        df = pd.merge(df_liv, df_yd[["Article", "Volume de l'US"]], on="Article", how="left")
        if "Volume de l'US" in df.columns:
            df["Volume de l'US"] = pd.to_numeric(df["Volume de l'US"].astype(str).str.replace(",", "."),
                                                errors="coerce").fillna(0)
        else:
            df["Volume de l'US"] = 0
        return df[["No livraison", "Article", "Client commande", "Quantité livrée US", "Volume de l'US"]]

    def _merge_delivery_data(self, df_poids, df_vol):
        return pd.merge(df_poids, df_vol, on=["No livraison", "Article", "Client commande"], how="left")

    def _add_city_client_info(self, df, wcliegps_file):
        df_clients = pd.read_excel(wcliegps_file)
        return pd.merge(df, df_clients[["Client", "Ville"]],
                        left_on="Client commande", right_on="Client", how="left")

    def _group_data(self, df):
        df_grouped = df.groupby(["No livraison", "Client", "Ville"], as_index=False).agg({
            "Article": lambda x: ", ".join(x.astype(str)),
            "Poids total": "sum",
            "Volume total": "sum"
        })
        df_city = df_grouped.groupby("Ville", as_index=False).agg({
            "Poids total": "sum",
            "Volume total": "sum",
            "No livraison": "count"
        }).rename(columns={"No livraison": "Nombre livraisons"})
        return df_grouped, df_city

    def _calculate_estafette_need(self, df_city):
        poids_max = 1550
        volume_max = 1.2 * 1.2 * 0.8 * 4
        df_city["Besoin estafette (poids)"] = df_city["Poids total"].apply(lambda p: math.ceil(p / poids_max))
        df_city["Besoin estafette (volume)"] = df_city["Volume total"].apply(lambda v: math.ceil(v / volume_max))
        df_city["Besoin estafette réel"] = df_city[["Besoin estafette (poids)", "Besoin estafette (volume)"]].max(axis=1)
        return df_city

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

    def export_results(self, df_grouped, df_city, df_grouped_zone, path_grouped, path_city, path_zone):
        df_grouped.to_excel(path_grouped, index=False)
        df_city.to_excel(path_city, index=False)
        df_grouped_zone.to_excel(path_zone, index=False)
        return True
