import pandas as pd
import numpy as np
import os
from datetime import datetime

class DeliveryProcessor:
    def __init__(self):
        # Constantes
        self.MAX_POIDS = 1550.0  # kg (Capacité estafette standard)
        self.MAX_VOLUME = 4.608  # m3 (Capacité estafette standard) 
        
        # Dictionnaires de référence
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
            df_filtre = self._filter_initial_data(df)
            
            # 2. Traiter les données YDLOGIST
            df_ydlogist = self._process_ydlogist(ydlogist_file)
            
            # 3. Calculer les volumes et poids
            df_volumes = self._calculate_volumes(df_filtre, df_ydlogist)
            df_poids = self._calculate_weights(df_filtre)
            
            # 4. Fusionner les données
            df_final = self._merge_volume_weight(df_volumes, df_poids)
            
            # 5. Ajouter les informations de ville et client
            df_final = self._add_city_client_info(df_final, wcliegps_file)
            
            # 6. Calculer le taux d'occupation
            df_final = self._calculate_occupation_rate(df_final)
            
            return df_final
            
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
        
        # Renommage des colonnes
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
        """Calculer les volumes"""
        df_liv_sel = df_liv[["No livraison", "Article","Quantité livrée US"]]
        df_art_sel = df_art[["Article", "Volume de l'US", "Unité Volume"]]
        
        # Conversion des volumes
        df_art_sel["Volume de l'US"] = pd.to_numeric(
            df_art_sel["Volume de l'US"].astype(str).str.replace(",", "."),
            errors="coerce"
        )
        
        return pd.merge(df_liv_sel, df_art_sel, on="Article", how="left")

    def _calculate_weights(self, df):
        """Calculer les poids"""
        df["Poids de l'US"] = df["Poids de l'US"].astype(str)
        df["Poids de l'US"] = df["Poids de l'US"].str.replace(",", ".")
        df["Poids de l'US"] = df["Poids de l'US"].str.replace(r"[^\d.]", "", regex=True)
        df["Poids de l'US"] = pd.to_numeric(df["Poids de l'US"], errors="coerce").fillna(0)
        
        df["Quantité livrée US"] = pd.to_numeric(df["Quantité livrée US"], errors="coerce").fillna(0)
        df["Poids total ligne"] = df["Quantité livrée US"] * df["Poids de l'US"]
        
        return df.groupby(["No livraison", "Client commande"], as_index=False)["Poids total ligne"].sum()

    def _merge_volume_weight(self, df_volume, df_poids):
        """Fusionner volumes et poids"""
        return pd.merge(df_poids, df_volume, on="No livraison", how="left")

    def _add_city_client_info(self, df, wcliegps_file):
        """Ajouter les informations de ville et client"""
        df_clients = pd.read_excel(wcliegps_file)
        df = pd.merge(
            df,
            df_clients[["Client", "Ville"]],
            left_on="Client commande",
            right_on="Client",
            how="left"
        )
        # Supprimer TRIPOLI et PERSOGSO
        df = df[~df["Ville"].isin(["TRIPOLI"])]
        df = df[df["Client commande"] != "PERSOGSO"]
        return df

    def _calculate_occupation_rate(self, df):
        """Calculer le taux d'occupation"""
        df["taux d'occupation (%)"] = df.apply(
            lambda row: max(
                row["Poids total"]/self.MAX_POIDS,
                row["Volume total"]/self.MAX_VOLUME
            )*100,
            axis=1
        )
        return df.round(2)

    def export_results(self, df, output_path):
        """Exporter les résultats"""
        try:
            df.to_excel(output_path, index=False)
            return True
        except Exception as e:
            raise Exception(f"Erreur lors de l'export: {str(e)}")