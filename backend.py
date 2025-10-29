import pandas as pd
import numpy as np
from io import BytesIO

# =====================================================
# CONSTANTES GLOBALES
# =====================================================
SEUIL_POIDS = 500.0   # Seuil de poids (kg) pour proposer une location de camion
SEUIL_VOLUME = 5.0    # Seuil de volume (m³) pour proposer une location de camion

# Capacités du véhicule
CAPACITE_POIDS_ESTAFETTE = 3500.0 # Capacité Estafette (en kg)
CAPACITE_VOLUME_ESTAFETTE = 25.0  # Capacité Estafette (en m³)
CAPACITE_POIDS_CAMION = 20000.0   # Capacité Camion Loué (en kg)
CAPACITE_VOLUME_CAMION = 80.0     # Capacité Camion Loué (en m³)

# Noms de colonnes standardisés pour l'usage interne et l'affichage
COL_CLIENT = "Client ID Std"
COL_POIDS = "Poids total (kg)"
COL_VOLUME = "Volume total (m³)"
COL_COUNT = "Nombre livraisons"
COL_ESTAFETTE_NEED = "Besoin estafette réel"
COL_VILLE = "Ville"
COL_ZONE = "Zone"

# =====================================================
# CLASSE DE TRAITEMENT INITIAL DES DONNÉES
# =====================================================
class DeliveryProcessor:
    """
    Gère le chargement, le nettoyage, la fusion et l'agrégation
    initiale des données de livraison, en utilisant des noms de colonnes configurables.
    """
    def __init__(self):
        pass

    def _load_data(self, file_uploader):
        """Charge un fichier uploader Streamlit en tant que DataFrame."""
        if file_uploader:
            return pd.read_excel(BytesIO(file_uploader.getvalue()))
        raise ValueError("Un fichier est manquant lors du chargement des données.")

    def _validate_columns(self, df, required_cols):
        """Vérifie si les colonnes requises sont présentes dans le DataFrame."""
        missing = [col for col in required_cols if col not in df.columns]
        if missing:
            raise ValueError(f"Colonnes manquantes dans un fichier : {', '.join(missing)}")
        return True

    def _process_data(self, df_liv, df_ydlogist, df_wcliegps, col_map):
        """Nettoyage et fusion des DataFrames en utilisant le mappage de colonnes."""
        
        client_col = col_map['client_id']
        poids_col = col_map['poids']
        volume_col = col_map['volume']
        zone_col = col_map['zone']
        
        # 1. Vérification de la présence des colonnes requises
        self._validate_columns(df_liv, [client_col, COL_VILLE])
        self._validate_columns(df_ydlogist, [client_col, poids_col, volume_col])
        self._validate_columns(df_wcliegps, [client_col, zone_col])
        
        # 2. Renommage des colonnes pour standardisation interne
        
        # DF Livraisons/Ville
        df_liv_std = df_liv[[client_col, COL_VILLE]].rename(columns={client_col: COL_CLIENT}).drop_duplicates()
        df_liv_std[COL_CLIENT] = df_liv_std[COL_CLIENT].astype(str)
        
        # DF Poids/Volume
        df_vol_std = df_ydlogist[[client_col, poids_col, volume_col]].rename(columns={
            client_col: COL_CLIENT,
            poids_col: COL_POIDS,
            volume_col: COL_VOLUME
        }).drop_duplicates()
        df_vol_std[COL_CLIENT] = df_vol_std[COL_CLIENT].astype(str)

        # DF Clients/Zone
        df_zone_std = df_wcliegps[[client_col, zone_col]].rename(columns={
            client_col: COL_CLIENT,
            zone_col: COL_ZONE
        }).drop_duplicates()
        df_zone_std[COL_CLIENT] = df_zone_std[COL_CLIENT].astype(str)

        # 3. Fusion des données
        
        # Fusion 1: Livraisons/Ville + Poids/Volume
        df_merged = pd.merge(df_liv_std, df_vol_std, on=COL_CLIENT, how='inner')
        
        # Fusion 2: Ajouter les Zones
        df_merged = pd.merge(df_merged, df_zone_std, on=COL_CLIENT, how='left')
        
        # Remplacer les NaN dans 'Zone' si nécessaire
        df_merged[COL_ZONE] = df_merged[COL_ZONE].fillna('Non_Assignée')
        
        return df_merged

    def _calculate_estafette_needs(self, df_grouped, group_cols):
        """Calcule le besoin en estafettes et les taux d'occupation."""
        
        df_result = df_grouped.copy()
        
        # Calcul du besoin théorique en estafettes
        df_result['Besoin Poids'] = np.ceil(df_result[COL_POIDS] / CAPACITE_POIDS_ESTAFETTE)
        df_result['Besoin Volume'] = np.ceil(df_result[COL_VOLUME] / CAPACITE_VOLUME_ESTAFETTE)
        
        # Le besoin réel est le maximum
        df_result[COL_ESTAFETTE_NEED] = df_result[['Besoin Poids', 'Besoin Volume']].max(axis=1).astype(int)
        
        # Calculer les colonnes pour l'affichage final
        df_result['Capacité Poids Estafette (kg)'] = df_result[COL_ESTAFETTE_NEED] * CAPACITE_POIDS_ESTAFETTE
        df_result['Capacité Volume Estafette (m³)'] = df_result[COL_ESTAFETTE_NEED] * CAPACITE_VOLUME_ESTAFETTE

        # Calcul des taux d'occupation initiaux
        df_result['Taux Poids (%)'] = (df_result[COL_POIDS] / df_result['Capacité Poids Estafette (kg)']) * 100
        df_result['Taux Volume (%)'] = (df_result[COL_VOLUME] / df_result['Capacité Volume Estafette (m³)']) * 100
        df_result['Taux d\'occupation (%)'] = df_result[['Taux Poids (%)', 'Taux Volume (%)']].max(axis=1)

        return df_result.drop(columns=['Besoin Poids', 'Besoin Volume', 'Taux Poids (%)', 'Taux Volume (%)'], errors='ignore')

    def process_delivery_data(self, liv_file, ydlogist_file, wcliegps_file, col_map):
        """
        Fonction principale pour charger, fusionner et agréger les données.
        """
        # 1. Chargement et fusion des données brutes
        df_liv = self._load_data(liv_file)
        df_ydlogist = self._load_data(ydlogist_file)
        df_wcliegps = self._load_data(wcliegps_file)
        
        df_merged = self._process_data(df_liv, df_ydlogist, df_wcliegps, col_map)
        
        # 2. Agrégation par Client, Ville et Zone
        df_grouped = df_merged.groupby([COL_CLIENT, COL_VILLE, COL_ZONE], dropna=False).agg(
            {COL_POIDS: 'sum', COL_VOLUME: 'sum', COL_CLIENT: 'size'}
        ).rename(columns={COL_CLIENT: COL_COUNT}).reset_index()
        
        # 3. Agrégation par Ville
        df_city = df_grouped.groupby(COL_VILLE).agg(
            {COL_POIDS: 'sum', COL_VOLUME: 'sum', COL_COUNT: 'sum'}
        ).reset_index()
        df_city = self._calculate_estafette_needs(df_city, group_cols=[COL_VILLE])
        
        # 4. Agrégation par Zone
        df_grouped_zone = df_grouped.groupby([COL_CLIENT, COL_ZONE], dropna=False).agg(
            {COL_POIDS: 'sum', COL_VOLUME: 'sum', COL_COUNT: 'sum'}
        ).reset_index()
        
        df_zone = df_grouped.groupby(COL_ZONE).agg(
            {COL_POIDS: 'sum', COL_VOLUME: 'sum', COL_COUNT: 'sum'}
        ).reset_index()
        df_zone = self._calculate_estafette_needs(df_zone, group_cols=[COL_ZONE])
        
        # 5. Création du DF "Voyages Optimisés" (niveau client)
        df_optimized_estafettes = df_grouped.copy()
        df_optimized_estafettes['Mode de livraison'] = 'Estafette'
        df_optimized_estafettes['Capacité Poids (kg)'] = CAPACITE_POIDS_ESTAFETTE
        df_optimized_estafettes['Capacité Volume (m³)'] = CAPACITE_VOLUME_ESTAFETTE

        # Calculer le taux d'occupation initial (pour 1 estafette)
        df_optimized_estafettes['Taux d\'occupation (%)'] = (
            df_optimized_estafettes[[COL_POIDS, COL_VOLUME]].max(axis=1) / 
            [CAPACITE_POIDS_ESTAFETTE, CAPACITE_VOLUME_ESTAFETTE]
        ).max(axis=1) * 100

        df_optimized_estafettes = df_optimized_estafettes.rename(columns={
            COL_POIDS: "Poids total chargé",
            COL_VOLUME: "Volume total chargé",
            COL_COUNT: "Nombre de colis",
            COL_CLIENT: "Client" # Renommage final pour affichage
        })
        
        # Stocker les noms standardisés pour le RentalProcessor
        return (
            df_grouped.rename(columns={COL_CLIENT: "Client", COL_POIDS: "Poids total (kg)", COL_VOLUME: "Volume total (m³)"}),
            df_city,
            df_grouped_zone.rename(columns={COL_CLIENT: "Client", COL_POIDS: "Poids total (kg)", COL_VOLUME: "Volume total (m³)"}),
            df_zone,
            df_optimized_estafettes
        )

