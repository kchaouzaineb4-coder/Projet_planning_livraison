# backend.py
import pandas as pd
import math
import numpy as np  # Import pour gérer les NaN plus efficacement
import re

# --- Constantes pour la location de camion ---
SEUIL_POIDS = 3000.0    # kg
SEUIL_VOLUME = 9.216    # m³ (ex: 2.4 * 2.4 * 0.8 * 2 = 9.216)
CAMION_CODE = "CAMION-LOUE"


class TruckRentalProcessor:
    """
    Classe pour gérer la logique de proposition et de décision de location de camion
    basée sur les données optimisées.
    """

    def __init__(self, df_optimized):
        """Initialise le processeur avec le DataFrame de base pour la gestion des propositions."""
        # Défensive: si df_optimized est None, on crée un DataFrame vide
        if df_optimized is None:
            df_optimized = pd.DataFrame()
        self.df_base = self._initialize_rental_columns(df_optimized.copy())
        # Initialiser le compteur de camions loués pour générer C1, C2, etc.
        self._next_camion_num = self.df_base[self.df_base.get("Code Véhicule", "") == CAMION_CODE].shape[0] + 1

    def _initialize_rental_columns(self, df):
        """Ajoute les colonnes d'état de location si elles n'existent pas et les renomme."""

        # Si df est vide, créer colonnes minimales pour éviter KeyError plus loin
        if df.empty:
            df = pd.DataFrame(columns=[
                "Zone", "Estafette N°", "Poids total chargé", "Volume total chargé",
                "Client(s) inclus", "Représentant(s) inclus", "BL inclus"
            ])

        # Renommage défensif si les colonnes existent
        rename_map = {}
        if "Poids total chargé" in df.columns:
            rename_map["Poids total chargé"] = "Poids total"
        if "Volume total chargé" in df.columns:
            rename_map["Volume total chargé"] = "Volume total"
        if "Client(s) inclus" in df.columns:
            rename_map["Client(s) inclus"] = "Client commande"
        if "Représentant(s) inclus" in df.columns:
            rename_map["Représentant(s) inclus"] = "Représentant"
        if rename_map:
            df.rename(columns=rename_map, inplace=True)

        # Assurer que les colonnes de décision existent
        if "Location_camion" not in df.columns:
            df["Location_camion"] = False
        if "Location_proposee" not in df.columns:
            df["Location_proposee"] = False
        if "Code Véhicule" not in df.columns:
            df["Code Véhicule"] = "ESTAFETTE"  # Valeur par défaut

        # S'assurer qu'il existe une colonne Estafette N° (si non, initialiser à 99999)
        if "Estafette N°" not in df.columns:
            df["Estafette N°"] = 99999
        df["Estafette N°"] = pd.to_numeric(df["Estafette N°"], errors='coerce').fillna(99999).astype(int)

        # Camion N° par défaut à partir d'Estafette N°
        if "Camion N°" not in df.columns:
            df["Camion N°"] = df["Estafette N°"].apply(lambda x: f"E{int(x)}" if pd.notna(x) and x != 0 else "À Optimiser")

        # Mettre à jour les "Camion N°" pour les lignes de location (si déjà là)
        mask_camion_loue = df.get("Code Véhicule", "") == CAMION_CODE
        if mask_camion_loue.any():
            df.loc[mask_camion_loue, "Camion N°"] = [f"C{i+1}" for i in range(mask_camion_loue.sum())]

        # S'assurer que les BLs sont bien des chaînes
        if "BL inclus" in df.columns:
            df['BL inclus'] = df['BL inclus'].astype(str)
        else:
            df['BL inclus'] = ""

        # Standardiser noms colonnes 'Poids total' et 'Volume total' même si absentes
        if "Poids total" not in df.columns:
            df["Poids total"] = 0.0
        if "Volume total" not in df.columns:
            df["Volume total"] = 0.0

        return df

    def detecter_propositions(self):
        """
        Regroupe les données par Client commande pour déterminer si le SEUIL est dépassé.
        Retourne un DataFrame des clients proposables.
        """
        # Exclure les clients déjà traités (ceux où Location_proposee est True)
        processed_clients = self.df_base[self.df_base.get("Location_proposee", False)]["Client commande"].unique() \
            if "Client commande" in self.df_base.columns else []

        # Filtrer toutes les lignes de df_base pour exclure les commandes des clients déjà traités
        if "Client commande" in self.df_base.columns:
            df_pending = self.df_base[~self.df_base["Client commande"].isin(processed_clients)].copy()
        else:
            # Si colonne manquante, rien à proposer
            return pd.DataFrame()

        if df_pending.empty:
            return pd.DataFrame()  # Retourne un DataFrame vide si tout est déjà traité

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

        if not propositions.empty:
            propositions["Raison"] = propositions.apply(get_raison, axis=1)
            propositions.rename(columns={
                "Client commande": "Client",
                "Poids_sum": "Poids total (kg)",
                "Volume_sum": "Volume total (m³)",
                "Zones": "Zones concernées"
            }, inplace=True)

        return propositions.sort_values(["Poids total (kg)", "Volume total (m³)"], ascending=False).reset_index(drop=True)

    def get_details_client(self, client):
        """Récupère et formate les détails de tous les BLs/voyages pour un client."""
        # Filtrer en s'assurant que 'Client commande' est bien dans le df
        if "Client commande" not in self.df_base.columns:
            return "Erreur: Colonne 'Client commande' manquante.", pd.DataFrame()

        data = self.df_base[self.df_base["Client commande"] == client].copy()

        if data.empty:
            return f"Aucune donnée pour {client}", pd.DataFrame()

        total_poids = data["Poids total"].sum() if "Poids total" in data.columns else 0.0
        total_volume = data["Volume total"].sum() if "Volume total" in data.columns else 0.0

        # Déterminer l'état actuel pour ce client
        etat = "Non décidée"

        if (data.get("Location_camion", False)).any():
            etat = "Location ACCEPTÉE"
        elif (data.get("Location_proposee", False)).any():
            etat = "Proposition REFUSÉE"

        # Colonnes pour l'affichage des détails (adaptées au DataFrame optimisé)
        colonnes_affichage = [
            "Zone", "Camion N°", "Poids total", "Volume total", "BL inclus", "Taux d'occupation (%)",
            "Client commande", "Représentant", "Location_camion", "Location_proposee", "Code Véhicule"
        ]

        # Réorganiser et sélectionner les colonnes existantes
        data_display = data[[col for col in colonnes_affichage if col in data.columns]]

        resume = f"Client {client} — Poids total : {total_poids:.1f} kg ; Volume total : {total_volume:.3f} m³ | État : {etat}"

        # Retourner (resume, DataFrame) — stylisation côté streamlit si souhaitée
        return resume, data_display

    def appliquer_location(self, client, accepter):
        """Applique ou refuse la location pour un client et met à jour le DataFrame de base."""
        if "Client commande" not in self.df_base.columns:
            return False, "Client commande absent du dataset.", self.df_base

        mask = self.df_base["Client commande"] == client
        if not mask.any():
            return False, "Client introuvable.", self.df_base

        df = self.df_base.copy()

        # Récupérer les données totales (somme de tous les voyages du client)
        poids_total = df.loc[mask, "Poids total"].sum()
        volume_total = df.loc[mask, "Volume total"].sum()
        bl_concat = ";".join(df.loc[mask, "BL inclus"].astype(str).unique().tolist())
        representants = ";".join(sorted(df.loc[mask, "Représentant"].astype(str).unique().tolist()))
        zones = ";".join(sorted(df.loc[mask, "Zone"].astype(str).unique().tolist()))

        # Taux d'occupation (basé sur des seuils plus importants pour le camion loué)
        TAUX_POIDS_MAX_LOC = 5000  # kg, par exemple
        TAUX_VOLUME_MAX_LOC = 15  # m3, par exemple

        taux_occu = 0.0
        if TAUX_POIDS_MAX_LOC > 0 or TAUX_VOLUME_MAX_LOC > 0:
            taux_occu = max(poids_total / TAUX_POIDS_MAX_LOC * 100 if TAUX_POIDS_MAX_LOC > 0 else 0,
                            volume_total / TAUX_VOLUME_MAX_LOC * 100 if TAUX_VOLUME_MAX_LOC > 0 else 0)

        if accepter:
            # --- MODIFICATION CLÉ ICI ---
            # 1. Générer le numéro de camion C1, C2, C3...
            camion_num_final = f"C{self._next_camion_num}"

            # 2. Créer un nouveau voyage (une seule ligne) pour le camion loué
            new_row = pd.DataFrame([{
                "Zone": zones,
                "Estafette N°": 0,  # Mettre à 0 pour le tri
                "Poids total": poids_total,
                "Volume total": volume_total,
                "BL inclus": bl_concat,
                "Client commande": client,
                "Représentant": representants,
                "Location_camion": True,
                "Location_proposee": True,
                "Code Véhicule": CAMION_CODE,
                "Camion N°": camion_num_final,  # Assigner le nouveau numéro
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
            if "Estafette N°" in df.columns:
                df.loc[mask, "Camion N°"] = df.loc[mask, "Estafette N°"].apply(lambda x: f"E{int(x)}" if pd.notna(x) else "E?")
            else:
                df.loc[mask, "Camion N°"] = "E?"

            self.df_base = df
            return True, f"❌ Proposition REFUSÉE pour {client}. Les commandes restent réparties en Estafettes.", self.detecter_propositions()

    def get_df_result(self):
        """
        Retourne le DataFrame optimisé final avec les modifications de location.
        Inclut la modification demandée : fusion de 'Estafette N°' et 'Camion N°'
        dans la seule colonne 'Véhicule N°'.
        """
        df_result = self.df_base.copy()

        # Renommer les colonnes pour les rendre conformes à l'affichage final
        rename_map = {}
        if "Poids total" in df_result.columns:
            rename_map["Poids total"] = "Poids total chargé"
        if "Volume total" in df_result.columns:
            rename_map["Volume total"] = "Volume total chargé"
        if "Client commande" in df_result.columns:
            rename_map["Client commande"] = "Client(s) inclus"
        if "Représentant" in df_result.columns:
            rename_map["Représentant"] = "Représentant(s) inclus"
        if "Camion N°" in df_result.columns:
            rename_map["Camion N°"] = "Véhicule N°"

        if rename_map:
            df_result.rename(columns=rename_map, inplace=True)

        # Tri final: Les camions loués (Code_Tri=0) en premier, puis les estafettes.
        df_result['Code_Tri'] = df_result.get('Code Véhicule', 'ESTAFETTE').apply(lambda x: 0 if x == CAMION_CODE else 1)

        # Assurer Estafette N° existe pour le tri (si non, créer colonne temporaire)
        if "Estafette N°" not in df_result.columns:
            df_result["Estafette N°"] = 99999

        # Tri: camions d'abord, puis estafettes par numéro puis véhicule n°
        sort_cols = ["Code_Tri", "Estafette N°", "Véhicule N°", "Zone"]
        existing_sort_cols = [c for c in sort_cols if c in df_result.columns]
        df_result = df_result.sort_values(by=existing_sort_cols, ascending=[True] * len(existing_sort_cols))

        # Suppression des colonnes de tri et temporaires
        df_result = df_result.drop(columns=['Code_Tri', 'Estafette N°'], errors='ignore')

        # Définition des colonnes finales pour l'affichage (sans Estafette N° mais avec Véhicule N°)
        final_cols_display = [
            "Zone",
            "Véhicule N°",  # Contient maintenant E1, E2, C1, C2...
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

        return df_result[[col for col in final_cols_display if col in df_result.columns]]


class DeliveryProcessor:

    # =====================================================
    # ✅ Fonction principale : traitement complet
    # =====================================================
    def process_delivery_data(self, liv_file, ydlogist_file, wcliegps_file):
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
            df_final["Volume de l'US"] = pd.to_numeric(df_final.get("Volume de l'US", 0), errors='coerce').fillna(0) / 1_000_000
            df_final["Volume total"] = df_final["Volume de l'US"] * df_final["Quantité livrée US"]

            # Regroupement par ville et client (pour l'affichage "Livraisons Client/Ville")
            df_grouped, df_city = self._group_data(df_final)

            # Calcul du besoin en estafette par ville
            df_city = self._calculate_estafette_need(df_city)

            # Nouveau tableau : ajout Zone
            # On renomme 'Client' en 'Client de l'estafette' (convention utilisée dans ton code)
            df_grouped_zone = self._add_zone(df_grouped.rename(columns={"Client": "Client de l'estafette"}))

            # Filtrer les livraisons avec "Zone inconnue"
            df_grouped_zone = df_grouped_zone[df_grouped_zone["Zone"] != "Zone inconnue"].copy()

            # 🆕 Groupement par zone
            df_zone = self._group_by_zone(df_grouped_zone)

            # 🆕 Calcul du besoin en estafette par zone
            df_zone = self._calculate_estafette_need(df_zone)

            # 🆕 Calcul des voyages optimisés
            df_optimized_estafettes = self._calculate_optimized_estafette(df_grouped_zone)

            # 🆕 Retourne les DataFrames + l'instance TruckRentalProcessor
            return df_grouped, df_city, df_grouped_zone, df_zone, df_optimized_estafettes

        except Exception as e:
            raise Exception(f"❌ Erreur lors du traitement des données : {str(e)}")

    # =====================================================
    # 🔹 Chargement des données
    # =====================================================
    def _load_livraisons(self, liv_file):
        df = pd.read_excel(liv_file)

        # ✅ CORRECTION BUG : Renommer la colonne 'N° BON LIVRAISON' en 'No livraison'
        if 'N° BON LIVRAISON' in df.columns:
            df.rename(columns={'N° BON LIVRAISON': 'No livraison'}, inplace=True)

        # Renommage de la 5ème colonne (index 4) en 'Quantité livrée US'
        if len(df.columns) > 4 and "Quantité livrée US" not in df.columns:
            df.rename(columns={df.columns[4]: "Quantité livrée US"}, inplace=True)

        return df

    def _load_ydlogist(self, file_path):
        df = pd.read_excel(file_path)
        # Renommage des colonnes Unité Volume (index 16) et Poids de l'US (index 13)
        if len(df.columns) > 16 and "Unité Volume" not in df.columns:
            df.rename(columns={df.columns[16]: "Unité Volume"}, inplace=True)
        if len(df.columns) > 13 and "Poids de l'US" not in df.columns:
            df.rename(columns={df.columns[13]: "Poids de l'US"}, inplace=True)
        return df

    def _load_wcliegps(self, wcliegps_file):
        df_clients = pd.read_excel(wcliegps_file)

        # Identifier et renommer la colonne Représentant (index 16, colonne Q)
        if len(df_clients.columns) > 16 and "Représentant" not in df_clients.columns:
            df_clients.rename(columns={df_clients.columns[16]: "Représentant"}, inplace=True)

        # S'assurer que les colonnes 'Client' et 'Représentant' existent pour la jointure
        required_cols = ["Client", "Ville", "Représentant"]
        for col in required_cols:
            if col not in df_clients.columns:
                raise ValueError(f"La colonne '{col}' est manquante dans le fichier clients. Veuillez vérifier le format.")

        return df_clients[["Client", "Ville", "Représentant"]].copy()

    # =====================================================
    # 🔹 Filtrage
    # =====================================================
    def _filter_initial_data(self, df):
        clients_exclus = [
            "AMECAP", "SANA", "SOPAL", "SOPALGAZ", "SOPALSERV", "SOPALTEC",
            "SOPALALG", "AQUA", "WINOX", "QUIVEM", "SANISTONE",
            "SOPAMAR", "SOPALAFR", "SOPALINTER"
        ]
        # Gestion défensive des colonnes existantes
        if "Type livraison" in df.columns and "Client commande" in df.columns:
            return df[(df["Type livraison"] != "SDC") & (~df["Client commande"].isin(clients_exclus))]
        else:
            # Si colonnes manquantes, retourner df inchangé
            return df

    # =====================================================
    # 🔹 Calcul Poids
    # =====================================================
    def _calculate_weights(self, df):
        # Conversion Poids de l'US
        if "Poids de l'US" in df.columns:
            df["Poids de l'US"] = pd.to_numeric(
                df["Poids de l'US"].astype(str).str.replace(",", ".").str.replace(r"[^\d.]", "", regex=True),
                errors="coerce"
            ).fillna(0)
        else:
            df["Poids de l'US"] = 0.0

        # Conversion Quantité livrée US
        if "Quantité livrée US" in df.columns:
            df["Quantité livrée US"] = pd.to_numeric(df["Quantité livrée US"], errors="coerce").fillna(0)
        else:
            df["Quantité livrée US"] = 0.0

        df["Poids total"] = df["Quantité livrée US"] * df["Poids de l'US"]
        cols = ["No livraison", "Article", "Client commande", "Poids total", "Quantité livrée US", "Poids de l'US"]
        return df[[c for c in cols if c in df.columns]]

    # =====================================================
    # 🔹 Calcul Volume
    # =====================================================
    def _calculate_volumes(self, df_liv, df_art):
        cols_liv = ["No livraison", "Article", "Quantité livrée US", "Client commande"]
        df_liv_sel = df_liv[[c for c in cols_liv if c in df_liv.columns]]
        df_art_sel = df_art[["Article", "Volume de l'US", "Unité Volume"]].copy() if all(c in df_art.columns for c in ["Article", "Volume de l'US"]) else df_art.copy()

        # Conversion Volume de l'US
        if "Volume de l'US" in df_art_sel.columns:
            df_art_sel["Volume de l'US"] = pd.to_numeric(df_art_sel["Volume de l'US"].astype(str).str.replace(",", "."), errors="coerce")
        return pd.merge(df_liv_sel, df_art_sel, on="Article", how="left")

    # =====================================================
    # 🔹 Fusion
    # =====================================================
    def _merge_delivery_data(self, df_poids, df_vol):
        # On fusionne avec les colonnes de poids pour garder les colonnes initiales
        left = df_poids.drop(columns=["Quantité livrée US", "Poids de l'US"], errors='ignore')
        merged = pd.merge(left, df_vol, on=["No livraison", "Article", "Client commande"], how="left")
        return merged

    # =====================================================
    # 🔹 Ajout Client, Ville et Représentant
    # =====================================================
    def _add_city_client_info(self, df, df_clients):
        # Jointure pour ajouter Ville et Représentant
        # Attention: 'Client commande' est le code du BL, 'Client' est le code du client dans df_clients
        if "Client commande" not in df.columns:
            raise ValueError("Colonne 'Client commande' manquante dans les livraisons.")
        return pd.merge(df, df_clients[["Client", "Ville", "Représentant"]], left_on="Client commande", right_on="Client", how="left")

    # =====================================================
    # 🔹 Groupement par Livraison/Client/Ville/Représentant
    # =====================================================
    def _group_data(self, df):
        # La colonne "Client commande" devient "Client" ici pour le regroupement
        if not all(c in df.columns for c in ["No livraison", "Client", "Ville", "Représentant"]):
            # Si le df n'a pas toutes les colonnes, retourner df minimal
            df_grouped = df.copy()
            df_city = pd.DataFrame()
            return df_grouped, df_city

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
    def _calculate_estafette_need(self, df):
        poids_max = 1550  # kg
        volume_max = 4.608  # m3 (1.2 * 1.2 * 0.8 * 4)

        if "Poids total" in df.columns and "Volume total" in df.columns:
            df["Besoin estafette (poids)"] = df["Poids total"].apply(lambda p: math.ceil(p / poids_max) if poids_max > 0 else 0)
            df["Besoin estafette (volume)"] = df["Volume total"].apply(lambda v: math.ceil(v / volume_max) if volume_max > 0 else 0)
            df["Besoin estafette réel"] = df[["Besoin estafette (poids)", "Besoin estafette (volume)"]].max(axis=1)
        else:
            # ne rien faire si colonnes manquantes
            pass
        return df

    # =====================================================
    # 🔹 Ajout Zone
    # =====================================================
    def _add_zone(self, df):
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

        def get_zone(ville):
            ville = str(ville).upper().strip()
            for z, villes in zones.items():
                if ville in villes:
                    return z
            return "Zone inconnue"

        if "Ville" in df.columns:
            df["Zone"] = df["Ville"].apply(get_zone)
        else:
            df["Zone"] = "Zone inconnue"
        return df

    # =====================================================
    # 🆕 Groupement par Zone
    # =====================================================
    def _group_by_zone(self, df_grouped_zone):
        if "Zone" not in df_grouped_zone.columns:
            return pd.DataFrame(columns=["Zone", "Poids total", "Volume total", "Nombre livraisons"])
        df_zone = df_grouped_zone.groupby("Zone", as_index=False).agg({
            "Poids total": "sum",
            "Volume total": "sum",
            "No livraison": "count"
        }).rename(columns={"No livraison": "Nombre livraisons"})
        return df_zone

    # =====================================================
    # 🆕 Calcul des voyages optimisés par Estafette
    # =====================================================
    def _calculate_optimized_estafette(self, df_grouped_zone):
        # === Capacités max ===
        MAX_POIDS = 1550    # kg
        MAX_VOLUME = 4.608  # m3 (1.2 * 1.2 * 0.8 * 4)

        resultats = []
        estafette_num = 1  # compteur global unique pour les estafettes

        # === Boucle par zone ===
        if "Zone" not in df_grouped_zone.columns:
            return pd.DataFrame(columns=["Zone", "Estafette N°", "Poids total chargé", "Volume total chargé",
                                         "Client(s) inclus", "Représentant(s) inclus", "BL inclus"])

        for zone, group in df_grouped_zone.groupby("Zone"):
            # Trier les BL par poids décroissant (heuristique First Fit Decreasing)
            # Si la colonne 'Poids total' a un autre nom, essayer 'Poids total chargé'
            poids_col = "Poids total" if "Poids total" in group.columns else ("Poids total chargé" if "Poids total chargé" in group.columns else None)
            volume_col = "Volume total" if "Volume total" in group.columns else ("Volume total chargé" if "Volume total chargé" in group.columns else None)

            if poids_col is None or volume_col is None:
                # si manquant, ignorer la zone
                continue

            group_sorted = group.sort_values(by=poids_col, ascending=False).reset_index(drop=True)
            estafettes = []  # liste des estafettes déjà créées pour la zone

            for idx, row in group_sorted.iterrows():
                bl = str(row.get("No livraison", row.get("BL inclus", "")))
                poids = float(row.get(poids_col, 0.0) or 0.0)
                volume = float(row.get(volume_col, 0.0) or 0.0)
                client = str(row.get("Client de l'estafette", row.get("Client", "")))
                representant = str(row.get("Représentant", ""))

                placed = False

                # Chercher la 1ère estafette où ça rentre
                for e in estafettes:
                    if e["poids"] + poids <= MAX_POIDS and e["volume"] + volume <= MAX_VOLUME:
                        e["poids"] += poids
                        e["volume"] += volume
                        e["bls"].append(bl)
                        # Ajout du client/représentant à l'ensemble (set) pour l'unicité
                        for c in client.split(','):
                            e["clients"].add(c.strip())
                        for r in representant.split(','):
                            e["representants"].add(r.strip())
                        placed = True
                        break

                # Si aucun emplacement trouvé -> créer une nouvelle estafette
                if not placed:
                    estafettes.append({
                        "poids": poids,
                        "volume": volume,
                        "bls": [bl],
                        "clients": {c.strip() for c in client.split(',') if c.strip()},
                        "representants": {r.strip() for r in representant.split(',') if r.strip()},
                        "num_global": estafette_num  # On assigne le numéro global ici
                    })
                    estafette_num += 1  # On incrémente le compteur global seulement si on crée une nouvelle estafette

            # Sauvegarder les résultats
            for e in estafettes:
                clients_list = ", ".join(sorted(list(e["clients"]))) if e["clients"] else ""
                representants_list = ", ".join(sorted(list(e["representants"]))) if e["representants"] else ""
                resultats.append([
                    zone,
                    e["num_global"],  # Utilisation du numéro global
                    e["poids"],
                    e["volume"],
                    clients_list,
                    representants_list,
                    ";".join([str(x) for x in e["bls"]])
                ])

        # === Créer un DataFrame résultat ===
        df_estafettes = pd.DataFrame(resultats, columns=[
            "Zone", "Estafette N°", "Poids total chargé", "Volume total chargé",
            "Client(s) inclus", "Représentant(s) inclus", "BL inclus"
        ])

        # CALCUL DU TAUX D'OCCUPATION
        if not df_estafettes.empty:
            df_estafettes["Taux Poids (%)"] = (df_estafettes["Poids total chargé"] / MAX_POIDS) * 100
            df_estafettes["Taux Volume (%)"] = (df_estafettes["Volume total chargé"] / MAX_VOLUME) * 100
            df_estafettes["Taux d'occupation (%)"] = df_estafettes[["Taux Poids (%)", "Taux Volume (%)"]].max(axis=1).round(2)
        else:
            df_estafettes["Taux d'occupation (%)"] = []

        # Initialisation des colonnes de location pour le TruckRentalProcessor
        df_estafettes["Location_camion"] = False
        df_estafettes["Location_proposee"] = False
        df_estafettes["Code Véhicule"] = "ESTAFETTE"
        # La colonne "Camion N°" doit refléter le numéro d'Estafette (E1, E2...)
        if "Estafette N°" in df_estafettes.columns:
            df_estafettes["Camion N°"] = df_estafettes["Estafette N°"].apply(lambda x: f"E{int(x)}")
        else:
            df_estafettes["Camion N°"] = "E?"

        # Nettoyage et formatage final
        df_estafettes = df_estafettes.drop(columns=["Taux Poids (%)", "Taux Volume (%)"], errors='ignore')

        return df_estafettes

    # =====================================================
    # 🆕 Transfert des BL d'une estafette à une autre dans la même zone
    # =====================================================
    def transfer_bl_between_estafettes(self, source_estafette_num, target_estafette_num, bl_list):
        """
        Transfert une ou plusieurs BLs d'une estafette source à une estafette cible
        dans la même zone. Le poids et volume sont recalculés automatiquement.

        :param source_estafette_num: Numéro de l'estafette source (E1, E2...)
        :param target_estafette_num: Numéro de l'estafette cible (E1, E2...)
        :param bl_list: Liste de BLs à transférer (list ou string séparés par ;)
        :return: (success: bool, message: str)
        """
        df = self.df_base.copy()

        # Normaliser la liste de BL
        if isinstance(bl_list, str):
            bl_list = [b.strip() for b in bl_list.split(';') if b.strip()]

        if source_estafette_num == target_estafette_num:
            return False, "❌ L'estafette source et cible sont identiques."

        # Vérifier que les deux estafettes existent
        mask_source = df["Camion N°"] == source_estafette_num
        mask_target = df["Camion N°"] == target_estafette_num

        if not mask_source.any():
            return False, f"❌ Estafette source {source_estafette_num} introuvable."
        if not mask_target.any():
            return False, f"❌ Estafette cible {target_estafette_num} introuvable."

        # Vérifier que les BLs existent dans l'estafette source
        bl_source = df.loc[mask_source, "BL inclus"].str.split(';').explode().str.strip()
        if not all(bl in bl_source.values for bl in bl_list):
            return False, "❌ Certains BLs n'existent pas dans l'estafette source."

        # Transfert BLs : enlever de la source, ajouter à la cible
        for bl in bl_list:
            # Retirer le BL de l'estafette source (toutes les lignes matching)
            df.loc[mask_source, "BL inclus"] = df.loc[mask_source, "BL inclus"].apply(
                lambda x: ";".join([b for b in x.split(';') if b.strip() != bl])
            )

            # Ajouter le BL à l'estafette cible (ajout simple en fin)
            df.loc[mask_target, "BL inclus"] = df.loc[mask_target, "BL inclus"].apply(
                lambda x: ";".join([i for i in (x.split(';') + [bl]) if i and i.strip()])
            )

        # Recalculer poids et volume pour les deux estafettes
        def recalc_totals_for_mask(local_mask):
            # Pour chaque ligne correspondant au mask, recalculer Poids total chargé et Volume total chargé
            for idx in df[local_mask].index:
                bls_current = [b.strip() for b in str(df.at[idx, "BL inclus"]).split(';') if b.strip()]
                total_poids = 0.0
                total_vol = 0.0
                # Somme des poids/volumes correspondants aux BLs parmi toutes les lignes du df (original)
                for bl in bls_current:
                    # Chercher lignes qui contiennent exactement ce BL (sécurité regex word boundary)
                    pattern = rf"(?:^|;)\s*{re.escape(bl)}\s*(?:;|$)"
                    matched = df["BL inclus"].astype(str).str.contains(pattern, regex=True, na=False)
                    # additionner les valeurs numériques disponibles
                    if "Poids total chargé" in df.columns:
                        total_poids += df.loc[matched, "Poids total chargé"].sum()
                    elif "Poids total" in df.columns:
                        total_poids += df.loc[matched, "Poids total"].sum()
                    if "Volume total chargé" in df.columns:
                        total_vol += df.loc[matched, "Volume total chargé"].sum()
                    elif "Volume total" in df.columns:
                        total_vol += df.loc[matched, "Volume total"].sum()

                # Écrire les totaux recalculés (création des colonnes si nécessaire)
                df.at[idx, "Poids total chargé"] = float(total_poids)
                df.at[idx, "Volume total chargé"] = float(total_vol)
                # Recalcul taux occupation
                df.at[idx, "Taux d'occupation (%)"] = max(
                    (total_poids / 1550) * 100 if total_poids is not None else 0,
                    (total_vol / 4.608) * 100 if total_vol is not None else 0
                )

        recalc_totals_for_mask(mask_source)
        recalc_totals_for_mask(mask_target)

        # Mettre à jour le DataFrame
        self.df_base = df
        return True, f"✅ BLs transférés de {source_estafette_num} vers {target_estafette_num} avec succès."


# =====================================================
# 🆕 CLASSE : Gestion du transfert de BLs entre estafettes
# =====================================================
class TruckTransferManager:
    def __init__(self, df_livraisons):
        """
        df_livraisons : DataFrame contenant au moins les colonnes suivantes :
        ['Zone', 'Estafette', 'BL', 'Poids (kg)', 'Volume (m³)']
        """
        self.df = df_livraisons.copy()

    def get_estafettes_in_zone(self, zone):
        """Retourne la liste unique des estafettes dans une zone donnée."""
        df_zone = self.df[self.df["Zone"] == zone]
        return sorted(df_zone["Estafette"].dropna().unique().tolist())

    def get_bls_of_estafette(self, zone, estafette):
        """Retourne la liste des BLs associés à une estafette donnée dans une zone."""
        df_filt = self.df[(self.df["Zone"] == zone) & (self.df["Estafette"] == estafette)]
        return sorted(df_filt["BL"].dropna().astype(str).unique().tolist())

    def check_transfer(self, zone, estafette_source, estafette_cible, bls_transfer):
        """
        Vérifie si le transfert est possible selon les contraintes :
        - poids <= 1550 kg
        - volume <= 4.608 m³
        Retourne : (bool, dict)
        """
        SEUIL_POIDS_LOCAL = 1550
        SEUIL_VOLUME_LOCAL = 4.608

        df_zone = self.df[self.df["Zone"] == zone]

        # Données source et cible
        df_src = df_zone[df_zone["Estafette"] == estafette_source]
        df_dst = df_zone[df_zone["Estafette"] == estafette_cible]

        # Calcul totaux actuels
        poids_src, vol_src = df_src["Poids (kg)"].sum(), df_src["Volume (m³)"].sum()
        poids_dst, vol_dst = df_dst["Poids (kg)"].sum(), df_dst["Volume (m³)"].sum()

        # BLs à transférer
        df_bls = df_src[df_src["BL"].astype(str).isin(bls_transfer)]
        poids_bls, vol_bls = df_bls["Poids (kg)"].sum(), df_bls["Volume (m³)"].sum()

        # Simulation du transfert
        poids_src_new = poids_src - poids_bls
        vol_src_new = vol_src - vol_bls
        poids_dst_new = poids_dst + poids_bls
        vol_dst_new = vol_dst + vol_bls

        # Vérification des seuils
        transfert_autorise = (poids_dst_new <= SEUIL_POIDS_LOCAL) and (vol_dst_new <= SEUIL_VOLUME_LOCAL)

        info = {
            "Zone": zone,
            "Estafette source": estafette_source,
            "Estafette cible": estafette_cible,
            "Poids transféré (kg)": poids_bls,
            "Volume transféré (m³)": vol_bls,
            "Poids source avant/après": f"{poids_src:.2f} → {poids_src_new:.2f}",
            "Volume source avant/après": f"{vol_src:.3f} → {vol_src_new:.3f}",
            "Poids cible avant/après": f"{poids_dst:.2f} → {poids_dst_new:.2f}",
            "Volume cible avant/après": f"{vol_dst:.3f} → {vol_dst_new:.3f}",
            "Résultat": "✅ TRANSFERT AUTORISÉ" if transfert_autorise else "❌ TRANSFERT REFUSÉ : CAPACITÉ DÉPASSÉE"
        }

        return transfert_autorise, info
