import pandas as pd
import math
import numpy as np # Import pour gérer les NaN plus efficacement

# --- Constantes pour la location de camion ---
SEUIL_POIDS = 3000.0    # kg
SEUIL_VOLUME = 9.216    # m³ (ex: 2.4 * 2.4 * 0.8 * 2 = 9.216)
CAMION_CODE = "CAMION-LOUE"

import pandas as pd

# --- Constantes de déclenchement de proposition ---
SEUIL_POIDS = 3000.0    # kg → déclenche une proposition si le client dépasse ce seuil
SEUIL_VOLUME = 9.216    # m³ → déclenche une proposition si le client dépasse ce seuil
CAMION_CODE = "CAMION"


class TruckRentalProcessor:
    """
    Classe pour gérer la logique de proposition et de décision de location de camion
    basée sur les données optimisées.
    """

    def __init__(self, df_optimized):
        """Initialise le processeur avec le DataFrame de base pour la gestion des propositions."""
        self.df_base = self._initialize_rental_columns(df_optimized.copy())
        self._next_camion_num = self.df_base[self.df_base["Code Véhicule"] == CAMION_CODE].shape[0] + 1

    def _initialize_rental_columns(self, df):
        """Ajoute les colonnes d'état de location si elles n'existent pas et les renomme."""
        df.rename(columns={
            "Poids total chargé": "Poids total",
            "Volume total chargé": "Volume total",
            "Client(s) inclus": "Client commande",
            "Représentant(s) inclus": "Représentant"
        }, inplace=True)

        if "Location_camion" not in df.columns:
            df["Location_camion"] = False
        if "Location_proposee" not in df.columns:
            df["Location_proposee"] = False
        if "Code Véhicule" not in df.columns:
            df["Code Véhicule"] = "ESTAFETTE"
        if "Camion N°" not in df.columns:
            df["Camion N°"] = df["Estafette N°"].apply(lambda x: f"E{int(x)}" if pd.notna(x) and x != 0 else "À Optimiser")

        mask_camion_loue = df["Code Véhicule"] == CAMION_CODE
        if mask_camion_loue.any():
            df.loc[mask_camion_loue, "Camion N°"] = [f"C{i+1}" for i in range(mask_camion_loue.sum())]

        df['BL inclus'] = df['BL inclus'].astype(str)
        df["Estafette N°"] = pd.to_numeric(df["Estafette N°"], errors='coerce').fillna(99999).astype(int)

        return df

    def detecter_propositions(self):
        """
        Détecte les clients dont le total Poids ou Volume dépasse les seuils
        et crée une proposition de camion pour l'ensemble de leurs BLs.
        """
        processed_clients = self.df_base[self.df_base["Location_proposee"]]["Client commande"].unique()
        df_pending = self.df_base[~self.df_base["Client commande"].isin(processed_clients)].copy()

        if df_pending.empty:
            return pd.DataFrame()

        # Agréger par client pour savoir si une proposition est nécessaire
        grouped = df_pending.groupby("Client commande").agg(
            Poids_sum=pd.NamedAgg(column="Poids total", aggfunc="sum"),
            Volume_sum=pd.NamedAgg(column="Volume total", aggfunc="sum"),
            Zones=pd.NamedAgg(column="Zone", aggfunc=lambda s: ", ".join(sorted(set(s.astype(str).tolist()))))
        ).reset_index()

        # Clients dont le total dépasse le seuil
        propositions_clients = grouped[(grouped["Poids_sum"] >= SEUIL_POIDS) | (grouped["Volume_sum"] >= SEUIL_VOLUME)].copy()

        # Création de la colonne Raison
        def get_raison(row):
            raisons = []
            if row["Poids_sum"] >= SEUIL_POIDS:
                raisons.append(f"Poids total ≥ {SEUIL_POIDS} kg")
            if row["Volume_sum"] >= SEUIL_VOLUME:
                raisons.append(f"Volume total ≥ {SEUIL_VOLUME:.3f} m³")
            return " & ".join(raisons)

        propositions_clients["Raison"] = propositions_clients.apply(get_raison, axis=1)
        propositions_clients.rename(columns={
            "Client commande": "Client",
            "Poids_sum": "Poids total (kg)",
            "Volume_sum": "Volume total (m³)",
            "Zones": "Zones concernées"
        }, inplace=True)

        return propositions_clients.sort_values(["Poids total (kg)", "Volume total (m³)"], ascending=False).reset_index(drop=True)

    def get_details_client(self, client):
        """Récupère tous les BLs d’un client, même ceux qui individuellement ne dépassent pas le seuil."""
        data = self.df_base[self.df_base["Client commande"] == client].copy()

        if data.empty:
            return f"Aucune donnée pour {client}", pd.DataFrame()

        total_poids = data["Poids total"].sum()
        total_volume = data["Volume total"].sum()

        etat = "Non décidée"
        if data["Location_camion"].any():
            etat = "Location ACCEPTÉE"
        elif data["Location_proposee"].any():
            etat = "Proposition REFUSÉE"

        colonnes_affichage = [
            "Zone", "Camion N°", "Poids total", "Volume total", "BL inclus", "Taux d'occupation (%)",
            "Client commande", "Représentant", "Location_camion", "Location_proposee", "Code Véhicule"
        ]
        data_display = data[[col for col in colonnes_affichage if col in data.columns]]

        resume = f"Client {client} — Poids total : {total_poids:.1f} kg ; Volume total : {total_volume:.3f} m³ | État : {etat}"

        data_display_styled = data_display.style.format({
            "Poids total": "{:.2f} kg",
            "Volume total": "{:.3f} m³",
            "Taux d'occupation (%)": "{:.2f}%"
        }).set_table_attributes('data-table-name="details-client-table"')

        return resume, data_display_styled

    def appliquer_location(self, client, accepter):
        """Accepte ou refuse la location et met à jour le DataFrame."""
        mask = self.df_base["Client commande"] == client
        if not mask.any():
            return False, "Client introuvable.", self.df_base

        df = self.df_base.copy()
        poids_total = df.loc[mask, "Poids total"].sum()
        volume_total = df.loc[mask, "Volume total"].sum()
        bl_concat = ";".join(df.loc[mask, "BL inclus"].astype(str).unique().tolist())
        representants = ";".join(sorted(df.loc[mask, "Représentant"].astype(str).unique().tolist()))
        zones = ";".join(sorted(df.loc[mask, "Zone"].astype(str).unique().tolist()))

        taux_occu = max(poids_total / 5000 * 100, volume_total / 15 * 100)

        if accepter:
            camion_num_final = f"C{self._next_camion_num}"
            new_row = pd.DataFrame([{
                "Zone": zones,
                "Estafette N°": 0,
                "Poids total": poids_total,
                "Volume total": volume_total,
                "BL inclus": bl_concat,
                "Client commande": client,
                "Représentant": representants,
                "Location_camion": True,
                "Location_proposee": True,
                "Code Véhicule": CAMION_CODE,
                "Camion N°": camion_num_final,
                "Taux d'occupation (%)": taux_occu
            }])
            self._next_camion_num += 1
            df = df[~mask]
            df = pd.concat([df, new_row], ignore_index=True)
            self.df_base = df
            return True, f"✅ Location ACCEPTÉE pour {client}.", self.detecter_propositions()
        else:
            df.loc[mask, ["Location_proposee", "Location_camion", "Code Véhicule"]] = [True, False, "ESTAFETTE"]
            df.loc[mask, "Camion N°"] = df.loc[mask, "Estafette N°"].apply(lambda x: f"E{int(x)}")
            self.df_base = df
            return True, f"❌ Proposition REFUSÉE pour {client}.", self.detecter_propositions()

    def get_df_result(self):
        df_result = self.df_base.copy()
        df_result.rename(columns={
            "Poids total": "Poids total chargé",
            "Volume total": "Volume total chargé",
            "Client commande": "Client(s) inclus",
            "Représentant": "Représentant(s) inclus",
            "Camion N°": "Véhicule N°"
        }, inplace=True)

        df_result['Code_Tri'] = df_result['Code Véhicule'].apply(lambda x: 0 if x == CAMION_CODE else 1)
        df_result = df_result.sort_values(by=["Code_Tri", "Estafette N°", "Véhicule N°", "Zone"], ascending=[True, True, True, True])
        df_result = df_result.drop(columns=['Code_Tri', 'Estafette N°'], errors='ignore')

        final_cols_display = [
            "Zone", "Véhicule N°", "Poids total chargé", "Volume total chargé",
            "Client(s) inclus", "Représentant(s) inclus", "BL inclus", "Taux d'occupation (%)",
            "Location_camion", "Location_proposee", "Code Véhicule"
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
            df_final["Volume de l'US"] = pd.to_numeric(df_final["Volume de l'US"], errors='coerce').fillna(0) / 1_000_000
            df_final["Volume total"] = df_final["Volume de l'US"] * df_final["Quantité livrée US"]

            # Regroupement par ville et client (pour l'affichage "Livraisons Client/Ville")
            df_grouped, df_city = self._group_data(df_final)

            # Calcul du besoin en estafette par ville
            df_city = self._calculate_estafette_need(df_city)

            # Nouveau tableau : ajout Zone
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
        if len(df.columns) > 4:
            df.rename(columns={df.columns[4]: "Quantité livrée US"}, inplace=True)
            
        return df

    def _load_ydlogist(self, file_path):
        df = pd.read_excel(file_path)
        # Renommage des colonnes Unité Volume (index 16) et Poids de l'US (index 13)
        if len(df.columns) > 16:
            df.rename(columns={df.columns[16]: "Unité Volume"}, inplace=True)
        if len(df.columns) > 13:
            df.rename(columns={df.columns[13]: "Poids de l'US"}, inplace=True)
            
        return df

    def _load_wcliegps(self, wcliegps_file):
        df_clients = pd.read_excel(wcliegps_file)
        
        # Identifier et renommer la colonne Représentant (index 16, colonne Q)
        if len(df_clients.columns) > 16:
            df_clients.rename(columns={df_clients.columns[16]: "Représentant"}, inplace=True)
        
        # S'assurer que les colonnes 'Client' et 'Représentant' existent pour la jointure
        required_cols = ["Client", "Ville", "Représentant"]
        for col in required_cols:
            if col not in df_clients.columns:
                 # Gérer le cas où la colonne n'a pas été trouvée à l'index 16
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
        return df[(df["Type livraison"] != "SDC") & (~df["Client commande"].isin(clients_exclus))]

    # =====================================================
    # 🔹 Calcul Poids
    # =====================================================
    def _calculate_weights(self, df):
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
    def _calculate_volumes(self, df_liv, df_art):
        df_liv_sel = df_liv[["No livraison", "Article", "Quantité livrée US", "Client commande"]]
        df_art_sel = df_art[["Article", "Volume de l'US", "Unité Volume"]].copy()
        
        # Conversion Volume de l'US
        df_art_sel["Volume de l'US"] = pd.to_numeric(df_art_sel["Volume de l'US"].astype(str).str.replace(",", "."),
                                                      errors="coerce")
        return pd.merge(df_liv_sel, df_art_sel, on="Article", how="left")

    # =====================================================
    # 🔹 Fusion
    # =====================================================
    def _merge_delivery_data(self, df_poids, df_vol):
        # On fusionne avec les colonnes de poids pour garder les colonnes initiales
        return pd.merge(df_poids.drop(columns=["Quantité livrée US", "Poids de l'US"], errors='ignore'), 
                         df_vol, on=["No livraison", "Article", "Client commande"], how="left")


    # =====================================================
    # 🔹 Ajout Client, Ville et Représentant
    # =====================================================
    def _add_city_client_info(self, df, df_clients):
        # Jointure pour ajouter Ville et Représentant
        # Attention: 'Client commande' est le code du BL, 'Client' est le code du client dans df_clients
        return pd.merge(df, df_clients[["Client", "Ville", "Représentant"]],
                         left_on="Client commande", right_on="Client", how="left")

    # =====================================================
    # 🔹 Groupement par Livraison/Client/Ville/Représentant
    # =====================================================
    def _group_data(self, df):
        # La colonne "Client commande" devient "Client" ici pour le regroupement
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
        poids_max = 1550 # kg
        volume_max = 4.608 # m3 (1.2 * 1.2 * 0.8 * 4)
        
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

        df["Zone"] = df["Ville"].apply(get_zone)
        return df

    # =====================================================
    # 🆕 Groupement par Zone
    # =====================================================
    def _group_by_zone(self, df_grouped_zone):
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
        for zone, group in df_grouped_zone.groupby("Zone"):
            # Trier les BL par poids décroissant (heuristique First Fit Decreasing)
            group_sorted = group.sort_values(by="Poids total", ascending=False).reset_index()
            estafettes = []  # liste des estafettes déjà créées pour la zone
            
            for idx, row in group_sorted.iterrows():
                bl = str(row["No livraison"])
                poids = row["Poids total"]
                volume = row["Volume total"]
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
                    estafette_num += 1 # On incrémente le compteur global seulement si on crée une nouvelle estafette

            # Sauvegarder les résultats
            for e in estafettes:
                clients_list = ", ".join(sorted(list(e["clients"])))
                representants_list = ", ".join(sorted(list(e["representants"])))
                resultats.append([
                    zone,
                    e["num_global"], # Utilisation du numéro global
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
        
        # Transfert BLs
        for bl in bl_list:
            # Retirer le BL de l'estafette source
            df.loc[mask_source, "BL inclus"] = df.loc[mask_source, "BL inclus"].apply(
                lambda x: ";".join([b for b in x.split(';') if b.strip() != bl])
            )
            
            # Ajouter le BL à l'estafette cible
            df.loc[mask_target, "BL inclus"] = df.loc[mask_target, "BL inclus"].apply(
                lambda x: ";".join(filter(None, list(x.split(';')) + [bl]))
            )
        
        # Recalculer poids et volume pour les deux estafettes
        for estafette_num in [source_estafette_num, target_estafette_num]:
            mask = df["Camion N°"] == estafette_num
            df.loc[mask, "Poids total chargé"] = df.loc[mask].apply(
                lambda row: sum(
                    df.loc[df["BL inclus"].str.contains(bl.strip(), na=False), "Poids total chargé"]
                    for bl in row["BL inclus"].split(';') if bl.strip()
                ), axis=1
            )
            df.loc[mask, "Volume total chargé"] = df.loc[mask].apply(
                lambda row: sum(
                    df.loc[df["BL inclus"].str.contains(bl.strip(), na=False), "Volume total chargé"]
                    for bl in row["BL inclus"].split(';') if bl.strip()
                ), axis=1
            )
            # Recalcul taux occupation
            df.loc[mask, "Taux d'occupation (%)"] = df.loc[mask].apply(
                lambda row: max(
                    row["Poids total chargé"] / 1550 * 100,
                    row["Volume total chargé"] / 4.608 * 100
                ), axis=1
            )
        
        # Mettre à jour le DataFrame
        self.df_base = df
        return True, f"✅ BLs transférés de {source_estafette_num} vers {target_estafette_num} avec succès."
    # ============================================================
    # 🔁 NOUVELLE CLASSE : Gestion du transfert de BLs entre estafettes
    # ============================================================


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
        SEUIL_POIDS = 1550
        SEUIL_VOLUME = 4.608

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
        transfert_autorise = (poids_dst_new <= SEUIL_POIDS) and (vol_dst_new <= SEUIL_VOLUME)

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
