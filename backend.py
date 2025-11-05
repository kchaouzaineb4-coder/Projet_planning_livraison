import pandas as pd
import math
import numpy as np
from typing import Tuple, List, Dict

# --- CONSTANTS ---
SEUIL_POIDS = 3000.0    # kg
SEUIL_VOLUME = 9.216    # m³
CAMION_CODE = "CAMION-LOUE"
CAMION_POIDS_MAX = 30500.0  # kg
CAMION_VOLUME_MAX = 77.5    # m³

class TruckRentalProcessor:
    """
    Classe pour gérer la logique de proposition et de décision de location de camion
    avec réoptimisation après chaque location.
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
        Regroupe les données par Client commande pour déterminer si le SEUIL est dépassé.
        Retourne un DataFrame des clients proposables.
        """
        processed_clients = self.df_base[self.df_base["Location_proposee"]]["Client commande"].unique()
        df_pending = self.df_base[~self.df_base["Client commande"].isin(processed_clients)].copy()

        if df_pending.empty:
            return pd.DataFrame()

        grouped = df_pending.groupby("Client commande").agg(
            Poids_sum=pd.NamedAgg(column="Poids total", aggfunc="sum"),
            Volume_sum=pd.NamedAgg(column="Volume total", aggfunc="sum"),
            Zones=pd.NamedAgg(column="Zone", aggfunc=lambda s: ", ".join(sorted(set(s.astype(str).tolist())))
        ).reset_index()

        propositions = grouped[(grouped["Poids_sum"] >= SEUIL_POIDS) | (grouped["Volume_sum"] >= SEUIL_VOLUME)].copy()

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

    def _reoptimiser_estafettes(self, df_estafettes_restantes):
        """
        Réoptimise la distribution des BLs dans les estafettes après suppression d'un client.
        """
        MAX_POIDS = 1550
        MAX_VOLUME = 4.608

        resultats = []
        estafette_num = 1

        for zone, group in df_estafettes_restantes.groupby("Zone"):
            bls_details = []
            for idx, row in group.iterrows():
                bls = row["BL inclus"].split(';')
                for bl in bls:
                    if bl.strip():
                        bls_details.append({
                            'bl': bl.strip(),
                            'poids': row["Poids total"] / len(bls),
                            'volume': row["Volume total"] / len(bls),
                            'client': row["Client commande"],
                            'representant': row["Représentant"]
                        })
            
            if not bls_details:
                continue

            bls_sorted = sorted(bls_details, key=lambda x: x['poids'], reverse=True)
            estafettes = []
            
            for bl_info in bls_sorted:
                placed = False
                
                for e in estafettes:
                    if e["poids"] + bl_info['poids'] <= MAX_POIDS and e["volume"] + bl_info['volume'] <= MAX_VOLUME:
                        e["poids"] += bl_info['poids']
                        e["volume"] += bl_info['volume']
                        e["bls"].append(bl_info['bl'])
                        e["clients"].add(bl_info['client'])
                        e["representants"].add(bl_info['representant'])
                        placed = True
                        break
                
                if not placed:
                    estafettes.append({
                        "poids": bl_info['poids'],
                        "volume": bl_info['volume'],
                        "bls": [bl_info['bl']],
                        "clients": {bl_info['client']},
                        "representants": {bl_info['representant']},
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

        if resultats:
            df_optimized = pd.DataFrame(resultats, columns=[
                "Zone", "Estafette N°", "Poids total", "Volume total", 
                "Client commande", "Représentant", "BL inclus"
            ])
            
            df_optimized["Taux Poids (%)"] = (df_optimized["Poids total"] / MAX_POIDS) * 100
            df_optimized["Taux Volume (%)"] = (df_optimized["Volume total"] / MAX_VOLUME) * 100
            df_optimized["Taux d'occupation (%)"] = df_optimized[["Taux Poids (%)", "Taux Volume (%)"]].max(axis=1).round(2)
            
            df_optimized["Location_camion"] = False
            df_optimized["Location_proposee"] = False
            df_optimized["Code Véhicule"] = "ESTAFETTE"
            df_optimized["Camion N°"] = df_optimized["Estafette N°"].apply(lambda x: f"E{int(x)}")
            
            df_optimized = df_optimized.drop(columns=["Taux Poids (%)", "Taux Volume (%)"])
            
            return df_optimized
        else:
            return pd.DataFrame()

    def appliquer_location(self, client, accepter, df_grouped_zone_original=None):
        """
        Applique ou refuse la location pour un client et met à jour le DataFrame de base.
        """
        mask = self.df_base["Client commande"] == client
        if not mask.any():
            return False, "Client introuvable.", self.df_base

        df = self.df_base.copy()
        
        if accepter:
            # Récupérer TOUTES les données du client
            poids_total = df.loc[mask, "Poids total"].sum()
            volume_total = df.loc[mask, "Volume total"].sum()
            bl_concat = ";".join(df.loc[mask, "BL inclus"].astype(str).unique().tolist())
            representants = ";".join(sorted(df.loc[mask, "Représentant"].astype(str).unique().tolist()))
            zones = ";".join(sorted(df.loc[mask, "Zone"].astype(str).unique().tolist()))
            
            # Vérifier la capacité du camion
            if poids_total > CAMION_POIDS_MAX:
                return False, f"❌ Poids total ({poids_total:.1f}kg) dépasse la capacité camion ({CAMION_POIDS_MAX}kg).", self.df_base
            if volume_total > CAMION_VOLUME_MAX:
                return False, f"❌ Volume total ({volume_total:.1f}m³) dépasse la capacité camion ({CAMION_VOLUME_MAX}m³).", self.df_base
            
            # Supprimer TOUTES les lignes du client
            df_sans_client = df[~mask].copy()
            
            # Réoptimiser les estafettes restantes
            df_estafettes_restantes = df_sans_client[df_sans_client["Code Véhicule"] == "ESTAFETTE"].copy()
            
            if not df_estafettes_restantes.empty:
                df_reoptimise = self._reoptimiser_estafettes(df_estafettes_restantes)
                
                if not df_reoptimise.empty:
                    df_sans_client = df_sans_client[df_sans_client["Code Véhicule"] != "ESTAFETTE"]
                    df_sans_client = pd.concat([df_sans_client, df_reoptimise], ignore_index=True)
            
            # Créer le camion loué
            camion_num_final = f"C{self._next_camion_num}"
            self._next_camion_num += 1
            
            taux_occu = max(
                (poids_total / CAMION_POIDS_MAX) * 100,
                (volume_total / CAMION_VOLUME_MAX) * 100
            )
            
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
                "Taux d'occupation (%)": taux_occu,
            }])
            
            df_final = pd.concat([df_sans_client, new_row], ignore_index=True)
            self.df_base = df_final
            
            return True, f"✅ Location ACCEPTÉE pour {client}. Réoptimisation effectuée. Commandes consolidées dans {camion_num_final}.", self.detecter_propositions()
        
        else:
            # REFUS : Rien ne change
            df.loc[mask, ["Location_proposee", "Location_camion", "Code Véhicule"]] = [True, False, "ESTAFETTE"]
            df.loc[mask, "Camion N°"] = df.loc[mask, "Estafette N°"].apply(lambda x: f"E{int(x)}")
            
            self.df_base = df
            return True, f"❌ Proposition REFUSÉE pour {client}. La distribution optimisée est conservée.", self.detecter_propositions()

    def get_df_result(self):
        """Retourne le DataFrame optimisé final avec les modifications de location."""
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
             "Client(s) inclus", "Représentant(s) inclus", "BL inclus", 
             "Taux d'occupation (%)", "Location_camion", "Location_proposee", "Code Véhicule"
        ]

        return df_result[[col for col in final_cols_display if col in df_result.columns]]


