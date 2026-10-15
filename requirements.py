requirements.txt
streamlit
pandas
numpy
plotly
openpyxl
fpdf



Backend.py





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









APP.PY






import streamlit as st
import pandas as pd
from backend import DeliveryProcessor, TruckRentalProcessor, TruckTransferManager, SEUIL_POIDS, SEUIL_VOLUME 
import plotly.express as px


# =====================================================
# === Fonction show_df pour arrondir à 3 décimales ===
# =====================================================
def show_df(df, **kwargs):
    """
    Affiche un DataFrame avec tous les nombres arrondis à 3 décimales.
    kwargs sont transmis à st.dataframe.
    """
    if isinstance(df, pd.DataFrame):
        df_to_display = df.copy()
        df_to_display = df_to_display.round(3)
        st.dataframe(df_to_display, **kwargs)
    else:
        st.dataframe(df, **kwargs)

# =====================================================
# === Fonction show_df_multiline avec affichage HTML ===
# =====================================================
def show_df_multiline(df, column_to_multiline):
    """
    Affiche un DataFrame avec les articles multilignes dans la même cellule.
    Chaque 'No livraison' reste sur une seule ligne.
    """
    df_display = df.copy()

    # Grouper les lignes par livraison et concaténer les articles avec des <br>
    df_display = df_display.groupby(
        ['No livraison', 'Client', 'Ville', 'Représentant', 'Poids total', 'Volume total'],
        as_index=False
    ).agg({column_to_multiline: lambda x: "<br>".join(x.astype(str))})

    # CSS pour forcer l'affichage des <br> sur plusieurs lignes
    css = """
    <style>
    table {
        width: 100%;
        border-collapse: collapse;
    }
    th, td {
        border: 1px solid #555;
        padding: 8px;
        text-align: left;
        vertical-align: top;
        white-space: normal;
        word-wrap: break-word;
    }
    th {
        background-color: #222;
        color: white;
    }
    td {
        color: #ddd;
    }
    </style>
    """

    html = df_display.to_html(escape=False, index=False)
    st.markdown(css + html, unsafe_allow_html=True)

# =====================================================
# 📌 Constantes pour les véhicules et chauffeurs
# =====================================================
VEHICULES_DISPONIBLES = [
    'SLG-VEH11', 'SLG-VEH14', 'SLG-VEH22', 'SLG-VEH19',
    'SLG-VEH10', 'SLG-VEH16', 'SLG-VEH23', 'SLG-VEH08', 'SLG-VEH20', 'code-Camion'
]

CHAUFFEURS_DETAILS = {
    '09254': 'DAMMAK Karim', '06002': 'MAAZOUN Bassem', '11063': 'SASSI Ramzi',
    '10334': 'BOUJELBENE Mohamed', '15144': 'GADDOUR Rami', '08278': 'DAMMAK Wissem',
    '18339': 'REKIK Ahmed', '07250': 'BARKIA Mustapha', '13321': 'BADRI Moez','Matricule': 'Chauffeur Camion'
}

# Configuration page
st.set_page_config(page_title="Planning Livraisons", layout="wide")
st.title("🚚 Planning de Livraisons & Optimisation des Tournées")
st.markdown("---")

# =====================================================
# INITIALISATION DE L'ÉTAT DE SESSION
# =====================================================
if 'data_processed' not in st.session_state:
    st.session_state.data_processed = False
    st.session_state.df_grouped = None
    st.session_state.df_city = None
    st.session_state.df_grouped_zone = None
    st.session_state.df_zone = None 
    st.session_state.df_optimized_estafettes = None
    st.session_state.df_livraisons_original = None
    st.session_state.rental_processor = None
    st.session_state.propositions = None
    st.session_state.selected_client = None
    st.session_state.message = ""
    st.session_state.df_voyages = None
    st.session_state.df_livraisons = None

# =====================================================
# Fonctions de Callback pour la Location
# =====================================================

