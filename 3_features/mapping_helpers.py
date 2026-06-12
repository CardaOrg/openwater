"""
mapping_helpers.py
==================

Doel
----
Dit bestand bevat *kleine join-functies* die de JSON in WOK_Game_Session 
omzetten naar handige Python-dicts (in RAM). Die dicts worden vervolgens 
gebruikt door features om snel Transaction_ID's te koppelen aan spelers en sessies.

Waarom?
-------
- In WOK_Game_Session zit de kolom `Game_Transactions` als JSON.
- Daarin zitten Transaction_ID's, maar die staan niet rechtstreeks in de 
  Player Account Transaction (PAT) tabel.
- Om een feature te kunnen maken die beide tabellen combineert 
  (zoals `game_sum` of `time_eas`), heb je dus een *mapping* nodig.
- Deze helpers bouwen die mapping *streamend* en houden alleen het resultaat
  (dict) in RAM. Je hoeft de hele sessie-tabel dus niet in één keer te laden.

Functies
--------
- **build_txid_to_player_map_ram**  
  Bouwt een dict van:
      Transaction_ID → Player_Profile_ID  
  → Handig voor features waar alleen de speler nodig is (bijv. `game_sum`).

- **build_txid_to_player_and_session_map_ram**  
  Bouwt een dict van:
      Transaction_ID → (Player_Profile_ID, Game_Session_ID)  
  → Handig voor features die sessie-informatie nodig hebben 
    (bijv. `end_accel_score_stream`).

Werking in stappen
------------------
1. Beide functies gebruiken `normalize_game_transactions_stream` 
   (uit `reading_difficult_json.py`) om de JSON kolom 
   `Game_Transactions` te ontleden, chunk voor chunk.
   - Elke chunk levert een klein DataFrame met kolommen:
       ["Transaction_ID", "Player_Profile_ID", "Game_Session_ID"]

2. Terwijl chunks binnenkomen:
   - Loopt de functie over alle rijen.
   - Zet Transaction_ID altijd om naar string (consistentie).
   - Slaat de eerste Player_ID/Session_ID weg voor dat TxID.
     (duplicaten worden genegeerd → eerste waarde wint).

3. Logging:
   - Als `logger` is meegegeven → schrijft naar logbestand.
   - Anders → print een korte samenvatting (rows_seen, unique_tx).

Return
------
- Een Python-dict, nooit None.
- Sleutels: alle unieke Transaction_ID’s (str).
- Waarden:
  - bij `build_txid_to_player_map_ram`: Player_Profile_ID (of None)
  - bij `build_txid_to_player_and_session_map_ram`: tuple(Player_Profile_ID, Game_Session_ID)

Gebruik
-------
```python
from mapping_helpers import build_txid_to_player_map_ram

session_paths = [Path(".../WOK_Game_Session_1_clean.csv")]
mapping = build_txid_to_player_map_ram(session_paths)

pid = mapping.get("some_transaction_id")
"""

from __future__ import annotations
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set
from reading_difficult_json import normalize_game_transactions_iterator
from path_finding import iter_csv_chunks
import pandas as pd
from reading_difficult_json import _safe_load_json_relaxed, Player_Profile_Bank_Account_json_iterator

def build_txid_to_player_map_ram(
    session_paths: List[Path],
    *,
    chunksize: int = 200_000,
    batch_out: int = 200_000,
    verbose: bool = True,
    logger=None,
) -> Dict[str, Optional[str]]:
    """
    Bouw een RAM mapping van TxID → Player_Profile_ID door de sessie-JSON te streamen.
    """
    mapping: Dict[str, Optional[str]] = {}
    rows_seen = 0

    # hier gebruiken we een iterator die stukjes DataFrame teruggeeft, en json ontleedt
    for df in normalize_game_transactions_iterator(
        session_paths, chunksize=chunksize, batch_out=batch_out, verbose=verbose
    ):
        rows_seen += len(df)
        # verwacht kolommen: Transaction_ID, Player_Profile_ID, Game_Session_ID
        for tx, pid in zip(df["Transaction_ID"], df["Player_Profile_ID"]):
            tx = str(tx)
            if tx not in mapping:
                mapping[tx] = None if pd.isna(pid) else str(pid)

    if logger:
        logger.info(f"build_txid_to_player_map_ram: rows_seen={rows_seen:,}, unique_tx={len(mapping):,}")
    elif verbose:
        print(f"✅ build_txid_to_player_map_ram: rows_seen={rows_seen:,}, unique_tx={len(mapping):,}")

    return mapping  # nooit None

