
import re, json
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Callable 
from typing import Iterable, Optional, Tuple


organisatie_SCHEMA_BY_FILE = {
    "WOK_Bet.csv": {
        # Key fields
        "Record_ID": "stringMedium",
        "Extraction_Date": "dateTimeUTC",
        "Operator_ID": "stringMedium",
        "Data_Safe_ID": "stringMedium|null|optional",
        "Replaced_Record_ID": "stringMedium|null|optional",

        # Bet
        "Bet_ID": "stringMedium",
        "Bet_Start_Datetime": "dateTimeUTC",
        "Bet_Cancellation_Reason": "stringLong|null|optional",
        "Bet_Type": "Enumeration",
        "Bet_XY": "Int|null|optional",
        "Bet_Commission": "stringMedium|null|optional",
        "Bet_Status": "Enumeration",

        # JSON (zoals in de print)
        "Bet_Parts": "json",
        "Bet_Total_Stake": "monetaryAmount",

        "Bet_Transactions": "json",

        # platform/meta (niet-organisatie)
        "_event_date": "meta:dateTimeUTC",
        "_filter_label": "meta:string|null",
        "_write_timestamp": "meta:dateTimeUTC",
        "_partitiontime": "meta:string|int",
    },

    "WOK_Complaint.csv": {
        "Record_ID": "stringMedium",
        "Extraction_Date": "dateTimeUTC",
        "Operator_ID": "stringMedium",
        "Data_Safe_ID": "stringMedium|null|optional",

        "Complaint_ID": "stringMedium|optional",
        "Complaint_Type": "stringMedium",
        "Complaint_Datetime": "dateTimeUTC",
        "Complaint_Player_ID": "stringMedium|null|optional",

        # JSON
        "Responses": "json|optional",
    },

    "WOK_Game_Session.csv": {
        "Record_ID": "stringMedium",
        "Extraction_Date": "dateTimeUTC",
        "Operator_ID": "stringMedium",
        "Data_Safe_ID": "stringMedium|null|optional",
        "Replaced_Record_ID": "stringMedium|null|optional",

        "Game_ID": "stringMedium",
        "Game_Session_ID": "stringMedium",
        "Game_Session_Start_Datetime": "dateTimeUTC",
        "Game_Session_End_Datetime": "dateTimeUTC",
        "Game_Session_Commission": "monetaryAmount|null|optional",
        "Game_Session_Rounds": "Int",
        "Game_Session_Rounds_Won": "Int",

        # JSON
        "Game_Transactions": "json",

        # platform/meta
        "_event_date": "meta:dateTimeUTC",
        "_write_timestamp": "meta:dateTimeUTC",
        "_partitiontime": "meta:string|int",
    },

    "WOK_Game.csv": {
        "Record_ID": "stringMedium",
        "Extraction_Date": "dateTimeUTC",
        "Operator_ID": "stringMedium",
        "Data_Safe_ID": "stringMedium|null|optional",

        "Game_ID": "stringMedium",
        "Game_Type": "Enumeration",
        "Game_Commercial_Name": "stringMedium",
        "Game_Datetime_Introduction": "dateTimeUTC",
        "Game_Datetime_Active": "dateTimeUTC",
        "Game_Datetime_Inactive": "dateTimeUTC|null|optional",
    },

    "WOK_Intervention.csv": {
        "Record_ID": "stringMedium",
        "Extraction_Date": "dateTimeUTC",
        "Operator_ID": "stringMedium",
        "Data_Safe_ID": "stringMedium|null|optional",
        "Replaced_Record_ID": "stringMedium|null|optional",

        "Player_Profile_ID": "stringMedium",
        "Intervention_ID": "stringMedium",
        "Intervention_Begin_Datetime": "dateTimeUTC",
        "Intervention_End_Datetime": "dateTimeUTC|null|optional",
        "Intervention_Type": "Enumeration",
        "Intervention_Cause": "Enumeration",
        "Intervention_Owner": "stringMedium",
    },

    "WOK_Net_Deposit_Threshold.csv": {
        "Record_ID": "stringMedium",
        "Extraction_Date": "dateTimeUTC",
        "Operator_ID": "stringMedium",
        "Data_Safe_ID": "stringMedium|null|optional",
        "Replaced_Record_ID": "stringMedium|null|optional",
        "Player_Profile_ID": "stringMedium",
        "Net_Deposit_Threshold_Value": "monetaryAmount|Int",  # organisatie: monetaryAmount
        "Net_Deposit_Threshold_Datetime": "dateTimeUTC",
    },

    "WOK_Operator.csv": {
        "Record_ID": "stringMedium",
        "Extraction_Date": "dateTimeUTC",
        "Operator_ID": "stringMedium",
        "Data_Safe_ID": "stringMedium|null|optional",

        "Concerned_Date": "date",
        "Replaced_Record_ID": "stringMedium|null|optional",

        # JSON
        "Totals": "json",

        # platform/meta
        "_event_date": "meta:dateTimeUTC",
        "_write_timestamp": "meta:dateTimeUTC",
        "_partitiontime": "meta:string|int",
        "_filter_label": "meta:string|null",
    },

    "WOK_Player_Account_Transaction.csv": {
        "Record_ID": "stringMedium",
        "Extraction_Date": "dateTimeUTC",
        "Operator_ID": "stringMedium",
        "Data_Safe_ID": "stringMedium|null|optional",
        "Replaced_Record_ID": "stringMedium|null|optional",

        "Player_Profile_ID": "stringMedium",
        "Transaction_ID": "stringMedium",
        "Transaction_Datetime": "dateTimeUTC",
        "Transaction_Amount": "monetaryAmount",
        "Transaction_Deposit_Instrument": "Enumeration|null",
        "Transaction_Type": "Enumeration",
        "Transaction_Status": "Enumeration",
    },

    "WOK_Player_Flags.csv": {
        "Record_ID": "stringMedium",
        "Extraction_Date": "dateTimeUTC",
        "Operator_ID": "stringMedium",
        "Data_Safe_ID": "stringMedium|null|optional",
        "Player_Profile_ID": "stringMedium",

        # JSON
        "Flag_RG_Class": "json",
        # "Flag_RG_Class.RG_Class_Value": "stringShort",
        # "Flag_RG_Class.RG_Class_Datetime": "dateTimeUTC",
    },

    "WOK_Player_Limits.csv": {
        "Record_ID": "stringMedium",
        "Extraction_Date": "dateTimeUTC",
        "Operator_ID": "stringMedium",
        "Data_Safe_ID": "stringMedium|null|optional",
        "Replaced_Record_ID": "stringMedium|null|optional",
        "Player_Profile_ID": "stringMedium",

        # JSON (zoals in print)
        "Limit_Deposit": "json|null",

        "Limit_Participation": "json|null|optional",

        "Limit_Login": "json|null",

        "Limit_Game_Type": "json|null|optional",

        "Limit_Balance": "json|null",
    },

    "WOK_Player_Profile.csv": {
        "Record_ID": "stringMedium",
        "Extraction_Date": "dateTimeUTC",
        "Operator_ID": "stringMedium",
        "Data_Safe_ID": "stringMedium|null|optional",

        "Player_Profile_ID": "stringMedium",
        "Player_Profile_Registration_Datetime": "dateTimeUTC",
        "Player_Profile_DOB": "date",
        "Player_Profile_Modified": "dateTimeUTC",
        "Player_Profile_Status": "Enumeration",
        "Player_Profile_EOD_Balance": "monetaryAmount",

        # JSON
        "Player_Profile_Bank_Account": "json|null|optional",

        # platform/meta
        "_event_date": "meta:dateTimeUTC",
        "_filter_label": "meta:string|null",
        "_write_timestamp": "meta:dateTimeUTC",
        "_partitiontime": "meta:string|int",
        "_content_hash": "meta:string",
        "_sub_player_profile_id": "meta:string",
    },
}

# === Bestand → schema-key (hergebruik path_finding, met veilige fallback) ===

