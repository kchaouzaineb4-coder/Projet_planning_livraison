import pandas as pd
import math
import numpy as np 

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
        
        # S'assurer que 'Camion N°' existe avant de copier/filtrer
        if 'Camion N°' not in df_optimized.columns:
             df_optimized['Camion N°'] = df_optimized["Estafette N°"].apply(lambda x: f"E{int(x)}" if pd.notna(x) else "À Optimiser")
             
        self.df_base = self._initialize_rental_columns(df_optimized.copy())
        
        # Initialiser le prochain numéro séquentiel C# pour les nouvelles locations
        self._next_camion_num = self._get_initial_camion_num(self.df_base)

    def _get_initial_camion_num(self, df):
        """Détermine le prochain numéro séquentiel (C#) à partir des données existantes."""
        # On regarde dans 'Camion N°' car c'est là que l'ID C# est stocké après l'application de location
        if 'Camion N°' not in df.columns:
            return 1
            
        c_nums = df[df['Camion N°'].astype(str).str.startswith('C', na=False)]['Camion N°'].astype(str)
        if c_nums.empty:
            return 1
            
        max_c = 0
        for c in c_nums:
            try:
                # Extrait le numéro après 'C' (ex: 'C12' -> 12)
                num = int(c[1:]) 
                max_c = max(max_c, num)
            except ValueError:
                continue
        # Le prochain numéro est max + 1
        return max_c + 1

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
            df["Code Véhicule"] = ""
        # Assurer que les BLs sont bien des chaînes
        df['BL inclus'] = df['BL inclus'].astype(str)
        
        return df

    def detecter_propositions(self):
        """
        Regroupe les données par Client commande pour déterminer si le SEUIL est dépassé.
        Retourne un DataFrame des clients proposables.
        """
        # Exclure les clients déjà traités (ceux où Location_proposee est True)
        df_pending = self.df_base[~self.df_base["Location_proposee"]].copy()

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

    def get_details_client(self, client):
        """Récupère et formate les détails de tous les BLs/voyages pour un client."""
        if "Client commande" not in self.df_base.columns:
            return "Erreur: Colonne 'Client commande' manquante.", pd.DataFrame()
            
        data = self.df_base[self.df_base["Client commande"] == client].copy()
        
        if data.empty:
            return f"Aucune donnée pour {client}", pd.DataFrame()

        total_poids = data["Poids total"].sum()
        total_volume = data["Volume total"].sum()
        
        etat = "Non décidée" 
        
        if (data["Location_camion"]).any():
            etat = "Location ACCEPTÉE"
        elif (data["Location_proposee"]).any():
            etat = "Proposition REFUSÉE"
        
        # Colonnes pour l'affichage des détails
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
        """Applique ou refuse la location pour un client et met à jour le DataFrame de base."""
        mask = self.df_base["Client commande"] == client
        if not mask.any():
            return False, "Client introuvable.", self.df_base

        df = self.df_base.copy()
        
        poids_total = df.loc[mask, "Poids total"].sum()
        volume_total = df.loc[mask, "Volume total"].sum()
        bl_concat = ";".join(df.loc[mask, "BL inclus"].astype(str).unique().tolist()) 
        representants = ";".join(sorted(df.loc[mask, "Représentant"].astype(str).unique().tolist()))
        zones = ";".join(sorted(df.loc[mask, "Zone"].astype(str).unique().tolist()))
        
        TAUX_POIDS_MAX_LOC = 5000 
        TAUX_VOLUME_MAX_LOC = 15 
        
        taux_occu = max(poids_total / TAUX_POIDS_MAX_LOC * 100, volume_total / TAUX_VOLUME_MAX_LOC * 100)
        
        if accepter:
            # --- LOGIQUE C# SÉQUENTIELLE ---
            camion_id = f"C{self._next_camion_num}"
            self._next_camion_num += 1
            # -------------------------------
            
            # Créer un nouveau voyage (une seule ligne) pour le camion loué
            new_row = pd.DataFrame([{
                "Zone": zones,
                "Estafette N°": 0, # Mettre à 0 pour le tri (les camions loués seront triés en premier)
                "Poids total": poids_total,
                "Volume total": volume_total,
                "BL inclus": bl_concat,
                "Client commande": client,
                "Représentant": representants,
                "Location_camion": True,
                "Location_proposee": True,
                "Code Véhicule": CAMION_CODE,
                "Camion N°": camion_id,    # Stocke l'ID C# ici pour l'affichage final
                "Taux d'occupation (%)": taux_occu,
            }])
            
            # Supprimer les lignes d'estafette existantes pour ce client
            df = df[~mask]
            
            # Ajouter la nouvelle ligne
            df = pd.concat([df, new_row], ignore_index=True)
            
            self.df_base = df
            return True, f"✅ Location ACCEPTÉE pour {client}. ID Voyage: {camion_id}. Les commandes ont été consolidées.", self.detecter_propositions()
        else:
            # Refuser la proposition (les commandes restent dans les estafettes optimisées)
            df.loc[mask, ["Location_proposee", "Location_camion", "Code Véhicule"]] = [True, False, "ESTAFETTE"]
            self.df_base = df
            return True, f"❌ Proposition REFUSÉE pour {client}. Les commandes restent réparties en Estafettes.", self.detecter_propositions()

    def get_df_result(self):
        """Retourne le DataFrame optimisé final avec les modifications de location."""
        df_result = self.df_base.copy() 
        
        # 1. Créer la colonne d'affichage unique (ID Voyage)
        # Utilise Camion N° (qui contient C#) si Location_camion est True, sinon utilise E#
        df_result['ID Voyage'] = np.where(
            df_result['Location_camion'] == True,
            df_result['Camion N°'], 
            df_result['Estafette N°'].apply(lambda x: f"E{int(x)}" if pd.notna(x) and x > 0 else 'Erreur ID')
        )
        
        # 2. Renommer les colonnes pour les rendre conformes à l'affichage final
        df_result.rename(columns={
             "Poids total": "Poids total chargé",
             "Volume total": "Volume total chargé",
             "Client commande": "Client(s) inclus",
             "Représentant": "Représentant(s) inclus"
        }, inplace=True)
        
        # 3. Colonnes à inclure dans le résultat final, dans l'ordre
        final_cols_display = [
             "Zone", "ID Voyage", "Poids total chargé", "Volume total chargé", 
             "Client(s) inclus", "Représentant(s) inclus", "BL inclus", "Taux d'occupation (%)"
        ]
        
        # 4. Tri final: Les camions loués (Estafette N°=0) en premier, puis les autres par numéro
        # Estafette N° est la colonne de tri numérique
        df_result = df_result.sort_values(by=["Estafette N°", "Zone"], ascending=[True, True])

        # 5. Retourner uniquement les colonnes d'affichage
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
            
            # Groupement par zone
            df_zone = self._group_by_zone(df_grouped_zone)
            
            # Calcul du besoin en estafette par zone
            df_zone = self._calculate_estafette_need(df_zone)

            # Calcul des voyages optimisés 
            df_optimized_estafettes = self._calculate_optimized_estafette(df_grouped_zone)

            # Retourne les DataFrames + l'instance TruckRentalProcessor
            return df_grouped, df_city, df_grouped_zone, df_zone, df_optimized_estafettes

        except Exception as e:
            raise Exception(f"❌ Erreur lors du traitement des données : {str(e)}")

    # ... (les autres méthodes de DeliveryProcessor restent inchangées)

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
        
        required_cols = ["Client", "Ville", "Représentant"]
        for col in required_cols:
            if col not in df_clients.columns:
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
                    if e["poids"] + poids <= MAX_POIDS and e["volume"] + volume <= MAX_VOLUME:
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
            
        df_estafettes = pd.DataFrame(resultats, columns=["Zone", "Estafette N°", "Poids total chargé", "Volume total chargé", "Client(s) inclus", "Représentant(s) inclus", "BL inclus"])
        
        # CALCUL DU TAUX D'OCCUPATION
        df_estafettes["Taux Poids (%)"] = (df_estafettes["Poids total chargé"] / MAX_POIDS) * 100
        df_estafettes["Taux Volume (%)"] = (df_estafettes["Volume total chargé"] / MAX_VOLUME) * 100
        df_estafettes["Taux d'occupation (%)"] = df_estafettes[["Taux Poids (%)", "Taux Volume (%)"]].max(axis=1).round(2)
        
        # Initialisation des colonnes de location pour le TruckRentalProcessor
        df_estafettes["Location_camion"] = False
        df_estafettes["Location_proposee"] = False
        df_estafettes["Code Véhicule"] = "ESTAFETTE"
        df_estafettes["Camion N°"] = df_estafettes["Estafette N°"].apply(lambda x: f"E{int(x)}")
        
        # Nettoyage et formatage final
        df_estafettes = df_estafettes.drop(columns=["Taux Poids (%)", "Taux Volume (%)"]) 
        
        return df_estafettes
