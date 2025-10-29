import pandas as pd
import math
import numpy as np 
from typing import List, Tuple, Dict, Any

# --- Constantes pour la location de camion ---
SEUIL_POIDS = 3000.0    # kg (Seuil de poids pour proposer une location)
SEUIL_VOLUME = 9.216    # m³ (Seuil de volume pour proposer une location)
CAMION_CODE = "CAMION-LOUE"
MAX_POIDS_ESTAFETTE = 1550    # kg (Capacité max Estafette)
MAX_VOLUME_ESTAFETTE = 4.608  # m3 (Capacité max Estafette)

class TruckRentalProcessor:
    """
    Classe pour gérer la logique de proposition, de décision et d'ajustement manuel 
    de location de camion, basée sur les données optimisées.
    """
     
    def __init__(self, df_optimized: pd.DataFrame, df_granular_bls: pd.DataFrame):
        """
        Initialise le processeur.
        
        :param df_optimized: DataFrame des voyages optimisés (une ligne par Estafette/Voyage).
        :param df_granular_bls: DataFrame des données granulaires (une ligne par BL/livraison) pour le recalcul.
        """
        self.df_granular_bls = df_granular_bls.copy()
        self.df_base = self._initialize_rental_columns(df_optimized.copy())
        
        # Initialiser le compteur de camions loués (C1, C2, etc.)
        self._next_camion_num = self.df_base[self.df_base["Code Véhicule"] == CAMION_CODE].shape[0] + 1

    def _initialize_rental_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Ajoute/renomme les colonnes d'état de location pour la cohérence interne."""
        
        # Renommage pour la cohérence interne
        df.rename(columns={
            "Poids total chargé": "Poids total",
            "Volume total chargé": "Volume total",
            "Client(s) inclus": "Client commande",
            "Représentant(s) inclus": "Représentant"
        }, inplace=True)

        # Assurer que les colonnes de décision existent
        if "Location_camion" not in df.columns:
            df["Location_camion"] = False
        if "Location_proposee" not in df.columns:
            df["Location_proposee"] = False
        if "Code Véhicule" not in df.columns:
            df["Code Véhicule"] = "ESTAFETTE"
        if "Camion N°" not in df.columns:
            # Assigner le numéro Estafette (E1, E2...) comme numéro Camion par défaut
            df["Camion N°"] = df["Estafette N°"].apply(lambda x: f"E{int(x)}" if pd.notna(x) and x != 0 else "À Optimiser")
            
        # Mettre à jour les "Camion N°" pour les lignes de location (si déjà là)
        mask_camion_loue = df["Code Véhicule"] == CAMION_CODE
        if mask_camion_loue.any():
            # Assigner C1, C2, C3... en fonction de l'ordre d'apparition
            df.loc[mask_camion_loue, "Camion N°"] = [f"C{i+1}" for i in range(mask_camion_loue.sum())]

        # S'assurer que les BLs sont bien des chaînes
        df['BL inclus'] = df['BL inclus'].astype(str)
        
        # Correction: s'assurer que 'Estafette N°' est numérique pour le tri
        df["Estafette N°"] = pd.to_numeric(df["Estafette N°"], errors='coerce').fillna(99999).astype(int)

        return df

    def detecter_propositions(self) -> pd.DataFrame:
        """
        Regroupe les données par Client pour déterminer si le SEUIL (poids/volume) est dépassé.
        Retourne un DataFrame des clients proposables, excluant ceux déjà traités.
        """
        # Exclure les clients déjà traités (ceux où Location_proposee est True)
        processed_clients = self.df_base[self.df_base["Location_proposee"]]["Client commande"].unique()
        
        # Filtrer toutes les lignes de df_base pour exclure les commandes des clients déjà traités
        df_pending = self.df_base[~self.df_base["Client commande"].isin(processed_clients)].copy()

        if df_pending.empty:
            return pd.DataFrame() 

        # Utiliser df_pending pour l'agrégation
        grouped = df_pending.groupby("Client commande").agg(
            Poids_sum=pd.NamedAgg(column="Poids total", aggfunc="sum"),
            Volume_sum=pd.NamedAgg(column="Volume total", aggfunc="sum"),
            Zones=pd.NamedAgg(column="Zone", aggfunc=lambda s: ", ".join(sorted(set(s.astype(str).tolist()))))
        ).reset_index()

        # Filtrage : Poids ou Volume dépasse le seuil
        propositions = grouped[(grouped["Poids_sum"] >= SEUIL_POIDS) | (grouped["Volume_sum"] >= SEUIL_VOLUME)].copy()

        # Création de la colonne Raison
        def get_raison(row):
            raisons = []
            if row["Poids_sum"] >= SEUIL_POIDS:
                raisons.append(f"Poids ≥ {SEUIL_POIDS} kg")
            if row["Volume_sum"] >= SEUIL_VOLUME:
                raisons.append(f"Volume ≥ {SEUIL_VOLUME:.3f} m³")
            return " & ".join(raisons)

        propositions["Raison"] = propositions.apply(get_raison, axis=1)
        propositions.rename(columns={
             "Client commande": "Client",
             "Poids_sum": "Poids total (kg)",
             "Volume_sum": "Volume total (m³)",
             "Zones": "Zones concernées"
          }, inplace=True)

        return propositions.sort_values(["Poids total (kg)", "Volume total (m³)"], ascending=False).reset_index(drop=True)

    def get_details_client(self, client: str) -> Tuple[str, pd.io.formats.style.Styler]:
        """Récupère et formate les détails de tous les voyages optimisés pour un client."""
        
        if "Client commande" not in self.df_base.columns:
             return "Erreur: Colonne 'Client commande' manquante.", pd.DataFrame()
             
        data = self.df_base[self.df_base["Client commande"] == client].copy()
        
        if data.empty:
            return f"Aucune donnée pour {client}", pd.DataFrame().style

        total_poids = data["Poids total"].sum()
        total_volume = data["Volume total"].sum()
        
        # Déterminer l'état actuel pour ce client
        etat = "Non décidée" 
        
        if (data["Location_camion"]).any():
            etat = "Location ACCEPTÉE"
        elif (data["Location_proposee"]).any():
            etat = "Proposition REFUSÉE"
        
        # Colonnes pour l'affichage des détails (adaptées au DataFrame optimisé)
        colonnes_affichage = [
             "Zone", "Camion N°", "Poids total", "Volume total", "BL inclus", "Taux d'occupation (%)",
             "Client commande", "Représentant", "Location_camion", "Location_proposee", "Code Véhicule"
           ]
        
        # Réorganiser et sélectionner les colonnes
        data_display = data[[col for col in colonnes_affichage if col in data.columns]]
        
        resume = f"Client {client} — Poids total : {total_poids:.1f} kg ; Volume total : {total_volume:.3f} m³ | État : {etat}"
        
        # Formater les colonnes pour l'affichage
        data_display_styled = data_display.style.format({
            "Poids total": "{:.2f} kg",
            "Volume total": "{:.3f} m³",
            "Taux d'occupation (%)": "{:.2f}%"
        }).set_table_attributes('data-table-name="details-client-table"')

        return resume, data_display_styled

    def appliquer_location(self, client: str, accepter: bool) -> Tuple[bool, str, pd.DataFrame]:
        """Applique ou refuse la location pour un client et met à jour le DataFrame de base."""
        mask = self.df_base["Client commande"] == client
        if not mask.any():
            return False, "Client introuvable.", self.df_base

        df = self.df_base.copy()
        
        # Récupérer les données totales (somme de tous les voyages du client)
        poids_total = df.loc[mask, "Poids total"].sum()
        volume_total = df.loc[mask, "Volume total"].sum()
        
        # Concaténer tous les BLs associés aux voyages du client
        all_bls = df.loc[mask, "BL inclus"].str.split(';').explode().str.strip().unique()
        bl_concat = ";".join([b for b in all_bls if b])
        
        # Concaténer tous les représentants et zones
        representants = ";".join(sorted(df.loc[mask, "Représentant"].astype(str).str.split(',').explode().str.strip().unique().tolist()))
        zones = ";".join(sorted(df.loc[mask, "Zone"].astype(str).unique().tolist()))
        
        # Taux d'occupation (basé sur des seuils de camion loué, plus importants)
        TAUX_POIDS_MAX_LOC = 5000 # kg, par exemple 
        TAUX_VOLUME_MAX_LOC = 15 # m3, par exemple
        
        taux_occu = max(poids_total / TAUX_POIDS_MAX_LOC * 100, volume_total / TAUX_VOLUME_MAX_LOC * 100)
        
        if accepter:
            # 1. Générer le numéro de camion C1, C2, C3...
            camion_num_final = f"C{self._next_camion_num}"
            
            # 2. Créer un nouveau voyage (une seule ligne) pour le camion loué
            new_row = pd.DataFrame([{
                "Zone": zones,
                "Estafette N°": 0, # Mettre à 0 pour le tri
                "Poids total": poids_total,
                "Volume total": volume_total,
                "BL inclus": bl_concat,
                "Client commande": client,
                "Représentant": representants,
                "Location_camion": True,
                "Location_proposee": True,
                "Code Véhicule": CAMION_CODE,
                "Camion N°": camion_num_final, # Assigner le nouveau numéro
                "Taux d'occupation (%)": taux_occu,
            }])
            
            # 3. Mettre à jour le compteur
            self._next_camion_num += 1

            # 4. Supprimer les lignes d'estafette existantes pour ce client
            df = df[~mask]
            
            # 5. Ajouter la nouvelle ligne
            df = pd.concat([df, new_row], ignore_index=True)
            
            self.df_base = df
            return True, f"✅ Location ACCEPTÉE pour {client}. Les commandes ont été consolidées dans le véhicule {camion_num_final}.", self.detecter_propositions()
        else:
            # Refuser la proposition (les commandes restent dans les estafettes optimisées)
            # Marquer Location_proposee à True pour qu'elles n'apparaissent plus
            df.loc[mask, ["Location_proposee", "Location_camion", "Code Véhicule"]] = [True, False, "ESTAFETTE"]
            
            # Mettre à jour 'Camion N°' pour s'assurer que c'est bien l'estafette E1, E2...
            df.loc[mask, "Camion N°"] = df.loc[mask, "Estafette N°"].apply(lambda x: f"E{int(x)}")
            
            self.df_base = df
            return True, f"❌ Proposition REFUSÉE pour {client}. Les commandes restent réparties en Estafettes.", self.detecter_propositions()

    def transfer_bl_between_estafettes(self, source_estafette_num: str, target_estafette_num: str, bl_list: List[str]) -> Tuple[bool, str, pd.DataFrame]:
        """
        CORRIGÉ. Transfère une ou plusieurs BLs d'une estafette source à une estafette cible
        dans le DataFrame optimisé. Le poids et volume sont recalculés à partir des données granulaires.
        
        :param source_estafette_num: Numéro de l'estafette source (E1, E2...)
        :param target_estafette_num: Numéro de l'estafette cible (E1, E2...)
        :param bl_list: Liste de BLs à transférer
        :return: (success: bool, message: str, df_base: pd.DataFrame)
        """
        
        df = self.df_base.copy()
        
        # Normaliser la liste de BL
        if isinstance(bl_list, str):
            bl_list = [b.strip() for b in bl_list.split(';') if b.strip()]
        if not bl_list:
             return False, "❌ Aucune BL spécifiée pour le transfert.", self.df_base
        
        if source_estafette_num == target_estafette_num:
            return False, "❌ L'estafette source et cible sont identiques.", self.df_base
        
        # Vérifier que les deux estafettes existent
        mask_source = df["Camion N°"] == source_estafette_num
        mask_target = df["Camion N°"] == target_estafette_num
        
        if not mask_source.any():
            return False, f"❌ Estafette source {source_estafette_num} introuvable.", self.df_base
        if not mask_target.any():
            return False, f"❌ Estafette cible {target_estafette_num} introuvable.", self.df_base
        
        # Extraction des BLs existants
        bls_source_existants = [b.strip() for b in df.loc[mask_source, "BL inclus"].iloc[0].split(';') if b.strip()]
        
        # Vérifier que TOUS les BLs à transférer sont bien dans la source
        if not all(bl in bls_source_existants for bl in bl_list):
             missing_bls = [bl for bl in bl_list if bl not in bls_source_existants]
             return False, f"❌ Certains BLs sont manquants dans l'estafette source {source_estafette_num}: {', '.join(missing_bls)}.", self.df_base

        # Vérifier que le transfert ne dépasse pas la capacité cible
        bl_data_to_move = self.df_granular_bls[self.df_granular_bls["No livraison"].astype(str).isin(bl_list)]
        poids_a_ajouter = bl_data_to_move["Poids total"].sum()
        volume_a_ajouter = bl_data_to_move["Volume total"].sum()
        
        poids_cible_actuel = df.loc[mask_target, "Poids total"].iloc[0]
        volume_cible_actuel = df.loc[mask_target, "Volume total"].iloc[0]

        if (poids_cible_actuel + poids_a_ajouter > MAX_POIDS_ESTAFETTE or
            volume_cible_actuel + volume_a_ajouter > MAX_VOLUME_ESTAFETTE):
            return False, f"❌ Le transfert des BLs ferait dépasser la capacité de l'Estafette cible {target_estafette_num}.", self.df_base

        # --- Mise à jour de la colonne BL inclus ---
        # 1. Retirer les BLs de la source
        new_bls_source = [b for b in bls_source_existants if b not in bl_list]
        df.loc[mask_source, "BL inclus"] = ";".join(new_bls_source)
        
        # 2. Ajouter les BLs à la cible
        bls_target_existants = [b.strip() for b in df.loc[mask_target, "BL inclus"].iloc[0].split(';') if b.strip()]
        new_bls_target = bls_target_existants + bl_list
        df.loc[mask_target, "BL inclus"] = ";".join(new_bls_target)

        # --- Recalculer poids, volume, taux d'occupation, clients et représentants ---
        for estafette_num in [source_estafette_num, target_estafette_num]:
            mask = df["Camion N°"] == estafette_num
            
            current_bl_string = df.loc[mask, "BL inclus"].iloc[0]
            current_bls = [b.strip() for b in current_bl_string.split(';') if b.strip()]

            # Rechercher les données granulaires pour tous les BLs dans l'Estafette
            bl_data = self.df_granular_bls[self.df_granular_bls["No livraison"].astype(str).isin(current_bls)]

            new_poids = bl_data["Poids total"].sum()
            new_volume = bl_data["Volume total"].sum()

            df.loc[mask, "Poids total"] = new_poids
            df.loc[mask, "Volume total"] = new_volume

            # Recalculer Taux d'occupation
            new_taux_occu = max(new_poids / MAX_POIDS_ESTAFETTE * 100, new_volume / MAX_VOLUME_ESTAFETTE * 100)
            df.loc[mask, "Taux d'occupation (%)"] = new_taux_occu.round(2)
            
            # Recalculer Client(s) inclus et Représentant(s) inclus (liste unique triée)
            new_clients = ", ".join(sorted(bl_data["Client de l'estafette"].astype(str).unique().tolist()))
            new_reps = ", ".join(sorted(bl_data["Représentant"].astype(str).unique().tolist()))
            
            df.loc[mask, "Client commande"] = new_clients
            df.loc[mask, "Représentant"] = new_reps

        # Mettre à jour le DataFrame de base
        self.df_base = df
        
        # Gérer la suppression si l'estafette source est vide
        mask_source_empty = self.df_base["Camion N°"] == source_estafette_num
        if self.df_base.loc[mask_source_empty, "Poids total"].iloc[0] < 0.001: # Si le poids est proche de zéro
             self.df_base = self.df_base[~mask_source_empty].reset_index(drop=True)
             return True, f"✅ BLs transférés. L'Estafette source {source_estafette_num} a été supprimée car elle est vide. Le plan de livraison est mis à jour.", self.df_base
        
        return True, f"✅ BLs transférés de {source_estafette_num} vers {target_estafette_num} avec succès. Le plan de livraison est mis à jour.", self.df_base


    def get_df_result(self) -> pd.DataFrame:
        """
        Retourne le DataFrame optimisé final avec les modifications de location, 
        dans le format d'affichage demandé.
        """
        df_result = self.df_base.copy()
        
        # Renommer les colonnes pour les rendre conformes à l'affichage final
        df_result.rename(columns={
             "Poids total": "Poids total chargé",
             "Volume total": "Volume total chargé",
             "Client commande": "Client(s) inclus",
             "Représentant": "Représentant(s) inclus",
             "Camion N°": "Véhicule N°" 
        }, inplace=True)
        
        # Tri final: Les camions loués (Code_Tri=0) en premier, puis les estafettes.
        df_result['Code_Tri'] = df_result['Code Véhicule'].apply(lambda x: 0 if x == CAMION_CODE else 1)
        
        # Utiliser 'Véhicule N°' (qui contient E1, E2 ou C1, C2...) pour le tri des véhicules
        df_result = df_result.sort_values(by=["Code_Tri", "Estafette N°", "Véhicule N°", "Zone"], ascending=[True, True, True, True])

        # Suppression des colonnes de tri et temporaires
        df_result = df_result.drop(columns=['Code_Tri'], errors='ignore')
        df_result = df_result.drop(columns=['Estafette N°'], errors='ignore')
        
        # Définition des colonnes finales pour l'affichage
        final_cols_display = [
             "Zone", 
             "Véhicule N°", 
             "Poids total chargé", 
             "Volume total chargé", 
             "Client(s) inclus", 
             "Représentant(s) inclus", 
             "BL inclus", 
             "Taux d'occupation (%)",
             "Location_camion", 
             "Location_proposee", 
             "Code Véhicule"
        ]

        # Sélection des colonnes dans l'ordre final
        return df_result[[col for col in final_cols_display if col in df_result.columns]]


