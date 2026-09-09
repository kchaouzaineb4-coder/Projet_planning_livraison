import pandas as pd
import math
import numpy as np

# --- Constantes pour la location de camion ---
SEUIL_POIDS = 3000.0    # kg
SEUIL_VOLUME = 9.216    # m³
CAPACITE_POIDS_ESTAFETTE = 1550  # kg
CAPACITE_VOLUME_ESTAFETTE = 4.608  # m³

# NOUVELLES CONSTANTES POUR LES TYPES DE CAMIONS
CAPACITE_POIDS_CAMION_5T = 5000  # kg
CAPACITE_VOLUME_CAMION_5T = 20.0  # m³
CAPACITE_POIDS_CAMION_10T = 10000  # kg
CAPACITE_VOLUME_CAMION_10T = 40.0  # m³

CAMION_CODE = "CAMION-LOUE"

# REMPLACER LES ANCIENNES CONSTANTES PAR DES FONCTIONS
def get_capacite_poids_camion(truck_type="5 tonnes"):
    """Retourne la capacité poids selon le type de camion."""
    if truck_type == "10 tonnes":
        return CAPACITE_POIDS_CAMION_10T
    else:  # 5 tonnes par défaut
        return CAPACITE_POIDS_CAMION_5T

def get_capacite_volume_camion(truck_type="5 tonnes"):
    """Retourne la capacité volume selon le type de camion."""
    if truck_type == "10 tonnes":
        return CAPACITE_VOLUME_CAMION_10T
    else:  # 5 tonnes par défaut
        return CAPACITE_VOLUME_CAMION_5T

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

            # Stocker les données originales du tableau "Livraisons par Client & Ville + Zone"
            self.df_livraisons_original = df_grouped_zone.copy()

            # Retourner 6 valeurs
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
        }).rename(columns={"No livraison": "Nombre de BLs"})
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
        """Initialise avec le DataFrame optimisé ET les données originales."""
        self.df_base = self._initialize_rental_columns(df_optimized.copy())
        self.df_livraisons_original = df_livraisons_original.copy()
        self._next_camion_num = self.df_base[self.df_base["Code Véhicule"] == CAMION_CODE].shape[0] + 1
        self.truck_type = "5 tonnes"  # Valeur par défaut
    
    def _get_capacites_camion(self, truck_type="5 tonnes"):
        """Retourne les capacités selon le type de camion."""
        return get_capacite_poids_camion(truck_type), get_capacite_volume_camion(truck_type)
    
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
            # Vérifier que le client existe
            if client is None or client == "":
                return "Client non spécifié", pd.DataFrame()
            
            # Récupérer les totaux RÉELS du client depuis les données originales
            if self.df_livraisons_original is None or self.df_livraisons_original.empty:
                return f"⚠️ Données originales non disponibles pour {client}", pd.DataFrame()
            
            client_data_original = self.df_livraisons_original[
                self.df_livraisons_original["Client de l'estafette"] == client
            ]
            
            if client_data_original.empty:
                return f"⚠️ Aucune donnée pour {client}", pd.DataFrame()

            # Calculer les totaux RÉELS
            total_poids_reel = client_data_original["Poids total"].sum() if "Poids total" in client_data_original.columns else 0
            total_volume_reel = client_data_original["Volume total"].sum() if "Volume total" in client_data_original.columns else 0
            
            # Récupérer les BLs du client
            bls_client = client_data_original["No livraison"].unique() if "No livraison" in client_data_original.columns else []
            
            # Trouver les estafettes qui contiennent ces BLs
            details_estafettes = []
            if self.df_base is not None and not self.df_base.empty:
                for _, row in self.df_base.iterrows():
                    bls_in_vehicle = str(row.get("BL inclus", "")).split(';')
                    bls_commun = set(map(str, bls_client)) & set(bls_in_vehicle)
                    
                    if bls_commun:
                        details_estafettes.append({
                            'Zone': row.get('Zone', 'Inconnue'),
                            'Camion N°': row.get('Camion N°', row.get('Véhicule N°', 'Inconnu')),
                            'Poids total': row.get('Poids total', row.get('Poids total chargé', 0)),
                            'Volume total': row.get('Volume total', row.get('Volume total chargé', 0)),
                            'BL inclus': row.get('BL inclus', ''),
                            'Taux d\'occupation (%)': row.get('Taux d\'occupation (%)', 0)
                        })
            
            # Déterminer l'état
            etat = "Non décidée"
            if self.df_base is not None and not self.df_base.empty:
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
            return f"❌ Erreur avec le client {client}: {str(e)}", pd.DataFrame()

    def appliquer_location(self, client, accepter, truck_type="5 tonnes"):
        """Applique la décision de location pour un client avec réoptimisation automatique."""
        try:
            # Stocker le type de camion
            self.truck_type = truck_type
            
            # Récupérer les capacités pour ce type de camion
            capacite_poids, capacite_volume = self._get_capacites_camion(truck_type)
            
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
                
                # Vérifier que les totaux ne dépassent pas la capacité du camion
                if poids_total > capacite_poids:
                    return False, f"❌ Le poids total ({poids_total:.1f} kg) dépasse la capacité du camion {truck_type} ({capacite_poids} kg).", self.df_base
                
                if volume_total > capacite_volume:
                    return False, f"❌ Le volume total ({volume_total:.3f} m³) dépasse la capacité du camion {truck_type} ({capacite_volume} m³).", self.df_base
                
                # Calcul du taux d'occupation du camion avec les capacités appropriées
                taux_poids = (poids_total / capacite_poids) * 100
                taux_volume = (volume_total / capacite_volume) * 100
                taux_occu = max(taux_poids, taux_volume)
                
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
                    "Type_Camion": truck_type,
                    "Capacite_Poids": capacite_poids,
                    "Capacite_Volume": capacite_volume
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
                return True, f"✅ Location ACCEPTÉE pour {client} avec camion {truck_type}. Commandes transférées vers {camion_num_final}. Réoptimisation des estafettes effectuée.", self.detecter_propositions()
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
            df_result["Véhicule N°"]