def resolve_schema_key(raw_filename: str, schema_keys: Iterable[str]) -> Tuple[Optional[str], Optional[str]]:
    """
    Bepaal de juiste schema key (zoals gedefinieerd in organisatie_SCHEMA_BY_FILE) op basis van een ruwe bestandsnaam.

    Doelen / aanpak:
    - Strip eventuele vendor-prefix vóór 'WOK_' (bijv. 'NSUSMALTALIMITED_').
    - Negeer chunktellers zoals '_1', '_2', etc.
    - Normaliseer kleine spelfouten en enkelvoud/meervoud-varianten via een interne alias-tabel.
    - Match case-insensitief tegen de aangeleverde schema_keys en geef de *daadwerkelijke* key terug.
      (Dus exact de key zoals die in `organisatie_SCHEMA_BY_FILE` voorkomt, inclusief '.csv').

    Parameters
    ----------
    raw_filename : str
        De originele bestandsnaam (mag met of zonder pad zijn)
    schema_keys : Iterable[str]
        De beschikbare schema-keys, doorgaans `organisatie_SCHEMA_BY_FILE.keys()`, bijv.
        ['WOK_Player_Limits.csv', 'WOK_Net_Deposit_Threshold.csv', 'WOK_Game_Session.csv', ...]

    Returns
    -------
    Optional[str]
        De gevonden schema-key (exact zoals die in schema_keys staat) of None als er geen match is.

    Opmerkingen
    -----------
    - Deze functie doet *geen* bestands-I/O; het is puur string-normalisatie + matching.
    - Wil je extra varianten ondersteunen? Voeg die toe aan `COMMON_CANONICAL_ALIASES`.
    """

    # 1) Voorbewerking: alleen de bestandsnaam + lowercase hulpsets
    # ------------------------------------------------------------
    # Haal directory-delen weg; werk met de kale bestandsnaam.
    basename = raw_filename.split("/")[-1].split("\\")[-1]

    # Maak een hulplookup: case-insensitieve mapping van 'genormaliseerde' schema_keys
    # naar de *originele* sleutel (zodat we exact die terug kunnen geven).
    normalized_schema_index = {}
    for key in schema_keys:
        # normaliseer: lowercase en verwijder overbodige spaties
        normalized_schema_index[key.strip().lower()] = key

    # 2) Vind het WOK-gedeelte in de bestandsnaam
    # -------------------------------------------
    # We zoeken expliciet naar het begin van 'WOK_' en nemen vanaf daar de rest van de 'kern'.
    # Alles vóór 'WOK_' behandelen we als vendor-prefix en negeren we.
    match_wok_start = re.search(r'WOK_', basename, flags=re.IGNORECASE)
    if not match_wok_start:
        return None, ""  # geen WOK_* in de naam -> we kunnen niet mappen

    wok_core_with_suffixes = basename[match_wok_start.start():]  

    # 3a) Strip extension
    # -------------------------------------------------------------------
    # Verwijder bestandsextensie
    core_no_ext = re.sub(r'\.[A-Za-z0-9]+$', '', wok_core_with_suffixes)

    # 3b) Strip eventuele "_out" suffix
    # ------------------------------------------------------------
    core_no_ext = re.sub(r'_out$', '', core_no_ext, flags=re.IGNORECASE)

    # 4) Extract chunk-suffix
    # ------------------------------------------------------------
    # Sommige aanbieders leveren bestanden in meerdere "chunks"
    # (delen) aan, bijvoorbeeld:
    #
    #   • WOK_Player_Profile_12.csv
    #   • WOK_Player_Profile[12].csv
    #   • WOK_Player_Profile_[12].csv
    #
    # We willen deze suffix (12) opslaan als chunk_suffix="_12",
    # zodat die later in de bestandsnaam kan worden meegenomen bij
    # het wegschrijven van de schoongemaakte bestanden.
    #
    # Als er géén chunk aanwezig is, blijft chunk_suffix gewoon een lege string "".
    #
    chunk_suffix = ""
    core_no_chunk = core_no_ext  # startpunt: de naam zonder extensie

    # a) Vorm: _N  (bijv. "_12")
    # --------------------------------
    m = re.search(r'_(\d+)$', core_no_ext)
    if m:
        chunk_suffix = f"_{m.group(1)}"
        core_no_chunk = core_no_ext[:m.start()]
    else:
        # b) Vorm: [N] of _[N]  (bijv. "[12]" of "_[12]")
        # -----------------------------------------------
        # Deze varianten komen regelmatig voor bij aanbieders.
        m = re.search(r'(?:_\[|\[)(\d+)\]$', core_no_ext)
        if m:
            chunk_suffix = f"_{m.group(1)}"
            core_no_chunk = core_no_ext[:m.start()]

    # 5) Normaliseer meerdere underscores, casing, en kleine typefouten
    # -----------------------------------------------------------------
    # Maak van spaties underscores
    core_only_underscores = re.sub(r' ', '_', core_no_chunk)
    
    # Soms ontstaan dubbele underscores na eerdere bewerkingen; reduceer die.
    core_single_underscores = re.sub(r'_+', '_', core_only_underscores)

    # Normaliseer casing (we matchen case-insensitief, maar alias-keys hieronder zijn in vaste casing)
    normalized_core = core_single_underscores.strip()

    # 6) Bouw een kandidaat-sleutel met '.csv'
    # ----------------------------------------
    # De schema_keys bevatten normaliter '.csv' aan het eind (bv. 'WOK_Game_Session.csv')
    candidate_key = f"{normalized_core}.csv"  # bijv. 'WOK_Player_Limit.csv'

    # 7) Probeer eerst een directe (case-insensitieve) match
    # -------------------------------------------------------
    lowercase_candidate = candidate_key.lower()
    if lowercase_candidate in normalized_schema_index:
        return normalized_schema_index[lowercase_candidate], chunk_suffix
    
    # 8) Canonicaliseer veelvoorkomende varianten via een alias-mapping
    # -----------------------------------------------------------------
    # Hier corrigeer je enkelvoud/meervoud of typefouten. Voeg gerust uit je domeinervaring toe.
    COMMON_CANONICAL_ALIASES = {
        # enkelvoud -> meervoud zoals schema het definieert
        "wok_player_limit.csv": "WOK_Player_Limits.csv",
        "wok_player_limits.csv": "WOK_Player_Limits.csv",  # idempotent

        # veelgemaakte typefout: Thread -> Threshold
        "wok_net_deposit_thread.csv": "WOK_Net_Deposit_Threshold.csv",
        "wok_net_deposit_threshold.csv": "WOK_Net_Deposit_Threshold.csv",  # idempotent

        # voorbeeld: sessies hebben vaste naam
        "wok_game_session.csv": "WOK_Game_Session.csv",
        "wok_player_account_transaction.csv": "WOK_Player_Account_Transaction.csv",
        "wok_player_flags.csv": "WOK_Player_Flags.csv",
        "wok_player_profile.csv": "WOK_Player_Profile.csv",
        "wok_operator.csv": "WOK_Operator.csv",
        "wok_complaint.csv": "WOK_Complaint.csv",  # als jouw schema 'Complaints' (meervoud) gebruikt
        "wok_complaints.csv": "WOK_Complaint.csv",
        # voeg hier meer domein-specifieke fixes toe indien nodig
    }

    if lowercase_candidate in COMMON_CANONICAL_ALIASES:
        alias_target = COMMON_CANONICAL_ALIASES[lowercase_candidate]
        # Controleer of de alias-doel *daadwerkelijk* in schema_keys zit
        alias_target_lower = alias_target.lower()
        if alias_target_lower in normalized_schema_index:
            return normalized_schema_index[alias_target_lower], chunk_suffix

    # Geen robuuste match gevonden
    return None, chunk_suffix

# ---------- type validators ----------
_RE_DATE      = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_RE_DT_UTC_Z  = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
# _RE_UUID      = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
_RE_INT       = re.compile(r"^-?\d+$")
_RE_DECIMAL   = re.compile(r"^-?\d+(?:\.\d+)?$")

def _is_null(v: Any) -> bool:
    return v is None or (isinstance(v, str) and v.strip().lower() in ("", "null", "none", "nan"))

def _norm_type(t: str) -> str:
    return t.split(":", 1)[1] if t.startswith("meta:") else t

def _parse_type_spec(type_spec: str, verbose=False) -> Tuple[List[str], bool, bool]:
    """
    Returns (allowed_base_types, is_nullable_value, is_optional_presence)

    Examples:
      "dateTimeUTC"                  -> (["dateTimeUTC"], False, False)
      "UID|null"                     -> (["UID"], True, False)
      "json|null|optional"           -> (["json"], True, True)
      "meta:dateTimeUTC"             -> (["dateTimeUTC"], False, True)  # meta => optional
      "stringMedium|optional"        -> (["stringMedium"], False, True)
    """
    if verbose:
        print(f'17.a.1.a.1. De toegestane types uit {type_spec} halen, returns (allowed_base_types, is_nullable_value, is_optional_presence)')
    parts = [p.strip() for p in type_spec.split("|")]
    nullable = any(p.lower() == "null" for p in parts)
    optional = any(p.lower() == "optional" for p in parts)
    base_types = [_norm_type(p) for p in parts if p.lower() not in ("null", "optional")]
    # meta:* impliciet optional
    if any(p.startswith("meta:") for p in parts) or type_spec.startswith("meta:"):
        optional = True
    if verbose:
        print(f'17.a.1.a.2 returns base_types {base_types}')
    return base_types, nullable, optional

