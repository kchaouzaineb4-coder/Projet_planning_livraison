import pandas as pd
import numpy as np

class DeliveryProcessor:
    def __init__(self):
        # Constantes
        self.MAX_POIDS = 1550.0  # kg (Capacité estafette standard)
        self.MAX_VOLUME = 4.608  # m3 (Capacité estafette standard)
        
    def process_delivery_data(self, liv_file, ydlogist_file, wcliegps_file):
        """
        Traitement principal des données de livraison
        """
        try:
            # 1. Charger et filtrer les données initiales
            df_liv = pd.read_excel(liv_file)
            df_liv = self._rename_columns_liv(df_liv)
            
            # 2. Traiter les données YDLOGIST
            df_ydlogist = self._process_ydlogist(ydlogist_file)
            
            # 3. Fusionner livraisons et YDLOGIST
            df = pd.merge(df_liv, df_ydlogist, on="Article", how="left")
            
            # 4. Calculer Poids total et Volume total par article
            df["Poids total"] = df["Quantité livrée US"] * df["Poids de l'US"]
            df["Volume total"] = df["Quantité livrée US"] * df["Volume de l'US"]
            
            # 5. Ajouter informations Ville et Client
            df = self._add_city_client_info(df, wcliegps_file)
            
            # 6. Supprimer colonnes inutiles
            df = df.drop(columns=["Client commande", "Unité Volume", "Poids de l'US", "Volume de l'US"])
            
            # 7. Agréger par No livraison
            df_final = df.groupby("No livraison", as_index=False).agg({
                "Article": lambda x: ", ".join(x.astype(str)),  # concaténation articles
                "Poids total": "sum",
                "Volume total": "sum",
                "Client": "first",
                "Ville": "first"
            })
            
            return df_final
        
        except Exception as e:
            raise Exception(f"Erreur lors du traitement des données: {str(e)}")
    
    def _rename_columns_liv(self, df):
        """Renommer les colonnes du fichier livraisons"""
        df = df.rename(columns={
            df.columns[0]: "No livraison",
            df.columns[1]: "Client commande",
            df.columns[2]: "Article",
            df.columns[4]: "Quantité livrée US"  # Colonne E
        })
        return df
    
    def _process_ydlogist(self, file_path):
        """Traiter le fichier YDLOGIST"""
        df = pd.read_excel(file_path)
        
        # Renommage colonnes importantes
        df = df.rename(columns={
            df.columns[2]: "Catégorie",
            df.columns[5]: "Acheté",
            df.columns[6]: "Fabriqué",
            df.columns[8]: "Unité Stock",
            df.columns[9]: "Date création",
            df.columns[13]: "Poids de l'US",
            df.columns[16]: "Volume de l'US"
        })
        
        # Conversion en float
        df["Poids de l'US"] = pd.to_numeric(df["Poids de l'US"].astype(str).str.replace(",", "."), errors="coerce").fillna(0)
        df["Volume de l'US"] = pd.to_numeric(df["Volume de l'US"].astype(str).str.replace(",", "."), errors="coerce").fillna(0)
        
        # Convertir Volume en m³ si >100 (supposé cm3)
        df.loc[df["Volume de l'US"] > 100, "Volume de l'US"] = df["Volume de l'US"] / 1000000
        
        return df
    
    def _add_city_client_info(self, df, wcliegps_file):
        """Ajouter les informations de ville et client"""
        df_clients = pd.read_excel(wcliegps_file)
        df = pd.merge(df, df_clients[["Client", "Ville"]], left_on="Client commande", right_on="Client", how="left")
        
        # Supprimer certains clients ou villes spécifiques
        df = df[df["Ville"] != "TRIPOLI"]
        df = df[df["Client commande"] != "PERSOGSO"]
        return df
    
    def export_results(self, df, output_path):
        """Exporter les résultats"""
        try:
            df.to_excel(output_path, index=False)
            return True
        except Exception as e:
            raise Exception(f"Erreur lors de l'export: {str(e)}")
