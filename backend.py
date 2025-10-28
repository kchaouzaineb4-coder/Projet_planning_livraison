import pandas as pd
import numpy as np
from io import BytesIO

# Constantes de capacité (doivent correspondre à celles utilisées dans app.py)
MAX_POIDS = 1550  # Capacité maximale en kg
MAX_VOLUME = 4.608 # Capacité maximale en m³ (volume)

class DeliveryProcessor:
    """
    Classe responsable du chargement, du nettoyage, de la fusion et du traitement
    des données de livraison pour générer les différents tableaux de bord.
    """

    def _load_data(self, liv_file, ydlogist_file, wcliegps_file):
        """Charge les fichiers Excel depuis les objets téléchargés par Streamlit."""
        df_liv = pd.read_excel(liv_file)
        df_ydlogist = pd.read_excel(ydlogist_file)
        df_wcliegps = pd.read_excel(wcliegps_file)
        return df_liv, df_ydlogist, df_wcliegps

    def _clean_and_merge(self, df_liv, df_ydlogist):
        """Nettoie les données et fusionne les livraisons avec les volumes."""
        
        # S'assurer que les clés de fusion sont des chaînes de caractères
        df_liv['N° BON LIVRAISON'] = df_liv['N° BON LIVRAISON'].astype(str).str.strip()
        df_ydlogist['N° BON LIVRAISON'] = df_ydlogist['N° BON LIVRAISON'].astype(str).str.strip()

        # Fusionner les livraisons et les volumes
        df_merged = pd.merge(df_liv, df_ydlogist, on='N° BON LIVRAISON', how='left')

        # Nettoyage et conversion des codes postaux (assure la cohérence)
        df_merged['Code postal'] = df_merged['Code postal'].astype(str).str.zfill(5)
        
        # Calculer le volume et le poids total par livraison (si les colonnes existent)
        # S'assurer des noms de colonnes : 'Poids (kg)' et 'Volume (m3)'
        
        # Renommage si nécessaire (pour être plus générique)
        if 'Poids (kg)' in df_merged.columns and 'Volume (m3)' in df_merged.columns:
            df_merged['Poids total'] = df_merged['Poids (kg)']
            df_merged['Volume total'] = df_merged['Volume (m3)']
        elif 'Poids Total' in df_merged.columns and 'Volume Total' in df_merged.columns:
             # Utilisation des colonnes existantes si elles ont déjà les totaux
            df_merged['Poids total'] = df_merged['Poids Total']
            df_merged['Volume total'] = df_merged['Volume Total']
        else:
            # Si les colonnes de poids/volume unitaires devaient être multipliées par la quantité,
            # cette logique serait implémentée ici. Pour l'instant, on assume des colonnes 'Total'.
            df_merged['Poids total'] = 0
            df_merged['Volume total'] = 0
            
            # Gestion des valeurs manquantes après la fusion
            df_merged['Poids total'] = df_merged['Poids total'].fillna(0)
            df_merged['Volume total'] = df_merged['Volume total'].fillna(0)

        return df_merged

    def _calculate_city_data(self, df_merged):
        """
        Calcule les données groupées par Client/Ville et le besoin en estafettes par Ville.
        """
        # Tableau 1: Livraisons par Client & Ville
        df_grouped = df_merged.groupby(['Code Client', 'Client', 'Ville', 'Code postal']).agg(
            {'N° BON LIVRAISON': 'count', 
             'Poids total': 'sum', 
             'Volume total': 'sum'}
        ).rename(columns={'N° BON LIVRAISON': 'Nombre livraisons'}).reset_index()

        # Tableau 2: Besoin Estafette par Ville
        df_city = df_grouped.groupby('Ville').agg(
            {'Nombre livraisons': 'sum', 
             'Poids total': 'sum', 
             'Volume total': 'sum'}
        ).reset_index()

        # Calcul du besoin estafette réel (basé sur la contrainte max Poids ou Volume)
        df_city['Besoin estafette Poids'] = np.ceil(df_city['Poids total'] / MAX_POIDS)
        df_city['Besoin estafette Volume'] = np.ceil(df_city['Volume total'] / MAX_VOLUME)
        
        # Le besoin estafette réel est le maximum des deux contraintes
        df_city['Besoin estafette réel'] = df_city[['Besoin estafette Poids', 'Besoin estafette Volume']].max(axis=1)
        
        # Nettoyage des colonnes temporaires
        df_city = df_city.drop(columns=['Besoin estafette Poids', 'Besoin estafette Volume'])

        return df_grouped, df_city

    def _add_zone_and_calculate_zone_data(self, df_grouped, df_wcliegps):
        """
        Ajoute la zone aux données groupées et calcule les statistiques par Zone.
        """
        # Assurer que la clé de fusion est cohérente
        df_wcliegps['Code Client'] = df_wcliegps['Code Client'].astype(str).str.strip()
        df_grouped['Code Client'] = df_grouped['Code Client'].astype(str).str.strip()
        
        # Renommage de la colonne Zone dans le fichier client si nécessaire
        df_wcliegps = df_wcliegps.rename(columns={'ZONAGE': 'Zone'})
        
        # Sélectionner uniquement Code Client et Zone (pour éviter les doublons/conflits de colonnes)
        df_zones = df_wcliegps[['Code Client', 'Zone']].drop_duplicates()
        
        # Fusionner pour ajouter la colonne 'Zone' à df_grouped
        df_grouped_zone = pd.merge(df_grouped, df_zones, on='Code Client', how='left')

        # Remplir les zones manquantes (ex: avec 'ZONE_INCONNUE')
        df_grouped_zone['Zone'] = df_grouped_zone['Zone'].fillna('ZONE_INCONNUE').astype(str).str.strip()
        
        # Tableau 3: Livraisons par Client & Ville + Zone (copie du df_grouped_zone)
        # (C'est la base pour l'optimisation)
        
        # Tableau 4: Besoin Estafette par Zone
        df_zone = df_grouped_zone.groupby('Zone').agg(
            {'Nombre livraisons': 'sum', 
             'Poids total': 'sum', 
             'Volume total': 'sum'}
        ).reset_index()

        # Calcul du besoin estafette réel par Zone
        df_zone['Besoin estafette Poids'] = np.ceil(df_zone['Poids total'] / MAX_POIDS)
        df_zone['Besoin estafette Volume'] = np.ceil(df_zone['Volume total'] / MAX_VOLUME)
        df_zone['Besoin estafette réel'] = df_zone[['Besoin estafette Poids', 'Besoin estafette Volume']].max(axis=1)
        df_zone = df_zone.drop(columns=['Besoin estafette Poids', 'Besoin estafette Volume'])

        return df_grouped_zone, df_zone

    def _optimize_estafettes(self, df_grouped_zone):
        """
        Simule la répartition des livraisons dans des estafettes (Voyages) par Zone.
        """
        
        # Trier par Zone pour s'assurer que l'optimisation se fait par zone contiguë
        df_sorted = df_grouped_zone.sort_values(by='Zone').copy()
        
        # Initialisation des variables de suivi
        voyages = []
        current_zone = None
        voyage_id = 0
        current_poids = 0
        current_volume = 0
        
        # Colonne pour stocker l'ID du voyage assigné à chaque ligne de livraison
        df_sorted['Voyage_ID'] = -1 

        for index, row in df_sorted.iterrows():
            zone = row['Zone']
            poids = row['Poids total']
            volume = row['Volume total']

            # Si on change de zone, ou si le chargement dépasse la capacité
            is_new_zone = (zone != current_zone)
            poids_exceeded = (current_poids + poids > MAX_POIDS)
            volume_exceeded = (current_volume + volume > MAX_VOLUME)

            if is_new_zone:
                # Nouvelle zone : réinitialiser le voyage
                current_zone = zone
                voyage_id += 1 # Nouveau voyage
                current_poids = poids
                current_volume = volume
            elif poids_exceeded or volume_exceeded:
                # Capacité dépassée : démarrer un nouveau voyage dans la même zone
                voyage_id += 1 # Nouveau voyage
                current_poids = poids
                current_volume = volume
            else:
                # Peut être ajouté au voyage actuel
                current_poids += poids
                current_volume += volume
            
            # Assignation de l'ID du voyage à la ligne
            df_sorted.loc[index, 'Voyage_ID'] = voyage_id

        # Consolidation des résultats par voyage pour le Tableau 5
        df_optimized_estafettes = df_sorted.groupby(['Zone', 'Voyage_ID']).agg(
            {'Poids total': 'sum', 
             'Volume total': 'sum',
             'Nombre livraisons': 'sum'}
        ).rename(columns={'Poids total': 'Poids total chargé', 
                          'Volume total': 'Volume total chargé'}).reset_index()
        
        # Renommer la colonne Voyage_ID pour un affichage plus clair
        df_optimized_estafettes['Voyage'] = 'Voyage N°' + (df_optimized_estafettes['Voyage_ID'].astype(str))
        df_optimized_estafettes = df_optimized_estafettes.drop(columns=['Voyage_ID'])
        
        # Réorganiser les colonnes
        df_optimized_estafettes = df_optimized_estafettes[['Zone', 'Voyage', 'Poids total chargé', 'Volume total chargé', 'Nombre livraisons']]

        return df_optimized_estafettes


    def process_delivery_data(self, liv_file, ydlogist_file, wcliegps_file):
        """
        Méthode principale pour exécuter l'ensemble du pipeline de traitement.
        Retourne les 5 DataFrames requis par Streamlit.
        """
        # 1. Chargement et Nettoyage
        df_liv, df_ydlogist, df_wcliegps = self._load_data(liv_file, ydlogist_file, wcliegps_file)
        df_merged = self._clean_and_merge(df_liv, df_ydlogist)

        # 2. Calcul des données par Ville (Tableaux 1 & 2)
        df_grouped, df_city = self._calculate_city_data(df_merged)

        # 3. Ajout des zones et calcul des données par Zone (Tableaux 3 & 4)
        df_grouped_zone, df_zone = self._add_zone_and_calculate_zone_data(df_grouped, df_wcliegps)
        
        # 4. Optimisation des voyages (Tableau 5)
        df_optimized_estafettes = self._optimize_estafettes(df_grouped_zone)
        
        # Retourner les 5 DataFrames dans l'ordre attendu par app.py
        return df_grouped, df_city, df_grouped_zone, df_zone, df_optimized_estafettes
