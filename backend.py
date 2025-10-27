import pandas as pd
import numpy as np

class DeliveryProcessor:
    def __init__(self):
        # Constantes
        self.MAX_POIDS = 1550.0  # kg
        self.MAX_VOLUME = 4.608  # m3 (estafette standard)
        
        # Zones (si besoin pour futur usage)
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
        """
        Traitement principal des données de livraison
        """
        try:
            # 1. Charger et filtrer les données initiales
            df = pd.read_excel(liv_file)
            df = self._filter_initial_data(df)
            
            # 2. Traiter les données YDLOGIST
            df_ydlogist = self._process_ydlogist(ydlogist_file)
            
            # 3. Calculer le volume total et poids total par article
            df_calc = self._calculate_volume_weight(df, df_ydlogist)
            
            # 4. Ajouter les informations Client et Ville
            df_final = self._add_city_client_info(df_calc, wcliegps_file)
            
            # 5. Regrouper par No livraison
            df_grouped = self._group_by_livraison(df_final)
            
            return df_grouped
            
        except Exception as e:
            raise Exception(f"Erreur lors du traitement des données: {str(e)}")

    def _filter_initial_data(self, df):
        """Filtrer les données initiales"""
        # Supprimer SDC
        df = df[df["Type livraison"] != "SDC"]
        
        # Supprimer clients spécifiques
        clients_a_supprimer = [
            "AMECAP", "SANA", "SOPAL", "SOPALGAZ", "SOPALSERV", "SOPALTEC",
            "SOPALALG", "AQUA", "WINOX", "QUIVEM", "SANISTONE", "SOPAMAR",
            "SOPALAFR", "SOPALINTER"
        ]
        return df[~df["Client commande"].isin(clients_a_supprimer)]

    def _process_ydlogist(self, file_path):
        """Traiter le fichier YDLOGIST"""
        df = pd.read_excel(file_path)
        
        # Renommage des colonnes importantes
        renommage = {
            df.columns[2]: "Catégorie",
            df.columns[5]: "Acheté",
            df.columns[6]: "Fabriqué", 
            df.columns[8]: "Unité Stock",
            df.columns[9]: "Date création",
            df.columns[13]: "Poids de l'US",
            df.columns[16]: "Volume de l'US"  # On enlèvera l'unité Volume
        }
        df = df.rename(columns=renommage)
        
        # Convertir Volume de l'US en m3 si nécessaire (si cm3)
        if df["Volume de l'US"].max() > 100:  # supposition si > 100 m3, alors probablement cm3
            df["Volume de l'US"] = df["Volume de l'US"] / 1000000  # cm3 -> m3
        
        return df

    def _calculate_volume_weight(self, df_liv, df_art):
        """Calculer le volume total et le poids total par article"""
        # Renommage colonne Quantité livrée US si nécessaire
        if df_liv.columns[4] != "Quantité livrée US":
            df_liv.rename(columns={df_liv.columns[4]: "Quantité livrée US"}, inplace=True)
        
        # Merge pour récupérer Volume et Poids
        df_merged = pd.merge(
            df_liv,
            df_art[["Article", "Poids de l'US", "Volume de l'US"]],
            on="Article",
            how="left"
        )
        
        # Calcul poids total et volume total par article
        df_merged["Poids total"] = df_merged["Quantité livrée US"] * df_merged["Poids de l'US"]
        df_merged["Volume total"] = df_merged["Quantité livrée US"] * df_merged["Volume de l'US"]
        
        # Supprimer colonnes inutiles
        if "Poids de l'US" in df_merged.columns:
            df_merged.drop(columns=["Poids de l'US"], inplace=True)
        if "Volume de l'US" in df_merged.columns:
            df_merged.drop(columns=["Volume de l'US"], inplace=True)
        if "Unité Volume" in df_merged.columns:
            df_merged.drop(columns=["Unité Volume"], inplace=True)
        if "Client commande" in df_merged.columns:
            df_merged.drop(columns=["Client commande"], inplace=True)
        
        return df_merged

    def _add_city_client_info(self, df, wcliegps_file):
        """Ajouter les informations de ville et client"""
        df_clients = pd.read_excel(wcliegps_file)
        df = pd.merge(
            df,
            df_clients[["Client", "Ville"]],
            left_on="Client",
            right_on="Client",
            how="left"
        )
        # Supprimer TRIPOLI et PERSOGSO
        df = df[~df["Ville"].isin(["TRIPOLI"])]
        df = df[df["Client"] != "PERSOGSO"]
        return df

    def _group_by_livraison(self, df):
        """Regrouper par No livraison"""
        df_grouped = df.groupby(["No livraison", "Client", "Ville"], as_index=False).agg({
            "Article": lambda x: ", ".join(x.astype(str)),
            "Poids total": "sum",
            "Volume total": "sum"
        })
        return df_grouped

    def export_results(self, df, output_path):
        """Exporter les résultats"""
        try:
            df.to_excel(output_path, index=False)
            return True
        except Exception as e:
            raise Exception(f"Erreur lors de l'export: {str(e)}")
