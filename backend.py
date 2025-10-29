import pandas as pd
import numpy as np
import random
from typing import Tuple, List

# =====================================================
# CONSTANTES GLOBALES
# =====================================================
SEUIL_POIDS = 1500  # Poids (kg) au-delà duquel une location est suggérée
SEUIL_VOLUME = 8    # Volume (m³) au-delà duquel une location est suggérée
MAX_POIDS = 2000    # Capacité maximale en Poids (Estafette standard)
MAX_VOLUME = 10     # Capacité maximale en Volume (Estafette standard)

# =====================================================
# FONCTIONS UTILITAIRES DE RECALCUL
# (Nécessaires pour maintenir la cohérence après transfert)
# =====================================================

def _get_unique_clients(bl_list: List[str], bl_to_client_dict: dict) -> List[str]:
    """Extrait la liste unique des clients à partir d'une liste de BLs."""
    clients = set()
    for bl in bl_list:
        if bl in bl_to_client_dict:
            clients.add(bl_to_client_dict[bl]['Client'])
    return sorted(list(clients))

def _get_unique_representatives(client_list: List[str], client_to_rep_dict: dict) -> List[str]:
    """Extrait la liste unique des représentants à partir d'une liste de clients."""
    representatives = set()
    for client in client_list:
        if client in client_to_rep_dict:
            representatives.add(client_to_rep_dict[client])
    return sorted(list(representatives))

def _calculer_taux_occupation(df: pd.DataFrame) -> pd.DataFrame:
    """Recalcule les taux d'occupation Poids et Volume."""
    df['Taux occupation Poids (%)'] = (df['Poids total'] / MAX_POIDS) * 100
    df['Taux occupation Volume (%)'] = (df['Volume total'] / MAX_VOLUME) * 100
    df['Taux d\'occupation (%)'] = df[['Taux occupation Poids (%)', 'Taux occupation Volume (%)']].max(axis=1)
    # Nettoyage des colonnes temporaires
    df = df.drop(columns=['Taux occupation Poids (%)', 'Taux occupation Volume (%)'])
    return df

def _determiner_suggestion_voyage(row: pd.Series, suggestion_dict: dict) -> str:
    """Détermine si la suggestion de camion s'applique au voyage."""
    suggestion = "Non"
    zone = row['Zone']
    
    # Vérifier pour chaque client du voyage si une suggestion est active pour lui
    for client in row['Clients inclus']:
        if zone in suggestion_dict and client in suggestion_dict[zone]:
            if suggestion_dict[zone][client]['Statut'] == 'Proposé':
                suggestion = "Oui (Proposé)"
                break
            elif suggestion_dict[zone][client]['Statut'] == 'Accepté':
                suggestion = "Oui (Accepté)"
                break
    return suggestion


# =====================================================
# PROCESSOR DE LIVRAISONS (MOCKUP pour la démonstration)
# =====================================================

