# backend.py
import pandas as pd
import math
import numpy as np

# ----------------------------
# CONSTANTES / CAPACITÉS
# ----------------------------
SEUIL_POIDS = 3000.0         # seuil initial de proposition (historique)
SEUIL_VOLUME = 9.216         # seuil initial de proposition (historique)
CAMION_CODE = "CAMION-LOUE"

# Capacités réelles
CAMION_POIDS_MAX = 30500.0
CAMION_VOLUME_MAX = 77.5

CAPACITE_POIDS_ESTAFETTE = 1550.0
CAPACITE_VOLUME_ESTAFETTE = 4.608

# =====================================================
# CLASSE : Traiteur des fichiers de livraison & calculs
# =====================================================
class DeliveryProcessor:
    def __init__(self):
        self.df_livraisons_original = None

    def process_delivery_data(self, liv_file, ydlogist_file, wcliegps_file):
        """
        Traite les 3 fichiers d'input et retourne :
        df_grouped, df_city, df_grouped_zone, df_zone, df_optimized_estafettes, df_livraisons_original
        """
        try:
            df_liv = self._load_livraisons(liv_file)
            df_yd = self._load_ydlogist(ydlogist_file)
            df_clients = self._load_wcliegps(wcliegps_file)

            df_liv = self._filter_initial_data(df_liv)

            df_poids = self._calculate_weights(df_liv)
            df_vol = self._calculate_volumes(df_liv, df_yd)

            df_merged = self._merge_delivery_data(df_poids, df_vol)
            df_final = self._add_city_client_info(df_merged, df_clients)

            # Calcul du volume total (m³)
            df_final["Volume de l'US"] = pd.to_numeric(df_final["Volume de l'US"], errors='coerce').fillna(0) / 1_000_000
            df_final["Volume total"] = df_final["Volume de l'US"] * df_final["Quantité livrée US"]

            # Groupements
            df_grouped, df_city = self._group_data(df_final)
            df_city = self._calculate_estafette_need(df_city)

            df_grouped_zone = self._add_zone(df_grouped.rename(columns={"Client": "Client de l'estafette"}))
            df_grouped_zone = df_grouped_zone[df_grouped_zone["Zone"] != "Zone inconnue"].copy()

            df_zone = self._group_by_zone(df_grouped_zone)
            df_zone = self._calculate_estafette_need(df_zone)

            df_optimized_estafettes = self._calculate_optimized_estafette(df_grouped_zone)

            # Stocker la source des livraisons (utilisée par les autres classes)
            self.df_livraisons_original = df_grouped_zone.copy()

            return df_grouped, df_city, df_grouped_zone, df_zone, df_optimized_estafettes, self.df_livraisons_original

        except Exception as e:
            raise Exception(f"❌ Erreur lors du traitement des données : {str(e)}")

    # -------------------------
    # Chargement / nettoyage
    # -------------------------
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

    # -------------------------
    # Calculs poids / volume
    # -------------------------
    def _calculate_weights(self, df):
        df["Poids de l'US"] = pd.to_numeric(
            df["Poids de l'US"].astype(str).str.replace(",", ".").str.replace(r"[^\d.]", "", regex=True),
            errors='coerce'
        ).fillna(0)
        df["Quantité livrée US"] = pd.to_numeric(df["Quantité livrée US"], errors='coerce').fillna(0)
        df["Poids total"] = df["Quantité livrée US"] * df["Poids de l'US"]
        return df[["No livraison", "Article", "Client commande", "Poids total", "Quantité livrée US", "Poids de l'US"]]

    def _calculate_volumes(self, df_liv, df_art):
        df_liv_sel = df_liv[["No livraison", "Article", "Quantité livrée US", "Client commande"]]
        df_art_sel = df_art[["Article", "Volume de l'US", "Unité Volume"]].copy()
        df_art_sel["Volume de l'US"] = pd.to_numeric(df_art_sel["Volume de l'US"].astype(str).str.replace(",", "."), errors='coerce')
        return pd.merge(df_liv_sel, df_art_sel, on="Article", how="left")

    def _merge_delivery_data(self, df_poids, df_vol):
        return pd.merge(df_poids.drop(columns=["Quantité livrée US", "Poids de l'US"], errors='ignore'),
                        df_vol, on=["No livraison", "Article", "Client commande"], how="left")

    def _add_city_client_info(self, df, df_clients):
        return pd.merge(df, df_clients[["Client", "Ville", "Représentant"]],
                        left_on="Client commande", right_on="Client", how="left")

    # -------------------------
    # Groupement / besoin estafette
    # -------------------------
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

    # -------------------------
    # Zones / groupements
    # -------------------------
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

    # -------------------------
    # Calcul estafettes optimisées (heuristique FFD)
    # -------------------------
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
                        "representants": {r.strip() for r in representant.split(',') if r.strip()},
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

        # Init colonnes
        df_estafettes["Location_camion"] = False
        df_estafettes["Location_proposee"] = False
        df_estafettes["Code Véhicule"] = "ESTAFETTE"
        df_estafettes["Camion N°"] = df_estafettes["Estafette N°"].apply(lambda x: f"E{int(x)}")

        df_estafettes = df_estafettes.drop(columns=["Taux Poids (%)", "Taux Volume (%)"])
        # Harmoniser noms colonnes en sortie (Poids/Volume sans 'chargé' pour compatibilité)
        df_estafettes.rename(columns={
            "Poids total chargé": "Poids total",
            "Volume total chargé": "Volume total",
            "Client(s) inclus": "Client(s) inclus",
            "Représentant(s) inclus": "Représentant(s) inclus",
            "BL inclus": "BL inclus"
        }, inplace=True)

        return df_estafettes

