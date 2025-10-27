import pandas as pd
import numpy as np

class DeliveryProcessor:
    def __init__(self):
        # Capacités estafette
        self.MAX_POIDS = 1550.0  # kg
        self.MAX_VOLUME = 4.608  # m3
        
        # Zones (optionnel, pour future utilisation)
        self.zones = {
            "Zone 1": ["TUNIS","ARIANA","MANOUBA","BEN AROUS","BIZERTE","MATEUR","MENZEL BOURGUIBA","UTIQUE"],
            "Zone 2": ["NABEUL","HAMMAMET","KORBA","MENZEL TEMIME","KELIBIA","SOLIMAN"],
            "Zone 3": ["SOUSSE","MONASTIR","MAHDIA","KAIROUAN"],
            "Zone 4": ["GABÈS","MÉDENINE","ZARZIS","DJERBA"],
            "Zone 5": ["GAFSA","KASSERINE","TOZEUR","NEFTA","DOUZ"],
            "Zone 6": ["JENDOUBA","BÉJA","LE KEF","TABARKA","SILIANA"],
            "Zone 7": ["SFAX"]
        }

    def process_delivery_data(self, liv_file, ydlogist_file, wcliegps_file):
        try:
            # Charger fichiers
            df_liv = pd.read_excel(liv_file)
            df_ydlogist = pd.read_excel(ydlogist_file)
            df_clients = pd.read_excel(wcliegps_file)

            # Normaliser les noms de colonnes (minuscules, sans espaces)
            df_liv.columns = df_liv.columns.str.strip().str.replace(" ", "_").str.lower()
            df_ydlogist.columns = df_ydlogist.columns.str.strip().str.replace(" ", "_").str.lower()
            df_clients.columns = df_clients.columns.str.strip().str.replace(" ", "_").str.lower()

            # Vérifier les colonnes importantes
            required_liv_cols = ["no_livraison", "article", "quantité_livrée_us", "client_commande"]
            for col in required_liv_cols:
                if col not in df_liv.columns:
                    raise Exception(f"Colonne manquante dans livraisons: {col}")

            # Filtrer livraisons (supprimer SDC et certains clients)
            df_liv = df_liv[df_liv.get("type_livraison","") != "SDC"]
            clients_a_supprimer = [
                "AMECAP", "SANA", "SOPAL", "SOPALGAZ", "SOPALSERV", "SOPALTEC",
                "SOPALALG", "AQUA", "WINOX", "QUIVEM", "SANISTONE", "SOPAMAR",
                "SOPALAFR", "SOPALINTER"
            ]
            df_liv = df_liv[~df_liv["client_commande"].isin(clients_a_supprimer)]

            # Renommer colonnes YDLOGIST utiles
            df_ydlogist = df_ydlogist.rename(columns={
                df_ydlogist.columns[2]: "catégorie",
                df_ydlogist.columns[5]: "acheté",
                df_ydlogist.columns[6]: "fabriqué",
                df_ydlogist.columns[8]: "unité_stock",
                df_ydlogist.columns[9]: "date_creation",
                df_ydlogist.columns[13]: "unité_poids",
                df_ydlogist.columns[16]: "unité_volume"
            })

            # Calcul poids total par ligne
            df_liv["quantité_livrée_us"] = pd.to_numeric(df_liv["quantité_livrée_us"], errors="coerce").fillna(0)
            df_ydlogist["poids_de_l_us"] = pd.to_numeric(df_ydlogist.get("poids_de_l_us", 0), errors="coerce").fillna(0)
            df_ydlogist["volume_de_l_us"] = pd.to_numeric(df_ydlogist.get("volume_de_l_us", 0), errors="coerce").fillna(0)

            # Fusion livraisons et volumes
            df_merge = pd.merge(df_liv, df_ydlogist[["article", "poids_de_l_us", "volume_de_l_us"]], on="article", how="left")
            df_merge["poids_total"] = df_merge["quantité_livrée_us"] * df_merge["poids_de_l_us"]
            df_merge["volume_total"] = df_merge["quantité_livrée_us"] * df_merge["volume_de_l_us"]

            # Ajouter ville et client
            df_merge = pd.merge(df_merge, df_clients[["client","ville"]], left_on="client_commande", right_on="client", how="left")
            df_merge = df_merge[~df_merge["ville"].isin(["TRIPOLI"])]
            df_merge = df_merge[df_merge["client_commande"] != "PERSOGSO"]

            # Calcul taux d'occupation
            df_merge["taux_occupation_%"] = df_merge.apply(
                lambda row: max(
                    row.get("poids_total",0)/self.MAX_POIDS,
                    row.get("volume_total",0)/self.MAX_VOLUME
                )*100,
                axis=1
            )

            return df_merge.round(2)

        except Exception as e:
            raise Exception(f"Erreur lors du traitement des données: {str(e)}")

    def export_results(self, df, output_path):
        try:
            df.to_excel(output_path, index=False)
            return True
        except Exception as e:
            raise Exception(f"Erreur lors de l'export: {str(e)}")