class DeliveryProcessor:

    # =====================================================
    # ✅ Fonction principale : traitement complet
    # =====================================================
    def process_delivery_data(self, liv_file: str, ydlogist_file: str, wcliegps_file: str) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """
        Gère le flux complet de lecture, préparation, groupement et optimisation des livraisons.
        Retourne les DataFrames intermédiaires et finaux.
        """
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

            # Charger le fichier clients/représentants
            df_clients = self._load_wcliegps(wcliegps_file)

            # Ajouter Client, Ville et Représentant
            df_final = self._add_city_client_info(df_merged, df_clients)

            # Calcul Volume total en m3
            df_final["Volume de l'US"] = pd.to_numeric(df_final["Volume de l'US"], errors='coerce').fillna(0) / 1_000_000
            df_final["Volume total"] = df_final["Volume de l'US"] * df_final["Quantité livrée US"]

            # Regroupement par ville et client (pour l'affichage "Livraisons Client/Ville")
            df_grouped, df_city = self._group_data(df_final)

            # Calcul du besoin en estafette par ville
            df_city = self._calculate_estafette_need(df_city)

            # Nouveau tableau : ajout Zone
            # Renommer "Client" (Client du BL) en "Client de l'estafette" avant l'ajout de zone
            df_grouped_zone = self._add_zone(df_grouped.rename(columns={"Client": "Client de l'estafette"}))

            # Filtrer les livraisons avec "Zone inconnue"
            df_grouped_zone = df_grouped_zone[df_grouped_zone["Zone"] != "Zone inconnue"].copy()
            
            # Stocker les données granulaires (BL-level) nécessaires au TruckRentalProcessor pour les ajustements manuels.
            df_granular_bls = df_grouped_zone.copy()
            
            # 🆕 Groupement par zone
            df_zone = self._group_by_zone(df_grouped_zone)
            
            # 🆕 Calcul du besoin en estafette par zone
            df_zone = self._calculate_estafette_need(df_zone)

            # 🆕 Calcul des voyages optimisés 
            df_optimized_estafettes = self._calculate_optimized_estafette(df_grouped_zone)

            # Retourne tous les DataFrames, y compris le granular pour le TruckRentalProcessor
            return df_grouped, df_city, df_grouped_zone, df_zone, df_optimized_estafettes, df_granular_bls

        except Exception as e:
            raise Exception(f"❌ Erreur lors du traitement des données : {str(e)}")

    # =====================================================
    # 🔹 Chargement des données
    # =====================================================
    def _load_livraisons(self, liv_file: str) -> pd.DataFrame:
        df = pd.read_excel(liv_file)
        
        # ✅ CORRECTION BUG : Renommer la colonne 'N° BON LIVRAISON' en 'No livraison'
        if 'N° BON LIVRAISON' in df.columns:
            df.rename(columns={'N° BON LIVRAISON': 'No livraison'}, inplace=True)
            
        # Renommage de la 5ème colonne (index 4) en 'Quantité livrée US'
        if len(df.columns) > 4:
            df.rename(columns={df.columns[4]: "Quantité livrée US"}, inplace=True)
            
        return df

    def _load_ydlogist(self, file_path: str) -> pd.DataFrame:
        df = pd.read_excel(file_path)
        # Renommage des colonnes Unité Volume (index 16) et Poids de l'US (index 13)
        if len(df.columns) > 16:
            df.rename(columns={df.columns[16]: "Unité Volume"}, inplace=True)
        if len(df.columns) > 13:
            df.rename(columns={df.columns[13]: "Poids de l'US"}, inplace=True)
            
        return df

    def _load_wcliegps(self, wcliegps_file: str) -> pd.DataFrame:
        df_clients = pd.read_excel(wcliegps_file)
        
        # Identifier et renommer la colonne Représentant (index 16, colonne Q)
        if len(df_clients.columns) > 16:
            df_clients.rename(columns={df_clients.columns[16]: "Représentant"}, inplace=True)
        
        required_cols = ["Client", "Ville", "Représentant"]
        for col in required_cols:
            if col not in df_clients.columns:
                 # Gérer le cas où la colonne n'a pas été trouvée à l'index 16 ou est manquante
                 raise ValueError(f"La colonne '{col}' est manquante dans le fichier clients. Veuillez vérifier le format.")
        
        return df_clients[["Client", "Ville", "Représentant"]].copy()

    # =====================================================
    # 🔹 Filtrage
    # =====================================================
    def _filter_initial_data(self, df: pd.DataFrame) -> pd.DataFrame:
        clients_exclus = [
             "AMECAP", "SANA", "SOPAL", "SOPALGAZ", "SOPALSERV", "SOPALTEC",
             "SOPALALG", "AQUA", "WINOX", "QUIVEM", "SANISTONE",
             "SOPAMAR", "SOPALAFR", "SOPALINTER"
        ]
        return df[(df["Type livraison"] != "SDC") & (~df["Client commande"].isin(clients_exclus))]

    # =====================================================
    # 🔹 Calcul Poids
    # =====================================================
    def _calculate_weights(self, df: pd.DataFrame) -> pd.DataFrame:
        # Conversion Poids de l'US
        df["Poids de l'US"] = pd.to_numeric(df["Poids de l'US"].astype(str).str.replace(",", ".")
                                             .str.replace(r"[^\d.]", "", regex=True), errors="coerce").fillna(0)
        
        # Conversion Quantité livrée US
        df["Quantité livrée US"] = pd.to_numeric(df["Quantité livrée US"], errors="coerce").fillna(0)
        
        df["Poids total"] = df["Quantité livrée US"] * df["Poids de l'US"]
        return df[["No livraison", "Article", "Client commande", "Poids total", "Quantité livrée US", "Poids de l'US"]]

    # =====================================================
    # 🔹 Calcul Volume
    # =====================================================
    def _calculate_volumes(self, df_liv: pd.DataFrame, df_art: pd.DataFrame) -> pd.DataFrame:
        df_liv_sel = df_liv[["No livraison", "Article", "Quantité livrée US", "Client commande"]]
        df_art_sel = df_art[["Article", "Volume de l'US", "Unité Volume"]].copy()
        
        # Conversion Volume de l'US
        df_art_sel["Volume de l'US"] = pd.to_numeric(df_art_sel["Volume de l'US"].astype(str).str.replace(",", "."),
                                                     errors="coerce")
        return pd.merge(df_liv_sel, df_art_sel, on="Article", how="left")

    # =====================================================
    # 🔹 Fusion
    # =====================================================
    def _merge_delivery_data(self, df_poids: pd.DataFrame, df_vol: pd.DataFrame) -> pd.DataFrame:
        # On fusionne avec les colonnes de poids pour garder les colonnes initiales
        return pd.merge(df_poids.drop(columns=["Quantité livrée US", "Poids de l'US"], errors='ignore'), 
                        df_vol, on=["No livraison", "Article", "Client commande"], how="left")


    # =====================================================
    # 🔹 Ajout Client, Ville et Représentant
    # =====================================================
    def _add_city_client_info(self, df: pd.DataFrame, df_clients: pd.DataFrame) -> pd.DataFrame:
        # Jointure pour ajouter Ville et Représentant
        # Attention: 'Client commande' est le code du BL, 'Client' est le code du client dans df_clients
        return pd.merge(df, df_clients[["Client", "Ville", "Représentant"]],
                        left_on="Client commande", right_on="Client", how="left")

    # =====================================================
    # 🔹 Groupement par Livraison/Client/Ville/Représentant
    # =====================================================
    def _group_data(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
        # La colonne "Client commande" est utilisée pour la jointure, la colonne "Client" issue de la jointure
        # est le code client réel (WCLIEGPS)
        df_grouped = df.groupby(["No livraison", "Client", "Ville", "Représentant"], as_index=False).agg({
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

    # =====================================================
    # 🔹 Calcul besoin estafette (Applicable à Ville ou Zone)
    # =====================================================
    def _calculate_estafette_need(self, df: pd.DataFrame) -> pd.DataFrame:
        poids_max = MAX_POIDS_ESTAFETTE  # kg
        volume_max = MAX_VOLUME_ESTAFETTE # m3
        
        if "Poids total" in df.columns and "Volume total" in df.columns:
            df["Besoin estafette (poids)"] = df["Poids total"].apply(lambda p: math.ceil(p / poids_max))
            df["Besoin estafette (volume)"] = df["Volume total"].apply(lambda v: math.ceil(v / volume_max))
            df["Besoin estafette réel"] = df[["Besoin estafette (poids)", "Besoin estafette (volume)"]].max(axis=1)
        else:
            print("Colonnes Poids total ou Volume total manquantes pour le calcul estafette.")
        return df

    # =====================================================
    # 🔹 Ajout Zone
    # =====================================================
    def _add_zone(self, df: pd.DataFrame) -> pd.DataFrame:
        zones = {
             "Zone 1": ["TUNIS", "ARIANA", "MANOUBA", "BEN AROUS", "BIZERTE", "MATEUR",
                         "MENZEL BOURGUIBA", "UTIQUE"],
             "Zone 2": ["NABEUL", "HAMMAMET", "KORBA", "MENZEL TEMIME", "KELIBIA", "SOLIMAN"],
             "Zone 3": ["SOUSSE", "MONASTIR", "MAHDIA", "KAIROUAN"],
             "Zone 4": ["GABÈS", "MEDENINE", "ZARZIS", "DJERBA"],
             "Zone 5": ["GAFSA", "KASSERINE", "TOZEUR", "NEFTA", "DOUZ"],
             "Zone 6": ["JENDOUBA", "BÉJA", "LE KEF", "TABARKA", "SILIANA"],
             "Zone 7": ["SFAX"]
           }

        def get_zone(ville: Any) -> str:
            ville = str(ville).upper().strip()
            for z, villes in zones.items():
                if ville in villes:
                    return z
            return "Zone inconnue"

        df["Zone"] = df["Ville"].apply(get_zone)
        return df

    # =====================================================
    # 🆕 Groupement par Zone
    # =====================================================
    def _group_by_zone(self, df_grouped_zone: pd.DataFrame) -> pd.DataFrame:
        df_zone = df_grouped_zone.groupby("Zone", as_index=False).agg({
            "Poids total": "sum",
            "Volume total": "sum",
            "No livraison": "count"
        }).rename(columns={"No livraison": "Nombre livraisons"})
        return df_zone

    # =====================================================
    # 🆕 Calcul des voyages optimisés par Estafette (Bin Packing)
    # =====================================================
    def _calculate_optimized_estafette(self, df_grouped_zone: pd.DataFrame) -> pd.DataFrame:
        # === Capacités max ===
        MAX_POIDS = MAX_POIDS_ESTAFETTE   # kg
        MAX_VOLUME = MAX_VOLUME_ESTAFETTE # m3

        resultats = []
        estafette_num = 1  # compteur global unique pour les estafettes

        # === Boucle par zone ===
        for zone, group in df_grouped_zone.groupby("Zone"):
            # Trier les BL par poids décroissant (heuristique First Fit Decreasing)
            group_sorted = group.sort_values(by="Poids total", ascending=False).reset_index()
            estafettes = []  # liste des estafettes déjà créées pour la zone
            
            for _, row in group_sorted.iterrows():
                bl = str(row["No livraison"])
                poids = row["Poids total"]
                volume = row["Volume total"]
                # Le nom de colonne est "Client de l'estafette" ici suite au rename dans process_delivery_data
                client = str(row["Client de l'estafette"]) 
                representant = str(row["Représentant"])
                placed = False
                
                # Chercher la 1ère estafette où ça rentre
                for e in estafettes:
                    if e["poids"] + poids <= MAX_POIDS and e["volume"] + volume <= MAX_VOLUME:
                        e["poids"] += poids
                        e["volume"] += volume
                        e["bls"].append(bl)
                        # Ajout du client/représentant à l'ensemble (set) pour l'unicité
                        for c in client.split(','): e["clients"].add(c.strip())
                        for r in representant.split(','): e["representants"].add(r.strip())
                        placed = True
                        break
                
                # Si aucun emplacement trouvé -> créer une nouvelle estafette
                if not placed:
                    estafettes.append({
                         "poids": poids,
                         "volume": volume,
                         "bls": [bl],
                         "clients": {c.strip() for c in client.split(',')},
                         "representants": {r.strip() for r in representant.split(',')},
                         "num_global": estafette_num # On assigne le numéro global ici
                    })
                    estafette_num += 1 # On incrémente le compteur global
            
            # Sauvegarder les résultats
            for e in estafettes:
                clients_list = ", ".join(sorted(list(e["clients"])))
                representants_list = ", ".join(sorted(list(e["representants"])))
                resultats.append([
                     zone,
                     e["num_global"], 
                     e["poids"],
                     e["volume"],
                     clients_list,    
                     representants_list,
                     ";".join(e["bls"])
                ])
                
        # === Créer un DataFrame résultat ===
        df_estafettes = pd.DataFrame(resultats, columns=["Zone", "Estafette N°", "Poids total chargé", "Volume total chargé", "Client(s) inclus", "Représentant(s) inclus", "BL inclus"])
        
        # CALCUL DU TAUX D'OCCUPATION
        df_estafettes["Taux Poids (%)"] = (df_estafettes["Poids total chargé"] / MAX_POIDS) * 100
        df_estafettes["Taux Volume (%)"] = (df_estafettes["Volume total chargé"] / MAX_VOLUME) * 100
        df_estafettes["Taux d'occupation (%)"] = df_estafettes[["Taux Poids (%)", "Taux Volume (%)"]].max(axis=1).round(2)
        
        # Initialisation des colonnes de location pour le TruckRentalProcessor
        df_estafettes["Location_camion"] = False
        df_estafettes["Location_proposee"] = False
        df_estafettes["Code Véhicule"] = "ESTAFETTE"
        # La colonne "Camion N°" doit refléter le numéro d'Estafette (E1, E2...)
        df_estafettes["Camion N°"] = df_estafettes["Estafette N°"].apply(lambda x: f"E{int(x)}")
        
        # Nettoyage et formatage final
        df_estafettes = df_estafettes.drop(columns=["Taux Poids (%)", "Taux Volume (%)"]) 
        
        return df_estafettes