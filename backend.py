import pandas as pd
import numpy as np
import math

# --- Constantes pour la location de camion ---
SEUIL_POIDS = 3000.0    # kg
SEUIL_VOLUME = 9.216    # m³
CAMION_CODE = "CAMION-LOUE"

class TruckRentalProcessor:
    """
    Classe pour gérer la logique de proposition et de décision de location de camion
    avec transfert de BLs et suivi des estafettes.
    """

    def __init__(self, df_optimized):
        self.df_result = df_optimized.copy()
        self._next_camion_num = self.df_result[self.df_result["Code Véhicule"] == CAMION_CODE].shape[0] + 1
        self.propositions = self.detecter_propositions()

    def detecter_propositions(self):
        """Retourne les clients pour lesquels une location est proposée"""
        df_prop = self.df_result[(self.df_result["Poids total chargé"] > SEUIL_POIDS) |
                                 (self.df_result["Volume total chargé"] > SEUIL_VOLUME)].copy()
        if df_prop.empty:
            return pd.DataFrame()
        df_prop["Raison"] = df_prop.apply(
            lambda row: "Poids dépassé" if row["Poids total chargé"] > SEUIL_POIDS else "Volume dépassé", axis=1
        )
        return df_prop[["Client(s) inclus", "Poids total chargé", "Volume total chargé", "Raison"]].rename(
            columns={"Client(s) inclus": "Client",
                     "Poids total chargé": "Poids total (kg)",
                     "Volume total chargé": "Volume total (m³)"}
        )

    def appliquer_location(self, client, accepter=True):
        """
        Applique la location pour un client : True = accepter, False = refuser
        Transfert immédiat des BLs si accepté.
        """
        if client not in self.propositions["Client"].astype(str).tolist():
            return False, f"Client {client} non trouvé dans les propositions.", None

        idx = self.df_result[self.df_result["Client(s) inclus"].astype(str) == client].index
        if accepter:
            # Générer le numéro de camion loué
            camion_num_final = f"C{self._next_camion_num}"
            self._next_camion_num += 1

            # Appliquer la location sur toutes les lignes du client
            self.df_result.loc[idx, "Code Véhicule"] = CAMION_CODE
            self.df_result.loc[idx, "Camion N°"] = camion_num_final
            self.df_result.loc[idx, "Location_camion"] = True
            self.df_result.loc[idx, "Location_proposee"] = True
            msg = f"✅ Location acceptée pour {client}. Les BLs sont transférés dans {camion_num_final}."
        else:
            # Refuser la proposition
            self.df_result.loc[idx, "Code Véhicule"] = "ESTAFETTE"
            self.df_result.loc[idx, "Camion N°"] = self.df_result.loc[idx, "Estafette N°"].apply(lambda x: f"E{int(x)}")
            self.df_result.loc[idx, "Location_camion"] = False
            self.df_result.loc[idx, "Location_proposee"] = True
            msg = f"❌ Proposition de location refusée pour {client}."

        # Mise à jour des propositions
        self.propositions = self.detecter_propositions()
        return True, msg, self.df_result.loc[idx]

    def get_details_client(self, client):
        """Retourne un résumé et un DataFrame filtré pour le client"""
        df_client = self.df_result[self.df_result["Client(s) inclus"].astype(str) == client]
        resume = f"Client {client} - {len(df_client)} lignes, poids total {df_client['Poids total chargé'].sum():.2f} kg"
        return resume, df_client

    def get_df_result(self):
        """Retourne le DataFrame final avec toutes les décisions de location appliquées"""
        return self.df_result.copy()

    def transfer_bl(self, bl_list, estafette_dest):
        """
        Transfert d'une ou plusieurs BLs vers une autre estafette.
        :param bl_list: liste de BLs à transférer
        :param estafette_dest: numéro d'estafette destination (E1, E2...)
        """
        if isinstance(bl_list, str):
            bl_list = [b.strip() for b in bl_list.split(";") if b.strip()]

        if not bl_list:
            return False, "⚠️ Aucun BL sélectionné pour le transfert."

        df = self.df_result

        if estafette_dest not in df['Camion N°'].unique():
            return False, f"⚠️ L'estafette '{estafette_dest}' n'existe pas."

        # Vérifier que les BLs existent
        bls_existants = df['BL inclus'].str.split(";").explode().str.strip().unique()
        for bl in bl_list:
            if bl not in bls_existants:
                return False, f"⚠️ Le BL {bl} n'existe pas dans le planning."

        # Identifier source et destination
        mask_dest = df["Camion N°"] == estafette_dest

        for bl in bl_list:
            mask_source = df['BL inclus'].str.contains(fr'\b{bl}\b', regex=True)
            # Retirer BL de la source
            df.loc[mask_source, "BL inclus"] = df.loc[mask_source, "BL inclus"].apply(
                lambda x: ";".join([b for b in x.split(";") if b.strip() != bl])
            )
            # Ajouter BL à la destination
            df.loc[mask_dest, "BL inclus"] = df.loc[mask_dest, "BL inclus"].apply(
                lambda x: ";".join(filter(None, list(x.split(";")) + [bl]))
            )

        # Recalculer poids/volume pour les estafettes impliquées
        for estaf in [estafette_dest] + df.loc[df['BL inclus'].str.contains('|'.join(bl_list), regex=True), "Camion N°"].unique().tolist():
            mask = df["Camion N°"] == estaf
            df.loc[mask, "Poids total chargé"] = df.loc[mask].apply(
                lambda row: sum(df.loc[df['BL inclus'].str.contains(bl.strip(), regex=False), 'Poids total chargé'] for bl in row['BL inclus'].split(";") if bl.strip()), axis=1
            )
            df.loc[mask, "Volume total chargé"] = df.loc[mask].apply(
                lambda row: sum(df.loc[df['BL inclus'].str.contains(bl.strip(), regex=False), 'Volume total chargé'] for bl in row['BL inclus'].split(";") if bl.strip()), axis=1
            )
            df.loc[mask, "Taux d'occupation (%)"] = df.loc[mask].apply(
                lambda row: max(row["Poids total chargé"] / 1550 * 100, row["Volume total chargé"] / 4.608 * 100), axis=1
            )

        self.df_result = df
        return True, f"✅ BLs transférés vers {estafette_dest} avec succès."
