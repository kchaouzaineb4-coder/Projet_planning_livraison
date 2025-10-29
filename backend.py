import pandas as pd
import math
import numpy as np

# --- seuils pour la proposition de camions ---
SEUIL_POIDS = 3000.0  # kg
SEUIL_VOLUME = 9.216  # m³

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

            # Regroupement par ville et client
            df_grouped, df_city = self._group_data(df_final)

            # Calcul du besoin en estafette par ville
            df_city = self._calculate_estafette_need(df_city)

            # Nouveau tableau : ajout Zone
            df_grouped_zone = self._add_zone(df_grouped)

            # Filtrer les livraisons avec "Zone inconnue"
            df_grouped_zone = df_grouped_zone[df_grouped_zone["Zone"] != "Zone inconnue"].copy()
            
            # Préparer le dataframe pour l'optimisation en s'assurant que la colonne 'Client' et 'Représentant' est là
            df_grouped_zone = df_grouped_zone.rename(columns={"Client": "Client de l'estafette"})

            # 🆕 Groupement par zone
            df_zone = self._group_by_zone(df_grouped_zone)
            
            # 🆕 Calcul du besoin en estafette par zone
            df_zone = self._calculate_estafette_need(df_zone)

            # 🆕 1. Initialiser le DF pour la gestion des propositions (contient les colonnes de camion)
            df_truck_proposal_base = self._init_truck_columns(df_grouped_zone)
            
            # 🆕 2. Calcul des voyages optimisés (basé sur le DF initial sans camion loué)
            df_optimized_estafettes = self._calculate_optimized_estafette(df_truck_proposal_base)

            # 🆕 Retourne les six DataFrames
            return df_grouped, df_city, df_grouped_zone, df_zone, df_optimized_estafettes, df_truck_proposal_base

        except Exception as e:
            raise Exception(f"❌ Erreur lors du traitement des données : {str(e)}")

    # =====================================================
    # 🔹 Chargement des données
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
            df.rename(columns={df.columns[16]: "Unité Volume", df.columns[13]: "Poids de l'US"}, inplace=True)
        return df

    def _load_wcliegps(self, wcliegps_file):
        df_clients = pd.read_excel(wcliegps_file)
        
        if len(df_clients.columns) > 16:
            df_clients.rename(columns={df_clients.columns[16]: "Représentant"}, inplace=True)
        
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
        return df[(df["Type livraison"] != "SDC") & (~df["Client commande"].isin(clients_exclus))]

    # =====================================================
    # 🔹 Calcul Poids & Volume & Fusion
    # =====================================================
    def _calculate_weights(self, df):
        df["Poids de l'US"] = pd.to_numeric(df["Poids de l'US"].astype(str).str.replace(",", ".")
                                             .str.replace(r"[^\d.]", "", regex=True), errors="coerce").fillna(0)
        df["Quantité livrée US"] = pd.to_numeric(df["Quantité livrée US"], errors="coerce").fillna(0)
        df["Poids total"] = df["Quantité livrée US"] * df["Poids de l'US"]
        return df[["No livraison", "Article", "Client commande", "Poids total"]]

    def _calculate_volumes(self, df_liv, df_art):
        df_liv_sel = df_liv[["No livraison", "Article", "Quantité livrée US", "Client commande"]]
        df_art_sel = df_art[["Article", "Volume de l'US", "Unité Volume"]].copy()
        
        df_art_sel["Volume de l'US"] = pd.to_numeric(df_art_sel["Volume de l'US"].astype(str).str.replace(",", "."), errors="coerce")
        return pd.merge(df_liv_sel, df_art_sel, on="Article", how="left")

    def _merge_delivery_data(self, df_poids, df_vol):
        return pd.merge(df_poids, df_vol, on=["No livraison", "Article", "Client commande"], how="left")

    # =====================================================
    # 🔹 Ajout Client, Ville et Représentant
    # =====================================================
    def _add_city_client_info(self, df, df_clients):
        return pd.merge(df, df_clients[["Client", "Ville", "Représentant"]],
                        left_on="Client commande", right_on="Client", how="left")

    # =====================================================
    # 🔹 Groupement par Livraison/Client/Ville/Représentant
    # =====================================================
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
    # 🔹 Groupement par Zone
    # =====================================================
    def _group_by_zone(self, df_grouped_zone):
        df_zone = df_grouped_zone.groupby("Zone", as_index=False).agg({
            "Poids total": "sum",
            "Volume total": "sum",
            "No livraison": "count"
        }).rename(columns={"No livraison": "Nombre livraisons"})
        return df_zone

    # =====================================================
    # 🆕 1. Initialisation des colonnes de suivi de location
    # (Doit être appelée sur le df_grouped_zone après le traitement initial)
    # =====================================================
    def _init_truck_columns(self, df):
        """Ajoute les colonnes de suivi de location de camion au DataFrame de base."""
        df_truck = df.copy()
        
        if "Location_camion" not in df_truck.columns:
            df_truck["Location_camion"] = False       
        if "Location_proposee" not in df_truck.columns:
            df_truck["Location_proposee"] = False     
        
        if "Code Véhicule" not in df_truck.columns:
            df_truck["Code Véhicule"] = ""
        if "Camion N°" not in df_truck.columns:
            df_truck["Camion N°"] = "À Optimiser"
        if "taux d'occupation (%)" not in df_truck.columns:
            df_truck["taux d'occupation (%)"] = 0.0

        df_truck.rename(columns={"Client de l'estafette": "Client commande"}, inplace=True)
        
        return df_truck
        
    # =====================================================
    # 🆕 2. Détecter clients dépassant les seuils
    # =====================================================
    def detect_truck_proposals(self, df):
        """Détecte les clients dont la commande totale dépasse les seuils de poids ou volume."""
        
        # Exclure les clients déjà ACCOMPLISHED 
        df_open = df[df["Location_camion"] == False]
        
        grouped = df_open.groupby("Client commande", dropna=False).agg(
            Poids_sum=pd.NamedAgg(column="Poids total", aggfunc="sum"),
            Volume_sum=pd.NamedAgg(column="Volume total", aggfunc="sum"),
            Zones=pd.NamedAgg(column="Zone", aggfunc=lambda s: ", ".join(sorted(set([str(x) for x in s if pd.notna(x)]))))
        ).reset_index()

        propositions = grouped[(grouped["Poids_sum"] >= SEUIL_POIDS) | (grouped["Volume_sum"] >= SEUIL_VOLUME)].copy()

        def get_reason(row):
            reasons = []
            if row["Poids_sum"] >= SEUIL_POIDS:
                reasons.append(f"Poids ≥ {SEUIL_POIDS} kg")
            if row["Volume_sum"] >= SEUIL_VOLUME:
                reasons.append("Volume ≥ {:.3f} m³".format(SEUIL_VOLUME))
            return " & ".join(reasons)
            
        propositions["Raison"] = propositions.apply(get_reason, axis=1)
        
        return propositions.sort_values(["Poids_sum", "Volume_sum"], ascending=False).reset_index(drop=True)

    # =====================================================
    # 🆕 3. Appliquer/Refuser une proposition de location
    # =====================================================
    def apply_truck_rental(self, df, client, accept):
        """Applique ou refuse la location d'un camion pour un client donné."""
        mask = df["Client commande"] == client
        
        if not mask.any():
            return False, "Client introuvable.", df
        
        df_updated = df.copy()
        
        if accept:
            # MARQUAGE : marquer comme 'accepté'
            df_updated.loc[mask, ["Location_proposee", "Location_camion", "Code Véhicule"]] = [True, True, "CAMION-LOUE"]
            
            poids_total = df_updated.loc[mask, "Poids total"].sum()
            volume_total = df_updated.loc[mask, "Volume total"].sum()
            
            taux_occu = max(poids_total/SEUIL_POIDS*100, volume_total/SEUIL_VOLUME*100)
            
            # Appliquer les totaux et l'ID du camion à TOUTES les lignes BL de ce client
            df_updated.loc[mask, [
                "Camion N°", 
                "Poids total", 
                "Volume total", 
                "taux d'occupation (%)"
            ]] = [
                "C1", 
                poids_total, 
                volume_total, 
                taux_occu
            ]
            
            return True, f"✅ Location de camion acceptée pour le client **{client}**.", df_updated
            
        else:
            # MARQUAGE : marquer comme 'refusé' (Location_camion = False, Location_proposee = True)
            df_updated.loc[mask, ["Location_proposee", "Location_camion", "Code Véhicule"]] = [True, False, "REFUSÉ"]
            
            # Pour le refus, on réinitialise l'état du camion à 'À Optimiser'
            # Les poids/volumes individuels des BL du client doivent être rétablis
            # Nous n'avons pas la trace des poids/volumes individuels dans df_truck_proposal_base car il est déjà agrégé par BL.
            # MAIS le poids/volume appliqué lors du grouping est déjà celui du BL.
            # Seules les colonnes Camion N° et Taux d'occupation doivent être réinitialisées
            
            df_updated.loc[mask, ["Camion N°", "taux d'occupation (%)"]] = ["À Optimiser", 0.0]

            return True, f"❌ Proposition de location refusée pour le client **{client}**. La commande sera traitée par les Estafettes.", df_updated
            
    # =====================================================
    # 🆕 4. Calcul des voyages optimisés (mis à jour pour gérer les camions loués)
    # =====================================================
    def _calculate_optimized_estafette(self, df_grouped_zone):
        MAX_POIDS = 1550  # kg
        MAX_VOLUME = 4.608 # m3

        resultats = []
        estafette_num = 1 

        # 1. Identifier les livraisons déjà assignées (Camions loués C1)
        if "Camion N°" in df_grouped_zone.columns:
            # Filtrer pour ne conserver que les lignes à optimiser par Estafette
            df_to_optimize = df_grouped_zone[
                (df_grouped_zone["Camion N°"] == "À Optimiser") | 
                (df_grouped_zone["Camion N°"].isna())
            ].copy()
            
            # Récupérer les lignes déjà assignées (C1) et les agréger pour le rapport final
            df_trucks_assigned = df_grouped_zone[
                (df_grouped_zone["Camion N°"] != "À Optimiser") & 
                (~df_grouped_zone["Camion N°"].isna())
            ].copy()

            df_trucks_agg = pd.DataFrame()
            if not df_trucks_assigned.empty:
                # La colonne Client commande dans ce DF est 'Client commande'
                df_trucks_agg = df_trucks_assigned.groupby("Camion N°", as_index=False).agg(
                    Zone=pd.NamedAgg(column="Zone", aggfunc=lambda x: ", ".join(sorted(set(x)))),
                    Poids_total_chargé=pd.NamedAgg(column="Poids total", aggfunc="first"),
                    Volume_total_chargé=pd.NamedAgg(column="Volume total", aggfunc="first"),
                    Client_s_inclus=pd.NamedAgg(column="Client commande", aggfunc=lambda x: ", ".join(sorted(set(x)))),
                    Représentant_s_inclus=pd.NamedAgg(column="Représentant", aggfunc=lambda x: ", ".join(sorted(set(x)))),
                    BL_inclus=pd.NamedAgg(column="No livraison", aggfunc=lambda x: ";".join(x.astype(str))),
                    Taux_occupation=pd.NamedAgg(column="taux d'occupation (%)", aggfunc="first"),
                ).rename(columns={
                    "Poids_total_chargé": "Poids total chargé",
                    "Volume_total_chargé": "Volume total chargé",
                    "Client_s_inclus": "Client(s) inclus",
                    "Représentant_s_inclus": "Représentant(s) inclus",
                    "BL_inclus": "BL inclus",
                    "Taux_occupation": "Taux d'occupation (%)",
                    "Camion N°": "Estafette N°" 
                })
                # Assigner des numéros d'estafette uniques aux camions loués pour le rapport
                if "C1" in df_trucks_agg["Estafette N°"].values:
                     # On démarre la numérotation des estafettes après l'ID du camion
                    estafette_num += len(df_trucks_agg[df_trucks_agg["Estafette N°"] != "C1"])
                    df_trucks_agg.loc[df_trucks_agg["Estafette N°"] == "C1", "Estafette N°"] = "C1 (Loué)"
            
        else:
            df_to_optimize = df_grouped_zone.copy()
            df_trucks_agg = pd.DataFrame()
        
        # Le DF à optimiser doit avoir la colonne client correcte (Client de l'estafette pour la boucle)
        if "Client commande" in df_to_optimize.columns:
             df_to_optimize.rename(columns={"Client commande": "Client de l'estafette"}, inplace=True)


        # === Optimisation Estafette (sur les lignes restantes) ===
        for zone, group in df_to_optimize.groupby("Zone"):
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
                    if e["poids"] + poids <= MAX_POIDS and e["volume"] + volume <= MAX_VOLUME:
                        e["poids"] += poids
                        e["volume"] += volume
                        e["bls"].append(bl)
                        e["clients"].add(client) 
                        e["representants"].add(representant)
                        placed = True
                        break

                if not placed:
                    estafettes.append({
                        "poids": poids,
                        "volume": volume,
                        "bls": [bl],
                        "clients": {client},
                        "representants": {representant}
                    })

            for e in estafettes:
                clients_list = ", ".join(sorted(list(e["clients"])))
                representants_list = ", ".join(sorted(list(e["representants"])))
                
                resultats.append([
                    zone,
                    estafette_num,  
                    e["poids"],
                    e["volume"],
                    clients_list,   
                    representants_list,
                    ";".join(e["bls"])
                ])
                estafette_num += 1

        df_estafettes_optimized = pd.DataFrame(resultats, columns=["Zone", "Estafette N°", "Poids total chargé", "Volume total chargé", "Client(s) inclus", "Représentant(s) inclus", "BL inclus"])

        # CALCUL DU TAUX D'OCCUPATION pour les estafettes
        if not df_estafettes_optimized.empty:
            df_estafettes_optimized["Taux Poids (%)"] = (df_estafettes_optimized["Poids total chargé"] / MAX_POIDS) * 100
            df_estafettes_optimized["Taux Volume (%)"] = (df_estafettes_optimized["Volume total chargé"] / MAX_VOLUME) * 100
            df_estafettes_optimized["Taux d'occupation (%)"] = df_estafettes_optimized[["Taux Poids (%)", "Taux Volume (%)"]].max(axis=1).round(2)
            df_estafettes_optimized = df_estafettes_optimized.drop(columns=["Taux Poids (%)", "Taux Volume (%)"]) 
            df_estafettes_optimized["Estafette N°"] = "Estafette-" + df_estafettes_optimized["Estafette N°"].astype(str)
        
        # === Fusionner les résultats des camions loués (df_trucks_agg) et des estafettes optimisées ===
        if not df_trucks_agg.empty:
            df_final_optimized = pd.concat([df_trucks_agg, df_estafettes_optimized], ignore_index=True)
            # Remplacer les NaN qui peuvent survenir après la concaténation
            df_final_optimized.fillna('', inplace=True) 
        else:
            df_final_optimized = df_estafettes_optimized


        return df_final_optimized