def update_propositions_view():
    """Met à jour le DataFrame de propositions après une action."""
    if st.session_state.rental_processor:
        st.session_state.propositions = st.session_state.rental_processor.detecter_propositions()
        
        # CORRECTION : Vérifier si le DataFrame de propositions n'est pas vide et contient la colonne 'Client'
        if (st.session_state.propositions is not None and 
            not st.session_state.propositions.empty and 
            'Client' in st.session_state.propositions.columns):
            
            # Réinitialiser la sélection si le client n'est plus dans les propositions ouvertes
            if (st.session_state.selected_client is not None and 
                st.session_state.selected_client not in st.session_state.propositions['Client'].astype(str).tolist()):
                st.session_state.selected_client = None
    else:
        st.session_state.propositions = pd.DataFrame()

def handle_location_action(accepter):
    """Gère l'acceptation ou le refus de la proposition de location."""
    if st.session_state.rental_processor and st.session_state.selected_client:
        try:
            # Assurer que le client est une chaîne valide
            client_to_process = str(st.session_state.selected_client)
            ok, msg, _ = st.session_state.rental_processor.appliquer_location(
                client_to_process, accepter=accepter
            )
            st.session_state.message = msg
            update_propositions_view()
        except Exception as e:
            st.session_state.message = f"❌ Erreur lors du traitement : {str(e)}"
    elif not st.session_state.selected_client:
        st.session_state.message = "⚠️ Veuillez sélectionner un client à traiter."
    else:
        st.session_state.message = "⚠️ Le processeur de location n'est pas initialisé."

def accept_location_callback():
    handle_location_action(True)

def refuse_location_callback():
    handle_location_action(False)

# =====================================================
# 1. UPLOAD DES FICHIERS INPUT (Section 1)
# =====================================================
st.header("1. 📥 Importation des Données")

col_file_1, col_file_2, col_file_3, col_button = st.columns([1, 1, 1, 1])
with col_file_1:
    liv_file = st.file_uploader("Fichier Livraisons (BL)", type=["xlsx"])
with col_file_2:
    ydlogist_file = st.file_uploader("Fichier Volumes (Articles)", type=["xlsx"])
with col_file_3:
    wcliegps_file = st.file_uploader("Fichier Clients/Zones", type=["xlsx"])
with col_button:
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("Exécuter le traitement complet", type="primary"):
        if liv_file and ydlogist_file and wcliegps_file:
            processor = DeliveryProcessor()
            try:
                with st.spinner("Traitement des données en cours..."):
                    # Récupération des 6 valeurs
                    df_grouped, df_city, df_grouped_zone, df_zone, df_optimized_estafettes, df_livraisons_original = processor.process_delivery_data(liv_file, ydlogist_file, wcliegps_file)
                
                # Stockage des résultats dans l'état de session
                st.session_state.df_optimized_estafettes = df_optimized_estafettes
                st.session_state.df_grouped = df_grouped
                st.session_state.df_city = df_city
                st.session_state.df_grouped_zone = df_grouped_zone
                st.session_state.df_zone = df_zone 
                st.session_state.df_livraisons_original = df_livraisons_original
                st.session_state.df_livraisons = df_grouped_zone  # Pour la section transfert
                
                # Initialisation avec les données originales
                st.session_state.rental_processor = TruckRentalProcessor(df_optimized_estafettes, df_livraisons_original)
                update_propositions_view()
                
                st.session_state.data_processed = True
                st.session_state.message = "Traitement terminé avec succès ! Les résultats s'affichent ci-dessous."
                st.rerun()

            except Exception as e:
                st.error(f"❌ Erreur lors du traitement : {str(e)}")
                st.session_state.data_processed = False
        else:
            st.warning("Veuillez uploader tous les fichiers nécessaires.")
st.markdown("---")

# =====================================================
# AFFICHAGE DES RÉSULTATS (Se déclenche si les données sont traitées)
# =====================================================
if st.session_state.data_processed:
    
    # Affichage des messages d'opération
    if st.session_state.message.startswith("✅"):
        st.success(st.session_state.message)
    elif st.session_state.message.startswith("❌"):
        st.error(st.session_state.message)
    elif st.session_state.message.startswith("⚠️"):
        st.warning(st.session_state.message)
    else:
        st.info(st.session_state.message or "Prêt à traiter les propositions de location.")
    
    # Récupération du DF mis à jour à chaque fois
    df_optimized_estafettes = st.session_state.rental_processor.get_df_result() 
    