# =====================================================
# CLASSE : Gestion de la location et opérations client
# =====================================================
class TruckRentalProcessor:
    def __init__(self, df_optimized, df_livraisons_original):
        """
        df_optimized : DataFrame des estafettes optimisées (résultat de _calculate_optimized_estafette)
        df_livraisons_original : DataFrame 'Livraisons par Client & Ville + Zone' (source des BLs)
        """
        self.df_base = self._initialize_rental_columns(df_optimized.copy())
        self.df_livraisons_original = df_livraisons_original.copy()
        self._next_camion_num = self.df_base[self.df_base["Code Véhicule"] == CAMION_CODE].shape[0] + 1

    def _initialize_rental_columns(self, df):
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

        df['BL inclus'] = df['BL inclus'].astype(str)
        df["Estafette N°"] = pd.to_numeric(df["Estafette N°"], errors='coerce').fillna(99999).astype(int)

        return df

    # -------------------------
    # Extraire totaux réels par client (depuis df_livraisons_original)
    # -------------------------
    def _get_client_totals_from_original_data(self):
        required_cols = ["Client de l'estafette", "Poids total", "Volume total"]
        if any(col not in self.df_livraisons_original.columns for col in required_cols):
            return pd.DataFrame(columns=["Client", "Poids total (kg)", "Volume total (m³)"])

        df_client_totals = self.df_livraisons_original.groupby("Client de l'estafette").agg({
            "Poids total": "sum",
            "Volume total": "sum"
        }).reset_index().rename(columns={
            "Client de l'estafette": "Client",
            "Poids total": "Poids total (kg)",
            "Volume total": "Volume total (m³)"
        })
        return df_client_totals

    # -------------------------
    # Détecter propositions (clients dépassant SEUILS réels)
    # -------------------------
    def detecter_propositions(self):
        df_client_totals = self._get_client_totals_from_original_data()
        if df_client_totals.empty:
            return pd.DataFrame()

        processed_clients = self.df_base[self.df_base["Location_proposee"]]["Client commande"].unique()
        df_pending = df_client_totals[~df_client_totals["Client"].isin(processed_clients)].copy()
        if df_pending.empty:
            return pd.DataFrame()

        propositions = df_pending[
            (df_pending["Poids total (kg)"] >= SEUIL_POIDS) |
            (df_pending["Volume total (m³)"] >= SEUIL_VOLUME)
        ].copy()

        if propositions.empty:
            return pd.DataFrame()

        def get_raison(row):
            raisons = []
            if row["Poids total (kg)"] >= SEUIL_POIDS:
                raisons.append(f"Poids ≥ {SEUIL_POIDS} kg")
            if row["Volume total (m³)"] >= SEUIL_VOLUME:
                raisons.append(f"Volume ≥ {SEUIL_VOLUME:.3f} m³")
            return " & ".join(raisons)

        propositions["Raison"] = propositions.apply(get_raison, axis=1)
        return propositions.sort_values(["Poids total (kg)", "Volume total (m³)"], ascending=False).reset_index(drop=True)

    # -------------------------
    # Détails client (avec totaux réels)
    # -------------------------
    def get_details_client(self, client):
        try:
            client_data_original = self.df_livraisons_original[self.df_livraisons_original["Client de l'estafette"] == client]
            if client_data_original.empty:
                return f"Aucune donnée pour {client}", pd.DataFrame()

            total_poids_reel = client_data_original["Poids total"].sum()
            total_volume_reel = client_data_original["Volume total"].sum()
            bls_client = client_data_original["No livraison"].unique()

            details_estafettes = []
            for _, row in self.df_base.iterrows():
                bls_in_vehicle = str(row["BL inclus"]).split(';')
                bls_commun = set(map(str, bls_client)) & set(bls_in_vehicle)
                if bls_commun:
                    details_estafettes.append({
                        'Zone': row['Zone'],
                        'Camion N°': row['Camion N°'],
                        'Poids total': f"{row.get('Poids total', 0):.3f} kg",
                        'Volume total': f"{row.get('Volume total', 0):.3f} m³",
                        'BL inclus': row['BL inclus'],
                        'Taux d\'occupation (%)': f"{row.get('Taux d\'occupation (%)', 0):.2f}%"
                    })

            etat = "Non décidée"
            client_in_base = self.df_base[self.df_base["Client commande"].str.contains(client, na=False)]
            if not client_in_base.empty:
                if client_in_base["Location_camion"].any():
                    etat = "Location ACCEPTÉE"
                elif client_in_base["Location_proposee"].any():
                    etat = "Proposition REFUSÉE"

            resume = f"Client {client} — Poids total RÉEL : {total_poids_reel:.1f} kg ; Volume total RÉEL : {total_volume_reel:.3f} m³ | État : {etat}"
            df_details = pd.DataFrame(details_estafettes)
            return resume, df_details

        except Exception as e:
            return f"Erreur avec le client {client}: {e}", pd.DataFrame()

    # -------------------------
    # Appliquer location (accept/refuse)
    # -------------------------
    def appliquer_location(self, client, accepter):
        try:
            client_data_original = self.df_livraisons_original[self.df_livraisons_original["Client de l'estafette"] == client]
            if client_data_original.empty:
                return False, "Client introuvable dans les données originales.", self.df_base

            bls_client = client_data_original["No livraison"].unique()
            df = self.df_base.copy()

            if accepter:
                # Récupérer totaux et créer ligne camion
                poids_total = client_data_original["Poids total"].sum()
                volume_total = client_data_original["Volume total"].sum()
                bl_concat = ";".join([str(bl) for bl in bls_client])
                representants = ";".join(sorted(client_data_original["Représentant"].astype(str).unique().tolist()))
                zones = ";".join(sorted(client_data_original["Zone"].astype(str).unique().tolist()))

                if poids_total > CAMION_POIDS_MAX or volume_total > CAMION_VOLUME_MAX:
                    # Si la somme dépasse la capacité d'un seul camion, on va découper en plusieurs camions via bin-packing.
                    # Implémentation simple : tri par poids et remplissage (First Fit Decreasing)
                    bls_details = []
                    for _, row in client_data_original.iterrows():
                        bls_details.append({
                            "bl": str(row["No livraison"]).strip(),
                            "poids": float(row["Poids total"]),
                            "volume": float(row["Volume total"]),
                            "zone": row["Zone"],
                            "representant": row["Représentant"]
                        })
                    df_bls = pd.DataFrame(bls_details).sort_values("poids", ascending=False).reset_index(drop=True)

                    camions = []
                    for _, br in df_bls.iterrows():
                        placed = False
                        for camion in camions:
                            if camion["poids"] + br["poids"] <= CAMION_POIDS_MAX and camion["volume"] + br["volume"] <= CAMION_VOLUME_MAX:
                                camion["poids"] += br["poids"]
                                camion["volume"] += br["volume"]
                                camion["bls"].append(br["bl"])
                                camion["zones"].add(br["zone"])
                                camion["representants"].add(br["representant"])
                                placed = True
                                break
                        if not placed:
                            camions.append({
                                "poids": br["poids"],
                                "volume": br["volume"],
                                "bls": [br["bl"]],
                                "zones": {br["zone"]},
                                "representants": {br["representant"]}
                            })
                    # Supprimer anciennes lignes client
                    df = df[~df["Client commande"].str.contains(client, na=False)]
                    new_rows = []
                    for i, camion in enumerate(camions):
                        camion_num = f"C{self._next_camion_num + i}"
                        taux_occu = max(
                            (camion["poids"] / CAMION_POIDS_MAX) * 100,
                            (camion["volume"] / CAMION_VOLUME_MAX) * 100
                        )
                        new_rows.append({
                            "Zone": ";".join(sorted(list(camion["zones"]))),
                            "Estafette N°": 0,
                            "Poids total": camion["poids"],
                            "Volume total": camion["volume"],
                            "BL inclus": ";".join(camion["bls"]),
                            "Client commande": client,
                            "Représentant": ";".join(sorted(list(camion["representants"]))),
                            "Location_camion": True,
                            "Location_proposee": True,
                            "Code Véhicule": CAMION_CODE,
                            "Camion N°": camion_num,
                            "Taux d'occupation (%)": taux_occu
                        })
                    self._next_camion_num += len(camions)
                    df = pd.concat([df, pd.DataFrame(new_rows)], ignore_index=True)
                    self.df_base = df
                    msg = f"✅ Location ACCEPTÉE pour {client}. {len(bls_client)} BL(s) regroupé(s) dans {len(camions)} camion(s)."
                    return True, msg, self.detecter_propositions()
                else:
                    # Tout tient dans 1 camion
                    camion_num = f"C{self._next_camion_num}"
                    taux_occu = max((poids_total / CAMION_POIDS_MAX) * 100, (volume_total / CAMION_VOLUME_MAX) * 100)
                    new_row = {
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
                        "Camion N°": camion_num,
                        "Taux d'occupation (%)": taux_occu
                    }
                    # Supprimer anciennes lignes client
                    df = df[~df["Client commande"].str.contains(client, na=False)]
                    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                    self._next_camion_num += 1
                    self.df_base = df
                    msg = f"✅ Location ACCEPTÉE pour {client}. {len(bls_client)} BL(s) regroupé(s) dans 1 camion."
                    return True, msg, self.detecter_propositions()
            else:
                # Refus : marquer Location_proposee = True, Location_camion = False pour les BLs du client
                mask_original = df["BL inclus"].apply(lambda x: any(str(bl) in str(x).split(';') for bl in bls_client))
                df.loc[mask_original, ["Location_proposee", "Location_camion", "Code Véhicule"]] = [True, False, "ESTAFETTE"]
                df.loc[mask_original, "Camion N°"] = df.loc[mask_original, "Estafette N°"].apply(lambda x: f"E{int(x)}")
                self.df_base = df
                return True, f"❌ Proposition REFUSÉE pour {client}. Les commandes restent en Estafettes.", self.detecter_propositions()

        except Exception as e:
            return False, f"❌ Erreur lors de l'application de la décision: {str(e)}", self.df_base

    # -------------------------
    # Réoptimisation après transferts
    # -------------------------
    def _reoptimiser_estafettes_par_zone(self, bls_a_garder, zones_affectees):
        if not bls_a_garder:
            return pd.DataFrame()
        df_bls_data = self.df_livraisons_original[self.df_livraisons_original["No livraison"].isin(bls_a_garder)]
        if df_bls_data.empty:
            return pd.DataFrame()

        resultats_optimises = []
        estafette_num = 1

        for zone in zones_affectees:
            df_zone = df_bls_data[df_bls_data["Zone"] == zone]
            if df_zone.empty:
                continue
            df_zone_sorted = df_zone.sort_values(by="Poids total", ascending=False).reset_index()
            estafettes_zone = []
            for idx, row in df_zone_sorted.iterrows():
                bl = str(row["No livraison"])
                poids = row["Poids total"]
                volume = row["Volume total"]
                client = str(row["Client de l'estafette"])
                representant = str(row["Représentant"])
                placed = False
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

            for e in estafettes_zone:
                clients_list = ", ".join(sorted(list(e["clients"])))
                representants_list = ", ".join(sorted(list(e["representants"])))
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

        if resultats_optimises:
            return pd.DataFrame(resultats_optimises)
        else:
            return pd.DataFrame()

    # -------------------------
    # Récupérer DF résultat
    # -------------------------
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

    # -------------------------
    # NOUVEAU : Ajouter un objet manuel à un véhicule (refuse si dépasse)
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
            obj_code = f"OBJ-{name}-{len(df)}"

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

            # Si on a une colonne 'Code Véhicule' manquante, tenter de la normaliser
            if "Code Véhicule" not in df.columns:
                df["Code Véhicule"] = df.get("Code Véhicule", "ESTAFETTE")

            # Mettre à jour self.df_base si la source est le df_base
            # (l'appelant doit décider s'il veut maj self.df_base ou st.session_state.df_voyages)
            # Ici on met à jour self.df_base si les index concordent
            try:
                # Si vehicle existe dans self.df_base -> appliquer
                if "Véhicule N°" in self.df_base.columns:
                    mask_base = self.df_base["Camion N°"] == vehicle
                    if mask_base.any():
                        base_idx = self.df_base[mask_base].index[0]
                        # appliquer poids/volume/BL
                        self.df_base.at[base_idx, "BL inclus"] = df.at[idx, "BL inclus"]
                        # colonnes peuvent être 'Poids total'/'Volume total' ou 'Poids total chargé' etc.
                        if "Poids total chargé" in self.df_base.columns:
                            self.df_base.at[base_idx, "Poids total chargé"] = df.at[idx, "Poids total chargé"]
                        else:
                            self.df_base.at[base_idx, "Poids total"] = df.at[idx, "Poids total"]
                        if "Volume total chargé" in self.df_base.columns:
                            self.df_base.at[base_idx, "Volume total chargé"] = df.at[idx, "Volume total chargé"]
                        else:
                            self.df_base.at[base_idx, "Volume total"] = df.at[idx, "Volume total"]
                        self.df_base.at[base_idx, "Taux d'occupation (%)"] = df.at[idx, "Taux d'occupation (%)"]
            except Exception:
                # Ne pas bloquer si la sync échoue ; le df retourné est le df mis à jour
                pass

            return True, f"✅ Objet '{name}' ajouté à {vehicle} en zone {zone} (code {obj_code})", df

        except Exception as e:
            return False, f"❌ Erreur lors de l'ajout de l'objet : {str(e)}", df_voyages