class DeliveryProcessor:
    """
    Classe principale pour le traitement des données de livraison.
    """

    def process_delivery_data(self, liv_file, ydlogist_file, wcliegps_file):
        """
        Fonction principale : traitement complet des données de livraison.
        
        Returns:
            tuple: DataFrames résultats + instance TruckRentalProcessor
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

            # Regroupement par ville et client
            df_grouped, df_city = self._group_data(df_final)

            # Calcul du besoin en estafette par ville
            df_city = self._calculate_estafette_need(df_city)

            # Ajout Zone
            df_grouped_zone = self._add_zone(df_grouped.rename(columns={"Client": "Client de l'estafette"}))

            # Filtrer les livraisons avec "Zone inconnue"
            df_grouped_zone = df_grouped_zone[df_grouped_zone["Zone"] != "Zone inconnue"].copy()
            
            # Groupement par zone
            df_zone = self._group_by_zone(df_grouped_zone)
            
            # Calcul du besoin en estafette par zone
            df_zone = self._calculate_estafette_need(df_zone)

            # Calcul des voyages optimisés 
            df_optimized_estafettes = self._calculate_optimized_estafette(df_grouped_zone)

            # Création de l'instance TruckRentalProcessor
            truck_processor = TruckRentalProcessor(df_optimized_estafettes)

            return df_grouped, df_city, df_grouped_zone, df_zone, df_optimized_estafettes, truck_processor

        except Exception as e:
            raise Exception(f"❌ Erreur lors du traitement des données : {str(e)}")

    def _load_livraisons(self, liv_file):
        """Charge le fichier de livraisons."""
        df = pd.read_excel(liv_file)
        
        if 'N° BON LIVRAISON' in df.columns:
            df.rename(columns={'N° BON LIVRAISON': 'No livraison'}, inplace=True)
            
        if len(df.columns) > 4:
            df.rename(columns={df.columns[4]: "Quantité livrée US"}, inplace=True)
            
        return df

    def _load_ydlogist(self, file_path):
        """Charge le fichier YDLogist."""
        df = pd.read_excel(file_path)
        if len(df.columns) > 16:
            df.rename(columns={df.columns[16]: "Unité Volume"}, inplace=True)
        if len(df.columns) > 13:
            df.rename(columns={df.columns[13]: "Poids de l'US"}, inplace=True)
            
        return df

    def _load_wcliegps(self, wcliegps_file):
        """Charge le fichier clients/représentants."""
        df_clients = pd.read_excel(wcliegps_file)
        
        if len(df_clients.columns) > 16:
            df_clients.rename(columns={df_clients.columns[16]: "Représentant"}, inplace=True)
        
        required_cols = ["Client", "Ville", "Représentant"]
        for col in required_cols:
            if col not in df_clients.columns:
                raise ValueError(f"La colonne '{col}' est manquante dans le fichier clients.")
        
        return df_clients[["Client", "Ville", "Représentant"]].copy()

    def _filter_initial_data(self, df):
        """Filtre les données initiales."""
        clients_exclus = [
            "AMECAP", "SANA", "SOPAL", "SOPALGAZ", "SOPALSERV", "SOPALTEC",
            "SOPALALG", "AQUA", "WINOX", "QUIVEM", "SANISTONE",
            "SOPAMAR", "SOPALAFR", "SOPALINTER"
        ]
        return df[(df["Type livraison"] != "SDC") & (~df["Client commande"].isin(clients_exclus))]

    def _calculate_weights(self, df):
        """Calcule les poids totaux."""
        df["Poids de l'US"] = pd.to_numeric(
            df["Poids de l'US"].astype(str).str.replace(",", ".")
            .str.replace(r"[^\d.]", "", regex=True), errors="coerce"
        ).fillna(0)
        
        df["Quantité livrée US"] = pd.to_numeric(df["Quantité livrée US"], errors="coerce").fillna(0)
        
        df["Poids total"] = df["Quantité livrée US"] * df["Poids de l'US"]
        return df[["No livraison", "Article", "Client commande", "Poids total", "Quantité livrée US", "Poids de l'US"]]

    def _calculate_volumes(self, df_liv, df_art):
        """Calcule les volumes."""
        df_liv_sel = df_liv[["No livraison", "Article", "Quantité livrée US", "Client commande"]]
        df_art_sel = df_art[["Article", "Volume de l'US", "Unité Volume"]].copy()
        
        df_art_sel["Volume de l'US"] = pd.to_numeric(
            df_art_sel["Volume de l'US"].astype(str).str.replace(",", "."), errors="coerce"
        )
        return pd.merge(df_liv_sel, df_art_sel, on="Article", how="left")

    def _merge_delivery_data(self, df_poids, df_vol):
        """Fusionne les données poids et volume."""
        return pd.merge(
            df_poids.drop(columns=["Quantité livrée US", "Poids de l'US"], errors='ignore'), 
            df_vol, on=["No livraison", "Article", "Client commande"], how="left"
        )

    def _add_city_client_info(self, df, df_clients):
        """Ajoute les informations client et ville."""
        return pd.merge(
            df, df_clients[["Client", "Ville", "Représentant"]],
            left_on="Client commande", right_on="Client", how="left"
        )

    def _group_data(self, df):
        """Groupe les données par livraison/client/ville."""
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
        """Calcule le besoin en estafettes."""
        poids_max = 1550
        volume_max = 4.608
        
        if "Poids total" in df.columns and "Volume total" in df.columns:
            df["Besoin estafette (poids)"] = df["Poids total"].apply(lambda p: math.ceil(p / poids_max))
            df["Besoin estafette (volume)"] = df["Volume total"].apply(lambda v: math.ceil(v / volume_max))
            df["Besoin estafette réel"] = df[["Besoin estafette (poids)", "Besoin estafette (volume)"]].max(axis=1)
        
        return df

    def _add_zone(self, df):
        """Ajoute la zone géographique."""
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
        """Groupe les données par zone."""
        df_zone = df_grouped_zone.groupby("Zone", as_index=False).agg({
            "Poids total": "sum",
            "Volume total": "sum",
            "No livraison": "count"
        }).rename(columns={"No livraison": "Nombre livraisons"})
        return df_zone

    def _calculate_optimized_estafette(self, df_grouped_zone):
        """Calcule la distribution optimisée des estafettes."""
        MAX_POIDS = 1550
        MAX_VOLUME = 4.608

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
                    if e["poids"] + poids <= MAX_POIDS and e["volume"] + volume <= MAX_VOLUME:
                        e["poids"] += poids
                        e["volume"] += volume
                        e["bls"].append(bl)
                        for c in client.split(','): 
                            e["clients"].add(c.strip())
                        for r in representant.split(','): 
                            e["representants"].add(r.strip())
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
        
        # Calcul des taux d'occupation
        df_estafettes["Taux Poids (%)"] = (df_estafettes["Poids total chargé"] / MAX_POIDS) * 100
        df_estafettes["Taux Volume (%)"] = (df_estafettes["Volume total chargé"] / MAX_VOLUME) * 100
        df_estafettes["Taux d'occupation (%)"] = df_estafettes[["Taux Poids (%)", "Taux Volume (%)"]].max(axis=1).round(2)
        
        # Initialisation des colonnes de location
        df_estafettes["Location_camion"] = False
        df_estafettes["Location_proposee"] = False
        df_estafettes["Code Véhicule"] = "ESTAFETTE"
        df_estafettes["Camion N°"] = df_estafettes["Estafette N°"].apply(lambda x: f"E{int(x)}")
        
        df_estafettes = df_estafettes.drop(columns=["Taux Poids (%)", "Taux Volume (%)"]) 
        
        return df_estafettes


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
        Vérifie si le transfert est possible selon les contraintes.
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


# Fonction utilitaire pour l'export Excel
def export_to_excel(df_dict, filename):
    """
    Exporte plusieurs DataFrames vers un fichier Excel.
    
    Args:
        df_dict (dict): Dictionnaire {nom_onglet: dataframe}
        filename (str): Nom du fichier de sortie
    """
    try:
        with pd.ExcelWriter(filename, engine='openpyxl') as writer:
            for sheet_name, df in df_dict.items():
                df.to_excel(writer, sheet_name=sheet_name, index=False)
        return True, f"✅ Fichier {filename} exporté avec succès"
    except Exception as e:
        return False, f"❌ Erreur lors de l'export: {str(e)}"


# Point d'entrée pour les tests
if __name__ == "__main__":
    print("=== BACKEND.PY - Système de Gestion des Livraisons ===")
    print("Classes disponibles:")
    print("- DeliveryProcessor: Traitement principal des données")
    print("- TruckRentalProcessor: Gestion location camions") 
    print("- TruckTransferManager: Transfert BLs entre estafettes")