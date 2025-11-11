import pandas as pd
import math
import numpy as np

# --- Constantes pour la location de camion ---
SEUIL_POIDS = 3000.0    # kg
SEUIL_VOLUME = 9.216    # m³
CAPACITE_POIDS_ESTAFETTE = 1550  # kg
CAPACITE_VOLUME_ESTAFETTE = 4.608  # m³
CAMION_CODE = "CAMION-LOUE"
CAMION_POIDS_MAX = 30500  # kg
CAMION_VOLUME_MAX = 77.5  # m³

# =====================================================
# CLASSE PRINCIPALE DE TRAITEMENT DES LIVRAISONS
# =====================================================
class DeliveryProcessor:
    def __init__(self):
        self.df_livraisons_original = None
    
    def process_delivery_data(self, liv_file, ydlogist_file, wcliegps_file):
        """Traite les fichiers d'entrée et retourne les DataFrames résultants."""
        try:
            # Lecture des fichiers
            df_liv = self._load_livraisons(liv_file)
            df_yd = self._load_ydlogist(ydlogist_file)
            df_clients = self._load_wcliegps(wcliegps_file)

            # Filtrage des données
            df_liv = self._filter_initial_data(df_liv)

            # Calcul Poids & Volume
            df_poids = self._calculate_weights(df_liv)
            df_vol = self._calculate_volumes(df_liv, df_yd)

            # Fusionner poids + volume
            df_merged = self._merge_delivery_data(df_poids, df_vol)

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
            
            # Groupement par zone
            df_zone = self._group_by_zone(df_grouped_zone)
            
            # Calcul du besoin en estafette par zone
            df_zone = self._calculate_estafette_need(df_zone)

            # Calcul des voyages optimisés 
            df_optimized_estafettes = self._calculate_optimized_estafette(df_grouped_zone)

            # 🆕 CORRECTION : Stocker les données originales du tableau "Livraisons par Client & Ville + Zone"
            self.df_livraisons_original = df_grouped_zone.copy()

            # 🆕 CORRECTION : Retourner 6 valeurs
            return df_grouped, df_city, df_grouped_zone, df_zone, df_optimized_estafettes, self.df_livraisons_original

        except Exception as e:
            raise Exception(f"❌ Erreur lors du traitement des données : {str(e)}")

    # =====================================================
    # MÉTHODES AUXILIAIRES
    # =====================================================
    def _load_livraisons(self, liv_file):
        df = pd.read_excel(liv_file)
        if 'N° BON LIVRAISON' in df.columns:
            df.rename(columns={'N° BON LIVRAISON': 'No livraison'}, inplace=True)
        if len(df.columns) > 4:
            df.rename(columns={df.columns[4]: "Quantité livrée US"}, inplace=True)
        return df

    def _load_ydlogist(self, file_path):
        df = pd.read_excel(file_path)
        if len(df.columns) > 16:
            df.rename(columns={df.columns[16]: "Unité Volume"}, inplace=True)
        if len(df.columns) > 13:
            df.rename(columns={df.columns[13]: "Poids de l'US"}, inplace=True)
        return df

    def _load_wcliegps(self, wcliegps_file):
        df_clients = pd.read_excel(wcliegps_file)
        if len(df_clients.columns) > 16:
            df_clients.rename(columns={df_clients.columns[16]: "Représentant"}, inplace=True)
        required_cols = ["Client", "Ville", "Représentant"]
        for col in required_cols:
            if col not in df_clients.columns:
                raise ValueError(f"La colonne '{col}' est manquante dans le fichier clients.")
        return df_clients[["Client", "Ville", "Représentant"]].copy()

    def _filter_initial_data(self, df):
        clients_exclus = [
            "AMECAP", "SANA", "SOPAL", "SOPALGAZ", "SOPALSERV", "SOPALTEC",
            "SOPALALG", "AQUA", "WINOX", "QUIVEM", "SANISTONE",
            "SOPAMAR", "SOPALAFR", "SOPALINTER"
        ]
        return df[(df["Type livraison"] != "SDC") & (~df["Client commande"].isin(clients_exclus))]

    def _calculate_weights(self, df):
        df["Poids de l'US"] = pd.to_numeric(df["Poids de l'US"].astype(str).str.replace(",", ".")
                                           .str.replace(r"[^\d.]", "", regex=True), errors="coerce").fillna(0)
        df["Quantité livrée US"] = pd.to_numeric(df["Quantité livrée US"], errors="coerce").fillna(0)
        df["Poids total"] = df["Quantité livrée US"] * df["Poids de l'US"]
        return df[["No livraison", "Article", "Client commande", "Poids total", "Quantité livrée US", "Poids de l'US"]]

    def _calculate_volumes(self, df_liv, df_art):
        df_liv_sel = df_liv[["No livraison", "Article", "Quantité livrée US", "Client commande"]]
        df_art_sel = df_art[["Article", "Volume de l'US", "Unité Volume"]].copy()
        df_art_sel["Volume de l'US"] = pd.to_numeric(df_art_sel["Volume de l'US"].astype(str).str.replace(",", "."),
                                                    errors="coerce")
        return pd.merge(df_liv_sel, df_art_sel, on="Article", how="left")

    def _merge_delivery_data(self, df_poids, df_vol):
        return pd.merge(df_poids.drop(columns=["Quantité livrée US", "Poids de l'US"], errors='ignore'), 
                       df_vol, on=["No livraison", "Article", "Client commande"], how="left")

    def _add_city_client_info(self, df, df_clients):
        return pd.merge(df, df_clients[["Client", "Ville", "Représentant"]],
                       left_on="Client commande", right_on="Client", how="left")

    def _group_data(self, df):
        df_grouped = df.groupby(["No livraison", "Client", "Ville", "Représentant"], as_index=False).agg({
            "Article": lambda x: ", ".join(x.astype(str)),
            "Poids total": "sum",
            "Volume total": "sum"
        })
        df_city = df_grouped.groupby("Ville", as_index=False).agg({
            "Poids total": "sum",
            "Volume total": "sum",
            "No livraison": "count"
        }).rename(columns={"No livraison": "Nombre de BLs"})  # ← MODIFICATION ICI
        return df_grouped, df_city

    def _calculate_estafette_need(self, df):
        if "Poids total" in df.columns and "Volume total" in df.columns:
            df["Besoin estafette (poids)"] = df["Poids total"].apply(lambda p: math.ceil(p / CAPACITE_POIDS_ESTAFETTE))
            df["Besoin estafette (volume)"] = df["Volume total"].apply(lambda v: math.ceil(v / CAPACITE_VOLUME_ESTAFETTE))
            df["Besoin estafette réel"] = df[["Besoin estafette (poids)", "Besoin estafette (volume)"]].max(axis=1)
        return df

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

    def _group_by_zone(self, df_grouped_zone):
        df_zone = df_grouped_zone.groupby("Zone", as_index=False).agg({
            "Poids total": "sum",
            "Volume total": "sum",
            "No livraison": "count"
        }).rename(columns={"No livraison": "Nombre livraisons"})
        return df_zone

    def _calculate_optimized_estafette(self, df_grouped_zone):
        resultats = []
        estafette_num = 1

        for zone, group in df_grouped_zone.groupby("Zone"):
            group_sorted = group.sort_values(by="Poids total", ascending=False).reset_index()
            estafettes = []
            
            for idx, row in group_sorted.iterrows():
                bl = str(row["No livraison"])
                poids = row["Poids total"]
                volume = row["Volume total"]
                client = str(row["Client de l'estafette"]) 
                representant = str(row["Représentant"])
                placed = False
                
                for e in estafettes:
                    if e["poids"] + poids <= CAPACITE_POIDS_ESTAFETTE and e["volume"] + volume <= CAPACITE_VOLUME_ESTAFETTE:
                        e["poids"] += poids
                        e["volume"] += volume
                        e["bls"].append(bl)
                        for c in client.split(','): e["clients"].add(c.strip())
                        for r in representant.split(','): e["representants"].add(r.strip())
                        placed = True
                        break
                
                if not placed:
                    estafettes.append({
                        "poids": poids,
                        "volume": volume,
                        "bls": [bl],
                        "clients": {c.strip() for c in client.split(',')},
                        "representants": {r.strip() for r in representant.split(',')},
                        "num_global": estafette_num
                    })
                    estafette_num += 1

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
                
        df_estafettes = pd.DataFrame(resultats, columns=[
            "Zone", "Estafette N°", "Poids total chargé", "Volume total chargé", 
            "Client(s) inclus", "Représentant(s) inclus", "BL inclus"
        ])
        
        # Calcul du taux d'occupation
        df_estafettes["Taux Poids (%)"] = (df_estafettes["Poids total chargé"] / CAPACITE_POIDS_ESTAFETTE) * 100
        df_estafettes["Taux Volume (%)"] = (df_estafettes["Volume total chargé"] / CAPACITE_VOLUME_ESTAFETTE) * 100
        df_estafettes["Taux d'occupation (%)"] = df_estafettes[["Taux Poids (%)", "Taux Volume (%)"]].max(axis=1).round(2)
        
        # Initialisation des colonnes de location
        df_estafettes["Location_camion"] = False
        df_estafettes["Location_proposee"] = False
        df_estafettes["Code Véhicule"] = "ESTAFETTE"
        df_estafettes["Camion N°"] = df_estafettes["Estafette N°"].apply(lambda x: f"E{int(x)}")
        
        df_estafettes = df_estafettes.drop(columns=["Taux Poids (%)", "Taux Volume (%)"]) 
        
        return df_estafettes