# -----------------------------------------------------------------------------
# Date & DateTime coercers
# -----------------------------------------------------------------------------
"""
Deze functies zorgen voor robuuste herkenning en normalisatie van datum- en
tijdwaarden naar een strikt, uniform formaat, zoals gedefinieerd in het schema.

Doel
-----
Aanbieders leveren datumvelden in uiteenlopende formaten aan (met of zonder 'T',
met of zonder tijdzone, met slashes, enz.). De coercers accepteren al deze
varianten en zetten ze om naar:
  • Date   → 'YYYY-MM-DD'
  • DateTime UTC → 'YYYY-MM-DDTHH:MM:SSZ'

Werking
--------
- `_try_parse_any_date` herkent allerlei datumachtige invoer en geeft een naive
  datetime terug (tijd op 00:00:00). `_coerce_to_date` formatteert die.
- `_parse_any_dt_with_tz` herkent diverse datetimevormen, inclusief 'Z',
  offsets (+00:00/+0000), fracties, datum-only en EU slashes, en normaliseert
  naar UTC. `_coerce_to_datetime_utc` formatteert deze naar een vaste UTC string.

Gebruik
--------
Deze functies worden indirect aangeroepen vanuit `clean_row_for_file` tijdens
validatie en conversie van rijen:
- In 'check'-modus wordt alleen gevalideerd; fouten leiden tot warnings maar
  overschrijven de originele data niet.
- In 'clean'-modus worden velden die herkend kunnen worden actief overschreven
  met het genormaliseerde formaat. Mislukt de conversie, dan volgt een ERROR
  bij verplichte velden of een waarschuwing bij optionele velden.

Het geheel zorgt voor consistente en reproduceerbare parsing van ruwe
aanbiedersdata zonder afhankelijkheid van externe parsers zoals `dateutil`.
"""

def _try_parse_any_date(s: str) -> Optional[datetime]:
    """
    Probeert verschillende invoerformaten te parsen naar een naive datetime (datum op 00:00:00).
    Heuristiek voor slashes: EU-first (dd/mm/yyyy) als ambigu.
    """
    s = s.strip()
    # Pure date ISO
    try:
        return datetime.strptime(s, "%Y-%m-%d")
    except: pass
    # DateTime met Z of offset varianten
    for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ",
                "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f",
                "%Y-%m-%dT%H:%M:%S"):
        try:
            dt = datetime.strptime(s, fmt)
            return dt
        except: pass
    # Offsets als +00:00 of +0000 of ,000
    # Normalize common BigQuery-ish: "2025-07-11T08:38:39.182+0000"
    m = re.match(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.\d+)?([+-]\d{2}):?(\d{2})$", s)
    if m:
        base, hh, mm = m.group(1), m.group(2), m.group(3)
        try:
            dt = datetime.strptime(base, "%Y-%m-%dT%H:%M:%S")
            # we negeren offset voor 'date' (alleen datum)
            return dt
        except: pass
    # Slashes: EU dd/mm/yyyy of mm/dd/yyyy -> hanteer EU tenzij maand>12
    if re.match(r"^\d{1,2}/\d{1,2}/\d{4}$", s):
        d, m, y = s.split("/")
        d = int(d); m = int(m); y = int(y)
        if m > 12 and d <= 12:
            d, m = m, d  # fallback, maar praktisch niet nodig
        try:
            return datetime(y, m, d)
        except: pass
    return None

def _coerce_to_date(s: str) -> Optional[str]:
    dt = _try_parse_any_date(s)
    if not dt:
        return None
    return dt.strftime("%Y-%m-%d")

