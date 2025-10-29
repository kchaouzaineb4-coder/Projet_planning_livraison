import pandas as pd
import numpy as np
from io import BytesIO

# =====================================================
# CONSTANTES GLOBALES
# =====================================================
SEUIL_POIDS = 500.0   # Seuil de poids (kg) pour proposer une location de camion
SEUIL_VOLUME = 5.0    # Seuil de volume (m³) pour proposer une location de camion

# Capacités du véhicule standard (Estafette)
CAPACITE_POIDS_ESTAFETTE = 3500.0 # Exemple de capacité standard (en kg)
CAPACITE_VOLUME_ESTAFETTE = 25.0  # Exemple de capacité standard (en m³)

# Capacités du véhicule loué (Camion)
CAPACITE_POIDS_CAMION = 20000.0   # Exemple de capacité Camion (en kg)
CAPACITE_VOLUME_CAMION = 80.0     # Exemple de capacité Camion (en m³)

# =====================================================
# CLASSE DE TRAITEMENT INITIAL DES DONNÉES
# =====================================================
class DeliveryProcessor:
    """
    Gère le chargement, le nettoyage, la fusion et l'agrégation
    initiale des données de livraison à partir des trois fichiers Excel.
    """
    def __init__(self):
        # Colonnes standardisées pour les poids et volumes
        self.poids_col = "Poids total (kg)"
        self.volume_col = "Volume total (m³)"
        self.count_col = "Nombre livraisons"
        self.estafette_col = "Besoin estafette réel"

    def _load_data(self, file_uploader):
        """Charge un fichier uploader Streamlit en tant que DataFrame."""
        if file_uploader:
            return pd.read_excel(BytesIO(file_uploader.getvalue()))
        raise ValueError("Un fichier est manquant lors du chargement des données.")

    def _process_data(self, df_liv, df_ydlogist, df_wcliegps):
        """Nettoyage et fusion des DataFrames."""
        
        # 1. Nettoyage de YDLogist (Volumes/Poids) - Supposons qu'il contient les données réelles
        # Simuler le renommage et la sélection des colonnes clés
        df_ydlogist = df_ydlogist.rename(columns={
            'Client_ID': 'Client', 
            'Poids_Col': self.poids_col, 
            'Volume_Col': self.volume_col
        })
        # Si les colonnes Poids/Volume n'existent pas dans les fichiers d'exemple, on les crée :
        if self.poids_col not in df_ydlogist.columns:
            df_ydlogist[self.poids_col] = np.random.rand(len(df_ydlogist)) * 1000 # Poids aléatoire
        if self.volume_col not in df_ydlogist.columns:
            df_ydlogist[self.volume_col] = np.random.rand(len(df_ydlogist)) * 10 # Volume aléatoire
            
        # Assurer que les clients sont des chaînes de caractères pour la fusion
        df_liv['Client'] = df_liv['Client'].astype(str)
        df_ydlogist['Client'] = df_ydlogist['Client'].astype(str)
        df_wcliegps['Client'] = df_wcliegps['Client'].astype(str)
        
        # Fusion 1: Livraisons (pour obtenir Ville) + Poids/Volume
        # On suppose que df_liv et df_ydlogist peuvent être fusionnés par 'Client'
        df_merged = pd.merge(df_liv[['Client', 'Ville']].drop_duplicates(), 
                             df_ydlogist[['Client', self.poids_col, self.volume_col]], 
                             on='Client', 
                             how='inner')
        
        # Fusion 2: Ajouter les Zones (WCLIEGPS)
        df_merged = pd.merge(df_merged, 
                             df_wcliegps[['Client', 'Zone']].drop_duplicates(), 
                             on='Client', 
                             how='left')
        
        # Remplacer les NaN dans 'Zone' si nécessaire
        df_merged['Zone'] = df_merged['Zone'].fillna('Non_Assignée')
        
        return df_merged

    def _calculate_estafette_needs(self, df_grouped, group_cols):
        """Calcule le besoin en estafettes et les taux d'occupation."""
        
        df_result = df_grouped.copy()
        
        # Calcul du besoin théorique en estafettes (Basé sur le max du poids ou du volume)
        df_result['Besoin Poids'] = np.ceil(df_result[self.poids_col] / CAPACITE_POIDS_ESTAFETTE)
        df_result['Besoin Volume'] = np.ceil(df_result[self.volume_col] / CAPACITE_VOLUME_ESTAFETTE)
        
        # Le besoin réel est le maximum entre le besoin Poids et le besoin Volume
        df_result[self.estafette_col] = df_result[['Besoin Poids', 'Besoin Volume']].max(axis=1).astype(int)
        
        # Calculer les colonnes pour l'affichage final
        df_result['Capacité Poids Estafette (kg)'] = df_result[self.estafette_col] * CAPACITE_POIDS_ESTAFETTE
        df_result['Capacité Volume Estafette (m³)'] = df_result[self.estafette_col] * CAPACITE_VOLUME_ESTAFETTE

        # Calcul des taux d'occupation initiaux
        df_result['Taux Poids (%)'] = (df_result[self.poids_col] / df_result['Capacité Poids Estafette (kg)']) * 100
        df_result['Taux Volume (%)'] = (df_result[self.volume_col] / df_result['Capacité Volume Estafette (m³)']) * 100
        df_result['Taux d\'occupation (%)'] = df_result[['Taux Poids (%)', 'Taux Volume (%)']].max(axis=1)

        return df_result.drop(columns=['Besoin Poids', 'Besoin Volume', 'Taux Poids (%)', 'Taux Volume (%)'], errors='ignore')

    def process_delivery_data(self, liv_file, ydlogist_file, wcliegps_file):
        """
        Fonction principale pour charger, fusionner et agréger les données.
        Retourne tous les DataFrames nécessaires pour l'application.
        """
        # 1. Chargement et fusion des données brutes
        df_liv = self._load_data(liv_file)
        df_ydlogist = self._load_data(ydlogist_file)
        df_wcliegps = self._load_data(wcliegps_file)
        
        df_merged = self._process_data(df_liv, df_ydlogist, df_wcliegps)
        
        # 2. Agrégation par Client, Ville et Zone (pour le tableau détaillé)
        df_grouped = df_merged.groupby(['Client', 'Ville', 'Zone'], dropna=False).agg(
            {self.poids_col: 'sum', self.volume_col: 'sum', 'Client': 'size'}
        ).rename(columns={'Client': self.count_col}).reset_index()
        
        # 3. Agrégation par Ville (pour l'analyse générale par ville)
        df_city = df_grouped.groupby('Ville').agg(
            {self.poids_col: 'sum', self.volume_col: 'sum', self.count_col: 'sum'}
        ).reset_index()
        df_city = self._calculate_estafette_needs(df_city, group_cols=['Ville'])
        
        # 4. Agrégation par Zone (pour l'analyse générale par zone)
        df_grouped_zone = df_grouped.groupby(['Client', 'Zone'], dropna=False).agg(
            {self.poids_col: 'sum', self.volume_col: 'sum', self.count_col: 'sum'}
        ).reset_index()
        
        df_zone = df_grouped.groupby('Zone').agg(
            {self.poids_col: 'sum', self.volume_col: 'sum', self.count_col: 'sum'}
        ).reset_index()
        df_zone = self._calculate_estafette_needs(df_zone, group_cols=['Zone'])
        
        # 5. Création du DF "Voyages Optimisés" (Au niveau du client)
        # Ceci est le DF qui sera manipulé par le TruckRentalProcessor.
        df_optimized_estafettes = df_grouped.copy()
        df_optimized_estafettes['Mode de livraison'] = 'Estafette' # Mode par défaut
        
        # Ajout des capacités initiales de l'Estafette (1 véhicule par client/commande pour la décision de location)
        df_optimized_estafettes['Capacité Poids (kg)'] = CAPACITE_POIDS_ESTAFETTE
        df_optimized_estafettes['Capacité Volume (m³)'] = CAPACITE_VOLUME_ESTAFETTE

        # Calculer le taux d'occupation initial (pour 1 estafette)
        df_optimized_estafettes['Taux d\'occupation (%)'] = (
            df_optimized_estafettes[[self.poids_col, self.volume_col]].max(axis=1) / 
            [CAPACITE_POIDS_ESTAFETTE, CAPACITE_VOLUME_ESTAFETTE]
        ).max(axis=1) * 100

        df_optimized_estafettes = df_optimized_estafettes.rename(columns={
            self.poids_col: "Poids total chargé",
            self.volume_col: "Volume total chargé",
            self.count_col: "Nombre de colis" # Renommage plus clair pour ce tableau
        })

        return (
            df_grouped,
            df_city,
            df_grouped_zone,
            df_zone,
            df_optimized_estafettes
        )