def haal_uit_bank_json_iterator(
    session_paths: List[Path],
    *,
    chunksize: int = 200_000,
    batch_out: int = 200_000,
    verbose: bool = True,
    logger=None,
    need_cols: Optional[List[str]] = None,
    ) -> Dict[str, List[str]]:
    """
    Haal alle bank IDs uit de JSON kolom Player_Profile_Bank_Accounts. 
    Need_cols = ["Player_Profile_ID","Player_Profile_Bank_Account"]
    en uit Player_Profile_Bank_Account de Bank_Account_ID:
    [{"Bank_Account_ID":"1a","Bank_Account_Datetime":"2025-06-19T13:10:39Z","Bank_Account_Active":"true"} 
    """
    dict_bank_ids_per_speler: Dict[str, Set[str]] = {}
    rows_seen = 0
    need_cols = need_cols  
    for chunk in iter_csv_chunks(session_paths, usecols=need_cols, chunksize=chunksize, verbose=verbose):
        for rij in chunk:
            print('dit is de rij ---------', rij)
            rows_seen += 1
            personID = chunk.at[rij, "Player_Profile_ID"]
            
            if personID not in dict_bank_ids_per_speler:
                dict_bank_ids_per_speler[personID] = set()  # gebruik een set om duplicaten te vermijden
            else:
                bestaande_bank_accounts = dict_bank_ids_per_speler[personID]
                bestaande_bank_accounts.add(bank_account_ID)


        for rij_index in range(len(chunk)):
            id_var = need_cols[0]
            # uitleg wat hier onder gebeurt:
            # if id_var in chunk.columns:
            #     kolom_index_id_var = chunk.columns.get_loc(id_var)
            #     sessie_id = chunk.iat[rij_index, kolom_index_id_var]
            #     chunk.iat[rij_index, kolom_index_id_var] = str(sessie_id)
            # else:
            #     sessie_id = None
            
            cell = chunk.iat[rij_index, chunk.columns.get_loc(id_var)] if id_var in chunk.columns else None
            json_obj = _safe_load_json_relaxed(cell)
            if json_obj is None:
                bad_json_rows += 1
                continue
            # Loop over alle entries in het JSON-object Player_Profile_Bank_Account met een nieuwe iterator
            # uit de json [{"Bank_Account_ID":"1a","Bank_Account_Datetime":"2025-06-19T13:10:39Z","Bank_Account_Active":"true"} heb ik alleen Bank_Account_ID nodig
            for bank_account_ID, bank_account_datetime, bank_account_active in Player_Profile_Bank_Account_json_iterator(json_obj):
                dict_bank_ids_per_speler[personID] = bank_account_ID 

# Even kijken... hoe krijg ik nu de player profile ID erbij? 


# def build_txid_to_player_and_session_map_ram(
#     session_paths: List[Path],
#     *,
#     chunksize: int = 200_000,
#     batch_out: int = 200_000,
#     verbose: bool = True,
#     logger=None,
# ) -> Dict[str, Tuple[Optional[str], Optional[str]]]:
#     """
#     Bouw een RAM mapping van TxID → (Player_Profile_ID, Game_Session_ID).
#     """
#     mapping: Dict[str, Tuple[Optional[str], Optional[str]]] = {}
#     rows_seen = 0

#     for df in normalize_game_transactions_stream(
#         session_paths, chunksize=chunksize, batch_out=batch_out, verbose=verbose
#     ):
#         rows_seen += len(df)
#         for tx, pid, sid in zip(df["Transaction_ID"], df["Player_Profile_ID"], df["Game_Session_ID"]):
#             tx = str(tx)
#             if tx not in mapping:
#                 mapping[tx] = (
#                     None if pd.isna(pid) else str(pid),
#                     None if pd.isna(sid) else str(sid),
#                 )

#     if logger:
#         logger.info(f"build_txid_to_player_and_session_map_ram: rows_seen={rows_seen:,}, unique_tx={len(mapping):,}")
#     elif verbose:
#         print(f"✅ build_txid_to_player_and_session_map_ram: rows_seen={rows_seen:,}, unique_tx={len(mapping):,}")

#     return mapping  # nooit None


def maak_een_list_van_spelers(
    session_paths: List[Path],
    *,
    chunksize: int = 200_000,
    batch_out: int = 200_000,
    verbose: bool = True,
    logger=None,
) -> Dict[str, Optional[str]]:
    """
    Bouw een lijst van spelers.
    """
    Player_Profile_ID_list = []
    for path in session_paths:
        df = pd.read_csv(path, usecols=["Player_Profile_ID"], low_memory=False)
        Player_Profile_ID_list.extend(df["Player_Profile_ID"].dropna().astype(str).unique().tolist())
    return Player_Profile_ID_list