# =====================================================
# 2. ANALYSE DE LIVRAISON DÉTAILLÉE (Section 2)
# =====================================================
st.header("2. 🔍 Analyse de Livraison Détaillée")

tab_grouped, tab_city, tab_zone_group, tab_zone_summary, tab_charts = st.tabs([
    "Livraisons Client/Ville", 
    "Besoin Estafette par Ville", 
    "Livraisons Client/Zone", 
    "Besoin Estafette par Zone",
    "Graphiques"
])

# --- Onglet Livraisons Client/Ville ---
with tab_grouped:
    st.subheader("Livraisons par Client & Ville")
    show_df(st.session_state.df_grouped.drop(columns=["Zone"], errors='ignore'), use_container_width=True)
    
    # Bouton de téléchargement
    from io import BytesIO
    excel_buffer_grouped = BytesIO()
    with pd.ExcelWriter(excel_buffer_grouped, engine='openpyxl') as writer:
        st.session_state.df_grouped.drop(columns=["Zone"], errors='ignore').to_excel(writer, index=False, sheet_name="Livraisons Client Ville")
    excel_buffer_grouped.seek(0)
    
    st.download_button(
        label="💾 Télécharger Livraisons Client/Ville",
        data=excel_buffer_grouped,
        file_name="Livraisons_Client_Ville.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

# --- Onglet Besoin Estafette par Ville ---
with tab_city:
    st.subheader("Besoin Estafette par Ville")
    show_df(st.session_state.df_city, use_container_width=True)
    
    # Bouton de téléchargement
    excel_buffer_city = BytesIO()
    with pd.ExcelWriter(excel_buffer_city, engine='openpyxl') as writer:
        st.session_state.df_city.to_excel(writer, index=False, sheet_name="Besoin Estafette Ville")
    excel_buffer_city.seek(0)
    
    st.download_button(
        label="💾 Télécharger Besoin par Ville",
        data=excel_buffer_city,
        file_name="Besoin_Estafette_Ville.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

# --- Onglet Livraisons Client & Ville + Zone ---
with tab_zone_group:
    st.subheader("Livraisons par Client & Ville + Zone")
    show_df(st.session_state.df_grouped_zone, use_container_width=True)
    
    # Bouton de téléchargement
    excel_buffer_zone_group = BytesIO()
    with pd.ExcelWriter(excel_buffer_zone_group, engine='openpyxl') as writer:
        st.session_state.df_grouped_zone.to_excel(writer, index=False, sheet_name="Livraisons Client Ville Zone")
    excel_buffer_zone_group.seek(0)
    
    st.download_button(
        label="💾 Télécharger Livraisons Client/Ville/Zone",
        data=excel_buffer_zone_group,
        file_name="Livraisons_Client_Ville_Zone.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

# --- Onglet Besoin Estafette par Zone ---
with tab_zone_summary:
    st.subheader("Besoin Estafette par Zone")
    show_df(st.session_state.df_zone, use_container_width=True)
    
    # Bouton de téléchargement
    excel_buffer_zone = BytesIO()
    with pd.ExcelWriter(excel_buffer_zone, engine='openpyxl') as writer:
        st.session_state.df_zone.to_excel(writer, index=False, sheet_name="Besoin Estafette Zone")
    excel_buffer_zone.seek(0)
    
    st.download_button(
        label="💾 Télécharger Besoin par Zone",
        data=excel_buffer_zone,
        file_name="Besoin_Estafette_Zone.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

# --- Onglet Graphiques ---
with tab_charts:
    st.subheader("Statistiques par Ville")
    col1, col2 = st.columns(2)
    with col1:
        st.plotly_chart(
            px.bar(st.session_state.df_city, x="Ville", y="Poids total",
                   title="Poids total livré par ville"),
            use_container_width=True
        )
    with col2:
        st.plotly_chart(
            px.bar(st.session_state.df_city, x="Ville", y="Volume total",
                   title="Volume total livré par ville (m³)"),
            use_container_width=True
        )

    col3, col4 = st.columns(2)
    with col3:
        st.plotly_chart(
            px.bar(st.session_state.df_city, x="Ville", y="Nombre livraisons",
                   title="Nombre de livraisons par ville"),
            use_container_width=True
        )
    with col4:
        st.plotly_chart(
            px.bar(st.session_state.df_city, x="Ville", y="Besoin estafette réel",
                   title="Besoin en Estafettes par ville"),
            use_container_width=True
        )

st.markdown("---")

# =====================================================
# 3. PROPOSITION DE LOCATION DE CAMION (Section 3)
# =====================================================
st.header("3. 🚚 Proposition de location de camion")
st.markdown(f"🔸 Si un client dépasse **{SEUIL_POIDS} kg** ou **{SEUIL_VOLUME} m³**, une location est proposée (si non déjà décidée).")

if st.session_state.propositions is not None and not st.session_state.propositions.empty:
    col_prop, col_details = st.columns([2, 3])
    
    with col_prop:
        st.markdown("### Propositions ouvertes")
        
        # CORRECTION : Vérifier si la colonne 'Client' existe
        if 'Client' in st.session_state.propositions.columns:
            # Affichage des propositions ouvertes avec show_df
            show_df(
                st.session_state.propositions,
                use_container_width=True,
                column_order=["Client", "Poids total (kg)", "Volume total (m³)", "Raison"],
                hide_index=True
            )
            
            # Sélection du client
            client_options = st.session_state.propositions['Client'].astype(str).tolist()
            client_options_with_empty = [""] + client_options
            
            # Index de sélection par défaut
            default_index = 0
            if st.session_state.selected_client in client_options:
                 default_index = client_options_with_empty.index(st.session_state.selected_client)
            elif len(client_options) > 0:
                 default_index = 1

            st.session_state.selected_client = st.selectbox(
                "Client à traiter :", 
                options=client_options_with_empty, 
                index=default_index,
                key='client_select' 
            )
        else:
            st.warning("⚠️ Format de données incorrect dans les propositions.")
            st.session_state.selected_client = None

        col_btn_acc, col_btn_ref = st.columns(2)
        is_client_selected = st.session_state.selected_client != "" and st.session_state.selected_client is not None
        
        with col_btn_acc:
            st.button(
                "✅ Accepter la location", 
                on_click=accept_location_callback, 
                disabled=not is_client_selected,
                use_container_width=True
            )
        with col_btn_ref:
            st.button(
                "❌ Refuser la proposition", 
                on_click=refuse_location_callback, 
                disabled=not is_client_selected,
                use_container_width=True
            )

    with col_details:
        st.markdown("### Détails de la commande client")
        if is_client_selected:
            try:
                resume, details_df_styled = st.session_state.rental_processor.get_details_client(
                    st.session_state.selected_client
                )
                st.text(resume)
                show_df(details_df_styled, use_container_width=True, hide_index=True)
            except Exception as e:
                st.error(f"❌ Erreur lors de la récupération des détails : {str(e)}")
        else:
            st.info("Sélectionnez un client pour afficher les détails de la commande/estafettes.")
else:
    st.success("🎉 Aucune proposition de location de camion en attente de décision.")

st.markdown("---")

# =====================================================
# 4. VOYAGES PAR ESTAFETTE OPTIMISÉ (Section 4 - Résultat final)
# =====================================================
st.header("4. 🚐 Voyages par Estafette Optimisé (Inclut Camions Loués)")

try:
    # CORRECTION : Nettoyer les colonnes en double
    df_clean = df_optimized_estafettes.loc[:, ~df_optimized_estafettes.columns.duplicated()]
    
    # Vérifier les colonnes disponibles
    st.info(f"📊 Colonnes disponibles: {', '.join(df_clean.columns)}")
    
    # Définir l'ordre des colonnes pour l'affichage
    colonnes_ordre = [
        "Zone", "Véhicule N°", "Poids total chargé", "Volume total chargé",
        "Client(s) inclus", "Représentant(s) inclus", "BL inclus", 
        "Taux d'occupation (%)", "Location_camion", "Location_proposee", "Code Véhicule"
    ]
    
    # Filtrer seulement les colonnes qui existent
    colonnes_finales = [col for col in colonnes_ordre if col in df_clean.columns]
    
    # Créer le DataFrame d'affichage
    df_display = df_clean[colonnes_finales].copy()
    
    # Formater les colonnes numériques
    if "Poids total chargé" in df_display.columns:
        df_display["Poids total chargé"] = df_display["Poids total chargé"].map(lambda x: f"{x:.3f} kg")
    if "Volume total chargé" in df_display.columns:
        df_display["Volume total chargé"] = df_display["Volume total chargé"].map(lambda x: f"{x:.3f} m³")
    if "Taux d'occupation (%)" in df_display.columns:
        df_display["Taux d'occupation (%)"] = df_display["Taux d'occupation (%)"].map(lambda x: f"{x:.3f}%")
    
    # Afficher le tableau
    show_df(df_display, use_container_width=True)
    
    # Préparer l'export Excel
    df_export = df_clean.copy()
    if "Poids total chargé" in df_export.columns:
        df_export["Poids total chargé"] = df_export["Poids total chargé"].round(3)
    if "Volume total chargé" in df_export.columns:
        df_export["Volume total chargé"] = df_export["Volume total chargé"].round(3)
    
    # Bouton de téléchargement
    from io import BytesIO
    excel_buffer = BytesIO()
    with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
        df_export.to_excel(writer, index=False, sheet_name="Voyages Optimisés")
    excel_buffer.seek(0)
    
    st.download_button(
        label="💾 Télécharger Voyages Estafette Optimisés",
        data=excel_buffer,
        file_name="Voyages_Estafette_Optimises.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    
    # Mise à jour pour les sections suivantes
    st.session_state.df_voyages = df_clean

except Exception as e:
    st.error(f"❌ Erreur lors de l'affichage des voyages optimisés: {str(e)}")
    # Afficher les données brutes pour debug
    st.write("Données brutes pour debug:")
    st.write("Colonnes:", list(df_optimized_estafettes.columns))
    st.write("Doublons:", df_optimized_estafettes.columns.duplicated().sum())

# =====================================================
# 5️⃣ TRANSFERT DES BLs ENTRE ESTAFETTES / CAMIONS
# =====================================================
st.markdown("## 🔁 Transfert de BLs entre Estafettes / Camions")

MAX_POIDS = 1550  # kg
MAX_VOLUME = 4.608  # m³

if "df_voyages" not in st.session_state:
    st.warning("⚠️ Vous devez d'abord exécuter la section 4 (Voyages par Estafette Optimisé).")
elif "df_livraisons" not in st.session_state:
    st.warning("⚠️ Le DataFrame des livraisons détaillées n'est pas disponible.")
else:
    df_voyages = st.session_state.df_voyages.copy()
    df_livraisons = st.session_state.df_livraisons.copy()

    colonnes_requises = ["Zone", "Véhicule N°", "Poids total chargé", "Volume total chargé", "BL inclus"]

    if not all(col in df_voyages.columns for col in colonnes_requises):
        st.error(f"❌ Le DataFrame ne contient pas toutes les colonnes nécessaires : {', '.join(colonnes_requises)}")
    else:
        zones_disponibles = sorted(df_voyages["Zone"].dropna().unique().tolist())
        zone_selectionnee = st.selectbox("🌍 Sélectionner une zone", zones_disponibles)

        if zone_selectionnee:
            df_zone = df_voyages[df_voyages["Zone"] == zone_selectionnee]
            vehicules = sorted(df_zone["Véhicule N°"].dropna().unique().tolist())

            col1, col2 = st.columns(2)
            with col1:
                source = st.selectbox("🚐 Estafette / Camion source", vehicules)
            with col2:
                cible = st.selectbox("🎯 Estafette / Camion cible", [v for v in vehicules if v != source])

            if source and cible:
                df_source = df_zone[df_zone["Véhicule N°"] == source]
                if df_source.empty or df_source["BL inclus"].isna().all():
                    st.warning("⚠️ Aucun BL trouvé pour ce véhicule source.")
                else:
                    st.subheader(f"📦 BLs actuellement assignés à {source}")

                    # --- Affichage formaté pour Streamlit ---
                    df_source_display = df_source[["Véhicule N°", "Poids total chargé", "Volume total chargé", "BL inclus"]].copy()
                    df_source_display["Poids total chargé"] = df_source_display["Poids total chargé"].map(lambda x: f"{x:.3f} kg")
                    df_source_display["Volume total chargé"] = df_source_display["Volume total chargé"].map(lambda x: f"{x:.3f} m³")
                    show_df(df_source_display, use_container_width=True)

                    bls_disponibles = df_source["BL inclus"].iloc[0].split(";")
                    bls_selectionnes = st.multiselect("📋 Sélectionner les BLs à transférer :", bls_disponibles)

                    if bls_selectionnes and st.button("🔁 Exécuter le transfert"):

                        df_bls_selection = df_livraisons[df_livraisons["No livraison"].isin(bls_selectionnes)]
                        poids_bls = df_bls_selection["Poids total"].sum()
                        volume_bls = df_bls_selection["Volume total"].sum()

                        df_cible = df_zone[df_zone["Véhicule N°"] == cible]
                        poids_cible = df_cible["Poids total chargé"].sum()
                        volume_cible = df_cible["Volume total chargé"].sum()

                        if (poids_cible + poids_bls) > MAX_POIDS or (volume_cible + volume_bls) > MAX_VOLUME:
                            st.warning("⚠️ Le transfert dépasse les limites de poids ou volume du véhicule cible.")
                        else:
                            def transfer_bl(row):
                                bls = row["BL inclus"].split(";") if pd.notna(row["BL inclus"]) else []
                                bls_to_move = [b for b in bls if b in bls_selectionnes]

                                if row["Véhicule N°"] == source:
                                    new_bls = [b for b in bls if b not in bls_to_move]
                                    row["BL inclus"] = ";".join(new_bls)
                                    row["Poids total chargé"] = max(0, row["Poids total chargé"] - poids_bls)
                                    row["Volume total chargé"] = max(0, row["Volume total chargé"] - volume_bls)
                                elif row["Véhicule N°"] == cible:
                                    new_bls = bls + bls_to_move
                                    row["BL inclus"] = ";".join(new_bls)
                                    row["Poids total chargé"] += poids_bls
                                    row["Volume total chargé"] += volume_bls
                                return row

                            df_voyages = df_voyages.apply(transfer_bl, axis=1)
                            st.session_state.df_voyages = df_voyages
                            st.success(f"✅ Transfert réussi : {len(bls_selectionnes)} BL(s) déplacé(s) de {source} vers {cible}.")

                            # --- Affichage Streamlit ---
                            st.subheader("📊 Voyages après transfert (toutes les zones)")
                            df_display = df_voyages.sort_values(by=["Zone", "Véhicule N°"]).copy()
                            df_display["Poids total chargé"] = df_display["Poids total chargé"].map(lambda x: f"{x:.3f} kg")
                            df_display["Volume total chargé"] = df_display["Volume total chargé"].map(lambda x: f"{x:.3f} m³")
                            show_df(df_display[colonnes_requises], use_container_width=True)

                            # --- Export Excel arrondi ---
                            df_export = df_voyages.copy()
                            df_export["Poids total chargé"] = df_export["Poids total chargé"].round(3)
                            df_export["Volume total chargé"] = df_export["Volume total chargé"].round(3)

                            from io import BytesIO
                            excel_buffer = BytesIO()
                            with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                                df_export.to_excel(writer, index=False, sheet_name='Transfert BLs')
                            excel_buffer.seek(0)

                            st.download_button(
                                label="💾 Télécharger le tableau mis à jour (XLSX)",
                                data=excel_buffer,
                                file_name="voyages_apres_transfert.xlsx",
                                mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                            )

# =====================================================
# 6️⃣ VALIDATION DES VOYAGES APRÈS TRANSFERT
# =====================================================
st.markdown("## ✅ VALIDATION DES VOYAGES APRÈS TRANSFERT")

from io import BytesIO

# --- Fonction pour exporter DataFrame en Excel avec arrondi ---
def to_excel(df, sheet_name="Voyages Validés"):
    df_export = df.copy()
    if "Poids total chargé" in df_export.columns:
        df_export["Poids total chargé"] = df_export["Poids total chargé"].round(3)
    if "Volume total chargé" in df_export.columns:
        df_export["Volume total chargé"] = df_export["Volume total chargé"].round(3)

    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_export.to_excel(writer, index=False, sheet_name=sheet_name)
    return output.getvalue()

# --- Création du DataFrame de validation à partir du df_voyages ---
if "df_voyages" in st.session_state:
    voyages_apres_transfert = st.session_state.df_voyages.copy()
    df_validation = voyages_apres_transfert.copy()

    if "validations" not in st.session_state:
        st.session_state.validations = {}

    # --- Affichage interactif des voyages ---
    for idx, row in df_validation.iterrows():
        with st.expander(f"🚚 Voyage {row['Véhicule N°']} | Zone : {row['Zone']}"):
            st.write("**Informations du voyage :**")
            row_display = row.to_frame().T.copy()
            if "Poids total chargé" in row_display.columns:
                row_display["Poids total chargé"] = row_display["Poids total chargé"].map(lambda x: f"{x:.3f} kg")
            if "Volume total chargé" in row_display.columns:
                row_display["Volume total chargé"] = row_display["Volume total chargé"].map(lambda x: f"{x:.3f} m³")
            show_df(row_display, use_container_width=True)

            choix = st.radio(
                f"Valider ce voyage ? (Estafette {row['Véhicule N°']})",
                ["Oui", "Non"],
                index=0 if st.session_state.validations.get(idx) == "Oui" 
                      else 1 if st.session_state.validations.get(idx) == "Non" 
                      else 0,
                key=f"validation_{idx}"
            )
            st.session_state.validations[idx] = choix

    # --- Bouton pour appliquer les validations ---
    if st.button("🧮 Appliquer la validation"):
        valid_indexes = [i for i, v in st.session_state.validations.items() if v == "Oui"]
        valid_indexes = [i for i in valid_indexes if i in df_validation.index]

        df_voyages_valides = df_validation.loc[valid_indexes].reset_index(drop=True)
        st.session_state.df_voyages_valides = df_voyages_valides

        st.success(f"✅ {len(df_voyages_valides)} voyage(s) validé(s).")
        st.markdown("### 📦 Voyages Validés")

        # --- Affichage Streamlit avec unités ---
        df_display = df_voyages_valides.copy()
        if "Poids total chargé" in df_display.columns:
            df_display["Poids total chargé"] = df_display["Poids total chargé"].map(lambda x: f"{x:.3f} kg")
        if "Volume total chargé" in df_display.columns:
            df_display["Volume total chargé"] = df_display["Volume total chargé"].map(lambda x: f"{x:.3f} m³")
        show_df(df_display, use_container_width=True)

        # --- Export Excel arrondi ---
        excel_data = to_excel(df_voyages_valides)
        st.download_button(
            label="💾 Télécharger les voyages validés (XLSX)",
            data=excel_data,
            file_name="Voyages_valides.xlsx",
            mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
else:
    st.warning("⚠️ Vous devez d'abord exécuter la section 4 (Voyages par Estafette Optimisé).")

# =====================================================
# 7️⃣ ATTRIBUTION DES VÉHICULES ET CHAUFFEURS
# =====================================================
st.markdown("## 🚛 ATTRIBUTION DES VÉHICULES ET CHAUFFEURS")

if 'df_voyages_valides' in st.session_state and not st.session_state.df_voyages_valides.empty:

    df_attribution = st.session_state.df_voyages_valides.copy()

    if "attributions" not in st.session_state:
        st.session_state.attributions = {}

    for idx, row in df_attribution.iterrows():
        with st.expander(f"🚚 Voyage {row['Véhicule N°']} | Zone : {row['Zone']}"):
            st.write("**Informations du voyage :**")
            row_display = row.to_frame().T.copy()
            if "Poids total chargé" in row_display.columns:
                row_display["Poids total chargé"] = row_display["Poids total chargé"].map(lambda x: f"{x:.2f} kg")
            if "Volume total chargé" in row_display.columns:
                row_display["Volume total chargé"] = row_display["Volume total chargé"].map(lambda x: f"{x:.3f} m³")
            show_df(row_display, use_container_width=True)

            vehicule_selectionne = st.selectbox(
                f"Véhicule pour le voyage {row['Véhicule N°']}",
                VEHICULES_DISPONIBLES,
                index=0 if st.session_state.attributions.get(idx, {}).get("Véhicule") else 0,
                key=f"vehicule_{idx}"
            )
            chauffeur_selectionne = st.selectbox(
                f"Chauffeur pour le voyage {row['Véhicule N°']}",
                list(CHAUFFEURS_DETAILS.values()),
                index=0 if st.session_state.attributions.get(idx, {}).get("Chauffeur") else 0,
                key=f"chauffeur_{idx}"
            )

            st.session_state.attributions[idx] = {
                "Véhicule": vehicule_selectionne,
                "Chauffeur": chauffeur_selectionne
            }

    if st.button("✅ Appliquer les attributions"):

        df_attribution["Véhicule attribué"] = df_attribution.index.map(lambda i: st.session_state.attributions[i]["Véhicule"])
        df_attribution["Chauffeur attribué"] = df_attribution.index.map(lambda i: st.session_state.attributions[i]["Chauffeur"])

        
        st.markdown("### 📦 Voyages avec Véhicule et Chauffeur")

        # --- Affichage formaté ---
        df_display = df_attribution.copy()
        if "Poids total chargé" in df_display.columns:
            df_display["Poids total chargé"] = df_display["Poids total chargé"].map(lambda x: f"{x:.3f} kg")
        if "Volume total chargé" in df_display.columns:
            df_display["Volume total chargé"] = df_display["Volume total chargé"].map(lambda x: f"{x:.3f} m³")
        show_df(df_display, use_container_width=True)

        # --- Export Excel ---
        from io import BytesIO
        def to_excel(df):
            df_export = df.copy()
            if "Poids total chargé" in df_export.columns:
                df_export["Poids total chargé"] = df_export["Poids total chargé"].round(3)
            if "Volume total chargé" in df_export.columns:
                df_export["Volume total chargé"] = df_export["Volume total chargé"].round(3)
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_export.to_excel(writer, index=False, sheet_name='Voyages_Attribués')
            return output.getvalue()

        st.download_button(
            label="💾 Télécharger le tableau final (XLSX)",
            data=to_excel(df_attribution),
            file_name="Voyages_attribues.xlsx",
            mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )

        # --- Export PDF corrigé ---
        from fpdf import FPDF

        def to_pdf(df, title="Voyages Attribués"):
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Arial", 'B', 14)
            pdf.cell(0, 10, title, ln=True, align="C")
            pdf.ln(5)

            pdf.set_font("Arial", '', 10)

            # Créer une copie formatée pour le PDF avec unités
            df_pdf = df.copy()
            if "Poids total chargé" in df_pdf.columns:
                df_pdf["Poids total chargé"] = df_pdf["Poids total chargé"].map(lambda x: f"{x:.3f} kg")
            if "Volume total chargé" in df_pdf.columns:
                df_pdf["Volume total chargé"] = df_pdf["Volume total chargé"].map(lambda x: f"{x:.3f} m³")

            col_widths = [pdf.get_string_width(col)+6 for col in df_pdf.columns]

            # En-têtes
            for i, col in enumerate(df_pdf.columns):
                pdf.cell(col_widths[i], 8, str(col), border=1, align='C')
            pdf.ln()

            # Lignes
            for _, row in df_pdf.iterrows():
                for i, col in enumerate(df_pdf.columns):
                    pdf.cell(col_widths[i], 8, str(row[col]), border=1)
                pdf.ln()

            return pdf.output(dest='S').encode('latin1')

        st.download_button(
            label="📄 Télécharger le tableau final (PDF)",
            data=to_pdf(df_attribution),
            file_name="Voyages_attribues.pdf",
            mime='application/pdf'
        )
else:
    st.warning("⚠️ Vous devez d'abord valider les voyages dans la section 6.")