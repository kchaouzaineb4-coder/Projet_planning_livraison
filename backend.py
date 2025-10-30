import pandas as pd
import numpy as np
import math

# =====================================================
# ⚙️ CONSTANTES GLOBALES
# =====================================================
SEUIL_POIDS = 3000.0    # kg pour location camion
SEUIL_VOLUME = 9.216    # m³ pour location camion
MAX_POIDS_ESTAFETTE = 1550.0
MAX_VOLUME_ESTAFETTE = 4.608


# =====================================================
# 🟩 DELIVERY PROCESSOR - TRAITEMENT DES LIVRAISONS
# =====================================================
class DeliveryProcessor:

    def __init__(self):
        pass

    def process_delivery_data(self, liv_file, ydlogist_file, wcliegps_file):
        """Traitement complet des fichiers de livraisons."""
        df_liv = pd.read_excel(liv_file)
        df_vol = pd.read_excel(ydlogist_file)
        df_zone = pd.read_excel(wcliegps_file)

        # Nettoyage colonnes principales
        for df in [df_liv, df_vol, df_zone]:
            df.columns = df.columns.str.strip()

        # Vérification colonnes requises
        required_liv = ["Client", "Ville", "BL", "Poids (kg)", "Volume (m³)"]
        required_vol = ["BL", "Article", "Poids (kg)", "Volume (m³)"]
        required_zone = ["Client", "Ville", "Zone"]

        for cols, name in [(required_liv, "Livraisons"), (required_zone, "Clients/Zones")]:
            for c in cols:
                if c not in df_liv.columns and name == "Livraisons":
                    raise ValueError(f"Colonne '{c}' manquante dans le fichier Livraisons")
                if c not in df_zone.columns and name == "Clients/Zones":
                    raise ValueError(f"Colonne '{c}' manquante dans le fichier Clients/Zones")

        # Fusion livraisons + zones
        df = pd.merge(df_liv, df_zone, on=["Client", "Ville"], how="left")

        # Calcul par Client/Ville
        df_grouped = df.groupby(["Client", "Ville"], as_index=False).agg({
            "Poids (kg)": "sum",
            "Volume (m³)": "sum",
            "BL": "count"
        }).rename(columns={"BL": "Nombre livraisons"})

        # Besoin estafette par ville
        df_city = df_grouped.groupby("Ville", as_index=False).agg({
            "Poids (kg)": "sum",
            "Volume (m³)": "sum",
            "Nombre livraisons": "sum"
        })
        df_city["Besoin estafette réel"] = df_city.apply(
            lambda x: max(
                math.ceil(x["Poids (kg)"] / MAX_POIDS_ESTAFETTE),
                math.ceil(x["Volume (m³)"] / MAX_VOLUME_ESTAFETTE)
            ),
            axis=1
        )

        # Regroupement Client/Ville/Zone
        df_grouped_zone = df.groupby(["Client", "Ville", "Zone"], as_index=False).agg({
            "Poids (kg)": "sum",
            "Volume (m³)": "sum",
            "BL": "count"
        }).rename(columns={"BL": "Nombre livraisons"})

        # Besoin par Zone
        df_zone_sum = df_grouped_zone.groupby("Zone", as_index=False).agg({
            "Poids (kg)": "sum",
            "Volume (m³)": "sum",
            "Nombre livraisons": "sum"
        })
        df_zone_sum["Besoin estafette réel"] = df_zone_sum.apply(
            lambda x: max(
                math.ceil(x["Poids (kg)"] / MAX_POIDS_ESTAFETTE),
                math.ceil(x["Volume (m³)"] / MAX_VOLUME_ESTAFETTE)
            ),
            axis=1
        )

        # Optimisation estafettes
        df_optimized_estafettes = self._calculate_optimized_estafette(df)

        return df_grouped, df_city, df_grouped_zone, df_zone_sum, df_optimized_estafettes

    def _calculate_optimized_estafette(self, df):
        """Répartition optimisée des livraisons par estafette."""
        df_result = []
        estafette_id = 1
        for zone, group in df.groupby("Zone"):
            group = group.copy().reset_index(drop=True)
            current_weight, current_volume = 0.0, 0.0
            current_estafette = f"{zone}_E{estafette_id}"

            for i, row in group.iterrows():
                poids, volume = row["Poids (kg)"], row["Volume (m³)"]
                # Si dépassement
                if (current_weight + poids > MAX_POIDS_ESTAFETTE) or (current_volume + volume > MAX_VOLUME_ESTAFETTE):
                    estafette_id += 1
                    current_weight, current_volume = 0.0, 0.0
                    current_estafette = f"{zone}_E{estafette_id}"
                current_weight += poids
                current_volume += volume
                taux = min(100, (current_weight / MAX_POIDS_ESTAFETTE) * 100)

                df_result.append({
                    "Zone": zone,
                    "Estafette": current_estafette,
                    "Client": row["Client"],
                    "Ville": row["Ville"],
                    "BL": row["BL"],
                    "Poids total chargé": current_weight,
                    "Volume total chargé": current_volume,
                    "Taux d'occupation (%)": taux
                })
            estafette_id = 1  # reset compteur par zone

        return pd.DataFrame(df_result)


