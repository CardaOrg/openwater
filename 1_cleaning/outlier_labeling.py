"""
VOLLEDIGE PIPELINE — LABEL 1/2/3 (ITERATIEF) OP BASIS VAN UNIEKE Player_Profile_ID
+ EXTRA: outlier_Player_Profile_Modified (dagniveau zMAD + uur-concentratie check)

Nieuwe kolommen:
- outlier_Registration_Date (0/1/2/3)  -> gebaseerd op Extraction_Date (oude final_label)
- outlier_Player_Profile_Modified (0/1) -> gebaseerd op Player_Profile_Modified (count-based zMAD + uur-check)

Nieuwe parameter:
- mode:
    "both"         -> schrijf beide kolommen (default)
    "registration" -> alleen outlier_Registration_Date
    "modified"     -> alleen outlier_Player_Profile_Modified
"""

import os
import glob
import numpy as np
import pandas as pd
from collections import defaultdict

def label_outliers(
    cleaned_dir_for_letter: str,
    verbose: bool = False,
    inplace: bool = True,
    only_label: bool = False,
    mode: str = "both"  # "both" | "registration" | "modified"
):
    import os
    import glob
    import numpy as np
    import pandas as pd
    from collections import defaultdict

    assert mode in ("both", "registration", "modified"), f"Invalid mode: {mode}"

    # ------------------------------------------------------------
    # CONFIG (no-guessing op kolommen; alles moet cleaned zijn)
    # ------------------------------------------------------------
    EXTRACTION_COL = "Extraction_Date"
    MODIFIED_COL = "Player_Profile_Modified"
    OUT_COL_MODIFIED = "outlier_Player_Profile_Modified"
    PLAYER_ID_COL = "Player_Profile_ID"
    PROFILE_PATTERNS = ["CLEAN_WOK_Player_Profile.csv", "WOK_Player_Profile.csv", "WOK_Player_Profile_*.csv"]

    # Dagselectie (zMAD op unique-per-day) — label 1/2 (registration)
    ZMAD_THRESHOLD_LABEL_1 = 70.0
    ZMAD_THRESHOLD_LABEL_2 = 20.0

    # Concentratie binnen dag (uur/minuut) — registration
    HOUR_FACTOR_LABEL_1 = 10.0
    HOUR_FACTOR_LABEL_2 = 5.0
    MIN_FACTOR_IN_HOUR = 5.0

    # Label 3 (registration)
    ZMAD_THRESHOLD_LABEL_3 = 8.0
    MIN_DAGEN_ACTIEF_LABEL3 = 0
    TOPN_LABEL3_DEBUG = 20

    # KMV sizes (registration)
    KMV_K_LABEL12 = 1024
    KMV_K_LABEL3 = 64

    # Chunkgrootte
    CHUNKSIZE = 2_000_000

    # Labels (registration)
    LABEL_NORMAAL = 0
    LABEL_BURST_GROOT = 1
    LABEL_BURST_FREAK = 2
    LABEL_DAGELIJKSE_UPDATE = 3

    # ------------------------------------------------------------
    # Modified outliers (count-based, dag + uur)
    # ------------------------------------------------------------
    ZMAD_THRESHOLD_MODIFIED_DAY = 6.0
    MIN_COUNT_MODIFIED_DAY = 100
    HOUR_FACTOR_MODIFIED = 10.0
    TOPN_MODIFIED_DEBUG = 25

    # ------------------------------------------------------------
    # kleine logging helper
    # ------------------------------------------------------------
    def vprint(msg: str = ""):
        if verbose:
            print(msg)

    print()
    print("+++++++ Starting outlier labeling +++++++")
    print(f"Labeling outliers in cleaned data at: {cleaned_dir_for_letter} | mode={mode} | inplace={inplace}")

    if only_label:
        vprint("only_label=True → skipping re-cleaning step.")

    # ------------------------------------------------------------
    # Vind inputbestanden
    # ------------------------------------------------------------
    profile_files = []
    for pat in PROFILE_PATTERNS:
        profile_files.extend(glob.glob(os.path.join(cleaned_dir_for_letter, pat)))
    profile_files = sorted(set(profile_files))
    profile_files = [f for f in profile_files if "_labelled" not in os.path.basename(f)]

    if not profile_files:
        print("No WOK_Player_Profile files found here; skipping outlier labeling.")
        return

    vprint(f"Found {len(profile_files)} WOK_Player_Profile file(s):")
    for f in profile_files[:10]:
        vprint(f"  - {os.path.basename(f)}")
    if len(profile_files) > 10:
        vprint("  ...")

    # Header check
    header = pd.read_csv(profile_files[0], nrows=0)
    missing_cols = [c for c in [EXTRACTION_COL, PLAYER_ID_COL, MODIFIED_COL] if c not in header.columns]
    if missing_cols:
        print(f"SKIP: missing required columns in {os.path.basename(profile_files[0])}: {missing_cols}")
        print("First columns:", list(header.columns)[:40])
        return

    # ------------------------------------------------------------
    # Datetime parsing (robust)
    # ------------------------------------------------------------
    def parse_datetime_series(s: pd.Series) -> pd.Series:
        if pd.api.types.is_numeric_dtype(s):
            non_na = s.dropna()
            if non_na.empty:
                out = pd.to_datetime(s, errors="coerce")
            else:
                med = float(non_na.median())
                if med > 1e11:
                    out = pd.to_datetime(s, unit="ms", errors="coerce", utc=True)
                elif med > 1e9:
                    out = pd.to_datetime(s, unit="s", errors="coerce", utc=True)
                else:
                    out = pd.to_datetime(s, errors="coerce")
        else:
            out = pd.to_datetime(s, errors="coerce", utc=True)

        if hasattr(out.dt, "tz") and out.dt.tz is not None:
            out = out.dt.tz_convert(None)
        return out

    # ------------------------------------------------------------
    # KMV sketch (registration)
    # ------------------------------------------------------------
    class KMVSchets:
        __slots__ = ("k", "waardes")

        def __init__(self, k: int):
            self.k = k
            self.waardes = np.empty(0, dtype=np.uint64)

        def update(self, hashes_u64: np.ndarray):
            if hashes_u64.size == 0:
                return
            gecombineerd = np.concatenate([self.waardes, hashes_u64])
            gecombineerd = np.unique(gecombineerd)
            if gecombineerd.size > self.k:
                idx = np.argpartition(gecombineerd, self.k - 1)[: self.k]
                self.waardes = np.sort(gecombineerd[idx])
            else:
                self.waardes = np.sort(gecombineerd)

        def schat_uniek(self) -> float:
            if self.waardes.size < self.k:
                return float(self.waardes.size)
            rk = float(self.waardes[-1]) / float(2**64)
            if rk <= 0:
                return float(self.waardes.size)
            return float((self.k - 1) / rk)

    def hash_speler_ids_naar_u64(speler_ids: pd.Series) -> np.ndarray:
        return pd.util.hash_pandas_object(speler_ids.astype("string"), index=False).to_numpy(dtype=np.uint64)

    # ------------------------------------------------------------
    # Modified: outlier days/hours (count-based)
    # ------------------------------------------------------------
    def bepaal_outlier_dagen_en_uren_player_profile_modified(zmad_threshold_day: float, min_count_day: int, hour_factor: float):
        dag_counts = defaultdict(int)
        dag_uur_counts = defaultdict(int)

        for fp in profile_files:
            vprint(f"[modified] reading {os.path.basename(fp)}")
            for chunk in pd.read_csv(fp, usecols=[MODIFIED_COL], chunksize=CHUNKSIZE, low_memory=False):
                ts = parse_datetime_series(chunk[MODIFIED_COL]).dropna()
                if ts.empty:
                    continue

                dag64 = ts.dt.floor("D").to_numpy(dtype="datetime64[ns]")
                uur64 = ts.dt.floor("h").to_numpy(dtype="datetime64[ns]")

                vc_day = pd.Series(dag64).value_counts()
                for d, c in vc_day.items():
                    dag_counts[d] += int(c)

                df_tmp = pd.DataFrame({"dag": dag64, "uur": uur64})
                vc_du = df_tmp.value_counts()
                for (d, u), c in vc_du.items():
                    dag_uur_counts[(d, u)] += int(c)

        if not dag_counts:
            return set(), set(), pd.DataFrame()

        df = pd.DataFrame({"day": list(dag_counts.keys()), "count": list(dag_counts.values())}).sort_values("day").reset_index(drop=True)

        counts = df["count"].to_numpy(dtype=float)
        med = float(np.median(counts))
        mad = float(np.median(np.abs(counts - med)))
        if mad == 0:
            mad = 1.0

        df["zmad"] = 0.6745 * (df["count"] - med) / mad

        outlier_df = df[(df["count"] >= min_count_day) & (df["zmad"] > zmad_threshold_day)].copy()
        outlier_days = set(outlier_df["day"].to_numpy(dtype="datetime64[ns]"))

        outlier_hours = set()
        if outlier_days:
            for d in outlier_days:
                d_count = float(dag_counts.get(d, 0))
                if d_count <= 0:
                    continue
                avg_per_hour = d_count / 24.0
                for (d2, u), c in dag_uur_counts.items():
                    if d2 == d and float(c) > hour_factor * avg_per_hour:
                        outlier_hours.add((d2, u))

        vprint(f"[modified] baseline day-counts: median={med:,.1f} MAD={mad:,.1f}")
        vprint(f"[modified] outlier days: {len(outlier_days)} (zMAD>{zmad_threshold_day}, min_count>={min_count_day})")
        vprint(f"[modified] outlier (day,hour): {len(outlier_hours)} (hour_factor>{hour_factor}x day-hour-avg)")
        if verbose and not outlier_df.empty:
            vprint(f"[modified] top {TOPN_MODIFIED_DEBUG} outlier days:")
            for _, r in outlier_df.sort_values("zmad", ascending=False).head(TOPN_MODIFIED_DEBUG).iterrows():
                vprint(f"  - {pd.Timestamp(r['day']).strftime('%Y-%m-%d')}: count={int(r['count']):,} zMAD={r['zmad']:.2f}")

        return outlier_days, outlier_hours, df

    # ------------------------------------------------------------
    # Registration: sketches + bins (existing)
    # ------------------------------------------------------------
    def bouw_kmv_schetsen_maand_dag_uur(k: int):
        schets_maand = defaultdict(lambda: KMVSchets(k))
        schets_dag = defaultdict(lambda: KMVSchets(k))
        schets_dag_uur = defaultdict(lambda: KMVSchets(k))

        for fp in profile_files:
            vprint(f"[label12] reading {os.path.basename(fp)}")
            for chunk in pd.read_csv(fp, usecols=[EXTRACTION_COL, PLAYER_ID_COL], chunksize=CHUNKSIZE, low_memory=False):
                ts = parse_datetime_series(chunk[EXTRACTION_COL])
                pid = chunk[PLAYER_ID_COL].astype("string")
                mask = ts.notna() & pid.notna()
                if not mask.any():
                    continue
                ts = ts[mask]
                pid = pid[mask]
                hashes = hash_speler_ids_naar_u64(pid)

                maand64 = ts.dt.to_period("M").dt.to_timestamp().to_numpy(dtype="datetime64[ns]")
                dag64 = ts.dt.floor("D").to_numpy(dtype="datetime64[ns]")
                uur64 = ts.dt.floor("h").to_numpy(dtype="datetime64[ns]")

                df_tmp = pd.DataFrame({"maand": maand64, "dag": dag64, "uur": uur64, "hash": hashes})

                for maand_key, groep in df_tmp.groupby("maand")["hash"]:
                    schets_maand[maand_key].update(groep.to_numpy(dtype=np.uint64))
                for dag_key, groep in df_tmp.groupby("dag")["hash"]:
                    schets_dag[dag_key].update(groep.to_numpy(dtype=np.uint64))
                for (dag_key, uur_key), groep in df_tmp.groupby(["dag", "uur"])["hash"]:
                    schets_dag_uur[(dag_key, uur_key)].update(groep.to_numpy(dtype=np.uint64))

        return schets_maand, schets_dag, schets_dag_uur

    def bouw_kmv_schetsen_minuten_voor_doel_uren(doel_dag_uur: set, k: int):
        schets_dag_uur_minuut = defaultdict(lambda: KMVSchets(k))
        doelen = set(doel_dag_uur)

        for fp in profile_files:
            vprint(f"[label12] minute-scan reading {os.path.basename(fp)}")
            for chunk in pd.read_csv(fp, usecols=[EXTRACTION_COL, PLAYER_ID_COL], chunksize=CHUNKSIZE, low_memory=False):
                ts = parse_datetime_series(chunk[EXTRACTION_COL])
                pid = chunk[PLAYER_ID_COL].astype("string")
                mask = ts.notna() & pid.notna()
                if not mask.any():
                    continue
                ts = ts[mask]
                pid = pid[mask]
                hashes = hash_speler_ids_naar_u64(pid)

                dag64 = ts.dt.floor("D").to_numpy(dtype="datetime64[ns]")
                uur64 = ts.dt.floor("h").to_numpy(dtype="datetime64[ns]")

                keep = np.fromiter(((d, u) in doelen for d, u in zip(dag64, uur64)), dtype=bool, count=len(dag64))
                if not keep.any():
                    continue

                ts2 = ts[keep]
                hashes2 = hashes[keep]
                dag2 = dag64[keep]
                uur2 = uur64[keep]
                minuut64 = ts2.dt.floor("min").to_numpy(dtype="datetime64[ns]")

                df_tmp = pd.DataFrame({"dag": dag2, "uur": uur2, "minuut": minuut64, "hash": hashes2})
                for (dag_key, uur_key, minuut_key), groep in df_tmp.groupby(["dag", "uur", "minuut"])["hash"]:
                    schets_dag_uur_minuut[(dag_key, uur_key, minuut_key)].update(groep.to_numpy(dtype=np.uint64))

        return schets_dag_uur_minuut

    def bepaal_bins_label12(schets_maand, schets_dag, schets_dag_uur, zmad_threshold: float, factor_uur_vs_daguur: float, label_waarde: int, max_zmad: float | None = None):
        schatting_maand = {m: s.schat_uniek() for m, s in schets_maand.items()}
        if not schatting_maand:
            return {"dagen": set(), "uren": set(), "minuten": set()}

        schatting_dag = {d: s.schat_uniek() for d, s in schets_dag.items()}
        dag_waarden = np.array(list(schatting_dag.values()), dtype=float)
        mediaan_dag = float(np.median(dag_waarden))
        mad_dag = float(np.median(np.abs(dag_waarden - mediaan_dag)))
        if mad_dag == 0:
            mad_dag = 1.0

        def zmad(est: float) -> float:
            return 0.6745 * (est - mediaan_dag) / mad_dag

        vprint(f"[label{label_waarde}] day baseline: median={mediaan_dag:,.1f} MAD={mad_dag:,.1f}")
        vprint(f"[label{label_waarde}] zMAD threshold: > {zmad_threshold}" + ("" if max_zmad is None else f" and <= {max_zmad}"))

        deviante_dagen = []
        for d, est in schatting_dag.items():
            score = zmad(est)
            if score > zmad_threshold and (max_zmad is None or score <= max_zmad):
                deviante_dagen.append(d)

        te_labelen_dagen = set()
        te_labelen_uren = set()
        deviante_uren_voor_minuten = []

        for dag_key in deviante_dagen:
            dag_uniek = schatting_dag[dag_key]
            gemiddelde_uniek_per_uur_in_dag = dag_uniek / 24.0

            uren_in_dag = [(uur_key, schets_dag_uur[(dag_key, uur_key)].schat_uniek())
                           for (d, uur_key) in schets_dag_uur.keys() if d == dag_key]

            if not uren_in_dag:
                te_labelen_dagen.add(dag_key)
                continue

            deviante_uren = [(uur_key, est) for (uur_key, est) in uren_in_dag
                             if est > factor_uur_vs_daguur * gemiddelde_uniek_per_uur_in_dag]

            if len(deviante_uren) == 0:
                te_labelen_dagen.add(dag_key)
            else:
                for (uur_key, _est) in deviante_uren:
                    deviante_uren_voor_minuten.append((dag_key, uur_key))

        te_labelen_minuten = set()

        if deviante_uren_voor_minuten:
            schets_minuten = bouw_kmv_schetsen_minuten_voor_doel_uren(set(deviante_uren_voor_minuten), KMV_K_LABEL12)

            for (dag_key, uur_key) in deviante_uren_voor_minuten:
                uur_uniek = schets_dag_uur[(dag_key, uur_key)].schat_uniek()
                gemiddelde_uniek_per_minuut_in_uur = uur_uniek / 60.0

                minuten_in_uur = [(minuut_key, schets_minuten[(dag_key, uur_key, minuut_key)].schat_uniek())
                                  for (d, u, minuut_key) in schets_minuten.keys() if d == dag_key and u == uur_key]

                if not minuten_in_uur:
                    te_labelen_uren.add((dag_key, uur_key))
                    continue

                enige_minuut_gelabeld = False
                for (minuut_key, est) in minuten_in_uur:
                    if est > MIN_FACTOR_IN_HOUR * gemiddelde_uniek_per_minuut_in_uur:
                        te_labelen_minuten.add(np.datetime64(pd.Timestamp(minuut_key), "ns"))
                        enige_minuut_gelabeld = True

                if not enige_minuut_gelabeld:
                    te_labelen_uren.add((dag_key, uur_key))

        return {"dagen": te_labelen_dagen, "uren": te_labelen_uren, "minuten": te_labelen_minuten}

    def bepaal_uitgesloten_dagen_op_basis_van_label12_bins(bins_label1: dict, bins_label2: dict) -> set:
        uitgesloten_dagen = set()
        uitgesloten_dagen.update(bins_label1.get("dagen", set()))
        uitgesloten_dagen.update(bins_label2.get("dagen", set()))
        for (dag_key, _uur_key) in bins_label1.get("uren", set()):
            uitgesloten_dagen.add(dag_key)
        for (dag_key, _uur_key) in bins_label2.get("uren", set()):
            uitgesloten_dagen.add(dag_key)
        for minuut_key in bins_label1.get("minuten", set()):
            dag_key = np.datetime64(pd.Timestamp(minuut_key).floor("D"), "ns")
            uitgesloten_dagen.add(dag_key)
        for minuut_key in bins_label2.get("minuten", set()):
            dag_key = np.datetime64(pd.Timestamp(minuut_key).floor("D"), "ns")
            uitgesloten_dagen.add(dag_key)
        return uitgesloten_dagen

    # ------------------------------------------------------------
    # LABEL 3 (registration) — unchanged logic, but only used in relevant modes
    # ------------------------------------------------------------
    def detecteer_label3_outlier_minuten_van_dag_in_maand(maand_begin: np.datetime64, maand_einde_exclusief: np.datetime64, set_schone_dagen: set):
        schets_per_dag_en_minuut = defaultdict(lambda: KMVSchets(KMV_K_LABEL3))

        for fp in profile_files:
            vprint(f"[label3] reading {os.path.basename(fp)}")
            for chunk in pd.read_csv(fp, usecols=[EXTRACTION_COL, PLAYER_ID_COL], chunksize=CHUNKSIZE, low_memory=False):
                ts = parse_datetime_series(chunk[EXTRACTION_COL])
                pid = chunk[PLAYER_ID_COL].astype("string")
                mask = ts.notna() & pid.notna()
                if not mask.any():
                    continue
                ts = ts[mask]
                pid = pid[mask]

                ts64 = ts.to_numpy(dtype="datetime64[ns]")
                in_maand = (ts64 >= maand_begin) & (ts64 < maand_einde_exclusief)
                if not in_maand.any():
                    continue

                ts = ts[in_maand]
                pid = pid[in_maand]

                dag64 = ts.dt.floor("D").to_numpy(dtype="datetime64[ns]")
                is_schoon = np.isin(dag64, list(set_schone_dagen))
                if not is_schoon.any():
                    continue

                ts = ts[is_schoon]
                pid = pid[is_schoon]
                dag64 = dag64[is_schoon]

                hashes = hash_speler_ids_naar_u64(pid)
                minuut_van_dag = (ts.dt.hour.to_numpy() * 60 + ts.dt.minute.to_numpy()).astype(np.int16)

                df_tmp = pd.DataFrame({"dag": dag64, "minuut_van_dag": minuut_van_dag, "hash": hashes})
                for (dag_key, minuut_key), groep in df_tmp.groupby(["dag", "minuut_van_dag"])["hash"]:
                    schets_per_dag_en_minuut[(dag_key, int(minuut_key))].update(groep.to_numpy(dtype=np.uint64))

        waarden_per_minuut = defaultdict(list)
        dagen_actief_per_minuut = defaultdict(int)

        for (dag_key, minuut_key), schets in schets_per_dag_en_minuut.items():
            schatting = schets.schat_uniek()
            if schatting > 0:
                waarden_per_minuut[minuut_key].append(schatting)
                dagen_actief_per_minuut[minuut_key] += 1

        if not waarden_per_minuut:
            return []

        mediaan_per_minuut = {m: float(np.median(vals)) for m, vals in waarden_per_minuut.items()}
        if not mediaan_per_minuut:
            return []

        minute_keys = np.array(list(mediaan_per_minuut.keys()), dtype=int)
        minute_medians = np.array([mediaan_per_minuut[k] for k in minute_keys], dtype=float)

        median_all = float(np.median(minute_medians))
        mad_all = float(np.median(np.abs(minute_medians - median_all)))
        if mad_all == 0:
            mad_all = 1.0

        def zmad_minute(x: float) -> float:
            return 0.6745 * (x - median_all) / mad_all

        outlier_minuten_van_dag = []
        for k in mediaan_per_minuut:
            med = float(mediaan_per_minuut[k])
            days_active = int(dagen_actief_per_minuut.get(k, 0))
            z = float(zmad_minute(med))
            if days_active < MIN_DAGEN_ACTIEF_LABEL3:
                continue
            if z <= ZMAD_THRESHOLD_LABEL_3:
                continue
            outlier_minuten_van_dag.append(int(k))

        return sorted(outlier_minuten_van_dag)

    def bereken_label3_minuten_timestamps_iteratief(maand_starts: list, uitgesloten_dagen_label12: set):
        label3_minuten_timestamps = set()
        for maand_begin in sorted(maand_starts):
            maand_begin_ns = np.datetime64(maand_begin, "ns")
            maand_einde_ns = np.datetime64((pd.Timestamp(maand_begin_ns) + pd.offsets.MonthBegin(1)).to_datetime64(), "ns")

            alle_dagen_in_maand = pd.date_range(
                start=pd.Timestamp(maand_begin_ns),
                end=pd.Timestamp(maand_einde_ns) - pd.Timedelta(days=1),
                freq="D"
            )
            set_dagen_in_maand = set(np.datetime64(d.floor("D"), "ns") for d in alle_dagen_in_maand)
            set_schone_dagen = set_dagen_in_maand.difference(uitgesloten_dagen_label12)

            outlier_minuten_van_dag = detecteer_label3_outlier_minuten_van_dag_in_maand(
                maand_begin=maand_begin_ns,
                maand_einde_exclusief=maand_einde_ns,
                set_schone_dagen=set_schone_dagen
            )

            for dag in alle_dagen_in_maand:
                for minuut_key in outlier_minuten_van_dag:
                    hh = minuut_key // 60
                    mm = minuut_key % 60
                    minute_ts = pd.Timestamp(dag).replace(hour=int(hh), minute=int(mm), second=0)
                    label3_minuten_timestamps.add(np.datetime64(minute_ts, "ns"))

        return label3_minuten_timestamps

    # ------------------------------------------------------------
    # WRITE: add selected columns depending on mode, and output
    # ------------------------------------------------------------
    def schrijf_labelled_output(bins_label1: dict, bins_label2: dict, label3_minuten_timestamps: set,
                               outlier_days_modified: set, outlier_day_hours_modified: set, mode: str):
        totaal_rijen = 0
        aantal_label0 = 0
        aantal_label1 = 0
        aantal_label2 = 0
        aantal_label3 = 0

        lijst_label3 = list(label3_minuten_timestamps) if label3_minuten_timestamps else []
        lijst_label1_dagen = list(bins_label1["dagen"]) if bins_label1["dagen"] else []
        lijst_label1_minuten = list(bins_label1["minuten"]) if bins_label1["minuten"] else []
        set_label1_uren = bins_label1["uren"]

        lijst_label2_dagen = list(bins_label2["dagen"]) if bins_label2["dagen"] else []
        lijst_label2_minuten = list(bins_label2["minuten"]) if bins_label2["minuten"] else []
        set_label2_uren = bins_label2["uren"]

        outlier_days_modified_list = list(outlier_days_modified) if outlier_days_modified else []
        outlier_day_hours_modified_set = outlier_day_hours_modified if outlier_day_hours_modified else set()

        for fp in profile_files:
            input_path = fp

            if inplace:
                output_path = input_path
            else:
                archive_dir = os.path.join(cleaned_dir_for_letter, "archive")
                os.makedirs(archive_dir, exist_ok=True)
                base = os.path.basename(fp)
                prefix = "TEST_label"
                if mode == "modified":
                    prefix = "TEST_modified"
                elif mode == "registration":
                    prefix = "TEST_registration"
                output_path = os.path.join(archive_dir, f"{prefix}_{base}")

            tmp_path = output_path + ".tmp"
            print(f"Writing labelled file: {output_path} (inplace={inplace})")

            first = True
            for chunk in pd.read_csv(input_path, chunksize=CHUNKSIZE, low_memory=False):

                # ---------------------------
                # registration label (0/1/2/3)
                # ---------------------------
                if mode in ("both", "registration"):
                    ts = parse_datetime_series(chunk[EXTRACTION_COL])
                    outlier_Registration_Date = np.zeros(len(chunk), dtype=np.int8)

                    dag64 = ts.dt.floor("D").to_numpy(dtype="datetime64[ns]")
                    uur64 = ts.dt.floor("h").to_numpy(dtype="datetime64[ns]")
                    minuut64 = ts.dt.floor("min").to_numpy(dtype="datetime64[ns]")

                    if lijst_label3:
                        mask3 = np.isin(minuut64, lijst_label3)
                        outlier_Registration_Date[mask3] = LABEL_DAGELIJKSE_UPDATE

                    if lijst_label1_dagen:
                        outlier_Registration_Date[np.isin(dag64, lijst_label1_dagen)] = LABEL_BURST_GROOT
                    if set_label1_uren:
                        mask1_uur = np.fromiter(((d, u) in set_label1_uren for d, u in zip(dag64, uur64)),
                                                dtype=bool, count=len(dag64))
                        outlier_Registration_Date[mask1_uur] = LABEL_BURST_GROOT
                    if lijst_label1_minuten:
                        outlier_Registration_Date[np.isin(minuut64, lijst_label1_minuten)] = LABEL_BURST_GROOT

                    if lijst_label2_dagen:
                        outlier_Registration_Date[np.isin(dag64, lijst_label2_dagen)] = LABEL_BURST_FREAK
                    if set_label2_uren:
                        mask2_uur = np.fromiter(((d, u) in set_label2_uren for d, u in zip(dag64, uur64)),
                                                dtype=bool, count=len(dag64))
                        outlier_Registration_Date[mask2_uur] = LABEL_BURST_FREAK
                    if lijst_label2_minuten:
                        outlier_Registration_Date[np.isin(minuut64, lijst_label2_minuten)] = LABEL_BURST_FREAK

                    chunk["outlier_Registration_Date"] = outlier_Registration_Date

                    totaal_rijen += len(outlier_Registration_Date)
                    aantal_label0 += int((outlier_Registration_Date == 0).sum())
                    aantal_label1 += int((outlier_Registration_Date == 1).sum())
                    aantal_label2 += int((outlier_Registration_Date == 2).sum())
                    aantal_label3 += int((outlier_Registration_Date == 3).sum())

                # ---------------------------
                # modified outlier (0/1)
                # ---------------------------
                if mode in ("both", "modified"):
                    mod_ts = parse_datetime_series(chunk[MODIFIED_COL])
                    mod_day64 = mod_ts.dt.floor("D").to_numpy(dtype="datetime64[ns]")
                    mod_hour64 = mod_ts.dt.floor("h").to_numpy(dtype="datetime64[ns]")

                    out_mod = np.zeros(len(chunk), dtype=np.int8)
                    if outlier_days_modified_list:
                        out_mod[np.isin(mod_day64, outlier_days_modified_list)] = 1
                    if outlier_day_hours_modified_set:
                        mask_hour = np.fromiter(((d, h) in outlier_day_hours_modified_set for d, h in zip(mod_day64, mod_hour64)),
                                                dtype=bool, count=len(out_mod))
                        out_mod[mask_hour] = 1

                    chunk[OUT_COL_MODIFIED] = out_mod

                chunk.to_csv(tmp_path, index=False, mode="w" if first else "a", header=first)
                first = False

            os.replace(tmp_path, output_path)

        if mode in ("both", "registration"):
            print("\n" + "=" * 80)
            print("LABEL SUMMARY (outlier_Registration_Date)")
            print("=" * 80)
            if totaal_rijen:
                print(f"Total rows written: {totaal_rijen:,}")
                print(f"label0 (normal): {aantal_label0:,} ({aantal_label0/totaal_rijen*100:.2f}%)")
                print(f"label1 (big burst): {aantal_label1:,} ({aantal_label1/totaal_rijen*100:.2f}%)")
                print(f"label2 (freak burst): {aantal_label2:,} ({aantal_label2/totaal_rijen*100:.2f}%)")
                print(f"label3 (daily update): {aantal_label3:,} ({aantal_label3/totaal_rijen*100:.2f}%)")
                print("Priority applied: 2 > 1 > 3 > 0")
            else:
                print("No rows were written?")

    # ============================================================
    # RUN
    # ============================================================

    outlier_days_modified = set()
    outlier_day_hours_modified = set()
    modified_day_debug_df = None

    bins_label1 = {"dagen": set(), "uren": set(), "minuten": set()}
    bins_label2 = {"dagen": set(), "uren": set(), "minuten": set()}
    label3_minuten_timestamps = set()

    # 0) Modified (only if needed)
    if mode in ("both", "modified"):
        vprint()
        vprint("Computing outlier days/hours for Player_Profile_Modified (count-based, zMAD + hour concentration)...")
        outlier_days_modified, outlier_day_hours_modified, modified_day_debug_df = (
            bepaal_outlier_dagen_en_uren_player_profile_modified(
                zmad_threshold_day=ZMAD_THRESHOLD_MODIFIED_DAY,
                min_count_day=MIN_COUNT_MODIFIED_DAY,
                hour_factor=HOUR_FACTOR_MODIFIED,
            )
        )

    # 1) Registration (only if needed)
    if mode in ("both", "registration"):
        vprint("Building KMV sketches (month/day/hour) for label 1/2...")
        schets_maand, schets_dag, schets_dag_uur = bouw_kmv_schetsen_maand_dag_uur(KMV_K_LABEL12)
        maand_starts = list(schets_maand.keys())

        vprint()
        vprint("Computing label 1 bins (big bursts)...")
        bins_label1 = bepaal_bins_label12(
            schets_maand=schets_maand,
            schets_dag=schets_dag,
            schets_dag_uur=schets_dag_uur,
            zmad_threshold=ZMAD_THRESHOLD_LABEL_1,
            factor_uur_vs_daguur=HOUR_FACTOR_LABEL_1,
            label_waarde=LABEL_BURST_GROOT,
            max_zmad=None
        )

        vprint()
        vprint("Computing label 2 bins (freak bursts)...")
        bins_label2 = bepaal_bins_label12(
            schets_maand=schets_maand,
            schets_dag=schets_dag,
            schets_dag_uur=schets_dag_uur,
            zmad_threshold=ZMAD_THRESHOLD_LABEL_2,
            factor_uur_vs_daguur=HOUR_FACTOR_LABEL_2,
            label_waarde=LABEL_BURST_FREAK,
            max_zmad=ZMAD_THRESHOLD_LABEL_1
        )

        uitgesloten_dagen_label12 = bepaal_uitgesloten_dagen_op_basis_van_label12_bins(bins_label1, bins_label2)
        vprint(f"Excluded days for label3 computation (label1/2 projection): {len(uitgesloten_dagen_label12)}")

        vprint()
        vprint("Computing label 3 (daily updates) iteratively on clean days...")
        label3_minuten_timestamps = bereken_label3_minuten_timestamps_iteratief(
            maand_starts=maand_starts,
            uitgesloten_dagen_label12=uitgesloten_dagen_label12
        )
        vprint(f"Label3 minute timestamps selected: {len(label3_minuten_timestamps):,}")

    # 3) write
    if inplace:
        vprint(f"Writing labelled output files (mode={mode})...")
    else:
        vprint(f"inplace=False → write to /archive (mode={mode}).")

    schrijf_labelled_output(
        bins_label1=bins_label1,
        bins_label2=bins_label2,
        label3_minuten_timestamps=label3_minuten_timestamps,
        outlier_days_modified=outlier_days_modified,
        outlier_day_hours_modified=outlier_day_hours_modified,
        mode=mode
    )

    vprint("+++++++ Finished outlier labeling +++++++")