def _parse_any_dt_with_tz(s: str) -> Optional[datetime]:
    """
    Parse diverse datetime strings en normaliseer naar aware UTC.
    Ondersteunt 'Z', offsets +00:00/+0000, fractional seconds.
    Einddoel: 2024-12-03T11:36:36Z
    """
    ss = s.strip()

    # Normalize space to T if offset present
    if " " in ss and re.search(r"[+-]\d{2}:?\d{2}$", ss):
        ss = ss.replace(" ", "T")

    # Already strict UTC Z
    if _RE_DT_UTC_Z.match(ss):
        return datetime.strptime(ss, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    # With fractional seconds + Z
    try:
        dt = datetime.strptime(ss, "%Y-%m-%dT%H:%M:%S.%fZ")
        return dt.replace(tzinfo=timezone.utc)
    except: pass
    # ⚡ Extra: Z-formaat zonder seconden → "%Y-%m-%dT%H:%MZ"
    try:
        dt = datetime.strptime(ss, "%Y-%m-%dT%H:%MZ")
        return dt.replace(tzinfo=timezone.utc)
    except:
        pass
    # Offset +00:00 or +0000
    m = re.match(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.(\d+))?([+-]\d{2}):?(\d{2})$", ss)
    if m:
        base, frac, oh, om = m.groups()
        dt = datetime.strptime(base, "%Y-%m-%dT%H:%M:%S")
        if frac:  # we negeren subsec in output
            pass
        offset = timedelta(hours=int(oh), minutes=int(om))
        aware = dt - offset  # normaliseer naar UTC
        return aware.replace(tzinfo=timezone.utc)
    # Space separated or T without tz -> aanname: datatijd is UTC al
    # Hier geen US dingen toevoegen... dan moet hij crashen (los het nu op in operator-filters)
    for fmt in (
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M",
    ):
        try:
            dt = datetime.strptime(ss, fmt)
            return dt.replace(tzinfo=timezone.utc)
        except: pass
    # yyyy-mm-dd only -> klok op 00:00:00 UTC
    try:
        d = datetime.strptime(ss, "%Y-%m-%d")
        return d.replace(tzinfo=timezone.utc)
    except: pass
    # Slashes -> EU heuristiek
    if re.match(r"^\d{1,2}/\d{1,2}/\d{4}$", ss):
        d, m, y = map(int, ss.split("/"))
        dt = datetime(y, m, d)
        return dt.replace(tzinfo=timezone.utc)
    return None

def _coerce_to_datetime_utc(s: str) -> Optional[str]:
    dt = _parse_any_dt_with_tz(s)
    if not dt:
        return None
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")



def _coerce_bool(s: str) -> Optional[str]:
    v = str(s).strip().lower()
    if v in ("true", "1"):  return "true"
    if v in ("false", "0"): return "false"
    return None

# ---------- validate vs clean (row-level API) ----------

def _json_or_none(v, verbose=False):
    if verbose:
        print("10.b", v)

    if _is_null(v):
        return None

    # 1. Normale JSON
    try:
        return json.loads(str(v))
    except json.JSONDecodeError:
        if verbose:
            print("10.b.2 error: gewone json faalt → probeer list extract")

    s = str(v).strip()

    # 2. Check: is het een string zoals "[{...}]"[{""Deposit_Request_Datetime"": None, ""Deposit_Start_Datetime"": None, ""Deposit_Amount"":9, ""Deposit_Time_Window"": None}]
    if s.startswith("[") and s.endswith("]"):
        if verbose:
            print('het is een list')
        try:
            # Extract inside list
            inner = s[1:-1]

            # Fix single → double quotes
            inner_json = inner.replace("'", '"')

            # Replace Python None → JSON null
            inner_json2 = re.sub(r'\bNone\b', 'null', inner_json)

            # Fix doubled double-quotes ""key""
            inner_fixed = re.sub(r'""([^"]+)""', r'"\1"', inner_json2)

            parsed = json.loads(inner_fixed)
            
            # still return the original list, this is just a check.
            return s

        except Exception as e:
            if verbose:
                print("10.b.2.1 error bij list extract:", e)

    # 3. Fallback: double-quote fix
    if verbose:
        print("10.b.3 fallback quote fix")

    try:
        return json.loads(s.replace("'", '"'))
    except Exception:
        return None

# def _extract_by_path(root: Any, path: str) -> List[Any]:
#     nodes: List[Any] = [root]
#     for seg in path.split("."):
#         is_arr = seg.endswith("[]")
#         key = seg[:-2] if is_arr else seg
#         nxt: List[Any] = []
#         for node in nodes:
#             if isinstance(node, dict) and key in node:
#                 val = node[key]
#                 if is_arr and isinstance(val, list): nxt.extend(val)
#                 elif not is_arr: nxt.append(val)
#             elif isinstance(node, list):
#                 for item in node:
#                     if isinstance(item, dict) and key in item:
#                         val = item[key]
#                         if is_arr and isinstance(val, list): nxt.extend(val)
#                         elif not is_arr: nxt.append(val)
#         nodes = nxt
#         if not nodes: break
#     out: List[Any] = []
#     for n in nodes:
#         if isinstance(n, list): out.extend(n)
#         else: out.append(n)
#     return out

# def _toepassen_op_pad(data: Any, pad: str, bewerking: Callable[[Any], Any], verbose=False, logger=None) -> Any:
#     """
#     Geef een JSON-achtig object terug waarbij alle leaf-waarden op 'pad' door 'bewerking' zijn getransformeerd.
#     Let op: net als het origineel muteert dit de input 'data' *in place* (geen deep copy).
    
#     Argumenten
#     ----------
#     data : willekeurige geneste structuur (dict/list/scalars) die JSON representeert
#     pad : dot-notation pad, met '[]' om lijstelementen aan te duiden (bv. "A.B[].C.D[]")
#     bewerking : Callable die één leaf-waarde ontvangt en de getransformeerde waarde teruggeeft
#     """

#     if verbose:
#         print('12. === _toepassen_op_pad ===')
#         print('12. pad:', pad)
#         print('12. data (sample):', str(data)[:100] + ('...' if len(str(data)) > 100 else ''))

#     # 1) Snelle afslag: als de wortel None is, is er niets te transformeren.
#     if data is None:
#         if verbose:
#             print('13. Wortel is None')
#         return None

#     # 2) Splits het pad in segmenten op de punten (.)
#     #    Voorbeeld: "A.B[].C" -> ["A", "B[]", "C"]
#     pad_segmenten = pad.split(".")

#     def _doorlopen(knoop: Any, pad_index: int, verbose = False) -> Any:
#         """
#         Recursieve helper:
#         Dit zoekt naar de uiterste waarde in een JSON (de leaf), om de bewerkingsfunctie
#         op toe te passen!

#         - 'knoop' is de huidige subboom (dict/list/scalar)
#         - 'pad_index' zegt welk segment van 'pad_segmenten' we nu behandelen
#         """
#         if verbose:
#             print()
#             print(f'15. --- _doorlopen {pad_segmenten} ---')
#             print(f'16. pad_index:', pad_index, 'len:', len(pad_segmenten))

#         # 3) Basisgeval: als we het einde van het pad bereikt hebben,
#         #    zitten we op een leaf: pas de bewerking toe en geef de nieuwe waarde terug.
#         if pad_index == len(pad_segmenten):
#             if verbose:
#                 print(f'17. --- Leaf bereikt --- want pad_index {pad_index} == len {len(pad_segmenten)}')
#                 print(f'17.a!. We zitten op het laagste niveau, bewerking {bewerking.__name__} toepassen')
#             return bewerking(knoop)

#         # 4) Kijk naar het PAD uit het schema en detecteer of het een lijstsegment is (eindigt op "[]").
#         segment = pad_segmenten[pad_index]
#         if verbose:
#             print('17.b. segment: ', segment)
#         is_lijstsegment = segment.endswith("[]")
#         if verbose:
#             print('17.c. dit segment is ', is_lijstsegment, ' een lijstsegment')

#         #    Voor lijstsegmenten strippen we de "[]" om de sleutelnaam te krijgen.
#         sleutel = segment[:-2] if is_lijstsegment else segment
#         print('17.c.1. sleutel voor dit segment is:', sleutel)

#         # 5) Als de knoop een dict is en de sleutel bestaat:
#         if isinstance(knoop, dict) and sleutel in knoop:
#             #    a) En het padsegment zegt dat het een lijst is, én de waarde is een list:
#             if is_lijstsegment and isinstance(knoop[sleutel], list):
#                 if verbose:
#                     print(f'17.d. Sleutel {sleutel} in knoop {knoop} gevonden, maar sleutel is zelf een dict/key!')
#                 #       → pas recursie toe op elk element in de lijst, en schuif het pad 1 naar voren.
#                 knoop[sleutel] = [_doorlopen(element, pad_index + 1) for element in knoop[sleutel]]
#             else:
#                 if verbose:
#                     print(f'17.e. Sleutel {sleutel} in knoop {knoop} gevonden, maar sleutel is zelf een dict/key!')
#                 #    b) Anders is het een enkelvoudig vervolg: recursie op de child, pad +1.
#                 knoop[sleutel] = _doorlopen(knoop[sleutel], pad_index + 1)

#         # 6) Als de knoop zelf een lijst is (maar dit segment is géén expliciet "[]"-veld in een dict):
#         #    dan proberen we elk element met hetzelfde pad_index verder te laten lopen.
#         elif isinstance(knoop, list):
#             if verbose:
#                 print(f'17.f. Knoop is zelf een lijst {knoop}, dus elk element verder doorlopen met hetzelfde pad_index {pad_index}')
#             for i in range(len(knoop)):
#                 if verbose:
#                     print(f'17.f.1. Element index {i} van lijst {knoop[i]} verder doorlopen') 
#                 knoop[i] = _doorlopen(knoop[i], pad_index, verbose=verbose)

#         # 7) In alle andere gevallen (sleutel bestaat niet, of types passen niet), geef knoop ongewijzigd terug.
#         if verbose:
#             print(f'17.g. Sleutel {sleutel} niet gevonden in knoop {knoop}, of type mismatch; knoop ongewijzigd teruggeven')
#         return knoop

#     if verbose:
#         print(f'14. Start met doorlopen op {data} met pad index 0')

#     # 8) Start de recursie vanaf de wortel met pad_index 0.
#     return _doorlopen(data, 0, verbose=verbose)

def _validate_and_optionality(field_path: str, 
                              value_present: bool, 
                              value: Any, 
                              type_spec: str,
                              mode: str,  # "check" | "clean"
                              emit_warn: Callable[[str], None],
                              emit_error: Callable[[str], None],
                              verbose = False) -> Tuple[bool, Any, bool]:
    """
    - Bepaalt optional/nullable uit type_spec
    - Valideert value en zet waar mogelijk om
    - Gedragsmatrix:
        CHECK:
          missing or misformat -> warn alleen als NOT optional
        CLEAN:
          missing or misformat -> warn als optional, error als NOT optional
    Return: (ok, possibly_transformed_value, changed)
    """
    if verbose:
        print(f'17.a.1.a Validitie check on {value}')
    
    base_types, nullable, optional = _parse_type_spec(type_spec, verbose)

    # 1) presence check
    if not value_present:

        # Hier gebruiken we de 'verbose' flag om de error te ontwijken.
        if verbose:
            print(f'17.a.1.a.1. Value ontbreekt voor pad {field_path}')
        elif mode == "check":
            if not optional:
                emit_warn(f"{field_path}: ontbreekt (vereist)")
            return False, value, False
        else:  # clean
            if optional:
                emit_warn(f"{field_path}: ontbreekt (optioneel)")
                return False, value, False
            else:
                emit_error(f"{field_path}: ontbreekt (vereist)")
                return False, value, False

    # 2) null/empty
    if _is_null(value):
        if nullable:
            return True, None, (value is not None)
        # niet nullable
        if mode == "check":
            if not optional:
                emit_warn(f"{field_path}: leeg/NULL maar niet toegestaan")
            return False, value, False
        else:
            if optional:
                emit_warn(f"{field_path}: leeg/NULL (optioneel)")
                return False, value, False
            else:
                emit_warn(f"{field_path}: leeg/NULL maar niet toegestaan")
                return False, value, False

    value_as_string = str(value)

    # 3) type-specific validation + coercion
    # maak een functie die we later toepassen om 
    def _is_ok_na_omzetting(datatype: str, waarde_str: str, verbose: bool = False) -> Tuple[bool, Optional[str], bool]:
        """
        Controleer en (indien mogelijk) zet 'waarde_str' om naar het gewenste 'datatype'.

        Returns
        -------
        (is_ok, nieuwe_waarde, is_aangepast)
        - is_ok        : bool  → is de waarde geldig (eventueel na omzetting)?
        - nieuwe_waarde: str|None → de (mogelijk omgezette) waarde
        - is_aangepast : bool  → is er daadwerkelijk een omzetting uitgevoerd?

        Voorbeeld:
        ----------
        _is_ok_na_omzetting("Int", "11.0") → (True, "11", True)
        _is_ok_na_omzetting("boolean", "TRUE") → (True, "true", True)
        _is_ok_na_omzetting("date", "2025/10/24") → (True, "2025-10-24", True)
        """

        if verbose:
            print(f"[omzetting] datatype={datatype!r} | waarde={waarde_str!r}")

        # --- DATUM ---
        if datatype == "date":
            if _RE_DATE.match(waarde_str):
                if verbose: print("  → geldige ISO-datum, geen omzetting nodig")
                return True, waarde_str, False
            geconverteerd = _coerce_to_date(waarde_str)
            if verbose: print(f"  → omgezet naar datum: {geconverteerd!r}")
            return (geconverteerd is not None, geconverteerd, geconverteerd is not None)

        # --- DATUMTIJD (UTC) ---
        if datatype == "dateTimeUTC":
            if _RE_DT_UTC_Z.match(waarde_str):
                if verbose: print("  → geldige UTC-datumtijd met 'Z', geen omzetting nodig")
                return True, waarde_str, False
            geconverteerd = _coerce_to_datetime_utc(waarde_str)
            if verbose: print(f"  → omgezet naar UTC-datumtijd: {geconverteerd!r}")
            return (geconverteerd is not None, geconverteerd, geconverteerd is not None)

        # --- INTEGER ---
        if datatype in ("Int",):
            # 1) Geldige integers (met of zonder '+')
            if _RE_INT.match(waarde_str):
                zonder_plus = waarde_str.lstrip("+")
                if verbose:
                    msg = "  → geldig geheel getal (met '+' verwijderd)" if zonder_plus != waarde_str else "  → geldig geheel getal"
                    print(msg, "| resultaat:", repr(zonder_plus))
                return True, zonder_plus, (zonder_plus != waarde_str)

            # 2) Floats die eigenlijk een integer zijn, bv. '11.0' → '11'
            if re.match(r"^-?\d+\.0+$", waarde_str):
                try:
                    naar_int = str(int(float(waarde_str)))
                    if verbose: print(f"  → omgezet van float naar integer: {naar_int!r}")
                    return True, naar_int, True
                except Exception as e:
                    if verbose: print(f"  → fout bij omzetting float→int: {e}")

            # 3) Anders ongeldig
            if verbose: print("  → ongeldige integer")
            return False, waarde_str, False

        # --- DECIMAAL / GELDBEDRAG ---
        if datatype in ("Decimal", "monetaryAmount"):
            ok = bool(_RE_DECIMAL.match(waarde_str))
            if verbose: print(f"  → decimal/geldbedrag geldig={ok}")
            return ok, waarde_str, False

        # --- BOOLEAN ---
        if datatype in ("boolean", "Boolean"):
            geconverteerd = _coerce_bool(waarde_str)
            ok = geconverteerd is not None
            if verbose: print(f"  → boolean omgezet={geconverteerd!r} | geldig={ok}")
            return ok, (geconverteerd if ok else waarde_str), ok

        # --- JSON ---
        if datatype in ("json",):
            try:
                _ = _json_or_none(waarde_str, verbose)
                if verbose: print("  → JSON geaccepteerd (geen strenge validatie)")
                return True, waarde_str, False
            except Exception as e:
                if verbose: print(f"  → JSON-fout: {e}")
                return False, waarde_str, False

        # --- ALLES ANDERS (tekst, enum, timeWindow, etc.) ---
        if verbose: print("  → standaardtype (tekst/enum/timeWindow): altijd geldig")
        return True, waarde_str, False

    # slaagt als ÉÉN van de toegestane types accepteert
    any_ok, new_val, any_changed = False, value_as_string, False
    for base_type in base_types:
        ok, nv, ch = _is_ok_na_omzetting(datatype=base_type, waarde_str=value_as_string, verbose = verbose)
        if ok:
            any_ok, new_val, any_changed = True, nv, ch
            break

    if any_ok:
        # # bij clean: als er conversie nodig was → optioneel=warn, niet-optioneel=error
        # if mode == "clean" and any_changed:
        #     if optional:
        #         emit_warn(f"{field_path}: automatisch geconverteerd naar {base_types[0]}")
        #     else:
        #         emit_error(f"{field_path}: niet in juiste format, wel geconverteerd → {base_types[0]}")
        # elif mode == "check":
        #     # bij check: misformat maar wél converteerbaar → alleen warn als niet-optioneel
        #     if any_changed and (not optional):
        #         emit_warn(f"{field_path}: niet in juiste format; zou geconverteerd worden → {base_types[0]}")
        return True, new_val, any_changed

    # niet ok en niet converteerbaar
    if mode == "check":
        if not optional:
            emit_warn(f"{field_path}: ongeldig format voor {base_types}")
    else:
        if optional:
            emit_warn(f"{field_path}: ongeldig format (optioneel)")
        else:
            emit_warn(f"{field_path}: !!!! ongeldig format voor {base_types}")
    return False, value, False

def _synthesize_json_parent(
    out_dict: dict,
    parent_col: str,
    fields: dict,                 # {"SubKey": "typeSpec", ...}
    *,
    require_all: bool,
    filename: str,
    rownum: int,
    mode: str,
    emit_warn,
    emit_error,
) -> None:
    """
    Bouw parent_col (JSON) uit losse flat kolommen als die aanwezig zijn.
    - require_all=True  → alleen bouwen als ALLE subkeys aanwezig én non-null zijn
    - require_all=False → bouwen als MINSTENS één subkey aanwezig én non-null is
    Type-coercion gebruikt je bestaande validator (_validate_and_optionality).
    """
    # Als er al een JSON staat, laat staan
    if parent_col in out_dict and not _is_null(out_dict.get(parent_col)):
        return

    present = []
    for subkey in fields.keys():
        if subkey in out_dict and not _is_null(out_dict.get(subkey)):
            present.append(subkey)

    if require_all and len(present) < len(fields):
        return
    if not require_all and len(present) == 0:
        return

    payload = {}
    for subkey, type_spec in fields.items():
        if subkey in out_dict and not _is_null(out_dict.get(subkey)):
            label = f"[row {rownum}] {parent_col}.{subkey}"
            ok, coerced, changed = _validate_and_optionality(
                label, True, out_dict[subkey], type_spec, mode, emit_warn, emit_error
            )
            # Als ok en we hebben een coerced waarde, gebruik die; anders originele
            payload[subkey] = coerced if (ok and coerced is not None) else out_dict[subkey]

    if payload:
        out_dict[parent_col] = json.dumps(payload, ensure_ascii=False)

def clean_row_for_file(row: Dict[str, Any],
                       filename: str, *,
                       rownum: int,
                       emit_warn: Callable[[str], None],
                       emit_error: Callable[[str], None],
                       mode: str,
                       verbose: bool = False,
                       logger=None,
                       first_row=False,
                       present_columns: set | None = None) -> Dict[str, Any]:
    """
    mode = "check" (alleen beoordelen) of "clean" (converteer waar mogelijk, errors volgens regels)
    Retourneert een (mogelijk) gewijzigde row-dict voor FLAT kolommen + JSON kolommen.

    present_columns (organisatie-uitbreiding): als gezet, bevat dit de set kolommen die daadwerkelijk in
    het bronbestand staan. Platte schemavelden waarvan de kolom volledig ONTBREEKT in het bestand
    worden dan overgeslagen (geen "vereist"-fout). Zo werkt de cleaner ook op organisatie-data die alleen
    de inhoudelijke kolommen levert (zonder boilerplate als Record_ID/Extraction_Date/Operator_ID).
    Bij `present_columns=None` (oude aanroepen) of volledige bestanden verandert er niets.
    """
    schema = organisatie_SCHEMA_BY_FILE.get(filename, {})
    dictionary_van_rij = dict(row)
    if verbose:
        print(f'--- clean_row_for_file voor {filename} (row {rownum}) in mode {mode} ---')
        print('0. oorspronkelijke rij:', row)

    # --- STAP 0: synthese van JSON-ouders uit losse kolommen (twee concrete gevallen) ---

    # 0a) Operator: bouw Totals uit losse kolommen als er iig één aanwezig is
    # Kolommen zijn vóór row-cleaning al naar lowercase omgezet (cleaner.py regel 423),
    # dus we zoeken op lowercase keys.
    if filename == "WOK_Operator.csv":
        _synthesize_json_parent(
            dictionary_van_rij,
            parent_col="Totals",
            fields={
                "subtotal_previous_day": "monetaryAmount",
                "subtotal_previous365days": "monetaryAmount",
            },
            require_all=False,  # één of beide is ook goed
            filename=filename, rownum=rownum, mode=mode,
            emit_warn=emit_warn, emit_error=emit_error,
        )

    # 0b) Player Flags: bouw Flag_RG_Class alleen als beide subvelden er zijn
    # Kolommen zijn vóór row-cleaning al naar lowercase omgezet (cleaner.py regel 423).
    if filename == "WOK_Player_Flags.csv":
        _synthesize_json_parent(
            dictionary_van_rij,
            parent_col="Flag_RG_Class",
            fields={
                "rg_class_value": "stringShort",
                "rg_class_datetime": "dateTimeUTC",
            },
            require_all=True,  # beide verplicht
            filename=filename, rownum=rownum, mode=mode,
            emit_warn=emit_warn, emit_error=emit_error,
        )

    # --- daarna je bestaande stappen 1) FLAT en 2) JSON paden ---

    # Loop alle paden binnen deze JSON-basis af
    # 1) FLAT velden (platte top-level kolommen, zonder "." of "[]")
    # print('schema:', schema)
    for veldnaam, typespecificatie in schema.items():
        # print('veldnaam', veldnaam)
        # print('typespecificatie', typespecificatie)
        if "." in veldnaam or "[]" in veldnaam:
            # Sla JSON-paden en lijstelementen hier over: die komen in stap 2
            continue

        # organisatie-uitbreiding: kolommen die volledig ontbreken in het bronbestand niet valideren
        # (geen "vereist"-fout). Zo draait de cleaner ook op de minimale organisatie-kolomset.
        if present_columns is not None and veldnaam not in present_columns:
            continue

        base_types, is_null_toegestaan, is_optioneel = _parse_type_spec(typespecificatie)

        is_aanwezig = veldnaam in dictionary_van_rij
        huidige_waarde = dictionary_van_rij.get(veldnaam)

        # Valideer en pas (indien nodig) de waarde/optioneelheid aan
        is_geldig, nieuwe_waarde, is_aangepast = _validate_and_optionality(
            f"[row {rownum}] {veldnaam}",
            is_aanwezig,
            huidige_waarde,
            typespecificatie,
            mode,
            emit_warn,
            emit_error,
            verbose,
        )

        # In 'clean'-modus mag de waarde worden overschreven als de validator dat aangeeft
        if mode == "clean" and is_geldig and is_aangepast:
            dictionary_van_rij[veldnaam] = nieuwe_waarde

    # 2) JSON paden

    # zo zou het eruit moeten zien, dus 7 WOK-bestanden met in totaal 10 JSON velden (op volgorde in cdb-pdf):
    # 1. Operator: "{""Subtotal_Previous_Day"":""283.79"",""Subtotal_Previous365Days"":""-42095456.42""}"
    # 2. Player_Profile: "[{""Bank_Account_ID"":""b"",""Bank_Account_Datetime"":""2025-06-19T13:10:39Z"",""Bank_Account_Active"":""true""}]"
    # 3. Player_Flags: "{""RG_Class_Value"":""RG_RISK_LOW"",""RG_Class_Datetime"":""2025-06-20T00:00:00Z""}"
    # 4. Player_Limits: 
    ## "[{""Deposit_Request_Datetime"": ""1-1-1T1:1:1Z"", ""Deposit_Start_Datetime"": ""1-1-1T1:1:1Z"", ""Deposit_Amount"": 1, ""Deposit_Time_Window"": ""Week""}]"
    ## "[{""Login_Request_Datetime"": ""1-1-1T1:1:1Z"", ""Login_Start_Datetime"": ""1-1-1T1:1:1Z"", ""Login_Duration"": 1.1, ""Login_Time_Window"": ""Week""}]"
    ## "[{""Balance_Request_Datetime"": ""1-1-1T1:1:1Z"", ""Balance_Start_Datetime"": ""1-1-1T1:1:1Z"", ""Balance_Amount"": 1}]"
    # 5. Game_Session: "{""Game_Transaction"":[{""Player_Profile_ID"":""Piet"",""Transaction_ID"":""Piet_1""}]}"
    # 6. Bet: 
    ## "{""Part"":[{""Part_ID"":""5a12527c-0dfb-d325-8e3f-919569409537"",""Part_Event"":""|SV Sandhausen|"",""Part_Odds"":""11.00"",""Part_Sport"":""FOOTBALL"",""Part_Live"":""false"",""Part_Bank"":""false"",""Part_Match_Datetime"":""2025-07-11T15:30:00Z"",""Part_Prognosis_Result_Type"":""MATCH ODDS"",""Part_Prognosis_Value"":""|Draw|"",""Part_Stake"":""10.00""}]}"
    ## "{""Bet_Transaction"":[{""Player_Profile_ID"":""291463a9-5ab0-f2d8-9c44-6c9d499aa0a0"",""Transaction_ID"":""20d231e6-38d1-4d0d-80c7-21186526e5e0""}]}"
    # 7. Complaint: [{""Response"":[{""Response_ID"":""1"",""Response_Type"":""C1"",""Response_Description"":""1"",""Response_Datetime"":""2025-07-14T10:38:06Z""}]}]"
    
    # # Bouw een mapping van <JSON-basisveld> -> lijst van (pad, typespecificatie)
    # json_paden_per_basis: Dict[str, List[Tuple[str, str]]] = {}
    # if verbose:
    #     print(f'bouw een ideale map, want mode is {mode}')
    #     print('1. schema items', schema.items())
    #     print()

    # # voor elke veldnaam en type in schema (Player_Profile_ID, stringMedium), append aan de hoofdgroep (Game_Transaction)
    for veldnaam, typespecificatie in schema.items():
    #     # Alleen items die wél JSON-paden of lijstpaden bevatten
        if typespecificatie[0:2] != "js":
            if verbose == True:
                print(f'2.a veldnaam {veldnaam} geen Json')
            
            # ga door tot je een JSON veldnaam hebt
            continue

        else:
            if verbose == True:
                print(f'2.b JSON GEVONDEN: {veldnaam}')

        # Bepaal de JSON-basis (alles vóór de eerste '.' of '[]')
        # basisveld = veldnaam.split(".", 1)[0]
        # basisveld = basisveld.split("[]", 1)[0]
        basisveld = veldnaam

        if verbose == True:
            print('3. basisveld', basisveld)

        # # Het relatieve pad binnen de JSON (na de basis)
        # relatief_pad = veldnaam[len(basisveld):].lstrip(".")
        # if verbose: 
        #     print('4. relatief_pad', relatief_pad)
        #     print('4. platonisch jsonpad oud', json_paden_per_basis)
        # json_paden_per_basis.setdefault(basisveld, []).append((relatief_pad, typespecificatie))
        # if verbose:
        #     print('5. platonisch jsonpad nieuw', json_paden_per_basis)

        # Loop per JSON-basisveld alle paden af
        if verbose:
            print('6. Ga met deze Json aan de slag:', basisveld)
        # for basis_jsonkolom, paden in json_paden_per_basis.items():
        #     is_aanwezig = basis_jsonkolom in out
        ruwe_json = dictionary_van_rij.get(basisveld)
        if verbose:
            print('7. ruwe_json', ruwe_json)

    #     # Als de basis zelf als optioneel in het schema staat, neem die optionaliteit mee.
    #     # (Default naar "json|optional" als het basisveld niet expliciet in schema staat.)
    #     basis_typespecificatie = schema.get(basis_jsonkolom, "json|optional")
    #     if verbose:
    #         print('8. basis_typespecificatie', basis_typespecificatie)
        
    #     # # - Bepaalt optional/nullable uit type_spec
    #     # # - Valideert value en zet waar mogelijk om
    #     # is_geldig_basis, _, _ = _validate_and_optionality(
    #     #     field_path=f"[row {rownum}] {basis_jsonkolom}",
    #     #     value_present=is_aanwezig,
    #     #     value=ruwe_json,
    #     #     type_spec=basis_typespecificatie,
    #     #     mode=mode,
    #     #     emit_warn=emit_warn,
    #     #     emit_error=emit_error,
    #     # )
    #     # # print('field_path', f"[row {rownum}] {basis_jsonkolom}")
    #     # print('value', ruwe_json)

    #     # Als het basisveld ontbreekt of (null/empty) is, niets te doen voor deze basis
    #     if not is_aanwezig or _is_null(ruwe_json) and first_row:
    #     # If verbose want er is al een warning gegeven bij de validatie van het basisveld
    #         if verbose:
    #             print(f"9. [WARN] {basis_jsonkolom} niet in {out})")
    #         continue

        #### STRING MANIPULATIES VOOR SPECIFIEKE CASES ####

        if ruwe_json == '':
            if verbose:
                print('9.a ruwe_json is lege string')
        if ruwe_json is None:
            ruwe_json = ''
            if verbose:
                print('9.a ruwe_json is None')
                print('9.a ruwe_json nu:', ruwe_json)
        if ruwe_json == '[]':
            ruwe_json = ''
            if verbose:
                print('9.a ruwe_json is lege array []')
                print('9.a ruwe_json nu:', ruwe_json)
            

        ### Voor alle bestanden: fix dubbele aanhalingstekens (behalve voor WOK_Complaint, waar dat wel nodig is) ###
        # replace the single ' quotes with double ones (""). for some reason this doesn't work
        # ruwe_json = ruwe_json.replace("'", '""')
        
        if filename == "WOK_Bet.csv":
            if 'PartID' in ruwe_json:
                ruwe_json = ruwe_json.replace('PartStake', 'Part_Stake')
                ruwe_json = ruwe_json.replace('PartEvent', 'Part_Event')
                ruwe_json = ruwe_json.replace('PartID', 'Part_ID')
                ruwe_json = ruwe_json.replace('PartLive', 'Part_Live')
                ruwe_json = ruwe_json.replace('PartMatchStartDate', 'Part_Match_Datetime')
                ruwe_json = ruwe_json.replace('PartOdds', 'Part_Odds')
                ruwe_json = ruwe_json.replace('PartPrognosisResultType', 'Part_Prognosis_Result_Type')
                ruwe_json = ruwe_json.replace('PartPrognosisValue', 'Part_Prognosis_Value')
                ruwe_json = ruwe_json.replace('PartSport', 'Part_Sport')
            if 'BetTransaction' in ruwe_json:
                ruwe_json = ruwe_json.replace('BetTransaction', 'Bet_Transaction')
                ruwe_json = ruwe_json.replace('PlayerProfileID', 'Player_Profile_ID')
                ruwe_json = ruwe_json.replace('TransactionID', 'Transaction_ID')
            if basisveld == "Bet_Parts":
            # check if ruwe json has 3 opening braces in the string
                if ruwe_json.count('[{') > 1:
                    if verbose:
                        print(f"9.a.0.a [WARN] {basisveld} heeft te veel opening braces, parsen het als json")
                    # probeer hem als json in te laden
                    ruwe_json = json.loads(ruwe_json)
                    nieuwe_json_inhoud = []
                    for part_key in ruwe_json["Parts"]:
                        part_list = part_key.get("Part")
                        if isinstance(part_list, list):
                            nieuwe_json_inhoud.extend(part_list)
                    ruwe_json = {"Part": nieuwe_json_inhoud}
            if basisveld == "Bet_Transactions":
                if ruwe_json.count('[{') > 1:
                    if verbose:
                        print(f"9.a.0.b [WARN] {basisveld} heeft te veel opening braces, parsen het als json")
                    # probeer hem als json in te laden
                    ruwe_json = json.loads(ruwe_json)
                    nieuwe_json_inhoud = []
                    for wrongly_named_transaction in ruwe_json["Transactions"]:
                        transaction_list = wrongly_named_transaction.get("Transaction")
                        if isinstance(transaction_list, list):
                            nieuwe_json_inhoud.extend(transaction_list)
                    ruwe_json = {"Bet_Transaction": nieuwe_json_inhoud}
                if '''[{"B''' in ruwe_json:
                    if verbose:
                        print("9.a.0.c [WARN] heeft [{Bet_Transaction: {Player_Pr")
                    # find the wrong part and replace it with the correct one
                    ruwe_json = ruwe_json.replace('[{"Bet', '{"Bet')
                    ruwe_json = ruwe_json.replace('{"Pla', '[{"Pla')
                    ruwe_json = ruwe_json.replace('}}]', '}]}')
                # if verbose:
                #     print(f"9.a.0.a Bet Parts heeft te veel opening braces, dus pak alles vanaf de tweede")
                
                
                # # vind de index van de derde {
                # # er staat namelijk standaard een foutje in de data en die kunnen we zo fiksen
                # first_brace_index = ruwe_json.find('{')
                # second_brace_index = ruwe_json.find('{', first_brace_index + 1)
                # if basis_jsonkolom == "Bet_Transactions:":
                #     third_brace_index = ruwe_json.find('{', second_brace_index + 1)
                #     ruwe_json = ruwe_json[third_brace_index:]
                #     ruwe_json = '''{"Bet_Transaction":[''' + ruwe_json
                # elif basis_jsonkolom == "Game_Transactions":
                #     third_brace_index = ruwe_json.find('{', second_brace_index + 1)
                #     ruwe_json = ruwe_json[third_brace_index:]
                #     ruwe_json = '''{"Game_Transaction":[''' + ruwe_json
                # else:
                #     ruwe_json = ruwe_json[second_brace_index:]                

                # # haal nog twee letters van het einde af
                # ruwe_json = ruwe_json[:-2]
                # iets_gewijzigd = True

        ### WOK_Complaint ###
        # Complaint: [{""Response"":[{""Response_ID"":""1"",""Response_Type"":""C1"",""Response_Description"":""1"",""Response_Datetime"":""2025-07-14T10:38:06Z""}]}]"

        if filename == "WOK_Complaint.csv" and basisveld == "Responses":
            # {""Response"":{""Response_ID"
            if ruwe_json.startswith("{") and (':{' in ruwe_json or ': {' in ruwe_json):
                if verbose:
                    print(f"9.a.1.a [WARN] {basisveld} ResonseS is geen array EN Response is geen array, dus we wrappen in []")
                ruwe_json = ruwe_json.replace(':{', ':[{')
                ruwe_json = ruwe_json.replace(': {', ': [{')
                ruwe_json = "[" + ruwe_json
                # kan eenvoudig, want bestaat alleen maar uit '}' die vervangen kunnen worden door }]
                ruwe_json = ruwe_json.replace('}', '}]')
                if verbose:
                    print('9.a.1.a result', ruwe_json)
            # [{""Response"":{""Response_ID"":""1""}}, {""Response"":{""Response_ID"":""2""}}]"
            elif ruwe_json.startswith("[") and (':{' in ruwe_json or ': {' in ruwe_json):
                if verbose:
                    print(f"9.a.1.b [WARN] {ruwe_json} Response is geen array, dus we wrappen in []")
                ruwe_json = ruwe_json.replace(':{', ':[{')
                ruwe_json = ruwe_json.replace(': {', ': [{')
                ruwe_json = ruwe_json.replace('}}', '}]}')
            # {""Response"":[{""Response_ID"":""1"", ""bla"":""1""},{""Response_ID"":""2"", ""bla"":""1""}]}"
            elif ruwe_json.startswith("{") and not (':{' in ruwe_json or ': {' in ruwe_json):
                if verbose:
                    print(f"9.a.1.b [WARN] {basisveld} ResponseS is geen array, dus we wrappen in []")
                 # {"Response":null}
                if ruwe_json == '{"Response":null}':
                    ruwe_json = None
                 # {""Response_ID"":""1"", ""bla"":""1""}
                elif ruwe_json.count("{") == 1:
                    ruwe_json = '''{"Response":[''' + ruwe_json + "]}"
                else:
                    ruwe_json = "[" + ruwe_json + "]"
            # als laatste nog steeds een } is, wrap in []
            if ruwe_json:
                if ruwe_json.endswith("}"):
                    if verbose:
                        print(f"9.a.1.c [WARN] {basisveld} ResponseS eindigt verkeerd dus we wrappen in []")
                    ruwe_json = "[" + ruwe_json + "]"

        ### WOK_GAME_SESSION ###
        # Game_Session: "{""Game_Transaction"":[{""Player_Profile_ID"":""Piet"",""Transaction_ID"":""Piet_1""}]}"

        if filename == "WOK_Game_Session.csv" and basisveld == "Game_Transactions":
            print('9.a.2 Game Session gevonden') if verbose else None
            if ruwe_json[0] == "[" and ruwe_json[-1] == "]":
                if verbose:
                    print(f"9.a.2.0 [WARN] {basisveld} is een array, dus we strippen want we hebben gezien dat er niet meerdere Game_transactions in een rij staan)")
                ruwe_json = ruwe_json[1:-1]
            elif "[" not in ruwe_json:
                if verbose:
                    print("9.a.2.1 het is alleen maar een losse dict '{...}', dus daar gaan we wat tegenaan plakken")
                ruwe_json = '{"Game_Transaction":[' + ruwe_json + "]}"
                print('9.a.2.1 ruwe_json nu:', ruwe_json) if verbose else None
                        
            # check if ruwe json is like {"Transactions": [{"Transaction": [{"Transaction_ID":
            elif ruwe_json.count('[{') > 1:
                if verbose:
                    print(f"9.a.2.c [WARN] {basisveld} heeft te veel opening braces, parsen het als json")
                # probeer hem als json in te laden
                ruwe_json = json.loads(ruwe_json)
                nieuwe_json_inhoud = []
                for wrongly_named_transaction in ruwe_json["Transactions"]:
                    transaction_list = wrongly_named_transaction.get("Transaction")
                    if isinstance(transaction_list, list):
                        nieuwe_json_inhoud.extend(transaction_list)
                ruwe_json = {"Game_Transaction": nieuwe_json_inhoud}

        ### WOK_Player_Limits ###
        # # "[{""Deposit_Request_Datetime"": ""1-1-1T1:1:1Z"", ""Deposit_Start_Datetime"": ""1-1-1T1:1:1Z"", ""Deposit_Amount"": 1, ""Deposit_Time_Window"": ""Week""}]"
        # # "[{""Login_Request_Datetime"": ""1-1-1T1:1:1Z"", ""Login_Start_Datetime"": ""1-1-1T1:1:1Z"", ""Login_Duration"": 1.1, ""Login_Time_Window"": ""Week""}]"
        # # "[{""Balance_Request_Datetime"": ""1-1-1T1:1:1Z"", ""Balance_Start_Datetime"": ""1-1-1T1:1:1Z"", ""Balance_Amount"": 1}]"
        if filename == "WOK_Player_Limits.csv":
            print(f'9.a.4 Player Limits gevonden, basisveld {basisveld}') if verbose else None
            # p fixen: {"Limits": [{"Amount": 11
            print('---------', ruwe_json[7:8], '---------') if verbose else None
            if basisveld == "Limit_Deposit" and ruwe_json[7:8] == 's': 
                print('9.a.5.a found operator p, rename all the vars') if verbose else None
                ruwe_json = ruwe_json.replace('"Amount"', '"Deposit_Amount"')
                ruwe_json = ruwe_json.replace('"Time_Window"', '"Deposit_Time_Window"')
                ruwe_json = ruwe_json.replace('"Creation_Datetime"', '"Deposit_Request_Datetime"')
                ruwe_json = ruwe_json.replace('"Start_Datetime"', '"Deposit_Start_Datetime"')
            if basisveld == "Limit_Login" and ruwe_json[7:8] == 's': 
                ruwe_json = ruwe_json.replace('"Duration"', '"Login_Duration"')
                ruwe_json = ruwe_json.replace('"Time_Window"', '"Login_Time_Window"')
                ruwe_json = ruwe_json.replace('"Creation_Datetime"', '"Login_Request_Datetime"')
                ruwe_json = ruwe_json.replace('"Start_Datetime"', '"Login_Start_Datetime"')
            if basisveld == "Limit_Balance" and ruwe_json[7:8] == 's': 
                ruwe_json = ruwe_json.replace('"Amount"', '"Balance_Amount"')
                ruwe_json = ruwe_json.replace('"Creation_Datetime"', '"Balance_Request_Datetime"')
                ruwe_json = ruwe_json.replace('"Start_Datetime"', '"Balance_Start_Datetime"')
                ruwe_json = ruwe_json.replace('{""Limits"": ', '')
                ruwe_json = ruwe_json.replace('''}}''', '''}''')
            
            # check of json {"Limit_Deposits": [{"Limit_Deposit":[{....
            if ruwe_json == '':
                continue
            elif ruwe_json.count('[{') > 1:
                variabele = basisveld + "s"
                if verbose:
                    print(f"9.a.4.a [WARN] {basisveld} heeft te veel opening braces, parsen het als json")
                # probeer hem als json in te laden
                ruwe_json = json.loads(ruwe_json)
                nieuwe_json_inhoud = []
                for limit in ruwe_json[variabele]:
                    limit_list = limit.get(basisveld)
                    if isinstance(limit_list, list):
                        nieuwe_json_inhoud.extend(limit_list)
                ruwe_json = nieuwe_json_inhoud

            elif ruwe_json[0] != '[':
                if verbose:
                    print(f"9.a.4.b {ruwe_json} is geen list")
                try:
                    # pak de lijst binnen de string "{'bla': [{'bla': ... }]}" -> "[{'bla': ... }]"
                    start = ruwe_json.index('[')
                    end = ruwe_json.rindex(']') + 1
                    ruwe_json = ruwe_json[start:end]
                except:
                    if verbose:
                        print('9.a.4.c no dict of lists')
                    # Try to see if it is just a number:
                    try: 
                        float(ruwe_json)
                        if verbose:
                            print('9.a.4.c if it is a number, make it into a string')
                        if basisveld == "Limit_Deposit":
                            ruwe_json = '''[{"Deposit_Request_Datetime": None, "Deposit_Start_Datetime": None, "Deposit_Amount":'''+ str(ruwe_json) + ''', "Deposit_Time_Window": None}]'''
                        elif basisveld == "Limit_Login":
                            ruwe_json = '''[{"Login_Request_Datetime": None, "Login_Start_Datetime": None, "Login_Duration":'''+ str(ruwe_json) + ''', "Login_Time_Window": None}]'''
                        elif basisveld == "Limit_Balance":
                            ruwe_json = '''[{"Balance_Request_Datetime": None, "Balance_Start_Datetime": None, "Balance_Amount":''' + str(ruwe_json) + '''}]'''
                    except: 
                        if ruwe_json == None:
                            pass
                        # treat it as a single object
                        # e.g. "{""Balance_Request_Datetime"": ""1-1-1T1:1:1Z"", ""Balance_Start_Datetime"": ""1-1-1T1:1:1Z"", ""Balance_Amount"": 1}"  ->  "[{'bla': ... }]"
                        else:
                            print("9.a.4.d ruwe json is a single dict") if verbose else None
                            ruwe_json = f"[{ruwe_json}]"
            
        
        ### WOK_Player_Profile ###
        # Player_Profile: "[{""Bank_Account_ID"":""b"",""Bank_Account_Datetime"":""2025-06-19T13:10:39Z"",""Bank_Account_Active"":""true""}]"
        if filename == "WOK_Player_Profile.csv" and basisveld == "Player_Profile_Bank_Account":
            print(f'9.a.5 Player Profile gevonden, basisveld {basisveld}') if verbose else None
            if ruwe_json == '':
                pass
            elif ruwe_json[0] == "{" and ruwe_json[-1] == "}":
                if verbose:
                    print(f"9.a.5 [WARN] {basisveld} is een dict, dus we wrappen in []")
                ruwe_json = "[" + ruwe_json + "]"
        
        ########## ALLES WEGGOOIEN EN GEWOON DE RUWE JSON TERUGZETTEN ##########
        json_root = ruwe_json
        


        # # Parse de JSON-basis naar een Python-object (dict/list) of sla over als hij onleesbaar is
        # json_root = _json_or_none(ruwe_json, verbose)
        # if verbose:
        #     print('10. json_root:', json_root)
        # if json_root is None and first_row:
        #     if verbose:
        #         print(f"10. [WARN] {json_root} niet parsbaar)")
        #         1/0
        #         # Basis-JSON niet parsebaar: geen verdere paden verwerken
        #         continue

        # for pad, typespecificatie in paden:
        #     # Check alle values op dit pad; bij 'clean' kan dit leiden tot converteren
        #     if verbose:
        #         print('11. check alle values op dit pad')
        #         print('11. ----pad', pad, 'typespecificatie', typespecificatie)
            
            
            
            # waarden = _extract_by_path(json_root, pad)  # resultaat wordt niet gebruikt; call blijft bewust staan
            
            
            
            # # We moeten per waarde in het platonische pad bepalen of de waarde correct is, of dat deze geupdate
            # # moet worden. Hiervoor gebruiken we de functie _doorlopen, en daar stoppen we Transformatie-functie in 
            # # om een in-place update te doen `_toepassen_op_pad`
            # def _transformatie_fn(waarde):
            #     # 'presence' is hier altijd True (we zitten in bestaand pad binnen de JSON-basis)
            #     if verbose:
            #         print('17.a.1 te checken waarde', waarde)
            #     is_ok, nieuwe_waarde, is_aangepast = _validate_and_optionality(
            #         field_path=f"[row {rownum}] {basis_jsonkolom}.{pad}",
            #         value_present=True,
            #         value=waarde,
            #         type_spec=typespecificatie,
            #         mode=mode,
            #         emit_warn=emit_warn,
            #         emit_error=emit_error,
            #         verbose=verbose
            #     )
            #     if verbose:
            #         print('17.a.2 is_ok', is_ok)
            #         print('17.a.2 nieuwe waarde', nieuwe_waarde)
            #         print('17.a.2 is_aangepast', is_aangepast)

            #     nonlocal iets_gewijzigd
            #     if mode == "clean" and is_ok and is_aangepast:
            #         if verbose:
            #             print(f'18. clean: {mode} en is_ok {is_ok} en is_aangepast {is_aangepast}, return nieuwe_waarde {nieuwe_waarde}')
            #         iets_gewijzigd = True
            #         return nieuwe_waarde
            #     if verbose and mode != "clean":
            #         print(f'18. als clean aanstond, was {nieuwe_waarde} returned, maar nu alleen {waarde}')
            #     return waarde

            # Werk de JSON-structuur bij op het gegeven pad met de transformatie-functie
            # {'Game_Transaction': [{'Player_Profile_ID': 'Piet', 'Transaction_ID': 'Piet_1'}, {'Player_Profile_ID': 'Piet', 'Transaction_ID': 'Piet_2'}]}
            
            
            
            # if verbose:
            #     print('19. json root', json_root)
        
            # json_root = _toepassen_op_pad(data=json_root, pad=pad, bewerking=_transformatie_fn, verbose=verbose)
        
        # Als er in 'clean'-modus wijzigingen zijn, schrijf de bijgewerkte JSON-structuur terug naar de outputrij
        if mode == "clean":
            if verbose:
                print('20. json_root is now', json_root)
                print('20. Oude dictionary_van_rij was ', dictionary_van_rij)
            # schrijf terug, ga naar basisveld Game_Transactions en dump de json_root
            dictionary_van_rij[basisveld] = json_root
            print('21. Nieuwe dictionary_van_rij is ', dictionary_van_rij) if verbose else None
    print() if verbose else None
    print('90. EINDRESULTAAT dictionary_van_rij:', dictionary_van_rij) if verbose else None
    return dictionary_van_rij