# =====================================================
# CLASSE DE GESTION DE LA LOCATION DE CAMIONS
# =====================================================
class TruckRentalProcessor:
    def __init__(self, df_optimized, df_livraisons_original):
        """Initialise avec le DataFrame optimisé ET les données originales du tableau 'Livraisons par Client & Ville + Zone'."""
        self.df_base = self._initialize_rental_columns(df_optimized.copy())
        # Utiliser directement le tableau "Livraisons par Client & Ville + Zone"
        self.df_livraisons_original = df_livraisons_original.copy()
        self._next_camion_num = self.df_base[self.df_base["Code Véhicule"] == CAMION_CODE].shape[0] + 1

    def _initialize_rental_columns(self, df):
        """Initialise les colonnes pour la gestion de la location."""
        df.rename(columns={
            "Poids total chargé": "Poids total",
            "Volume total chargé": "Volume total"
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

    def _get_client_totals_from_original_data(self):
        """Extrait les totaux réels des clients depuis le tableau 'Livraisons par Client & Ville + Zone'."""
        try:
            # Vérifier que les colonnes nécessaires existent
            required_cols = ["Client de l'estafette", "Poids total", "Volume total"]
            missing_cols = [col for col in required_cols if col not in self.df_livraisons_original.columns]
            
            if missing_cols:
                print(f"⚠️ Colonnes manquantes dans les données originales: {missing_cols}")
                return pd.DataFrame(columns=["Client", "Poids total (kg)", "Volume total (m³)"])
            
            # Grouper par client pour obtenir les totaux RÉELS
            df_client_totals = self.df_livraisons_original.groupby("Client de l'estafette").agg({
                "Poids total": "sum",
                "Volume total": "sum"
            }).reset_index()
            
            df_client_totals = df_client_totals.rename(columns={
                "Client de l'estafette": "Client",
                "Poids total": "Poids total (kg)",
                "Volume total": "Volume total (m³)"
            })
            
            return df_client_totals
            
        except Exception as e:
            print(f"❌ Erreur lors de l'extraction des totaux clients: {e}")
            return pd.DataFrame(columns=["Client", "Poids total (kg)", "Volume total (m³)"])

    def detecter_propositions(self):
        """Détecte les propositions en utilisant les totaux RÉELS du tableau original."""
        # Récupérer les totaux réels des clients
        df_client_totals = self._get_client_totals_from_original_data()
        
        if df_client_totals.empty:
            return pd.DataFrame()

        # Exclure les clients déjà traités
        processed_clients = self.df_base[self.df_base["Location_proposee"]]["Client(s) inclus"].unique()
        
        # Filtrer les clients non traités
        df_pending = df_client_totals[~df_client_totals["Client"].isin(processed_clients)].copy()
        
        if df_pending.empty:
            return pd.DataFrame()

        # Appliquer les seuils sur les totaux RÉELS
        propositions = df_pending[
            (df_pending["Poids total (kg)"] >= SEUIL_POIDS) | 
            (df_pending["Volume total (m³)"] >= SEUIL_VOLUME)
        ].copy()

        if propositions.empty:
            return pd.DataFrame()

        # Ajouter la colonne Raison
        def get_raison(row):
            raisons = []
            if row["Poids total (kg)"] >= SEUIL_POIDS:
                raisons.append(f"Poids ≥ {SEUIL_POIDS} kg")
            if row["Volume total (m³)"] >= SEUIL_VOLUME:
                raisons.append(f"Volume ≥ {SEUIL_VOLUME:.3f} m³")
            return " & ".join(raisons)

        propositions["Raison"] = propositions.apply(get_raison, axis=1)

        return propositions.sort_values(["Poids total (kg)", "Volume total (m³)"], ascending=False).reset_index(drop=True)

    def get_details_client(self, client):
        """Affiche les détails avec les totaux RÉELS du tableau original."""
        try:
            # Récupérer les totaux RÉELS du client depuis les données originales
            client_data_original = self.df_livraisons_original[
                self.df_livraisons_original["Client de l'estafette"] == client
            ]
            
            if client_data_original.empty:
                return f"Aucune donnée pour {client}", pd.DataFrame()

            # Calculer les totaux RÉELS
            total_poids_reel = client_data_original["Poids total"].sum()
            total_volume_reel = client_data_original["Volume total"].sum()
            
            # Récupérer les BLs du client
            bls_client = client_data_original["No livraison"].unique()
            
            # Trouver les estafettes qui contiennent ces BLs
            details_estafettes = []
            for _, row in self.df_base.iterrows():
                bls_in_vehicle = str(row["BL inclus"]).split(';')
                bls_commun = set(map(str, bls_client)) & set(bls_in_vehicle)
                
                if bls_commun:
                    details_estafettes.append({
                        'Zone': row['Zone'],
                        'Camion N°': row['Camion N°'],
                        'Poids total': f"{row['Poids total']:.3f} kg",
                        'Volume total': f"{row['Volume total']:.3f} m³",
                        'BL inclus': row['BL inclus'],
                        'Taux d\'occupation (%)': f"{row['Taux d\'occupation (%)']:.2f}%"
                    })
            
            # Déterminer l'état
            etat = "Non décidée"
            client_in_base = self.df_base[self.df_base["Client(s) inclus"].str.contains(client, na=False)]
            
            if not client_in_base.empty:
                if client_in_base["Location_camion"].any():
                    etat = "Location ACCEPTÉE"
                elif client_in_base["Location_proposee"].any():
                    etat = "Proposition REFUSÉE"
            
            resume = f"Client {client} — Poids total RÉEL : {total_poids_reel:.1f} kg ; Volume total RÉEL : {total_volume_reel:.3f} m³ | État : {etat}"
            
            df_details = pd.DataFrame(details_estafettes)
            return resume, df_details
            
        except Exception as e:
            print(f"❌ Erreur dans get_details_client: {e}")
            return f"Erreur avec le client {client}", pd.DataFrame()

    def appliquer_location(self, client, accepter):
        """Applique la décision de location pour un client avec réoptimisation automatique."""
        try:
            # Utiliser les données originales pour trouver tous les BLs du client
            client_data_original = self.df_livraisons_original[
                self.df_livraisons_original["Client de l'estafette"] == client
            ]
            
            if client_data_original.empty:
                return False, "Client introuvable dans les données originales.", self.df_base

            # Récupérer tous les BLs du client
            bls_client = client_data_original["No livraison"].unique()
            
            df = self.df_base.copy()
            
            if accepter:
                # Récupérer les données consolidées pour le camion
                poids_total = client_data_original["Poids total"].sum()
                volume_total = client_data_original["Volume total"].sum()
                bl_concat = ";".join([str(bl) for bl in bls_client])
                representants = ";".join(sorted(client_data_original["Représentant"].astype(str).unique().tolist()))
                zones = ";".join(sorted(client_data_original["Zone"].astype(str).unique().tolist()))
                
                # Calcul du taux d'occupation du camion
                TAUX_POIDS_MAX_LOC = 30500
                TAUX_VOLUME_MAX_LOC = 77.5
                taux_occu = max(poids_total / TAUX_POIDS_MAX_LOC * 100, volume_total / TAUX_VOLUME_MAX_LOC * 100)
                
                # Créer un nouveau voyage pour le camion loué
                camion_num_final = f"C{self._next_camion_num}"
                new_row = pd.DataFrame([{
                    "Zone": zones,
                    "Estafette N°": 0,
                    "Poids total": poids_total,
                    "Volume total": volume_total,
                    "BL inclus": bl_concat,
                    "Client(s) inclus": client,
                    "Représentant(s) inclus": representants,
                    "Location_camion": True,
                    "Location_proposee": True,
                    "Code Véhicule": CAMION_CODE,
                    "Camion N°": camion_num_final,
                    "Taux d'occupation (%)": taux_occu,
                }])
                
                self._next_camion_num += 1
                
                # ÉTAPE 1: Identifier tous les BLs à garder (non transférés)
                bls_a_garder_total = []
                zones_affectees = set()
                
                for idx, row in df.iterrows():
                    if pd.notna(row["BL inclus"]):
                        bls_actuels = str(row["BL inclus"]).split(';')
                        # Garder seulement les BLs qui ne sont PAS du client à transférer
                        bls_a_garder = [bl for bl in bls_actuels if bl not in [str(b) for b in bls_client]]
                        bls_a_garder_total.extend(bls_a_garder)
                        
                        # Noter les zones affectées
                        if bls_a_garder:
                            zones_affectees.add(row["Zone"])
                
                # ÉTAPE 2: Réoptimiser COMPLÈTEMENT les estafettes pour chaque zone affectée
                df_estafettes_optimisees = self._reoptimiser_estafettes_par_zone(bls_a_garder_total, zones_affectees)
                
                # ÉTAPE 3: Combiner camions existants + nouvelles estafettes optimisées
                df_camions_existants = df[df["Code Véhicule"] == CAMION_CODE].copy()
                df_final = pd.concat([df_camions_existants, df_estafettes_optimisees, new_row], ignore_index=True)
                
                self.df_base = df_final
                return True, f"✅ Location ACCEPTÉE pour {client}. Commandes transférées vers {camion_num_final}. Réoptimisation des estafettes effectuée.", self.detecter_propositions()
            else:
                # Refuser la proposition - pas de changement dans l'optimisation
                mask_original = df["BL inclus"].apply(
                    lambda x: any(str(bl) in str(x).split(';') for bl in bls_client)
                )
                df.loc[mask_original, ["Location_proposee", "Location_camion", "Code Véhicule"]] = [True, False, "ESTAFETTE"]
                df.loc[mask_original, "Camion N°"] = df.loc[mask_original, "Estafette N°"].apply(lambda x: f"E{int(x)}")
                
                self.df_base = df
                return True, f"❌ Proposition REFUSÉE pour {client}. Les commandes restent en Estafettes.", self.detecter_propositions()
                
        except Exception as e:
            return False, f"❌ Erreur lors de l'application de la décision: {str(e)}", self.df_base

    def _reoptimiser_estafettes_par_zone(self, bls_a_garder, zones_affectees):
            """Réoptimise complètement les estafettes pour les BLs restants après transfert."""
            try:
                if not bls_a_garder:
                    return pd.DataFrame()
                
                # Récupérer les données complètes des BLs à garder
                df_bls_data = self.df_livraisons_original[
                    self.df_livraisons_original["No livraison"].isin(bls_a_garder)
                ]
                
                if df_bls_data.empty:
                    return pd.DataFrame()
                
                resultats_optimises = []
                estafette_num = 1  # Recommencer la numérotation
                
                # Optimiser par zone
                for zone in zones_affectees:
                    df_zone = df_bls_data[df_bls_data["Zone"] == zone]
                    
                    if df_zone.empty:
                        continue
                        
                    # Trier par poids décroissant pour l'optimisation
                    df_zone_sorted = df_zone.sort_values(by="Poids total", ascending=False).reset_index()
                    estafettes_zone = []
                    
                    # Algorithme d'optimisation (bin packing)
                    for idx, row in df_zone_sorted.iterrows():
                        bl = str(row["No livraison"])
                        poids = row["Poids total"]
                        volume = row["Volume total"]
                        client = str(row["Client de l'estafette"])
                        representant = str(row["Représentant"])
                        placed = False
                        
                        # Essayer de placer dans une estafette existante
                        for e in estafettes_zone:
                            if (e["poids"] + poids <= CAPACITE_POIDS_ESTAFETTE and 
                                e["volume"] + volume <= CAPACITE_VOLUME_ESTAFETTE):
                                e["poids"] += poids
                                e["volume"] += volume
                                e["bls"].append(bl)
                                e["clients"].add(client)
                                e["representants"].add(representant)
                                placed = True
                                break
                        
                        # Si pas placé, créer une nouvelle estafette
                        if not placed:
                            estafettes_zone.append({
                                "poids": poids,
                                "volume": volume,
                                "bls": [bl],
                                "clients": {client},
                                "representants": {representant},
                                "num_global": estafette_num
                            })
                            estafette_num += 1

                    # Formater les résultats pour la zone
                    for e in estafettes_zone:
                        clients_list = ", ".join(sorted(list(e["clients"])))
                        representants_list = ", ".join(sorted(list(e["representants"])))
                        
                        # Calcul du taux d'occupation
                        taux_poids = (e["poids"] / CAPACITE_POIDS_ESTAFETTE) * 100
                        taux_volume = (e["volume"] / CAPACITE_VOLUME_ESTAFETTE) * 100
                        taux_occupation = max(taux_poids, taux_volume)
                        
                        resultats_optimises.append({
                            "Zone": zone,
                            "Estafette N°": e["num_global"],
                            "Poids total": e["poids"],
                            "Volume total": e["volume"],
                            "Client(s) inclus": clients_list,
                            "Représentant(s) inclus": representants_list,
                            "BL inclus": ";".join(e["bls"]),
                            "Taux d'occupation (%)": taux_occupation,
                            "Location_camion": False,
                            "Location_proposee": False,
                            "Code Véhicule": "ESTAFETTE",
                            "Camion N°": f"E{e['num_global']}"
                        })
                
                # Créer le DataFrame final
                if resultats_optimises:
                    return pd.DataFrame(resultats_optimises)
                else:
                    return pd.DataFrame()
                    
            except Exception as e:
                print(f"❌ Erreur lors de la réoptimisation: {e}")
                return pd.DataFrame()

    def get_df_result(self):
        """Retourne le DataFrame optimisé final."""
        df_result = self.df_base.copy()
        
        # Renommer les colonnes si nécessaire
        rename_mapping = {
            "Poids total": "Poids total chargé",
            "Volume total": "Volume total chargé", 
            "Représentant": "Représentant(s) inclus"
        }
        
        # Appliquer seulement les renommages qui existent
        rename_mapping = {k: v for k, v in rename_mapping.items() if k in df_result.columns}
        if rename_mapping:
            df_result.rename(columns=rename_mapping, inplace=True)
        
        # S'assurer que "Véhicule N°" existe
        if "Camion N°" in df_result.columns and "Véhicule N°" not in df_result.columns:
            df_result["Véhicule N°"] = df_result["Camion N°"]
        
        # Préparer le tri
        df_result['Code_Tri'] = df_result['Code Véhicule'].apply(lambda x: 0 if x == CAMION_CODE else 1)
        
        # Définir l'ordre de tri par défaut
        sort_columns = ["Code_Tri", "Zone"]
        sort_ascending = [True, True]
        
        # Ajouter les colonnes de tri si elles existent
        if "Estafette N°" in df_result.columns:
            sort_columns.insert(1, "Estafette N°")
            sort_ascending.insert(1, True)
        
        if "Véhicule N°" in df_result.columns:
            sort_columns.append("Véhicule N°")
            sort_ascending.append(True)
        
        # Appliquer le tri
        df_result = df_result.sort_values(by=sort_columns, ascending=sort_ascending)
        
        # Nettoyer les colonnes temporaires
        df_result = df_result.drop(columns=['Code_Tri'], errors='ignore')
        
        # Ordre d'affichage final
        final_columns = [
            "Zone", "Véhicule N°", "Poids total chargé", "Volume total chargé",
            "Client(s) inclus", "Représentant(s) inclus", "BL inclus", "Taux d'occupation (%)",
            "Location_camion", "Location_proposee", "Code Véhicule"
        ]
        
        # Filtrer seulement les colonnes qui existent
        available_columns = [col for col in final_columns if col in df_result.columns]
        return df_result[available_columns]
# =====================================================
# CLASSE DE GESTION DES TRANSFERTS DE BL
# =====================================================
class TruckTransferManager:
    def __init__(self, df_voyages, df_livraisons):
        self.df_voyages = df_voyages.copy()
        self.df_livraisons = df_livraisons.copy()
        self.MAX_POIDS = CAPACITE_POIDS_ESTAFETTE
        self.MAX_VOLUME = CAPACITE_VOLUME_ESTAFETTE

    def transferer_bls(self, zone, source, cible, bls_a_transferer):
        """Transfère des BLs d'une estafette source à une estafette cible."""
        try:
            # Vérifier que les BLs existent dans la source
            df_source = self.df_voyages[
                (self.df_voyages["Zone"] == zone) & 
                (self.df_voyages["Véhicule N°"] == source)
            ]
            
            if df_source.empty:
                return False, f"❌ Véhicule source {source} non trouvé dans la zone {zone}", self.df_voyages
            
            bls_source = df_source["BL inclus"].iloc[0].split(';')
            bls_existants = [bl for bl in bls_a_transferer if bl in bls_source]
            
            if not bls_existants:
                return False, f"❌ Aucun des BLs sélectionnés n'est présent dans le véhicule source {source}", self.df_voyages
            
            # Calculer le poids et volume des BLs à transférer depuis les données originales
            df_bls_transfert = self.df_livraisons[
                self.df_livraisons["No livraison"].isin(bls_existants)
            ]
            poids_transfert = df_bls_transfert["Poids total"].sum()
            volume_transfert = df_bls_transfert["Volume total"].sum()
            
            # Vérifier la capacité du véhicule cible
            df_cible = self.df_voyages[
                (self.df_voyages["Zone"] == zone) & 
                (self.df_voyages["Véhicule N°"] == cible)
            ]
            
            if df_cible.empty:
                return False, f"❌ Véhicule cible {cible} non trouvé dans la zone {zone}", self.df_voyages
            
            poids_cible_actuel = df_cible["Poids total chargé"].iloc[0]
            volume_cible_actuel = df_cible["Volume total chargé"].iloc[0]
            
            if (poids_cible_actuel + poids_transfert > self.MAX_POIDS or 
                volume_cible_actuel + volume_transfert > self.MAX_VOLUME):
                return False, "❌ Le transfert dépasse les capacités du véhicule cible", self.df_voyages
            
            # Appliquer le transfert
            for idx, row in self.df_voyages.iterrows():
                if row["Zone"] == zone and row["Véhicule N°"] == source:
                    bls_restants = [bl for bl in row["BL inclus"].split(';') if bl not in bls_existants]
                    self.df_voyages.at[idx, "BL inclus"] = ';'.join(bls_restants)
                    self.df_voyages.at[idx, "Poids total chargé"] -= poids_transfert
                    self.df_voyages.at[idx, "Volume total chargé"] -= volume_transfert
                
                elif row["Zone"] == zone and row["Véhicule N°"] == cible:
                    bls_actuels = row["BL inclus"].split(';')
                    bls_nouveaux = bls_actuels + bls_existants
                    self.df_voyages.at[idx, "BL inclus"] = ';'.join(bls_nouveaux)
                    self.df_voyages.at[idx, "Poids total chargé"] += poids_transfert
                    self.df_voyages.at[idx, "Volume total chargé"] += volume_transfert
            
            message = f"✅ Transfert réussi : {len(bls_existants)} BL(s) déplacé(s) de {source} vers {cible}"
            return True, message, self.df_voyages
            
        except Exception as e:
            return False, f"❌ Erreur lors du transfert : {str(e)}", self.df_voyages

    def get_voyages_actuels(self):
        return self.df_voyages

    # -------------------------
    # MÉTHODE POUR AJOUTER UN OBJET MANUEL
    # -------------------------
    def add_manual_object(self, df_voyages, vehicle, zone, name, weight, volume):
        """
        Ajoute un objet manuel (objet virtuel) dans le véhicule sélectionné (estafette ou camion).
        - df_voyages : DataFrame des voyages (format attendu : celui retourné par get_df_result / df_optimized_estafettes)
        - vehicle : string e.g. "E1" ou "C1"
        - zone : string, même valeur que colonne Zone
        - name : désignation
        - weight : kg (float)
        - volume : m3 (float)
        Retour : (success: bool, message: str, df_updated: DataFrame)
        """
        try:
            # Validation inputs
            weight = float(weight)
            volume = float(volume)
            if weight < 0 or volume < 0:
                return False, "Poids et volume doivent être >= 0", df_voyages

            df = df_voyages.copy()

            # Rechercher la ligne du véhicule dans df (col peut être 'Véhicule N°' ou 'Camion N°')
            if "Véhicule N°" in df.columns:
                veh_col = "Véhicule N°"
            elif "Camion N°" in df.columns:
                veh_col = "Camion N°"
            else:
                return False, "Structure du DataFrame inattendue (pas de colonne Véhicule N° ni Camion N°).", df

            mask = (df[veh_col] == vehicle) & (df["Zone"] == zone)
            if not mask.any():
                return False, f"Véhicule {vehicle} non trouvé dans la zone {zone}.", df

            idx = df[mask].index[0]
            row = df.loc[idx].copy()

            is_camion = (row.get("Code Véhicule", "") == CAMION_CODE) or str(vehicle).upper().startswith("C")

            max_poids = CAMION_POIDS_MAX if is_camion else CAPACITE_POIDS_ESTAFETTE
            max_volume = CAMION_VOLUME_MAX if is_camion else CAPACITE_VOLUME_ESTAFETTE

            current_poids = float(row.get("Poids total chargé", row.get("Poids total", 0)) or 0)
            current_volume = float(row.get("Volume total chargé", row.get("Volume total", 0)) or 0)

            new_poids = current_poids + weight
            new_volume = current_volume + volume

            # Refuser si dépasse (contrainte demandée)
            if new_poids > max_poids or new_volume > max_volume:
                return False, "❌ Capacité dépassée : objet non ajouté.", df

            # Générer code unique pour l'objet
            obj_code = f"OBJ-{name}"

            # Mettre à jour BL inclus (s'assurer que ce soit une string)
            bls_current = str(row.get("BL inclus", "")).strip()
            if bls_current == "nan" or bls_current == "":
                new_bls = obj_code
            else:
                new_bls = bls_current + ";" + obj_code

            # Appliquer modifications
            df.at[idx, "BL inclus"] = new_bls
            # Mettre à jour colonnes poids/volume selon structure
            if "Poids total chargé" in df.columns:
                df.at[idx, "Poids total chargé"] = new_poids
            else:
                df.at[idx, "Poids total"] = new_poids

            if "Volume total chargé" in df.columns:
                df.at[idx, "Volume total chargé"] = new_volume
            else:
                df.at[idx, "Volume total"] = new_volume

            # Recalculer taux d'occupation
            taux = max((new_poids / max_poids) * 100, (new_volume / max_volume) * 100)
            df.at[idx, "Taux d'occupation (%)"] = taux

            return True, f"✅ Objet '{name}' ajouté à {vehicle} en zone {zone} (code {obj_code})", df

        except Exception as e:
            return False, f"❌ Erreur lors de l'ajout de l'objet : {str(e)}", df_voyages


# =====================================================
# CLASSE DE VALIDATION DES VOYAGES
# =====================================================
class VoyageValidator:
    def __init__(self, df_voyages):
        self.df_voyages = df_voyages.copy()
    
    def validate_voyages(self):
        """Valide les voyages et retourne un rapport de validation."""
        try:
            df = self.df_voyages.copy()
            rapports = []
            
            # Validation des capacités
            for idx, row in df.iterrows():
                vehicule = row.get("Véhicule N°", "Inconnu")
                zone = row.get("Zone", "Inconnue")
                poids = float(row.get("Poids total chargé", 0))
                volume = float(row.get("Volume total chargé", 0))
                code_vehicule = row.get("Code Véhicule", "ESTAFETTE")
                
                # Déterminer les capacités max selon le type de véhicule
                if code_vehicule == CAMION_CODE:
                    poids_max = CAMION_POIDS_MAX
                    volume_max = CAMION_VOLUME_MAX
                    type_veh = "Camion"
                else:
                    poids_max = CAPACITE_POIDS_ESTAFETTE
                    volume_max = CAPACITE_VOLUME_ESTAFETTE
                    type_veh = "Estafette"
                
                # Vérifier les dépassements
                if poids > poids_max:
                    rapports.append({
                        'Type': '❌ ERREUR',
                        'Message': f"{type_veh} {vehicule} (Zone {zone}) dépasse la capacité poids : {poids:.1f}kg > {poids_max}kg"
                    })
                
                if volume > volume_max:
                    rapports.append({
                        'Type': '❌ ERREUR', 
                        'Message': f"{type_veh} {vehicule} (Zone {zone}) dépasse la capacité volume : {volume:.3f}m³ > {volume_max}m³"
                    })
                
                # Vérifier le taux d'occupation
                taux_occupation = float(row.get("Taux d'occupation (%)", 0))
                if taux_occupation > 100:
                    rapports.append({
                        'Type': '⚠️ ALERTE',
                        'Message': f"{type_veh} {vehicule} (Zone {zone}) a un taux d'occupation > 100% : {taux_occupation:.1f}%"
                    })
                elif taux_occupation < 50:
                    rapports.append({
                        'Type': '💡 SUGGESTION',
                        'Message': f"{type_veh} {vehicule} (Zone {zone}) sous-utilisé : {taux_occupation:.1f}% - possibilité d'optimisation"
                    })
            
            # Validation des BLs dupliqués
            tous_bls = []
            for idx, row in df.iterrows():
                bls = str(row.get("BL inclus", "")).split(';')
                for bl in bls:
                    if bl.strip() and bl != 'nan':
                        tous_bls.append((bl.strip(), row["Véhicule N°"], row["Zone"]))
            
            bls_counts = {}
            for bl, vehicule, zone in tous_bls:
                if bl not in bls_counts:
                    bls_counts[bl] = []
                bls_counts[bl].append((vehicule, zone))
            
            for bl, occurrences in bls_counts.items():
                if len(occurrences) > 1 and not bl.startswith('OBJ-'):
                    vehicules = ", ".join([f"{veh} (Zone {zone})" for veh, zone in occurrences])
                    rapports.append({
                        'Type': '❌ ERREUR',
                        'Message': f"BL {bl} présent dans plusieurs véhicules : {vehicules}"
                    })
            
            # Validation de la cohérence des données
            for idx, row in df.iterrows():
                vehicule = row.get("Véhicule N°", "Inconnu")
                zone = row.get("Zone", "Inconnue")
                clients = str(row.get("Client(s) inclus", ""))
                representants = str(row.get("Représentant(s) inclus", ""))
                bls = str(row.get("BL inclus", ""))
                
                if not clients.strip() or clients == 'nan':
                    rapports.append({
                        'Type': '⚠️ ALERTE',
                        'Message': f"Véhicule {vehicule} (Zone {zone}) n'a pas de client associé"
                    })
                
                if not bls.strip() or bls == 'nan':
                    rapports.append({
                        'Type': '❌ ERREUR', 
                        'Message': f"Véhicule {vehicule} (Zone {zone}) n'a pas de BL associé"
                    })
            
            # Résumé global
            nb_estafettes = len(df[df["Code Véhicule"] == "ESTAFETTE"])
            nb_camions = len(df[df["Code Véhicule"] == CAMION_CODE])
            poids_total = df["Poids total chargé"].sum()
            volume_total = df["Volume total chargé"].sum()
            taux_moyen = df["Taux d'occupation (%)"].mean()
            
            rapports.append({
                'Type': '📊 RÉSUMÉ',
                'Message': f"Total : {nb_estafettes} estafettes, {nb_camions} camions | Poids total : {poids_total:.1f}kg | Volume total : {volume_total:.3f}m³ | Taux moyen : {taux_moyen:.1f}%"
            })
            
            return pd.DataFrame(rapports)
            
        except Exception as e:
            return pd.DataFrame([{
                'Type': '❌ ERREUR SYSTÈME',
                'Message': f"Erreur lors de la validation : {str(e)}"
            }])

    def generer_rapport_excel(self, file_path):
        """Génère un rapport Excel détaillé des voyages validés."""
        try:
            with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                # Feuille principale des voyages
                self.df_voyages.to_excel(writer, sheet_name='Voyages Optimisés', index=False)
                
                # Feuille de validation
                rapport_validation = self.validate_voyages()
                rapport_validation.to_excel(writer, sheet_name='Rapport Validation', index=False)
                
                # Feuille de statistiques par zone
                stats_zone = self.df_voyages.groupby('Zone').agg({
                    'Véhicule N°': 'count',
                    'Poids total chargé': 'sum',
                    'Volume total chargé': 'sum',
                    'Taux d\'occupation (%)': 'mean'
                }).rename(columns={
                    'Véhicule N°': 'Nombre Véhicules',
                    'Poids total chargé': 'Poids Total (kg)',
                    'Volume total chargé': 'Volume Total (m³)',
                    'Taux d\'occupation (%)': 'Taux Occupation Moyen (%)'
                }).round(2)
                
                stats_zone.to_excel(writer, sheet_name='Stats par Zone')
                
                # Feuille de détails par véhicule
                details_vehicules = self.df_voyages[[
                    'Zone', 'Véhicule N°', 'Code Véhicule', 'Poids total chargé', 
                    'Volume total chargé', 'Taux d\'occupation (%)', 'Client(s) inclus',
                    'Représentant(s) inclus', 'BL inclus'
                ]].copy()
                
                details_vehicules['Capacité Max Poids'] = details_vehicules['Code Véhicule'].apply(
                    lambda x: CAMION_POIDS_MAX if x == CAMION_CODE else CAPACITE_POIDS_ESTAFETTE
                )
                details_vehicules['Capacité Max Volume'] = details_vehicules['Code Véhicule'].apply(
                    lambda x: CAMION_VOLUME_MAX if x == CAMION_CODE else CAPACITE_VOLUME_ESTAFETTE
                )
                details_vehicules['Marge Poids'] = details_vehicules['Capacité Max Poids'] - details_vehicules['Poids total chargé']
                details_vehicules['Marge Volume'] = details_vehicules['Capacité Max Volume'] - details_vehicules['Volume total chargé']
                
                details_vehicules.to_excel(writer, sheet_name='Détails Véhicules', index=False)
            
            return True, f"✅ Rapport Excel généré avec succès : {file_path}"
            
        except Exception as e:
            return False, f"❌ Erreur lors de la génération du rapport Excel : {str(e)}"

    def get_voyages_valides(self):
        """Retourne les voyages après validation."""
        return self.df_voyages

# =====================================================
# CLASSE DE GESTION DES RAPPORTS AVANCÉS
# =====================================================
class AdvancedReportGenerator:
    def __init__(self, df_voyages, df_livraisons_original):
        self.df_voyages = df_voyages.copy()
        self.df_livraisons_original = df_livraisons_original.copy()
    
    def generer_rapport_analytique(self):
        """Génère un rapport analytique complet."""
        try:
            analyses = []
            
            # 1. Analyse par type de véhicule
            estafettes = self.df_voyages[self.df_voyages["Code Véhicule"] == "ESTAFETTE"]
            camions = self.df_voyages[self.df_voyages["Code Véhicule"] == CAMION_CODE]
            
            analyses.append("📊 ANALYSE PAR TYPE DE VÉHICULE")
            analyses.append(f"• Nombre total d'estafettes : {len(estafettes)}")
            analyses.append(f"• Nombre total de camions : {len(camions)}")
            analyses.append(f"• Poids total transporté par estafettes : {estafettes['Poids total chargé'].sum():.1f} kg")
            analyses.append(f"• Volume total transporté par estafettes : {estafettes['Volume total chargé'].sum():.3f} m³")
            analyses.append(f"• Poids total transporté par camions : {camions['Poids total chargé'].sum():.1f} kg")
            analyses.append(f"• Volume total transporté par camions : {camions['Volume total chargé'].sum():.3f} m³")
            
            # 2. Analyse par zone
            analyses.append("\n🌍 ANALYSE PAR ZONE GÉOGRAPHIQUE")
            for zone in self.df_voyages["Zone"].unique():
                df_zone = self.df_voyages[self.df_voyages["Zone"] == zone]
                analyses.append(f"• {zone} : {len(df_zone)} véhicules, {df_zone['Poids total chargé'].sum():.1f} kg, {df_zone['Volume total chargé'].sum():.3f} m³")
            
            # 3. Analyse d'efficacité
            analyses.append("\n⚡ ANALYSE D'EFFICACITÉ")
            taux_moyen_estafettes = estafettes["Taux d'occupation (%)"].mean()
            taux_moyen_camions = camions["Taux d'occupation (%)"].mean() if len(camions) > 0 else 0
            
            analyses.append(f"• Taux d'occupation moyen des estafettes : {taux_moyen_estafettes:.1f}%")
            analyses.append(f"• Taux d'occupation moyen des camions : {taux_moyen_camions:.1f}%")
            
            # Véhicules sous-utilisés (< 60%)
            vehicules_sous_utilises = self.df_voyages[self.df_voyages["Taux d'occupation (%)"] < 60]
            if len(vehicules_sous_utilises) > 0:
                analyses.append(f"• Véhicules sous-utilisés (< 60%) : {len(vehicules_sous_utilises)}")
                for idx, row in vehicules_sous_utilises.iterrows():
                    analyses.append(f"  - {row['Véhicule N°']} (Zone {row['Zone']}) : {row['Taux d\'occupation (%)']:.1f}%")
            
            # Véhicules sur-utilisés (> 95%)
            vehicules_sur_utilises = self.df_voyages[self.df_voyages["Taux d'occupation (%)"] > 95]
            if len(vehicules_sur_utilises) > 0:
                analyses.append(f"• Véhicules très chargés (> 95%) : {len(vehicules_sur_utilises)}")
                for idx, row in vehicules_sur_utilises.iterrows():
                    analyses.append(f"  - {row['Véhicule N°']} (Zone {row['Zone']}) : {row['Taux d\'occupation (%)']:.1f}%")
            
            # 4. Analyse économique
            analyses.append("\n💰 ANALYSE ÉCONOMIQUE")
            analyses.append(f"• Coût estimé des estafettes : {len(estafettes)} x [coût unitaire]")
            analyses.append(f"• Coût estimé des camions : {len(camions)} x [coût unitaire camion]")
            
            # 5. Recommandations
            analyses.append("\n🎯 RECOMMANDATIONS")
            if len(vehicules_sous_utilises) > len(vehicules_sur_utilises):
                analyses.append("• Optimisation possible : regrouper certains voyages sous-utilisés")
            
            if camions["Taux d'occupation (%)"].mean() < 70 and len(camions) > 0:
                analyses.append("• Attention : les camions sont sous-utilisés, envisager plus d'estafettes")
            
            if len(vehicules_sur_utilises) > 0:
                analyses.append("• Vigilance : certains véhicules sont à pleine capacité")
            
            return "\n".join(analyses)
            
        except Exception as e:
            return f"❌ Erreur lors de la génération du rapport analytique : {str(e)}"

    def generer_rapport_client(self, client):
        """Génère un rapport spécifique pour un client."""
        try:
            # Trouver tous les BLs du client dans les données originales
            bls_client = self.df_livraisons_original[
                self.df_livraisons_original["Client de l'estafette"] == client
            ]["No livraison"].unique()
            
            # Trouver les véhicules qui transportent ces BLs
            vehicules_client = []
            for idx, row in self.df_voyages.iterrows():
                bls_vehicule = str(row["BL inclus"]).split(';')
                if any(str(bl) in bls_vehicule for bl in bls_client):
                    vehicules_client.append({
                        'Véhicule': row['Véhicule N°'],
                        'Zone': row['Zone'],
                        'Type': 'Camion' if row['Code Véhicule'] == CAMION_CODE else 'Estafette',
                        'Poids': row['Poids total chargé'],
                        'Volume': row['Volume total chargé'],
                        'Taux Occupation': row['Taux d\'occupation (%)'],
                        'Date Livraison Estimée': 'À planifier'  # Peut être enrichi avec des données de planning
                    })
            
            if not vehicules_client:
                return f"Aucune livraison trouvée pour le client {client}"
            
            # Générer le rapport
            rapport = [f"📦 RAPPORT LIVRAISON - CLIENT {client}"]
            rapport.append(f"Nombre de véhicules concernés : {len(vehicules_client)}")
            rapport.append("\nDétails des véhicules :")
            
            for veh in vehicules_client:
                rapport.append(
                    f"• {veh['Type']} {veh['Véhicule']} ({veh['Zone']}) : "
                    f"{veh['Poids']:.1f}kg, {veh['Volume']:.3f}m³, "
                    f"Taux {veh['Taux Occupation']:.1f}%"
                )
            
            # Calcul des totaux
            total_poids = sum(veh['Poids'] for veh in vehicules_client)
            total_volume = sum(veh['Volume'] for veh in vehicules_client)
            
            rapport.append(f"\n📊 TOTAUX CLIENT {client}:")
            rapport.append(f"• Poids total : {total_poids:.1f} kg")
            rapport.append(f"• Volume total : {total_volume:.3f} m³")
            rapport.append(f"• Nombre de véhicules : {len(vehicules_client)}")
            
            return "\n".join(rapport)
            
        except Exception as e:
            return f"❌ Erreur lors de la génération du rapport client : {str(e)}"

# =====================================================
# FONCTIONS UTILITAIRES GLOBALES
# =====================================================
def calculer_couts_estimation(df_voyages, cout_estafette=150, cout_camion=800):
    """Estime les coûts de transport basés sur les véhicules utilisés."""
    try:
        nb_estafettes = len(df_voyages[df_voyages["Code Véhicule"] == "ESTAFETTE"])
        nb_camions = len(df_voyages[df_voyages["Code Véhicule"] == CAMION_CODE])
        
        cout_total = (nb_estafettes * cout_estafette) + (nb_camions * cout_camion)
        
        return {
            'estafettes': nb_estafettes,
            'camions': nb_camions,
            'cout_estafette_unitaire': cout_estafette,
            'cout_camion_unitaire': cout_camion,
            'cout_total': cout_total,
            'cout_estimation': f"💰 Estimation des coûts : {nb_estafettes} estafettes × {cout_estafette} TND + {nb_camions} camions × {cout_camion} TND = {cout_total} TND"
        }
    except Exception as e:
        return {'erreur': f"❌ Erreur dans le calcul des coûts : {str(e)}"}

def exporter_planning_excel(df_voyages, file_path, donnees_supplementaires=None, df_livraisons_original=None):
    """Exporte le planning complet vers Excel avec formatage personnalisé et retours à ligne."""
    try:
        import openpyxl
        from openpyxl.styles import Alignment
        
        with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
            # =====================================================
            # ORDRE EXACT DES COLONNES DEMANDÉ AVEC VILLE
            # =====================================================
            colonnes_demandees = [
                "Code voyage", "Zone", "Ville", "Véhicule N°", "Chauffeur", 
                "BL inclus", "Client(s) inclus", "Poids total chargé", 
                "Volume total chargé"
            ]
            
            # =====================================================
            # CORRECTION : UTILISATION DES COLONNES EXISTANTES
            # =====================================================
            
            # Faire une copie pour éviter les modifications sur l'original
            df_voyages_working = df_voyages.copy()
            
            # 1. Vérifier et mapper "Chauffeur" vers les colonnes existantes
            if "Chauffeur" not in df_voyages_working.columns:
                # Priorité 1 : Utiliser "Chauffeur attribué"
                if "Chauffeur attribué" in df_voyages_working.columns:
                    df_voyages_working["Chauffeur"] = df_voyages_working["Chauffeur attribué"]
                # Priorité 2 : Utiliser "Nom_chauffeur" 
                elif "Nom_chauffeur" in df_voyages_working.columns:
                    df_voyages_working["Chauffeur"] = df_voyages_working["Nom_chauffeur"]
                # Priorité 3 : Utiliser "Matricule chauffeur" avec format
                elif "Matricule chauffeur" in df_voyages_working.columns:
                    df_voyages_working["Chauffeur"] = df_voyages_working["Matricule chauffeur"].apply(
                        lambda x: f"Chauffeur {x}" if pd.notna(x) and x != "" else "À attribuer"
                    )
                # Fallback : Colonne vide
                else:
                    df_voyages_working["Chauffeur"] = "À attribuer"
            
            # 2. AJOUT DE LA COLONNE "VILLE" - NOUVELLE FONCTIONNALITÉ
            if "Ville" not in df_voyages_working.columns and df_livraisons_original is not None:
                print("🔄 Ajout de la colonne Ville depuis les données originales...")
                
                # Créer un mapping BL -> Ville depuis les données originales
                mapping_ville = {}
                
                # Parcourir les données originales pour créer le mapping
                for idx, row in df_livraisons_original.iterrows():
                    bl = str(row.get("No livraison", ""))
                    ville = str(row.get("Ville", ""))
                    if bl and bl != "nan" and ville and ville != "nan":
                        mapping_ville[bl] = ville
                
                # Fonction pour extraire les villes à partir des BLs d'un véhicule
                def get_villes_from_bls(bls_inclus):
                    if pd.isna(bls_inclus) or bls_inclus == "":
                        return ""
                    
                    bls_list = str(bls_inclus).split(';')
                    villes_trouvees = set()
                    
                    for bl in bls_list:
                        bl_clean = bl.strip()
                        if bl_clean in mapping_ville:
                            villes_trouvees.add(mapping_ville[bl_clean])
                        # Ignorer les objets manuels (OBJ-)
                        elif not bl_clean.startswith('OBJ-'):
                            # Chercher le BL dans les données originales
                            for original_bl, original_ville in mapping_ville.items():
                                if bl_clean == original_bl:
                                    villes_trouvees.add(original_ville)
                                    break
                    
                    return ", ".join(sorted(villes_trouvees)) if villes_trouvees else "Ville inconnue"
                
                # Appliquer la fonction pour créer la colonne Ville
                df_voyages_working["Ville"] = df_voyages_working["BL inclus"].apply(get_villes_from_bls)
                print("✅ Colonne 'Ville' ajoutée avec succès")
            
            # 3. FORMATER LES COLONNES AVEC RETOURS À LIGNE
            colonnes_retours_ligne = ['BL inclus', 'Client(s) inclus', 'Représentant(s) inclus']
            for col in colonnes_retours_ligne:
                if col in df_voyages_working.columns:
                    df_voyages_working[col] = df_voyages_working[col].apply(
                        lambda x: '\n'.join([elem.strip() for elem in str(x).replace(';', ',').split(',') if elem.strip()]) 
                        if pd.notna(x) else ""
                    )
            
            # 4. Filtrer seulement les colonnes qui existent
            colonnes_finales = [col for col in colonnes_demandees if col in df_voyages_working.columns]
            
            # 5. Vérifier qu'on a au moins les colonnes de base et que le DataFrame n'est pas vide
            if df_voyages_working.empty:
                # Créer une feuille vide avec les colonnes demandées pour éviter l'erreur
                df_voyages_ordered = pd.DataFrame(columns=colonnes_finales)
                print("⚠️ DataFrame vide - création d'une structure vide")
            else:
                colonnes_requises = ["Zone", "Véhicule N°", "BL inclus", "Client(s) inclus"]
                colonnes_manquantes = [col for col in colonnes_requises if col not in colonnes_finales]
                
                if colonnes_manquantes:
                    print(f"❌ Colonnes manquantes : {', '.join(colonnes_manquantes)}")
                    # Créer quand même l'export avec les colonnes disponibles
                    df_voyages_ordered = df_voyages_working[colonnes_finales].copy()
                else:
                    # 6. Réorganiser le DataFrame avec l'ordre exact demandé
                    df_voyages_ordered = df_voyages_working[colonnes_finales].copy()
            
            # =====================================================
            # FORMATAGE DES VALEURS NUMÉRIQUES
            # =====================================================
            if "Poids total chargé" in df_voyages_ordered.columns and not df_voyages_ordered.empty:
                df_voyages_ordered["Poids total chargé"] = df_voyages_ordered["Poids total chargé"].round(3)
            
            if "Volume total chargé" in df_voyages_ordered.columns and not df_voyages_ordered.empty:
                df_voyages_ordered["Volume total chargé"] = df_voyages_ordered["Volume total chargé"].round(3)
            
            # =====================================================
            # FEUILLE PRINCIPALE - PLANNING LIVRAISONS
            # =====================================================
            # CORRECTION : Vérifier que le DataFrame n'est pas vide avant d'exporter
            if not df_voyages_ordered.empty:
                df_voyages_ordered.to_excel(writer, sheet_name='Planning Livraisons', index=False)
            else:
                # Créer une feuille vide avec les colonnes pour éviter l'erreur
                pd.DataFrame(columns=colonnes_finales).to_excel(writer, sheet_name='Planning Livraisons', index=False)
            
            # =====================================================
            # APPLIQUER LE FORMATAGE DES RETOURS À LIGNE DANS EXCEL
            # =====================================================
            workbook = writer.book
            worksheet = writer.sheets['Planning Livraisons']
            
            # Style avec retours à ligne et centrage
            wrap_alignment = Alignment(
                horizontal='center', 
                vertical='center', 
                wrap_text=True
            )
            
            # Appliquer le formatage aux colonnes avec retours à ligne
            for col_idx, col_name in enumerate(df_voyages_ordered.columns, 1):
                if col_name in colonnes_retours_ligne:
                    for row_idx in range(2, len(df_voyages_ordered) + 2):  # +2 pour header
                        cell = worksheet.cell(row=row_idx, column=col_idx)
                        cell.alignment = wrap_alignment
            
            # Ajuster la hauteur des lignes pour les retours à ligne
            for row in range(2, len(df_voyages_ordered) + 2):
                worksheet.row_dimensions[row].height = 40
            
            # Ajuster automatiquement la largeur des colonnes
            for column in worksheet.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    try:
                        if cell.value:
                            # Calculer la longueur maximale en prenant en compte les retours à ligne
                            lines = str(cell.value).split('\n')
                            max_line_length = max(len(line) for line in lines)
                            max_length = max(max_length, max_line_length)
                    except:
                        pass
                adjusted_width = min(50, (max_length + 2))
                worksheet.column_dimensions[column_letter].width = adjusted_width
            
            # =====================================================
            # FEUILLE DE SYNTHÈSE (optionnelle)
            # =====================================================
            try:
                nb_estafettes = len(df_voyages_working[df_voyages_working["Code Véhicule"] == "ESTAFETTE"]) if "Code Véhicule" in df_voyages_working.columns else 0
                nb_camions = len(df_voyages_working[df_voyages_working["Code Véhicule"] == "CAMION-LOUE"]) if "Code Véhicule" in df_voyages_working.columns else 0
                poids_total = df_voyages_working['Poids total chargé'].sum() if 'Poids total chargé' in df_voyages_working.columns else 0
                volume_total = df_voyages_working['Volume total chargé'].sum() if 'Volume total chargé' in df_voyages_working.columns else 0
                taux_moyen = df_voyages_working['Taux d\'occupation (%)'].mean() if 'Taux d\'occupation (%)' in df_voyages_working.columns else 0
                
                synthèse_data = {
                    'Metric': ['Total Véhicules', 'Estafettes', 'Camions', 'Poids Total', 'Volume Total', 'Taux Occupation Moyen'],
                    'Valeur': [
                        len(df_voyages_working),
                        nb_estafettes,
                        nb_camions,
                        f"{poids_total:.1f} kg",
                        f"{volume_total:.3f} m³",
                        f"{taux_moyen:.1f}%" if taux_moyen > 0 else "N/A"
                    ]
                }
                pd.DataFrame(synthèse_data).to_excel(writer, sheet_name='Synthèse', index=False)
            except Exception as e:
                print(f"⚠️ Erreur lors de la création de la synthèse : {e}")
                # Créer une synthèse basique pour éviter l'erreur
                pd.DataFrame({'Metric': ['Erreur'], 'Valeur': ['Données non disponibles']}).to_excel(writer, sheet_name='Synthèse', index=False)
            
            # =====================================================
            # FEUILLE STATS PAR ZONE (optionnelle)
            # =====================================================
            try:
                if 'Zone' in df_voyages_working.columns and not df_voyages_working.empty:
                    agg_dict = {'Véhicule N°': 'count'}
                    
                    if 'Poids total chargé' in df_voyages_working.columns:
                        agg_dict['Poids total chargé'] = ['sum', 'mean']
                    if 'Volume total chargé' in df_voyages_working.columns:
                        agg_dict['Volume total chargé'] = ['sum', 'mean']
                    if 'Taux d\'occupation (%)' in df_voyages_working.columns:
                        agg_dict['Taux d\'occupation (%)'] = 'mean'
                    
                    stats_zone = df_voyages_working.groupby('Zone').agg(agg_dict).round(2)
                    
                    if isinstance(stats_zone.columns, pd.MultiIndex):
                        stats_zone.columns = ['_'.join(col).strip() for col in stats_zone.columns.values]
                    
                    stats_zone.to_excel(writer, sheet_name='Stats par Zone')
                else:
                    # Créer une feuille stats vide
                    pd.DataFrame(columns=['Zone', 'Nombre_Véhicules']).to_excel(writer, sheet_name='Stats par Zone', index=False)
            except Exception as e:
                print(f"⚠️ Erreur lors de la création des stats par zone : {e}")
                pd.DataFrame(columns=['Zone', 'Nombre_Véhicules']).to_excel(writer, sheet_name='Stats par Zone', index=False)
            
            # =====================================================
            # DONNÉES SUPPLÉMENTAIRES
            # =====================================================
            if donnees_supplementaires:
                for nom_feuille, data in donnees_supplementaires.items():
                    if isinstance(data, pd.DataFrame) and not data.empty:
                        nom_feuille = nom_feuille[:31]
                        data.to_excel(writer, sheet_name=nom_feuille, index=False)
                    else:
                        # Créer une feuille vide pour cette donnée supplémentaire
                        pd.DataFrame({f'Info': [f'Données non disponibles pour {nom_feuille}']}).to_excel(writer, sheet_name=nom_feuille[:31], index=False)
            
            # =====================================================
            # FEUILLE COMPLÈTE (toutes les colonnes) - pour référence
            # =====================================================
            try:
                if not df_voyages_working.empty:
                    df_voyages_complet = df_voyages_working.copy()
                    # Formater les valeurs numériques pour l'export complet
                    if "Poids total chargé" in df_voyages_complet.columns:
                        df_voyages_complet["Poids total chargé"] = df_voyages_complet["Poids total chargé"].round(3)
                    if "Volume total chargé" in df_voyages_complet.columns:
                        df_voyages_complet["Volume total chargé"] = df_voyages_complet["Volume total chargé"].round(3)
                    
                    df_voyages_complet.to_excel(writer, sheet_name='Données Complètes', index=False)
                else:
                    pd.DataFrame(columns=list(df_voyages_working.columns)).to_excel(writer, sheet_name='Données Complètes', index=False)
            except Exception as e:
                print(f"⚠️ Erreur lors de la création de la feuille complète : {e}")
                pd.DataFrame({'Erreur': ['Impossible de créer la feuille complète']}).to_excel(writer, sheet_name='Données Complètes', index=False)
        
        return True, f"✅ Planning exporté avec succès : {file_path}"
    
    except Exception as e:
        return False, f"❌ Erreur lors de l'export Excel : {str(e)}"
# =====================================================
# GARDEZ CETTE FONCTION INTACTE - NE PAS MODIFIER
# =====================================================
def verifier_integrite_donnees(df_voyages, df_livraisons_original):
    """Vérifie l'intégrité des données entre les voyages optimisés et les données originales."""
    try:
        problèmes = []
        
        # Vérifier que tous les BLs originaux sont présents dans les voyages
        bls_originaux = set(df_livraisons_original["No livraison"].astype(str).unique())
        bls_voyages = set()
        
        for bls in df_voyages["BL inclus"]:
            if pd.notna(bls):
                # EXCLURE les objets manuels des vérifications
                bls_filtres = [bl for bl in str(bls).split(';') if not bl.startswith('OBJ-')]
                bls_voyages.update(bls_filtres)
        
        bls_manquants = bls_originaux - bls_voyages
        bls_ajoutes = bls_voyages - bls_originaux
        
        if bls_manquants:
            problèmes.append(f"❌ BLs manquants dans les voyages : {len(bls_manquants)} BLs")
        
        if bls_ajoutes:
            problèmes.append(f"⚠️ BLs supplémentaires dans les voyages : {len(bls_ajoutes)} BLs (objets manuels exclus)")
        
        # Vérifier la cohérence des poids et volumes (EXCLURE les objets manuels)
        poids_total_originel = df_livraisons_original["Poids total"].sum()
        volume_total_originel = df_livraisons_original["Volume total"].sum()
        
        # Calculer les totaux des voyages SANS les objets manuels
        poids_total_voyages_sans_objets = 0
        volume_total_voyages_sans_objets = 0
        
        for idx, row in df_voyages.iterrows():
            bls = str(row.get("BL inclus", ""))
            if pd.notna(bls):
                # Identifier les objets manuels dans ce véhicule
                objets_manuels = [bl for bl in bls.split(';') if bl.startswith('OBJ-')]
                
                if objets_manuels:
                    # Estimer le poids/volume des objets manuels (approximatif)
                    # Ou simplement utiliser les valeurs actuelles comme référence
                    pass
            
            # Pour simplifier, utilisons les données originales comme référence
            poids_total_voyages_sans_objets += row.get("Poids total chargé", 0)
            volume_total_voyages_sans_objets += row.get("Volume total chargé", 0)
        
        # Ajuster pour les objets manuels (estimation)
        # Pour l'instant, utilisons une comparaison directe avec un message explicatif
        
        poids_total_voyages = df_voyages["Poids total chargé"].sum()
        volume_total_voyages = df_voyages["Volume total chargé"].sum()
        
        # Vérifier les écarts avec tolérance
        tolerance = 0.01  # 1%
        
        ecart_poids = abs(poids_total_originel - poids_total_voyages) / poids_total_originel
        ecart_volume = abs(volume_total_originel - volume_total_voyages) / volume_total_originel
        
        if ecart_poids > tolerance:
            problèmes.append(
                f"⚠️ Écart de poids : Original {poids_total_originel:.1f}kg vs "
                f"Voyages {poids_total_voyages:.1f}kg (diff: {poids_total_voyages-poids_total_originel:.1f}kg)"
            )
        
        if ecart_volume > tolerance:
            problèmes.append(
                f"⚠️ Écart de volume : Original {volume_total_originel:.3f}m³ vs "
                f"Voyages {volume_total_voyages:.3f}m³ (diff: {volume_total_voyages-volume_total_originel:.3f}m³)"
            )
        
        # Ajouter une note sur les objets manuels
        objets_count = sum(1 for bls in df_voyages["BL inclus"] if 'OBJ-' in str(bls))
        if objets_count > 0:
            problèmes.append(f"📦 Note : {objets_count} objet(s) manuel(s) inclus dans la planification")
        
        if not problèmes:
            return "✅ Intégrité des données vérifiée - Aucun problème détecté"
        else:
            return "\n".join(problèmes)
            
    except Exception as e:
        return f"❌ Erreur lors de la vérification d'intégrité : {str(e)}"
    
# =====================================================
# MAIN DE TEST (pour développement)
# =====================================================
if __name__ == "__main__":
    # Exemple d'utilisation des classes
    print("🚀 Système d'Optimisation des Livraisons - Backend")
    print("=" * 50)
    
    # Simulation de données de test
    df_test = pd.DataFrame({
        'Zone': ['Zone 1', 'Zone 1', 'Zone 2'],
        'Véhicule N°': ['E1', 'E2', 'C1'],
        'Poids total chargé': [1200, 1400, 15000],
        'Volume total chargé': [3.5, 4.0, 50.0],
        'Code Véhicule': ['ESTAFETTE', 'ESTAFETTE', CAMION_CODE],
        'Taux d\'occupation (%)': [77.4, 90.3, 48.4],
        'BL inclus': ['BL001;BL002', 'BL003', 'BL004;BL005']
    })
    
    # Test de la validation
    validateur = VoyageValidator(df_test)
    rapport = validateur.validate_voyages()
    print("Rapport de validation :")
    print(rapport)
    
    # Test de l'ajout d'objet manuel
    transfer_manager = TruckTransferManager(df_test, pd.DataFrame())
    success, message, df_updated = transfer_manager.add_manual_object(
        df_test, "E1", "Zone 1", "Matériel urgent", 50.0, 0.2
    )
    print(f"\nAjout d'objet manuel : {message}")
    
    print("\n✅ Backend prêt à l'utilisation !")