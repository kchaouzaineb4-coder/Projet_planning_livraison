# backend.py
import pandas as pd
import numpy as np
from io import BytesIO

class DeliveryProcessor:
    def __init__(self):
        # Capacités estafette standard
        self.MAX_POIDS = 1550.0  # kg
        self.MAX_VOLUME = 4.608  # m3

        # Dictionnaire zones (si besoin pour optimisation)
        self.zones = {
            "Zone 1": ["TUNIS","ARIANA","MANOUBA","BEN AROUS","BIZERTE","MATEUR","MENZEL BOURGUIBA","UTIQUE"],
            "Zone 2": ["NABEUL","HAMMAMET","KORBA","MENZEL TEMIME","KELIBIA","SOLIMAN"],
            "Zone 3": ["SOUSSE","MONASTIR","MAHDIA","KAIROUAN"],
            "Zone 4": ["GABÈS","MÉDENINE","ZARZIS","DJERBA"],
            "Zone 5": ["GAFSA","KASSERINE","TOZEUR","NEFTA","DOUZ"],
            "Zone 6": ["JENDOUBA","BÉJA","LE KEF","TABARKA","SILIANA"],
            "Zone 7": ["SFAX"]
        }

    def process_delivery_data(self, liv_file, wcliegps_file, ydlogist_file):
        """
        Traitement complet : calculs, fusion, volumes, poids, occupation
        """
        # 1️⃣ Charger les fichiers
        df_liv = pd.read_excel(liv_file)
        df_clients = pd.read_excel(wcliegps_file)
        df_volumes = pd.read_excel(ydlogist_file)

        # 2️⃣ Nettoyer et filtrer les données livraisons
        df_liv = self._filter_livraisons(df_liv)

        # 3️⃣ Préparer les colonnes numériques pour volumes et poids
        df_volumes = self._prepare_volumes(df_volumes)
        df_liv = self._prepare_quantites(df_liv)

        # 4️⃣ Fusionner livraisons avec clients et volumes
        df_merge = self._merge_all(df_liv, df_clients, df_volumes)

        # 5️⃣ Calculer poids total et volume total par livraison
        df_merge['Poids total'] = df_merge['Quantité'] * df_merge['Poids de l\'US']
        df_merge['Volume total'] = df_merge['Quantité'] * df_merge['Volume de l\'US']

        # 6️⃣ Calculer le taux d'occupation
        df_merge["taux d'occupation (%)"] = df_merge.apply(
            lambda row: max(row['Poids total']/self.MAX_POIDS, row['Volume total']/self.MAX_VOLUME)*100,
            axis=1
        ).round(2)

        # 7️⃣ Agrégation finale par client et représentant (ou autre niveau souhaité)
        df_final = df_merge.groupby(
            ['Client commande','Raison sociale','Ville'], as_index=False
        ).agg({
            'No livraison':'count',
            'Poids total':'sum',
            'Volume total':'sum',
            "taux d'occupation (%)":'mean'
        }).rename(columns={
            'No livraison':'Nb livraisons',
            'Poids total':'Poids total (kg)',
            'Volume total':'Volume total (m3)'
        })

        return df_final

    def _filter_livraisons(self, df):
        """Filtrer les livraisons inutiles"""
        # Supprimer type SDC et clients spécifiques
        df = df[df["Type livraison"] != "SDC"]
        clients_a_supprimer = [
            "AMECAP", "SANA", "SOPAL", "SOPALGAZ", "SOPALSERV", "SOPALTEC",
            "SOPALALG", "AQUA", "WINOX", "QUIVEM", "SANISTONE", "SOPAMAR",
            "SOPALAFR", "SOPALINTER"
        ]
        df = df[~df["Client commande"].isin(clients_a_supprimer)]
        return df

    def _prepare_volumes(self, df):
        """Convertir colonnes volumes et poids en numérique"""
        df["Volume de l'US"] = pd.to_numeric(df["Volume de l'US"].astype(str).str.replace(",", "."), errors='coerce').fillna(0)
        df["Poids de l'US"] = pd.to_numeric(df["Poids de l'US"].astype(str).str.replace(",", "."), errors='coerce').fillna(0)
        return df

    def _prepare_quantites(self, df):
        """Convertir quantités en numérique"""
        # Vérifier la colonne de quantité selon ton fichier (ici exemple: 'Nombre lignes')
        if 'Quantité livrée US' in df.columns:
            df['Quantité'] = pd.to_numeric(df['Quantité livrée US'], errors='coerce').fillna(0)
        else:
            # Si tu as une autre colonne pour quantité, adapter ici
            df['Quantité'] = 1  # Par défaut 1 si non défini
        return df

    def _merge_all(self, df_liv, df_clients, df_volumes):
        """Fusionner livraisons, clients et volumes"""
        df = df_liv.merge(
            df_clients[['Client','Raison sociale','Ville']],
            left_on='Client commande',
            right_on='Client',
            how='left'
        )
        df = df.merge(
            df_volumes[['Article','Poids de l\'US','Volume de l\'US']],
            on='Article',
            how='left'
        )
        return df

    def export_to_excel(self, df):
        """Retourner un fichier Excel en BytesIO pour Streamlit"""
        output = BytesIO()
        df.to_excel(output, index=False)
        output.seek(0)
        return output