class DeliveryProcessor:
    """Simule le traitement initial des fichiers d'entrée."""

    def __init__(self):
        # MOCK : Initialisation des dictionnaires pour les lookups
        self._bl_to_client_dict = {}
        self._client_to_rep_dict = {}

    def _create_mock_data(self) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Crée des données mock pour la démonstration."""
        
        # MOCK: Création d'un DF de BL détaillés (simule liv_file + ydlogist_file)
        data_bl = {
            'Bon de Livraison': [f'BL{i:03d}' for i in range(1, 40)],
            'Client': [f'C{random.randint(1, 10)}' for _ in range(39)],
            'Ville': ['RABAT', 'CASA', 'TANGER', 'RABAT', 'CASA', 'TANGER'] * 6 + ['RABAT', 'CASA', 'TANGER'],
            'Zone': ['Z1', 'Z2', 'Z3', 'Z1', 'Z2', 'Z3'] * 6 + ['Z1', 'Z2', 'Z3'],
            'Poids': [round(random.uniform(10, 800), 2) for _ in range(39)],
            'Volume': [round(random.uniform(0.1, 4.0), 3) for _ in range(39)],
        }
        df_bl_details = pd.DataFrame(data_bl)
        df_bl_details['Representant'] = df_bl_details['Client'].apply(lambda c: f'R{int(c[1:]) % 3 + 1}')

        self._bl_to_client_dict = df_bl_details.set_index('Bon de Livraison')[['Client', 'Poids', 'Volume']].to_dict('index')
        self._client_to_rep_dict = df_bl_details.set_index('Client')['Representant'].to_dict()

        # MOCK: Regroupement initial en voyages pour l'optimisation
        grouped = df_bl_details.groupby(['Zone', 'Ville', 'Client', 'Representant']).agg(
            BL_inclus=('Bon de Livraison', list),
            Poids_total=('Poids', 'sum'),
            Volume_total=('Volume', 'sum')
        ).reset_index()
        
        # MOCK: Création de voyages estafettes optimisés (Estafette N° simulée)
        df_estafettes_data = []
        for (zone, ville), group in grouped.groupby(['Zone', 'Ville']):
            num_estafette_zone = 1
            current_estafette = {
                'Zone': zone,
                'Ville': ville,
                'Estafette N°': f'{zone}-{num_estafette_zone}',
                'Code Véhicule': 'EST-1T',
                'Poids total': 0.0,
                'Volume total': 0.0,
                'BL inclus': [],
                'Clients inclus': [],
                'Representants inclus': [],
                'Statut Location': 'Non applicable',
                'Matricule chauffeur': f'CH{random.randint(100, 999)}',
                'Nom et prénom chauffeur': f'Nom Prénom {random.randint(1, 50)}',
            }

            for _, row in group.iterrows():
                # Simple logic: start a new estafette if the next client exceeds capacity
                if (current_estafette['Poids total'] + row['Poids_total'] > MAX_POIDS * 0.9) or \
                   (current_estafette['Volume total'] + row['Volume_total'] > MAX_VOLUME * 0.9):
                    
                    if current_estafette['BL inclus']:
                        df_estafettes_data.append(current_estafette)
                    
                    num_estafette_zone += 1
                    current_estafette = {
                        'Zone': zone,
                        'Ville': ville,
                        'Estafette N°': f'{zone}-{num_estafette_zone}',
                        'Code Véhicule': 'EST-1T',
                        'Poids total': 0.0,
                        'Volume total': 0.0,
                        'BL inclus': [],
                        'Clients inclus': [],
                        'Representants inclus': [],
                        'Statut Location': 'Non applicable',
                        'Matricule chauffeur': f'CH{random.randint(100, 999)}',
                        'Nom et prénom chauffeur': f'Nom Prénom {random.randint(1, 50)}',
                    }
                
                # Ajouter la commande au voyage actuel
                current_estafette['Poids total'] += row['Poids_total']
                current_estafette['Volume total'] += row['Volume_total']
                current_estafette['BL inclus'].extend(row['BL_inclus'])
                current_estafette['Clients inclus'].append(row['Client'])
                current_estafette['Representants inclus'].append(row['Representant'])

            if current_estafette['BL inclus']:
                df_estafettes_data.append(current_estafette)

        df_optimized_estafettes = pd.DataFrame(df_estafettes_data)
        
        # Recalculer les colonnes finales
        df_optimized_estafettes = df_optimized_estafettes.rename(columns={
            'Poids total': 'Poids total chargé', 
            'Volume total': 'Volume total chargé'
        })
        df_optimized_estafettes['Taux d\'occupation (%)'] = 0.0
        df_optimized_estafettes = _calculer_taux_occupation(df_optimized_estafettes)
        df_optimized_estafettes['Suggestion Camion'] = 'Non' # Sera mis à jour par TruckRentalProcessor

        return df_optimized_estafettes, df_bl_details, grouped

    def process_delivery_data(self, liv_file, ydlogist_file, wcliegps_file):
        """
        Méthode principale de traitement. 
        Note: Nous utilisons ici les données MOCK pour simuler le résultat complexe.
        """
        # --- Simuler la lecture et le traitement des fichiers ---
        df_optimized_estafettes, df_bl_details, df_grouped = self._create_mock_data()
        
        # Calcul des agrégats pour les onglets (Section 2)
        df_city = df_optimized_estafettes.groupby('Ville').agg(
            {'Poids total chargé': 'sum', 'Volume total chargé': 'sum', 'Estafette N°': 'nunique'}
        ).rename(columns={'Estafette N°': 'Besoin estafette réel', 
                          'Poids total chargé': 'Poids total', 
                          'Volume total chargé': 'Volume total'}).reset_index()
        df_city['Nombre livraisons'] = df_city['Besoin estafette réel'] # Mock
        
        df_grouped_zone = df_grouped.rename(columns={'Poids_total': 'Poids total', 'Volume_total': 'Volume total', 'BL_inclus': 'BLs inclus'})
        
        df_zone = df_optimized_estafettes.groupby('Zone').agg(
            {'Poids total chargé': 'sum', 'Volume total chargé': 'sum', 'Estafette N°': 'nunique'}
        ).rename(columns={'Estafette N°': 'Besoin estafette réel', 
                          'Poids total chargé': 'Poids total', 
                          'Volume total chargé': 'Volume total'}).reset_index()

        return df_grouped, df_city, df_grouped_zone, df_zone, df_optimized_estafettes, df_bl_details


# =====================================================
# PROCESSOR DE LOCATION DE CAMION ET DE GESTION DES VOYAGES
# =====================================================

class TruckRentalProcessor:
    """Gère la logique de location et la modification des voyages par estafette."""
    
    def __init__(self, df_estafettes: pd.DataFrame, df_bl_details: pd.DataFrame):
        self._df_estafettes = df_estafettes.copy()
        # Assurer que df_bl_details est indexé par 'Bon de Livraison' pour un lookup rapide
        self._df_bl_details = df_bl_details.copy().set_index('Bon de Livraison')
        self._bl_to_client_dict = df_bl_details.set_index('Bon de Livraison')[['Client', 'Poids', 'Volume']].to_dict('index')
        self._client_to_rep_dict = df_bl_details.set_index('Client')['Representant'].to_dict()
        
        # Structure de données pour stocker les décisions de location (pour maintenir l'état)
        # { 'Zone': { 'Client': { 'Poids': X, 'Volume': Y, 'Raison': R, 'Statut': 'Proposé' | 'Accepté' | 'Refusé' } } }
        self._suggestion_par_client_zone = {}
        
        # Initialiser les propositions basées sur les données initiales
        self.detecter_propositions()

    def get_df_result(self) -> pd.DataFrame:
        """Retourne le DataFrame de résultat final et à jour."""
        return self._df_estafettes.copy()

    def _update_suggestions_sur_df_estafettes(self):
        """Met à jour la colonne 'Suggestion Camion' après une modification."""
        self._df_estafettes['Suggestion Camion'] = self._df_estafettes.apply(
            lambda row: _determiner_suggestion_voyage(row, self._suggestion_par_client_zone), axis=1
        )

    # ----------------------------------------------------
    # LOGIQUE 1 : LOCATION (Existante)
    # ----------------------------------------------------

    def detecter_propositions(self) -> pd.DataFrame:
        """Détecte les clients nécessitant une proposition de location."""
        
        # 1. Grouper par Client pour vérifier les seuils
        df_client_agg = self._df_bl_details.reset_index().groupby(['Client', 'Zone']).agg(
            Poids_total=('Poids', 'sum'),
            Volume_total=('Volume', 'sum')
        ).reset_index()

        # 2. Identifier les clients qui dépassent le seuil
        df_propositions = df_client_agg[
            (df_client_agg['Poids_total'] > SEUIL_POIDS) | 
            (df_client_agg['Volume_total'] > SEUIL_VOLUME)
        ].copy()

        if df_propositions.empty:
            return pd.DataFrame()

        # 3. Déterminer la raison
        def get_raison(row):
            raisons = []
            if row['Poids_total'] > SEUIL_POIDS:
                raisons.append("Poids dépassé")
            if row['Volume_total'] > SEUIL_VOLUME:
                raisons.append("Volume dépassé")
            return " et ".join(raisons)

        df_propositions['Raison'] = df_propositions.apply(get_raison, axis=1)
        
        # 4. Gérer l'état interne des suggestions et filtrer ce qui a déjà été décidé
        propositions_ouvertes = []
        for index, row in df_propositions.iterrows():
            zone = row['Zone']
            client = row['Client']
            
            if zone not in self._suggestion_par_client_zone:
                self._suggestion_par_client_zone[zone] = {}
            
            # Si le client n'a pas encore de statut ou le statut est 'Proposé'
            if client not in self._suggestion_par_client_zone[zone] or \
               self._suggestion_par_client_zone[zone][client]['Statut'] == 'Proposé':
                
                self._suggestion_par_client_zone[zone][client] = {
                    'Poids': row['Poids_total'],
                    'Volume': row['Volume_total'],
                    'Raison': row['Raison'],
                    'Statut': 'Proposé'
                }
                propositions_ouvertes.append({
                    'Client': client,
                    'Zone': zone,
                    'Poids total (kg)': round(row['Poids_total'], 2),
                    'Volume total (m³)': round(row['Volume_total'], 3),
                    'Raison': row['Raison']
                })
        
        # Mettre à jour la colonne 'Suggestion Camion' après la détection
        self._update_suggestions_sur_df_estafettes()

        return pd.DataFrame(propositions_ouvertes)

    def appliquer_location(self, client: str, accepter: bool) -> Tuple[bool, str, pd.DataFrame]:
        """Applique la décision de location pour un client et met à jour les voyages."""
        
        # 1. Trouver le voyage concerné
        proposition_df = self.detecter_propositions()
        if proposition_df.empty or client not in proposition_df['Client'].astype(str).tolist():
            return False, f"❌ Le client {client} n'a pas de proposition ouverte.", self.get_df_result()

        zone = proposition_df[proposition_df['Client'] == client]['Zone'].iloc[0]

        # 2. Mettre à jour le statut dans l'état interne
        status = 'Accepté' if accepter else 'Refusé'
        self._suggestion_par_client_zone[zone][client]['Statut'] = status
        
        # 3. Mettre à jour le DataFrame des estafettes
        if accepter:
            # Créer un voyage dédié 'CAMION-LOUE' pour ce client
            
            # Récupérer tous les BLs pour ce client
            bls_client = self._df_bl_details.reset_index()
            bls_client = bls_client[bls_client['Client'] == client]['Bon de Livraison'].tolist()
            
            poids_total = self._suggestion_par_client_zone[zone][client]['Poids']
            volume_total = self._suggestion_par_client_zone[zone][client]['Volume']

            # Supprimer les BLs de tous les voyages existants
            self._df_estafettes['BL inclus'] = self._df_estafettes['BL inclus'].apply(
                lambda bl_list: [bl for bl in bl_list if bl not in bls_client]
            )
            
            # Recalculer les poids/volumes et supprimer les voyages vidés
            self._recalculer_voyages()

            # Ajouter le nouveau voyage de location
            new_voyage_data = {
                'Zone': [zone],
                'Ville': [self._df_bl_details.loc[bls_client[0]]['Ville'] if bls_client else 'N/A'],
                'Estafette N°': [f"LOC-{client}"],
                'Code Véhicule': ["CAMION-LOUE"],
                'Poids total chargé': [poids_total],
                'Volume total chargé': [volume_total],
                'BL inclus': [bls_client],
                'Clients inclus': [[client]],
                'Representants inclus': [[self._client_to_rep_dict.get(client, 'N/A')]],
                'Statut Location': ['Accepté'],
                'Matricule chauffeur': ['LOC-1'],
                'Nom et prénom chauffeur': ['Prestataire Externe'],
            }
            new_voyage_df = pd.DataFrame(new_voyage_data)
            self._df_estafettes = pd.concat([self._df_estafettes, new_voyage_df], ignore_index=True)
            self._df_estafettes = _calculer_taux_occupation(self._df_estafettes)
            
            msg = f"✅ Location acceptée pour le client {client}. Un voyage dédié (CAMION-LOUE) a été créé."
        
        else: # Refusé
            # Le BL reste dans les estafettes. On met juste à jour le statut.
            msg = f"✅ Proposition refusée pour le client {client}. La commande reste dans les estafettes existantes."
        
        # Mettre à jour la colonne 'Suggestion Camion'
        self._update_suggestions_sur_df_estafettes()
        
        return True, msg, self.get_df_result()

    def get_details_client(self, client: str) -> Tuple[str, pd.DataFrame]:
        """Retourne les détails et un résumé du client sélectionné pour la location."""
        
        if not self._suggestion_par_client_zone:
            return "Aucune donnée de proposition disponible.", pd.DataFrame()
        
        # Trouver la zone et les BLs
        zone = None
        for z, clients in self._suggestion_par_client_zone.items():
            if client in clients:
                zone = z
                break
        
        if not zone:
            return f"Le client {client} n'a pas de proposition en attente.", pd.DataFrame()

        bls_client = self._df_bl_details.reset_index()
        bls_client = bls_client[bls_client['Client'] == client]

        resume = (
            f"Client : {client}\n"
            f"Zone : {zone}\n"
            f"Poids total : {bls_client['Poids'].sum():.2f} kg\n"
            f"Volume total : {bls_client['Volume'].sum():.3f} m³\n"
            f"Statut actuel de la proposition : {self._suggestion_par_client_zone[zone][client]['Statut']}"
        )
        
        # Formater le DF pour l'affichage (ne garder que les colonnes pertinentes)
        details_df = bls_client[['Bon de Livraison', 'Poids', 'Volume']].copy()
        details_df = details_df.rename(columns={'Poids': 'Poids (kg)', 'Volume': 'Volume (m³)'})
        
        return resume, details_df

    def _recalculer_voyages(self):
        """Met à jour les poids, volumes et BLs des voyages après suppression de BLs."""
        
        new_data = []
        rows_to_keep = []
        for index, row in self._df_estafettes.iterrows():
            bl_list = row['BL inclus']
            if not bl_list:
                continue # Ignore les voyages qui sont devenus vides

            # Recalculer le poids et le volume
            poids_total = sum(self._bl_to_client_dict[bl]['Poids'] for bl in bl_list if bl in self._bl_to_client_dict)
            volume_total = sum(self._bl_to_client_dict[bl]['Volume'] for bl in bl_list if bl in self._bl_to_client_dict)

            row['Poids total chargé'] = poids_total
            row['Volume total chargé'] = volume_total
            row['Clients inclus'] = _get_unique_clients(bl_list, self._bl_to_client_dict)
            row['Representants inclus'] = _get_unique_representatives(row['Clients inclus'], self._client_to_rep_dict)
            
            rows_to_keep.append(row)
        
        self._df_estafettes = pd.DataFrame(rows_to_keep)
        self._df_estafettes = _calculer_taux_occupation(self._df_estafettes)
        
        if 'Estafette N°' in self._df_estafettes.columns:
            # Réassigner un index propre
            self._df_estafettes = self._df_estafettes.reset_index(drop=True)


    # ----------------------------------------------------
    # LOGIQUE 2 : TRANSFERT MANUEL (Nouveau)
    # ----------------------------------------------------

    def transferer_bls(self, zone: str, bls_a_transferer: List[str], estafette_source_num: str, estafette_cible_num: str) -> Tuple[bool, str]:
        """
        Transfère des BLs d'une estafette à une autre dans la même zone
        après vérification des capacités.
        """
        
        if estafette_source_num == estafette_cible_num or not bls_a_transferer:
            return False, "⚠️ Transfert non valide: Source et Cible doivent être différentes et des BLs doivent être sélectionnés."

        # 1. Identifier les indices (indices dans le DF)
        source_filter = (self._df_estafettes['Zone'] == zone) & (self._df_estafettes['Estafette N°'] == estafette_source_num)
        cible_filter = (self._df_estafettes['Zone'] == zone) & (self._df_estafettes['Estafette N°'] == estafette_cible_num)
        
        if source_filter.sum() != 1 or cible_filter.sum() != 1:
            return False, "❌ Erreur interne: Estafette source ou cible introuvable/non unique."

        idx_source = self._df_estafettes[source_filter].index[0]
        idx_cible = self._df_estafettes[cible_filter].index[0]

        # 2. Calculer le poids et le volume à transférer
        poids_transfert = sum(self._bl_to_client_dict.get(bl, {'Poids': 0})['Poids'] for bl in bls_a_transferer)
        volume_transfert = sum(self._bl_to_client_dict.get(bl, {'Volume': 0})['Volume'] for bl in bls_a_transferer)

        # 3. Vérification de la capacité (contre-mesure)
        poids_actuel_cible = self._df_estafettes.loc[idx_cible, 'Poids total chargé']
        volume_actuel_cible = self._df_estafettes.loc[idx_cible, 'Volume total chargé']
        
        nouveau_poids_cible = poids_actuel_cible + poids_transfert
        nouveau_volume_cible = volume_actuel_cible + volume_transfert

        depassement_poids = nouveau_poids_cible > MAX_POIDS
        depassement_volume = nouveau_volume_cible > MAX_VOLUME
        
        if depassement_poids or depassement_volume:
            msg = f"❌ **TRANSFERT REFUSÉ** : Capacité cible dépassée."
            if depassement_poids:
                 msg += f" (Poids: {nouveau_poids_cible:.2f} kg > {MAX_POIDS} kg max)"
            if depassement_volume:
                 msg += f" (Volume: {nouveau_volume_cible:.3f} m³ > {MAX_VOLUME} m³ max)"
            return False, msg

        # 4. Exécution du Transfert
        
        # Mise à jour de la Cible
        self._df_estafettes.loc[idx_cible, 'Poids total chargé'] = nouveau_poids_cible
        self._df_estafettes.loc[idx_cible, 'Volume total chargé'] = nouveau_volume_cible
        
        bl_actuel_cible = self._df_estafettes.loc[idx_cible, 'BL inclus']
        nouvelle_liste_cible = sorted(bl_actuel_cible + bls_a_transferer)
        self._df_estafettes.at[idx_cible, 'BL inclus'] = nouvelle_liste_cible

        # Mise à jour de la Source
        self._df_estafettes.loc[idx_source, 'Poids total chargé'] -= poids_transfert
        self._df_estafettes.loc[idx_source, 'Volume total chargé'] -= volume_transfert
        
        bl_actuel_source = self._df_estafettes.loc[idx_source, 'BL inclus']
        nouvelle_liste_source = [bl for bl in bl_actuel_source if bl not in bls_a_transferer]
        self._df_estafettes.at[idx_source, 'BL inclus'] = nouvelle_liste_source

        # 5. Suppression de l'estafette source si elle est vide
        if not nouvelle_liste_source:
            self._df_estafettes = self._df_estafettes.drop(idx_source).reset_index(drop=True)

        # 6. Recalcul des colonnes dérivées pour les estafettes concernées (Source si non supprimée, Cible)
        indices_a_recalculer = [idx_cible]
        if not nouvelle_liste_source:
             self._recalculer_voyages() # Fait un recalcul complet si un voyage a été supprimé
        else:
             indices_a_recalculer.append(idx_source)
             
             for index in indices_a_recalculer:
                row = self._df_estafettes.loc[index]
                row['Clients inclus'] = _get_unique_clients(row['BL inclus'], self._bl_to_client_dict)
                row['Representants inclus'] = _get_unique_representatives(row['Clients inclus'], self._client_to_rep_dict)
                self._df_estafettes.loc[index] = row # Update row
            
             self._df_estafettes = _calculer_taux_occupation(self._df_estafettes)
             
        # 7. Recalcul de la suggestion camion (car les clients inclus peuvent changer)
        self._update_suggestions_sur_df_estafettes()

        msg = f"✅ Transfert réussi: {len(bls_a_transferer)} BLs transférés de {estafette_source_num} à {estafette_cible_num} (Poids: {poids_transfert:.2f} kg, Volume: {volume_transfert:.3f} m³)."
        return True, msg

# ... (autres classes/fonctions si besoin, mais le minimum est là)