# =====================================================
# CLASSE DE GESTION DE LOCATION DE CAMION (Mise à jour pour le nom 'Client')
# =====================================================
class TruckRentalProcessor:
    
    def __init__(self, df_initial):
        self.df = df_initial.copy()
        self.clients_traites = set()

    def detecter_propositions(self):
        """Détecte les clients qui dépassent les seuils et n'ont pas encore été traités."""
        
        poids_col = "Poids total chargé"
        volume_col = "Volume total chargé"
        
        df_propositions = self.df[
            (self.df[poids_col] > SEUIL_POIDS) | 
            (self.df[volume_col] > SEUIL_VOLUME)
        ].copy()
        
        df_propositions['Client'] = df_propositions['Client'].astype(str)
        
        df_propositions = df_propositions[
            (df_propositions['Mode de livraison'] == 'Estafette') & 
            (~df_propositions['Client'].isin(self.clients_traites))
        ]

        if df_propositions.empty:
            return pd.DataFrame()
            
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
        """Applique la décision de location pour un client donné."""
        client_id_str = str(client_id)
        
        if client_id_str in self.clients_traites:
            return False, f"⚠️ Le client {client_id_str} a déjà été traité.", self.df

        if accepter:
            # Mise à jour des modes et capacités pour le camion loué
            self.df.loc[self.df['Client'] == client_id_str, 'Mode de livraison'] = 'Camion Loué'
            self.df.loc[self.df['Client'] == client_id_str, 'Capacité Poids (kg)'] = CAPACITE_POIDS_CAMION
            self.df.loc[self.df['Client'] == client_id_str, 'Capacité Volume (m³)'] = CAPACITE_VOLUME_CAMION
            
            # Recalculer l'occupation basée sur la nouvelle capacité
            poids = self.df.loc[self.df['Client'] == client_id_str, "Poids total chargé"].iloc[0]
            volume = self.df.loc[self.df['Client'] == client_id_str, "Volume total chargé"].iloc[0]
            
            poids_occup = (poids / CAPACITE_POIDS_CAMION) * 100
            volume_occup = (volume / CAPACITE_VOLUME_CAMION) * 100
            
            self.df.loc[self.df['Client'] == client_id_str, 'Taux d\'occupation (%)'] = max(poids_occup, volume_occup)
            
            self.clients_traites.add(client_id_str)
            return True, f"✅ Location acceptée pour le client {client_id_str}. Mode de livraison mis à jour.", self.df
        else:
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
        
        details_df = client_data[[
            'Client',
            'Ville',
            'Poids total chargé',
            'Volume total chargé',
            'Mode de livraison',
            'Taux d\'occupation (%)'
        ]].copy()
        
        styled_details = details_df.style.format({
            "Poids total chargé": "{:.2f} kg",
            "Volume total chargé": "{:.3f} m³",
            "Taux d\'occupation (%)": "{:.2f}%"
        })
        
        return resume, styled_details

    def get_df_result(self):
        """Retourne le DataFrame principal (Estafette Optimisé) dans son état actuel."""
        return self.df