# =====================================================
# CLASSE : Gestion des transferts (utilisée par l'UI)
# =====================================================
class TruckTransferManager:
    def __init__(self, df_voyages, df_livraisons):
        """
        df_voyages : df des voyages (Voyages optimisés)
        df_livraisons : df détaillé des livraisons (source)
        """
        self.df_voyages = df_voyages.copy()
        self.df_livraisons = df_livraisons.copy()
        self.MAX_POIDS = CAPACITE_POIDS_ESTAFETTE
        self.MAX_VOLUME = CAPACITE_VOLUME_ESTAFETTE

    def transferer_bls(self, zone, source, cible, bls_a_transferer):
        """
        Transfert BLs de source -> cible dans la même zone
        Retourne (success: bool, message: str, df_voyages_updated)
        """
        try:
            df = self.df_voyages.copy()

            df_source = df[(df["Zone"] == zone) & (df["Véhicule N°"] == source)]
            if df_source.empty:
                return False, f"Véhicule source {source} introuvable en zone {zone}", self.df_voyages

            bls_source = str(df_source["BL inclus"].iloc[0]).split(';')
            bls_existants = [bl for bl in bls_a_transferer if bl in bls_source]
            if not bls_existants:
                return False, "Aucun des BLs sélectionnés n'est présent dans le véhicule source.", self.df_voyages

            df_bls_transfert = self.df_livraisons[self.df_livraisons["No livraison"].isin(bls_existants)]
            poids_transfert = df_bls_transfert["Poids total"].sum()
            volume_transfert = df_bls_transfert["Volume total"].sum()

            df_cible = df[(df["Zone"] == zone) & (df["Véhicule N°"] == cible)]
            if df_cible.empty:
                return False, f"Véhicule cible {cible} introuvable en zone {zone}", self.df_voyages

            poids_cible_actuel = float(df_cible["Poids total chargé"].iloc[0])
            volume_cible_actuel = float(df_cible["Volume total chargé"].iloc[0])

            if (poids_cible_actuel + poids_transfert > self.MAX_POIDS) or (volume_cible_actuel + volume_transfert > self.MAX_VOLUME):
                return False, "❌ Le transfert dépasse les capacités du véhicule cible", self.df_voyages

            # Appliquer le transfert
            for idx, row in df.iterrows():
                if row["Zone"] == zone and row["Véhicule N°"] == source:
                    bls_restants = [bl for bl in str(row["BL inclus"]).split(';') if bl not in bls_existants]
                    df.at[idx, "BL inclus"] = ';'.join(bls_restants)
                    df.at[idx, "Poids total chargé"] = max(0, float(row["Poids total chargé"]) - poids_transfert)
                    df.at[idx, "Volume total chargé"] = max(0, float(row["Volume total chargé"]) - volume_transfert)
                elif row["Zone"] == zone and row["Véhicule N°"] == cible:
                    bls_actuels = str(row["BL inclus"]).split(';') if pd.notna(row["BL inclus"]) and row["BL inclus"] != "" else []
                    bls_nouveaux = bls_actuels + bls_existants
                    df.at[idx, "BL inclus"] = ';'.join(bls_nouveaux)
                    df.at[idx, "Poids total chargé"] = float(row["Poids total chargé"]) + poids_transfert
                    df.at[idx, "Volume total chargé"] = float(row["Volume total chargé"]) + volume_transfert

            self.df_voyages = df
            message = f"✅ Transfert réussi : {len(bls_existants)} BL(s) déplacé(s) de {source} vers {cible}"
            return True, message, self.df_voyages

        except Exception as e:
            return False, f"❌ Erreur lors du transfert : {str(e)}", self.df_voyages

    def get_voyages_actuels(self):
        return self.df_voyages.copy()