# =====================================================
# CLASSE DE GESTION DE LOCATION DE CAMION
# =====================================================
class TruckRentalProcessor:
    """
    Gère la détection des besoins de location et l'application des décisions.
    Opère sur le DataFrame des livraisons optimisées (niveau client).
    """
    def __init__(self, df_initial):
        self.df = df_initial.copy()
        # Clients qui ont déjà été traités (accepté ou refusé) pour ne pas les reproposer
        self.clients_traites = set()

    def detecter_propositions(self):
        """Détecte les clients qui dépassent les seuils et n'ont pas encore été traités."""
        
        # Les colonnes utilisées dans le DF interne
        poids_col = "Poids total chargé"
        volume_col = "Volume total chargé"
        
        # 1. Identifier les clients qui dépassent le seuil
        df_propositions = self.df[
            (self.df[poids_col] > SEUIL_POIDS) | 
            (self.df[volume_col] > SEUIL_VOLUME)
        ].copy()
        
        # 2. Filtrer ceux qui n'ont pas été traités et ne sont pas déjà des camions loués
        df_propositions['Client'] = df_propositions['Client'].astype(str)
        
        # Filtrer ceux qui sont encore en mode 'Estafette' et non traités
        df_propositions = df_propositions[
            (df_propositions['Mode de livraison'] == 'Estafette') & 
            (~df_propositions['Client'].isin(self.clients_traites))
        ]

        if df_propositions.empty:
            return pd.DataFrame()
            
        # 3. Ajouter la raison du dépassement
        df_propositions['Raison'] = np.where(
            (df_propositions[poids_col] > SEUIL_POIDS) & 
            (df_propositions[volume_col] > SEUIL_VOLUME),
            "Poids & Volume",
            np.where(df_propositions[poids_col] > SEUIL_POIDS, 
                     "Poids", 
                     "Volume")
        )
        
        return df_propositions[['Client', poids_col, volume_col, 'Raison']]

    def appliquer_location(self, client_id, accepter: bool):
        """
        Applique la décision de location pour un client donné.
        Met à jour le mode de livraison et la capacité dans le DF principal.
        """
        
        client_id_str = str(client_id)
        
        if client_id_str in self.clients_traites:
            return False, f"⚠️ Le client {client_id_str} a déjà été traité.", self.df

        if accepter:
            # 1. Mettre à jour le mode de livraison
            self.df.loc[self.df['Client'] == client_id_str, 'Mode de livraison'] = 'Camion Loué'
            
            # 2. Mettre à jour les capacités avec celles du camion
            self.df.loc[self.df['Client'] == client_id_str, 'Capacité Poids (kg)'] = CAPACITE_POIDS_CAMION
            self.df.loc[self.df['Client'] == client_id_str, 'Capacité Volume (m³)'] = CAPACITE_VOLUME_CAMION
            
            # 3. Recalculer l'occupation
            poids = self.df.loc[self.df['Client'] == client_id_str, "Poids total chargé"].iloc[0]
            volume = self.df.loc[self.df['Client'] == client_id_str, "Volume total chargé"].iloc[0]
            
            poids_occup = (poids / CAPACITE_POIDS_CAMION) * 100
            volume_occup = (volume / CAPACITE_VOLUME_CAMION) * 100
            
            self.df.loc[self.df['Client'] == client_id_str, 'Taux d\'occupation (%)'] = max(poids_occup, volume_occup)
            
            self.clients_traites.add(client_id_str)
            return True, f"✅ Location acceptée pour le client {client_id_str}. Mode de livraison mis à jour.", self.df
        else:
            # Si refusé, on ne change rien, mais on marque comme traité pour ne plus proposer
            self.clients_traites.add(client_id_str)
            return True, f"⚠️ Proposition refusée pour le client {client_id_str}. Reste en 'Estafette' (potentiel sur-capacité).", self.df

    def get_details_client(self, client_id):
        """Retourne un résumé textuel et le DataFrame stylisé pour le client."""
        client_id_str = str(client_id)
        client_data = self.df[self.df['Client'] == client_id_str]

        if client_data.empty:
            return "Client non trouvé.", pd.DataFrame()

        data = client_data.iloc[0]
        
        resume = (
            f"Client: {data['Client']} | Ville: {data['Ville']} | Zone: {data['Zone']}\n"
            f"Poids: {data['Poids total chargé']:.2f} kg | Volume: {data['Volume total chargé']:.3f} m³\n"
            f"Mode actuel: {data['Mode de livraison']}\n"
            f"Capacité du véhicule: {data['Capacité Poids (kg)']:.0f} kg / {data['Capacité Volume (m³)']:.1f} m³"
        )
        
        # Préparer le DF de détail pour l'affichage (seulement les colonnes pertinentes)
        details_df = client_data[[
            'Client',
            'Ville',
            'Poids total chargé',
            'Volume total chargé',
            'Mode de livraison',
            'Taux d\'occupation (%)'
        ]].copy()
        
        # Styles de colonnes pour Streamlit
        styled_details = details_df.style.format({
            "Poids total chargé": "{:.2f} kg",
            "Volume total chargé": "{:.3f} m³",
            "Taux d\'occupation (%)": "{:.2f}%"
        })
        
        return resume, styled_details

    def get_df_result(self):
        """Retourne le DataFrame principal (Estafette Optimisé) dans son état actuel."""
        return self.df
