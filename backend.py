import pandas as pd
import math


class DeliveryProcessor:

    # =====================================================
    # ✅ Fonction principale : Pipeline complet
    # =====================================================
    def process_delivery_data(self, liv_file, ydlogist_file, wcliegps_file):
        try:
            # Chargement des fichiers
            df_liv = self._load_livraisons(liv_file)
            df_art = self._load_ydlogist(ydlogist_file)

            # Nettoyage & filtrage
            df_liv = self._filter_initial_data(df_liv)

            # Calculs
            df_poids = self._calculate_weights(df_liv.copy())
            df_vol = self._calculate_volumes(df_liv.copy(), df_art)
            df_merged = self._merge_delivery_data(df_poids, df_vol)

            # Enrichissement géographique
            df_final = self._add_city_client_info(df_merged, wcliegps_file)

            # Conversion volume en m³
            df_final["Volume de l'US"] = df_final["Volume de l'US"] / 1_000_000
            df_final["Volume total"] = df_final["Volume de l'US"] * df_final["Quantité livrée US"]

            # Groupement statistique
            df_grouped, df_city = self._group_data(df_final)

            # Calcul des estafettes nécessaires
            df_city = self._calculate_estafette_need(df_city)

            return df_grouped, df_city

        except Exception as e:
            raise Exception(f"❌ Erreur traitement : {str(e)}")

    # =====================================================
    # 🔹 Lecture fichiers
    # =====================================================
    def _load_livraisons(self, liv_file):
        df = pd.read_excel(liv_file)
        df.rename(columns={df.columns[4]: "Quantité livrée US"}, inplace=True)
        return df

    def _load_ydlogist(self, file_path):
        df = pd.read_excel(file_path)
        df.rename(columns={
            df.columns[13]: "Poids de l'US",
            df.columns[16]: "Volume de l'US"
        }, inplace=True)
        return df

    # =====================================================
    # 🔹 Pré-Nettoyage : filtrage des clients
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
    # 🔹 Calculs Poids / Volume
    # =====================================================
    def _calculate_weights(self, df):
        df["Poids de l'US"] = (
            df["Poids de l'US"].astype(str)
            .str.replace(",", ".", regex=False)
            .str.replace(r"[^\d.]", "", regex=True)
        )
        df["Poids de l'US"] = pd.to_numeric(df["Poids de l'US"], errors="coerce").fillna(0)

        df["Quantité livrée US"] = pd.to_numeric(df["Quantité livrée US"], errors="coerce").fillna(0)
        df["Poids total"] = df["Poids total"] = df["Quantité livrée US"] * df["Poids de l'US"]

        return df[["No livraison", "Article", "Client commande", "Poids total"]]

    def _calculate_volumes(self, df_liv, df_art):
        df_art = df_art[["Article", "Volume de l'US"]].copy()
        df_art["Volume de l'US"] = pd.to_numeric(
            df_art["Volume de l'US"].astype(str).str.replace(",", "."),
            errors="coerce"
        )

        return pd.merge(df_liv, df_art, on="Article", how="left")

    # =====================================================
    # 🔹 Fusion des dataset
    # =====================================================
    def _merge_delivery_data(self, df_poids, df_vol):
        return pd.merge(
            df_poids, df_vol,
            on=["No livraison", "Article", "Client commande"],
            how="left"
        )

    # =====================================================
    # 🔹 Match Client → Ville
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
    # 🔹 Groupement par Client / Ville
    # =====================================================
    def _group_data(self, df):
        df_grouped = df.groupby(
            ["No livraison", "Client", "Ville"], as_index=False
        ).agg({
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

    # =====================================================
    # 🔹 Calcul estafettes par ville
    # =====================================================
    def _calculate_estafette_need(self, df_city):
        poids_max = 1550
        volume_max = 1.2 * 1.2 * 0.8 * 4  # m³

        df_city["Besoin estafette (poids)"] = (df_city["Poids total"] / poids_max).apply(math.ceil)
        df_city["Besoin estafette (volume)"] = (df_city["Volume total"] / volume_max).apply(math.ceil)

        df_city["Besoin estafette réel"] = df_city[
            ["Besoin estafette (poids)", "Besoin estafette (volume)"]
        ].max(axis=1)

        return df_city

    # =====================================================
    # ✅ Export Excel
    # =====================================================
    def export_results(self, df_grouped, df_city, path_grouped, path_city):
        df_grouped.to_excel(path_grouped, index=False)
        df_city.to_excel(path_city, index=False)
        return True
