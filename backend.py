import pandas as pd
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

            # ✅ Ajout des Zones
            df_grouped_zone = self._add_zone(df_grouped)

            # ✅ Suppression Zone inconnue
            df_grouped_zone = df_grouped_zone[df_grouped_zone["Zone"] != "Zone inconnue"].copy()

            # ✅ Groupement par zone
            df_zone = self._group_by_zone(df_grouped_zone)

            # ✅ Calcul besoin estafette par zone
            df_zone = self._calculate_estafette_need(df_zone)

            # ✅ Calcul optimisation voyages par zone
            df_estafettes = self._plan_estafettes(df_grouped_zone)

            return df_grouped, df_city, df_grouped_zone, df_zone, df_estafettes

        except Exception as e:
            raise Exception(f"❌ Erreur lors du traitement des données : {str(e)}")

    # =========================================================================
    # 🧩 Fonctions internes (identiques à ta version — pas modifiées sauf Zone)
    # =========================================================================
    def _load_livraisons(self, liv_file):
        df = pd.read_excel(liv_file)
        df.rename(columns={df.columns[4]: "Quantité livrée US"}, inplace=True)
        return df

    def _load_ydlogist(self, file_path):
        df = pd.read_excel(file_path)
        df.rename(columns={df.columns[16]: "Unité Volume", df.columns[13]: "Poids de l'US"}, inplace=True)
        return df

    def _filter_initial_data(self, df):
        clients_exclus = [
            "AMECAP", "SANA", "SOPAL", "SOPALGAZ", "SOPALSERV", "SOPALTEC",
            "SOPALALG", "AQUA", "WINOX", "QUIVEM", "SANISTONE",
            "SOPAMAR", "SOPALAFR", "SOPALINTER"
        ]
        return df[(df["Type livraison"] != "SDC") & (~df["Client commande"].isin(clients_exclus))]

    def _calculate_weights(self, df):
        df["Poids de l'US"] = pd.to_numeric(df["Poids de l'US"].astype(str).str.replace(",", ".")
                                             .str.replace(r"[^\d.]", "", regex=True), errors="coerce").fillna(0)
        df["Quantité livrée US"] = pd.to_numeric(df["Quantité livrée US"], errors="coerce").fillna(0)
        df["Poids total"] = df["Quantité livrée US"] * df["Poids de l'US"]
        return df[["No livraison", "Article", "Client commande", "Poids total"]]

    def _calculate_volumes(self, df_liv, df_art):
        df_liv_sel = df_liv[["No livraison", "Article", "Quantité livrée US", "Client commande"]]
        df_art_sel = df_art[["Article", "Volume de l'US", "Unité Volume"]].copy()
        df_art_sel["Volume de l'US"] = pd.to_numeric(df_art_sel["Volume de l'US"].astype(str).str.replace(",", "."),
                                                     errors="coerce")
        return pd.merge(df_liv_sel, df_art_sel, on="Article", how="left")

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

    def _calculate_estafette_need(self, df):
        poids_max = 1550
        volume_max = 4.608
        df["Besoin estafette (poids)"] = df["Poids total"].apply(lambda p: math.ceil(p / poids_max))
        df["Besoin estafette (volume)"] = df["Volume total"].apply(lambda v: math.ceil(v / volume_max))
        df["Besoin estafette réel"] = df[["Besoin estafette (poids)", "Besoin estafette (volume)"]].max(axis=1)
        return df

    def _add_zone(self, df):
        zones = {
            "Zone 1": ["TUNIS", "ARIANA", "MANOUBA", "BEN AROUS", "BIZERTE", "MATEUR", "MENZEL BOURGUIBA", "UTIQUE"],
            "Zone 2": ["NABEUL", "HAMMAMET", "KORBA", "MENZEL TEMIME", "KELIBIA", "SOLIMAN"],
            "Zone 3": ["SOUSSE", "MONASTIR", "MAHDIA", "KAIROUAN"],
            "Zone 4": ["GABÈS", "MEDENINE", "ZARZIS", "DJERBA"],
            "Zone 5": ["GAFSA", "KASSERINE", "TOZEUR", "NEFTA", "DOUZ"],
            "Zone 6": ["JENDOUBA", "BÉJA", "LE KEF", "TABARKA", "SILIANA"],
            "Zone 7": ["SFAX"]
        }
        df["Zone"] = df["Ville"].str.upper().apply(
            lambda v: next((z for z, villes in zones.items() if v in villes), "Zone inconnue")
        )
        return df

    def _group_by_zone(self, df):
        return df.groupby("Zone", as_index=False).agg({
            "Poids total": "sum",
            "Volume total": "sum",
            "No livraison": "count"
        }).rename(columns={"No livraison": "Nombre livraisons"})

    # =========================================================================
    # ✅ Optimisation voyages par zone
    # =========================================================================
    def _plan_estafettes(self, df):
        MAX_POIDS = 1550
        MAX_VOLUME = 4.608
        
        resultats = []
        estafette_num = 1  # ✅ Numérotation globale

        for zone, group in df.groupby("Zone"):
            group_sorted = group.sort_values(by="Poids total", ascending=False)

            estafettes = []

            for idx, row in group_sorted.iterrows():
                bl = row["No livraison"]
                poids = row["Poids total"]
                volume = row["Volume total"]
                placed = False

                # 🎯 Trouver une estafette existante où ça rentre
                for e in estafettes:
                    if e["poids"] + poids <= MAX_POIDS and e["volume"] + volume <= MAX_VOLUME:
                        e["poids"] += poids
                        e["volume"] += volume
                        e["bls"].append(bl)
                        placed = True
                        break

                if not placed:
                    estafettes.append({
                        "poids": poids,
                        "volume": volume,
                        "bls": [bl]
                    })

            # ✅ Enregistrement numérotation continue
            for e in estafettes:
                resultats.append([
                    zone,
                    estafette_num,
                    e["poids"],
                    e["volume"],
                    ";".join(e["bls"])
                ])
                estafette_num += 1

        return pd.DataFrame(resultats, columns=["Zone", "Estafette N°", "Poids total", "Volume total", "BL inclus"])
