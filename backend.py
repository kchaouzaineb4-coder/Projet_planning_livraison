import pandas as pd
import math
import numpy as np

# --- Constantes pour la location de camion ---
SEUIL_POIDS = 3000.0    # kg
SEUIL_VOLUME = 9.216    # m³
CAPACITE_POIDS_ESTAFETTE = 1550  # kg
CAPACITE_VOLUME_ESTAFETTE = 4.608  # m³
CAMION_CODE = "CAMION-LOUE"

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
        }).rename(columns={"No livraison": "Nombre livraisons"})
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
        
        df_result.rename(columns={
            "Poids total": "Poids total chargé",
            "Volume total": "Volume total chargé",
            "Client(s) inclus": "Client(s) inclus",
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

# =====================================================
# CLASSE POUR L'AJOUT MANUEL DE BLs/MACHINES
# =====================================================
class ManualBLManager:
    def __init__(self, df_voyages, df_livraisons_original):
        self.df_voyages = df_voyages.copy()
        self.df_livraisons_original = df_livraisons_original.copy()
        self.CAPACITE_POIDS_ESTAFETTE = CAPACITE_POIDS_ESTAFETTE
        self.CAPACITE_VOLUME_ESTAFETTE = CAPACITE_VOLUME_ESTAFETTE
        self.CAPACITE_POIDS_CAMION = 30500  # kg - capacité approximative d'un camion
        self.CAPACITE_VOLUME_CAMION = 77.5  # m³ - capacité approximative d'un camion

    def get_voyages_disponibles(self, zone=None):
        """Retourne la liste des voyages disponibles pour l'ajout manuel."""
        df_disponibles = self.df_voyages.copy()
        
        if zone:
            df_disponibles = df_disponibles[df_disponibles["Zone"] == zone]
        
        # Sélectionner les colonnes pertinentes pour l'affichage
        colonnes_a_garder = [
            "Zone", "Véhicule N°", "Poids total chargé", "Volume total chargé", 
            "Taux d'occupation (%)", "Code Véhicule", "BL inclus"
        ]
        
        df_disponibles = df_disponibles[[col for col in colonnes_a_garder if col in df_disponibles.columns]]
        
        return df_disponibles

    def verifier_capacite_ajout(self, vehicule_num, poids_ajout, volume_ajout):
        """Vérifie si l'ajout est possible dans le véhicule sélectionné."""
        try:
            # Trouver le véhicule
            vehicule = self.df_voyages[self.df_voyages["Véhicule N°"] == vehicule_num]
            
            if vehicule.empty:
                return False, f"❌ Véhicule {vehicule_num} non trouvé"
            
            ligne_vehicule = vehicule.iloc[0]
            poids_actuel = ligne_vehicule["Poids total chargé"]
            volume_actuel = ligne_vehicule["Volume total chargé"]
            code_vehicule = ligne_vehicule["Code Véhicule"]
            
            # Déterminer les capacités maximales selon le type de véhicule
            if code_vehicule == CAMION_CODE:
                capacite_poids = self.CAPACITE_POIDS_CAMION
                capacite_volume = self.CAPACITE_VOLUME_CAMION
                type_vehicule = "camion"
            else:
                capacite_poids = self.CAPACITE_POIDS_ESTAFETTE
                capacite_volume = self.CAPACITE_VOLUME_ESTAFETTE
                type_vehicule = "estafette"
            
            # Vérifier les capacités
            nouveau_poids = poids_actuel + poids_ajout
            nouveau_volume = volume_actuel + volume_ajout
            
            if nouveau_poids > capacite_poids:
                return False, f"❌ Capacité poids dépassée : {nouveau_poids:.1f} kg > {capacite_poids} kg"
            
            if nouveau_volume > capacite_volume:
                return False, f"❌ Capacité volume dépassée : {nouveau_volume:.3f} m³ > {capacite_volume} m³"
            
            # Calculer le nouveau taux d'occupation
            taux_poids = (nouveau_poids / capacite_poids) * 100
            taux_volume = (nouveau_volume / capacite_volume) * 100
            nouveau_taux_occupation = max(taux_poids, taux_volume)
            
            message = (
                f"✅ Ajout possible dans le {type_vehicule} {vehicule_num}\n"
                f"• Poids actuel : {poids_actuel:.1f} kg → {nouveau_poids:.1f} kg\n"
                f"• Volume actuel : {volume_actuel:.3f} m³ → {nouveau_volume:.3f} m³\n"
                f"• Taux d'occupation : {ligne_vehicule['Taux d\\'occupation (%)']:.1f}% → {nouveau_taux_occupation:.1f}%"
            )
            
            return True, message
            
        except Exception as e:
            return False, f"❌ Erreur lors de la vérification : {str(e)}"

    def ajouter_objet_manuel(self, designation, poids_kg, volume_m3, vehicule_num, client="AJOUT MANUEL", representant="AJOUT MANUEL"):
        """Ajoute manuellement un objet (BL, machine, etc.) dans un véhicule."""
        try:
            # Vérifier d'abord la capacité
            possible, message_verif = self.verifier_capacite_ajout(vehicule_num, poids_kg, volume_m3)
            
            if not possible:
                return False, message_verif, self.df_voyages
            
            # Trouver l'index du véhicule
            idx_vehicule = self.df_voyages[self.df_voyages["Véhicule N°"] == vehicule_num].index[0]
            ligne_vehicule = self.df_voyages.loc[idx_vehicule]
            
            # Mettre à jour les données du véhicule
            nouveau_poids = ligne_vehicule["Poids total chargé"] + poids_kg
            nouveau_volume = ligne_vehicule["Volume total chargé"] + volume_m3
            
            # Mettre à jour les BLs inclus
            bls_actuels = str(ligne_vehicule["BL inclus"]).split(';')
            bls_actuels = [bl for bl in bls_actuels if bl and bl != 'nan']  # Nettoyer
            bls_actuels.append(designation)
            nouveaux_bls = ";".join(bls_actuels)
            
            # Mettre à jour les clients inclus
            clients_actuels = str(ligne_vehicule["Client(s) inclus"]).split(',')
            clients_actuels = [c.strip() for c in clients_actuels if c.strip() and c.strip() != 'nan']
            if client not in clients_actuels:
                clients_actuels.append(client)
            nouveaux_clients = ", ".join(clients_actuels)
            
            # Mettre à jour les représentants inclus
            representants_actuels = str(ligne_vehicule["Représentant(s) inclus"]).split(',')
            representants_actuels = [r.strip() for r in representants_actuels if r.strip() and r.strip() != 'nan']
            if representant not in representants_actuels:
                representants_actuels.append(representant)
            nouveaux_representants = ", ".join(representants_actuels)
            
            # Recalculer le taux d'occupation
            if ligne_vehicule["Code Véhicule"] == CAMION_CODE:
                capacite_poids = self.CAPACITE_POIDS_CAMION
                capacite_volume = self.CAPACITE_VOLUME_CAMION
            else:
                capacite_poids = self.CAPACITE_POIDS_ESTAFETTE
                capacite_volume = self.CAPACITE_VOLUME_ESTAFETTE
            
            taux_poids = (nouveau_poids / capacite_poids) * 100
            taux_volume = (nouveau_volume / capacite_volume) * 100
            nouveau_taux_occupation = max(taux_poids, taux_volume)
            
            # Appliquer les modifications
            self.df_voyages.at[idx_vehicule, "Poids total chargé"] = nouveau_poids
            self.df_voyages.at[idx_vehicule, "Volume total chargé"] = nouveau_volume
            self.df_voyages.at[idx_vehicule, "BL inclus"] = nouveaux_bls
            self.df_voyages.at[idx_vehicule, "Client(s) inclus"] = nouveaux_clients
            self.df_voyages.at[idx_vehicule, "Représentant(s) inclus"] = nouveaux_representants
            self.df_voyages.at[idx_vehicule, "Taux d'occupation (%)"] = nouveau_taux_occupation
            
            message_succes = (
                f"✅ Objet '{designation}' ajouté avec succès au véhicule {vehicule_num}\n"
                f"• Poids ajouté : {poids_kg:.1f} kg\n"
                f"• Volume ajouté : {volume_m3:.3f} m³\n"
                f"• Nouveau taux d'occupation : {nouveau_taux_occupation:.1f}%"
            )
            
            return True, message_succes, self.df_voyages
            
        except Exception as e:
            return False, f"❌ Erreur lors de l'ajout manuel : {str(e)}", self.df_voyages

    def get_capacites_vehicules(self):
        """Retourne les capacités des différents types de véhicules."""
        return {
            "estafette": {
                "poids_max": self.CAPACITE_POIDS_ESTAFETTE,
                "volume_max": self.CAPACITE_VOLUME_ESTAFETTE
            },
            "camion": {
                "poids_max": self.CAPACITE_POIDS_CAMION,
                "volume_max": self.CAPACITE_VOLUME_CAMION
            }
        }

    def get_statistiques_vehicule(self, vehicule_num):
        """Retourne les statistiques détaillées d'un véhicule."""
        try:
            vehicule = self.df_voyages[self.df_voyages["Véhicule N°"] == vehicule_num]
            
            if vehicule.empty:
                return None
            
            ligne = vehicule.iloc[0]
            
            if ligne["Code Véhicule"] == CAMION_CODE:
                capacite_poids = self.CAPACITE_POIDS_CAMION
                capacite_volume = self.CAPACITE_VOLUME_CAMION
                type_vehicule = "Camion loué"
            else:
                capacite_poids = self.CAPACITE_POIDS_ESTAFETTE
                capacite_volume = self.CAPACITE_VOLUME_ESTAFETTE
                type_vehicule = "Estafette"
            
            stats = {
                "Véhicule": vehicule_num,
                "Type": type_vehicule,
                "Zone": ligne["Zone"],
                "Poids actuel": f"{ligne['Poids total chargé']:.1f} kg",
                "Volume actuel": f"{ligne['Volume total chargé']:.3f} m³",
                "Poids disponible": f"{capacite_poids - ligne['Poids total chargé']:.1f} kg",
                "Volume disponible": f"{capacite_volume - ligne['Volume total chargé']:.3f} m³",
                "Taux d'occupation": f"{ligne['Taux d\\'occupation (%)']:.1f}%",
                "BLs inclus": ligne["BL inclus"],
                "Clients inclus": ligne["Client(s) inclus"]
            }
            
            return stats
            
        except Exception as e:
            print(f"❌ Erreur lors de la récupération des statistiques: {e}")
            return None