# =====================================================
# 🟦 TRUCK RENTAL PROCESSOR - LOCATION DE CAMION
# =====================================================
class TruckRentalProcessor:
    def __init__(self, df_estafettes):
        self.df = df_estafettes.copy()

    def get_df_result(self):
        return self.df

    def detecter_propositions(self):
        """Détecte les clients qui dépassent les seuils de poids ou volume."""
        clients = (
            self.df.groupby("Client", as_index=False)
            .agg({"Poids total chargé": "sum", "Volume total chargé": "sum"})
            .rename(columns={
                "Poids total chargé": "Poids total (kg)",
                "Volume total chargé": "Volume total (m³)"
            })
        )

        clients["Raison"] = clients.apply(
            lambda x: "Poids dépassé" if x["Poids total (kg)"] > SEUIL_POIDS
            else ("Volume dépassé" if x["Volume total (m³)"] > SEUIL_VOLUME else ""), axis=1
        )
        return clients[clients["Raison"] != ""]

    def appliquer_location(self, client, accepter=True):
        """Accepte ou refuse la location pour un client donné."""
        if client not in self.df["Client"].astype(str).values:
            return False, f"❌ Client {client} introuvable.", self.df

        if accepter:
            self.df.loc[self.df["Client"].astype(str) == client, "Code Véhicule"] = "CAMION-LOUE"
            msg = f"✅ Location acceptée pour le client {client}."
        else:
            self.df.loc[self.df["Client"].astype(str) == client, "Code Véhicule"] = "REFUS-LOCATION"
            msg = f"❌ Location refusée pour le client {client}."

        return True, msg, self.df

    def get_details_client(self, client):
        """Renvoie les détails d’un client spécifique."""
        sub = self.df[self.df["Client"].astype(str) == str(client)]
        resume = f"Client {client} - {len(sub)} livraisons totalisant {sub['Poids total chargé'].sum():.2f} kg et {sub['Volume total chargé'].sum():.3f} m³."
        return resume, sub.style.format({
            "Poids total chargé": "{:.2f}",
            "Volume total chargé": "{:.3f}",
            "Taux d'occupation (%)": "{:.2f}"
        })


# =====================================================
# 🆕 BL TRANSFER PROCESSOR - TRANSFERT DE BL ENTRE ESTAFETTES
# =====================================================
class BLTransferProcessor:
    def __init__(self, df_estafettes):
        """Initialisation avec le DataFrame des estafettes."""
        self.df = df_estafettes.copy()

    def get_zones(self):
        """Retourne la liste des zones disponibles."""
        return sorted(self.df["Zone"].dropna().unique().tolist())

    def get_estafettes_by_zone(self, zone):
        """Retourne les estafettes d'une zone donnée."""
        return sorted(self.df[self.df["Zone"] == zone]["Estafette"].dropna().unique().tolist())

    def get_bls_of_estafette(self, estafette):
        """Retourne les BLs d'une estafette donnée."""
        return self.df[self.df["Estafette"] == estafette]["BL"].tolist()

    def get_weight_volume(self, estafette):
        """Retourne le poids et volume total d'une estafette."""
        sub = self.df[self.df["Estafette"] == estafette]
        return sub["Poids total chargé"].max(), sub["Volume total chargé"].max()

    def simulate_transfer(self, estafette_source, estafette_cible, bls_to_transfer):
        """Simule un transfert de BLs entre estafettes."""
        df_source = self.df[self.df["Estafette"] == estafette_source]
        df_cible = self.df[self.df["Estafette"] == estafette_cible]

        poids_bls = df_source[df_source["BL"].isin(bls_to_transfer)]["Poids total chargé"].diff().fillna(0).sum()
        volume_bls = df_source[df_source["BL"].isin(bls_to_transfer)]["Volume total chargé"].diff().fillna(0).sum()

        poids_source, volume_source = self.get_weight_volume(estafette_source)
        poids_cible, volume_cible = self.get_weight_volume(estafette_cible)

        poids_source_apres = poids_source - poids_bls
        volume_source_apres = volume_source - volume_bls
        poids_cible_apres = poids_cible + poids_bls
        volume_cible_apres = volume_cible + volume_bls

        autorise = (poids_cible_apres <= MAX_POIDS_ESTAFETTE) and (volume_cible_apres <= MAX_VOLUME_ESTAFETTE)

        result = {
            "poids_bls": poids_bls,
            "volume_bls": volume_bls,
            "poids_cible_apres": poids_cible_apres,
            "volume_cible_apres": volume_cible_apres,
            "autorise": autorise
        }
        return result

    def appliquer_transfer(self, estafette_source, estafette_cible, bls_to_transfer):
        """Applique le transfert sur le DataFrame (si autorisé)."""
        simulation = self.simulate_transfer(estafette_source, estafette_cible, bls_to_transfer)
        if not simulation["autorise"]:
            return False, "❌ TRANSFERT REFUSÉ : CAPACITÉ DÉPASSÉE ❌", self.df

        self.df.loc[self.df["BL"].isin(bls_to_transfer), "Estafette"] = estafette_cible
        msg = "✅ TRANSFERT AUTORISÉ (En attente de validation)"
        return True, msg, self.df
