import json
import math
import os
import sqlite3
import statistics
import time
from pathlib import Path

import requests


TABLES = {
    "insane": "https://darksabun.club/table/archive/insane1/header.json",
    "stella": "https://stellabms.xyz/st/header.json",
    "satellite": "https://stellabms.xyz/sl/header.json",
}

IR_DATA_URL = "https://raw.githubusercontent.com/c-ikeda123/bms-nexus/refs/heads/main/static/ir_data.json"


def safe_float(value, default=99.0):
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def map_beatoraja_clear(clear_value):
    if clear_value >= 8:
        return 4
    if clear_value >= 6:
        return 3
    if clear_value == 5:
        return 2
    if clear_value >= 2:
        return 1
    if clear_value == 1:
        return 0
    return -1


def build_user_lamps_from_dataframes(df_score, df_songdata=None):
    user_lamps = {}

    if df_score is None or "sha256" not in df_score.columns or "clear" not in df_score.columns:
        return user_lamps

    for _, row in df_score.iterrows():
        sha256 = row.get("sha256")
        if not sha256:
            continue
        lamp = map_beatoraja_clear(int(row.get("clear", 0)))
        if lamp != -1:
            key = str(sha256).lower()
            user_lamps[key] = max(user_lamps.get(key, -1), lamp)

    if df_songdata is not None and {"sha256", "md5"}.issubset(df_songdata.columns):
        md5_by_sha256 = {}
        for _, row in df_songdata.iterrows():
            sha256 = row.get("sha256")
            md5 = row.get("md5")
            if sha256 and md5:
                md5_by_sha256[str(sha256).lower()] = str(md5).lower()

        for sha256, lamp in list(user_lamps.items()):
            md5 = md5_by_sha256.get(sha256)
            if md5:
                user_lamps[md5] = max(user_lamps.get(md5, -1), lamp)

    return user_lamps


def parse_score_db(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    user_lamps = {}
    db_type = "Unknown"

    try:
        cursor.execute("SELECT sha256, clear FROM score")
        rows = cursor.fetchall()
        db_type = "beatoraja"
        for row in rows:
            lamp = map_beatoraja_clear(row["clear"])
            if lamp != -1:
                user_lamps[row["sha256"].lower()] = lamp

        songdata_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(db_path))), "songdata.db"
        )
        if os.path.exists(songdata_path):
            try:
                conn.execute(f"ATTACH DATABASE '{songdata_path}' AS songdb")
                query = "SELECT s.md5, sc.clear FROM songdb.song s JOIN score sc ON s.sha256 = sc.sha256"
                cursor.execute(query)
                for row in cursor.fetchall():
                    if row["md5"]:
                        lamp = map_beatoraja_clear(row["clear"])
                        if lamp != -1:
                            key = row["md5"].lower()
                            user_lamps[key] = max(user_lamps.get(key, -1), lamp)
                conn.execute("DETACH DATABASE songdb")
            except Exception:
                pass
    except Exception:
        pass

    conn.close()
    return user_lamps, db_type


class NexusCalculator:
    def __init__(self, ir_data_path=None, table_urls=None, cache_dir=".cache", ir_data_url=IR_DATA_URL):
        self.ir_data_path = ir_data_path
        self.ir_data_url = ir_data_url
        self.table_urls = table_urls or TABLES
        self.cache_dir = Path(cache_dir)
        self.table_cache_path = self.cache_dir / "bms_nexus_tables.json"
        self.skill_cache_path = self.cache_dir / "bms_nexus_skill.json"
        self.table_data_cache = {}
        self.ir_data_cache = None
        self.ir_data_remote_checked = False
        self.skill_chart_index = None

    def fetch_table_data(self):
        if self.table_data_cache:
            return self.table_data_cache

        cached = self.load_table_data_cache()
        if cached:
            self.table_data_cache = cached
            return self.table_data_cache

        for name, url in self.table_urls.items():
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            header = response.json()
            data_url = header.get("data_url")
            if not data_url:
                continue
            if not data_url.startswith("http"):
                base_url = url.rsplit("/", 1)[0]
                data_url = f"{base_url}/{data_url}"

            data_response = requests.get(data_url, timeout=30)
            data_response.raise_for_status()
            self.table_data_cache[name] = {
                "header": header,
                "charts": data_response.json(),
            }

        self.save_table_data_cache(self.table_data_cache)
        return self.table_data_cache

    def load_table_data_cache(self):
        if not self.table_cache_path.exists():
            return {}
        try:
            with open(self.table_cache_path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            return payload.get("tables", {})
        except Exception:
            return {}

    def save_table_data_cache(self, tables):
        try:
            self.cache_dir.mkdir(exist_ok=True)
            payload = {
                "created_at": int(time.time()),
                "tables": tables,
            }
            with open(self.table_cache_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False)
        except Exception:
            pass

    def load_cached_user_skill(self):
        if not self.skill_cache_path.exists():
            return None
        try:
            with open(self.skill_cache_path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            value = payload.get("user_skill")
            return float(value) if value is not None else None
        except Exception:
            return None

    def save_cached_user_skill(self, user_skill):
        try:
            self.cache_dir.mkdir(exist_ok=True)
            payload = {
                "created_at": int(time.time()),
                "user_skill": float(user_skill),
            }
            with open(self.skill_cache_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False)
        except Exception:
            pass

    def find_default_ir_data_path(self):
        candidates = []
        if self.ir_data_path:
            candidates.append(Path(self.ir_data_path))
        env_path = os.environ.get("BMS_NEXUS_IR_DATA")
        if env_path:
            candidates.append(Path(env_path))

        base_dir = Path(__file__).resolve().parent
        candidates.extend(
            [
                base_dir / "static" / "ir_data.json",
            ]
        )

        for path in candidates:
            if path.exists():
                return path
        return None

    def default_ir_data_path(self):
        if self.ir_data_path:
            return Path(self.ir_data_path)
        return Path(__file__).resolve().parent / "static" / "ir_data.json"

    def update_ir_data_from_remote_once(self):
        if self.ir_data_remote_checked:
            return False
        self.ir_data_remote_checked = True
        return self.update_ir_data_from_remote()

    def update_ir_data_from_remote(self):
        if not self.ir_data_url:
            return False

        response = requests.get(self.ir_data_url, timeout=30)
        response.raise_for_status()
        remote_data = response.json()

        target_path = self.default_ir_data_path()
        target_path.parent.mkdir(parents=True, exist_ok=True)

        current_text = None
        if target_path.exists():
            try:
                current_text = target_path.read_text(encoding="utf-8")
            except Exception:
                current_text = None

        remote_text = json.dumps(remote_data, ensure_ascii=False, indent=4) + "\n"
        if current_text == remote_text:
            self.ir_data_cache = remote_data
            return False

        with open(target_path, "w", encoding="utf-8") as f:
            f.write(remote_text)
        self.ir_data_cache = remote_data
        self.skill_chart_index = None
        return True

    def fetch_ir_data(self):
        if self.ir_data_cache is not None:
            return self.ir_data_cache

        local_path = self.find_default_ir_data_path()
        if local_path is not None:
            with open(local_path, "r", encoding="utf-8") as f:
                self.ir_data_cache = json.load(f)
            return self.ir_data_cache

        url = os.environ.get("BMS_NEXUS_IR_DATA_URL")
        if not url:
            raise FileNotFoundError(
                "ir_data.json was not found. Set BMS_NEXUS_IR_DATA or place static/ir_data.json in oraja_helper."
            )
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        self.ir_data_cache = response.json()
        return self.ir_data_cache

    def calculate_from_lamps(self, user_lamps):
        tables = self.fetch_table_data()
        ir_data = self.fetch_ir_data()
        result = calculate_recommendations(user_lamps, ir_data, tables)
        return format_result(result)

    def calculate_user_skill_from_lamps(self, user_lamps):
        chart_index = self.get_skill_chart_index()
        played_by_chart_id = {}
        for key, lamp in user_lamps.items():
            params = chart_index.get(str(key).lower())
            if not params:
                continue
            chart_id = params["chart_id"]
            if chart_id not in played_by_chart_id:
                played_by_chart_id[chart_id] = dict(params)
                played_by_chart_id[chart_id]["lamp"] = lamp
            else:
                played_by_chart_id[chart_id]["lamp"] = max(
                    played_by_chart_id[chart_id]["lamp"], lamp
                )

        played_charts = []
        for params in played_by_chart_id.values():
            played_charts.append(
                {
                    "lamp": params["lamp"],
                    "b_easy": params["b_easy"],
                    "b_normal": params["b_normal"],
                    "b_hard": params["b_hard"],
                    "b_fc": params["b_fc"],
                    "a": params["a"],
                }
            )
        return estimate_user_skill(played_charts)

    def get_skill_chart_index(self):
        if self.skill_chart_index is not None:
            return self.skill_chart_index

        tables = self.fetch_table_data()
        ir_data = self.fetch_ir_data()
        folder_medians = build_folder_medians(ir_data, tables)
        chart_index = {}

        for table_name, table_data in tables.items():
            for chart in table_data["charts"]:
                level_str = str(chart.get("level", "0"))
                if "?" in level_str:
                    continue

                md5 = chart.get("md5", "").lower()
                sha256 = chart.get("sha256", "").lower()
                level = safe_float(level_str)
                base_star = get_base_star(table_name, level)
                chart_stats = ir_data.get(md5, ir_data.get(sha256, {}))
                rates = get_rates(chart_stats)
                chart_id = f"{table_name}:{level_str}:{md5 or sha256}"
                params = {
                    "chart_id": chart_id,
                    "has_actual_difficulty": all(
                        chart_stats.get(key, 99.0) < 99.0
                        for key in ("diff_easy", "diff_normal", "diff_hard", "diff_fc")
                    ),
                    "b_easy": get_target_difficulty(
                        chart_stats, folder_medians, table_name, level_str, base_star, "diff_easy", -1.0, rates["easy"], "e"
                    ),
                    "b_normal": get_target_difficulty(
                        chart_stats, folder_medians, table_name, level_str, base_star, "diff_normal", 0.0, rates["normal"], "n"
                    ),
                    "b_hard": get_target_difficulty(
                        chart_stats, folder_medians, table_name, level_str, base_star, "diff_hard", 2.0, rates["hard"], "h"
                    ),
                    "b_fc": get_target_difficulty(
                        chart_stats, folder_medians, table_name, level_str, base_star, "diff_fc", 13.0, rates["fc"], "f"
                    ),
                    "a": get_discrimination(chart_stats, folder_medians, table_name, level_str),
                }
                if md5:
                    chart_index[md5] = params
                if sha256:
                    chart_index[sha256] = params

        self.skill_chart_index = chart_index
        return self.skill_chart_index

    def get_chart_skill_difficulties(self, *hashes):
        chart_index = self.get_skill_chart_index()
        return self.get_cached_chart_skill_difficulties(*hashes, chart_index=chart_index)

    def get_cached_chart_skill_difficulties(self, *hashes, chart_index=None):
        chart_index = chart_index if chart_index is not None else self.skill_chart_index
        if not chart_index:
            return None
        for hash_value in hashes:
            key = str(hash_value or "").lower()
            if not key:
                continue
            params = chart_index.get(key)
            if params and params.get("has_actual_difficulty"):
                return {
                    "easy": params["b_easy"],
                    "normal": params["b_normal"],
                    "hard": params["b_hard"],
                    "fc": params["b_fc"],
                }
        return None

    def get_cached_chart_nexus_info(self, user_skill, *hashes):
        chart_index = self.skill_chart_index
        if not chart_index or user_skill is None:
            return None
        for hash_value in hashes:
            key = str(hash_value or "").lower()
            if not key:
                continue
            params = chart_index.get(key)
            if params and params.get("has_actual_difficulty"):
                return {
                    "easy": params["b_easy"],
                    "normal": params["b_normal"],
                    "hard": params["b_hard"],
                    "fc": params["b_fc"],
                    "easyRate": probability(user_skill, params["b_easy"], params["a"]) * 100.0,
                    "normalRate": probability(user_skill, params["b_normal"], params["a"]) * 100.0,
                    "hardRate": probability(user_skill, params["b_hard"], params["a"]) * 100.0,
                    "fcRate": probability(user_skill, params["b_fc"], params["a"]) * 100.0,
                }
        return None

    def calculate_from_database_accessor(self, database_accessor):
        user_lamps = build_user_lamps_from_dataframes(
            getattr(database_accessor, "df_score", None),
            getattr(database_accessor, "df_songdata", None),
        )
        result = self.calculate_from_lamps(user_lamps)
        result["parsed_scores"] = len(user_lamps)
        result["db_type"] = "beatoraja"
        return result

    def calculate_user_skill_from_database_accessor(self, database_accessor):
        user_lamps = build_user_lamps_from_dataframes(
            getattr(database_accessor, "df_score", None),
            getattr(database_accessor, "df_songdata", None),
        )
        return self.calculate_user_skill_from_lamps(user_lamps)


def build_folder_medians(ir_data, tables):
    folder_medians = {}
    for table_name, table_data in tables.items():
        for chart in table_data["charts"]:
            level_str = str(chart.get("level", "0"))
            if "?" in level_str:
                continue
            md5 = chart.get("md5", "").lower()
            sha256 = chart.get("sha256", "").lower()
            chart_stats = ir_data.get(md5, ir_data.get(sha256, {}))
            if chart_stats.get("diff_easy", 99.0) < 99.0:
                key = (table_name, level_str)
                if key not in folder_medians:
                    folder_medians[key] = {"e": [], "n": [], "h": [], "f": [], "d": []}
                folder_medians[key]["e"].append(chart_stats.get("diff_easy"))
                folder_medians[key]["n"].append(chart_stats.get("diff_normal"))
                folder_medians[key]["h"].append(chart_stats.get("diff_hard"))
                folder_medians[key]["f"].append(chart_stats.get("diff_fc"))
                folder_medians[key]["d"].append(chart_stats.get("disc", 1.0))

    for key in folder_medians:
        for metric in folder_medians[key]:
            values = folder_medians[key][metric]
            folder_medians[key][metric] = statistics.median(values) if values else 99.0

    return folder_medians


def build_played_charts(user_lamps, ir_data, tables, folder_medians):
    played_charts = []
    for table_name, table_data in tables.items():
        for chart in table_data["charts"]:
            level_str = str(chart.get("level", "0"))
            if "?" in level_str:
                continue

            md5 = chart.get("md5", "").lower()
            sha256 = chart.get("sha256", "").lower()
            level = safe_float(level_str)
            base_star = get_base_star(table_name, level)
            lamp = user_lamps.get(md5, user_lamps.get(sha256, -1))

            if lamp != -1:
                chart_stats = ir_data.get(md5, ir_data.get(sha256, {}))
                rates = get_rates(chart_stats)
                played_charts.append(
                    {
                        "lamp": lamp,
                        "b_easy": get_target_difficulty(
                            chart_stats, folder_medians, table_name, level_str, base_star, "diff_easy", -1.0, rates["easy"], "e"
                        ),
                        "b_normal": get_target_difficulty(
                            chart_stats, folder_medians, table_name, level_str, base_star, "diff_normal", 0.0, rates["normal"], "n"
                        ),
                        "b_hard": get_target_difficulty(
                            chart_stats, folder_medians, table_name, level_str, base_star, "diff_hard", 2.0, rates["hard"], "h"
                        ),
                        "b_fc": get_target_difficulty(
                            chart_stats, folder_medians, table_name, level_str, base_star, "diff_fc", 13.0, rates["fc"], "f"
                        ),
                        "a": get_discrimination(chart_stats, folder_medians, table_name, level_str),
                    }
                )
    return played_charts


def calculate_recommendations(user_lamps, ir_data, tables):
    recommend = []
    weapon = []
    all_charts = []

    folder_medians = build_folder_medians(ir_data, tables)
    played_charts = build_played_charts(user_lamps, ir_data, tables, folder_medians)

    user_skill = estimate_user_skill(played_charts)

    for table_name, table_data in tables.items():
        prefix = "★" if table_name == "insane" else "st" if table_name == "stella" else "sl"
        for chart in table_data["charts"]:
            level_str = str(chart.get("level", "0"))
            if "?" in level_str:
                continue

            md5 = chart.get("md5", "").lower()
            sha256 = chart.get("sha256", "").lower()
            level = safe_float(level_str)
            base_star = get_base_star(table_name, level)
            table_str = f"{prefix}{level_str}"
            current_lamp = user_lamps.get(md5, user_lamps.get(sha256, -1))
            chart_stats = ir_data.get(md5, ir_data.get(sha256, {}))
            rates = get_rates(chart_stats)

            d_easy = get_target_difficulty(
                chart_stats, folder_medians, table_name, level_str, base_star, "diff_easy", -1.0, rates["easy"], "e"
            )
            d_normal = get_target_difficulty(
                chart_stats, folder_medians, table_name, level_str, base_star, "diff_normal", 0.0, rates["normal"], "n"
            )
            d_hard = get_target_difficulty(
                chart_stats, folder_medians, table_name, level_str, base_star, "diff_hard", 2.0, rates["hard"], "h"
            )
            d_fc = get_target_difficulty(
                chart_stats, folder_medians, table_name, level_str, base_star, "diff_fc", 13.0, rates["fc"], "f"
            )
            disc = get_discrimination(chart_stats, folder_medians, table_name, level_str)

            if current_lamp <= 0:
                diff_irt = d_easy
                current_lamp_diff = 0.0
            elif current_lamp == 1:
                diff_irt = d_normal
                current_lamp_diff = d_easy
            elif current_lamp == 2:
                diff_irt = d_hard
                current_lamp_diff = d_normal
            else:
                diff_irt = d_fc
                current_lamp_diff = d_hard if current_lamp == 3 else d_fc

            prob = probability(user_skill, diff_irt, disc)
            prob_current = probability(user_skill, current_lamp_diff, disc)

            row = [
                table_str,
                chart.get("title", "Unknown"),
                current_lamp,
                d_easy,
                diff_irt,
                disc,
                prob,
                md5,
                chart_stats.get("clear_rate", 0.0),
                current_lamp_diff,
                {
                    "diff_easy": d_easy,
                    "diff_normal": d_normal,
                    "diff_hard": d_hard,
                    "diff_fc": d_fc,
                    "rate_easy": rates["easy"],
                    "rate_normal": rates["normal"],
                    "rate_hard": rates["hard"],
                    "rate_fc": rates["fc"],
                },
                prob_current,
            ]
            all_charts.append(row)

            if current_lamp != -1:
                if current_lamp < 3:
                    recommend.append(row)
                if current_lamp >= 1:
                    weapon.append(row)

    return {
        "recommend": recommend,
        "weapon": weapon,
        "all_charts": all_charts,
        "user_skill": user_skill,
    }


def get_base_star(table_name, level):
    if table_name == "stella":
        return level + 20.0
    if table_name == "satellite":
        sl_map = {
            0: 0.0,
            1: 1.5,
            2: 3.0,
            3: 4.5,
            4: 6.5,
            5: 8.5,
            6: 10.5,
            7: 12.0,
            8: 13.5,
            9: 15.5,
            10: 16.5,
            11: 17.5,
            12: 18.5,
        }
        return sl_map.get(int(level), level * 1.5)
    return level


def get_rates(chart_stats):
    return {
        "easy": chart_stats.get("rate_easy", chart_stats.get("clear_rate", 0.5)),
        "normal": chart_stats.get("rate_normal", chart_stats.get("clear_rate", 0.5)),
        "hard": chart_stats.get("rate_hard", 0.0),
        "fc": chart_stats.get("rate_fc", 0.0),
    }


def get_target_difficulty(chart_stats, folder_medians, table_name, level_str, base_star, key, fallback_offset, rate, metric):
    value = chart_stats.get(key, 99.0)
    if value < 99.0:
        return value

    median_key = (table_name, level_str)
    if median_key in folder_medians and folder_medians[median_key][metric] < 99.0:
        return folder_medians[median_key][metric]

    clipped_rate = max(0.05, min(0.95, rate))
    return (base_star + 2.0 + fallback_offset) - (1.0 / 1.7) * math.log(
        clipped_rate / (1.0 - clipped_rate)
    )


def get_discrimination(chart_stats, folder_medians, table_name, level_str):
    if chart_stats.get("diff_easy", 99.0) >= 99.0:
        return folder_medians.get((table_name, level_str), {}).get("d", 1.0)
    return chart_stats.get("disc", chart_stats.get("discrimination", 1.0))


def probability(user_skill, difficulty, discrimination):
    exponent = -1.7 * discrimination * (user_skill - difficulty)
    exponent = max(min(exponent, 50), -50)
    return 1.0 / (1.0 + math.exp(exponent))


def estimate_user_skill(played_charts):
    if not played_charts:
        return 0.0
    if all(chart["lamp"] == 0 for chart in played_charts):
        return 0.0
    if all(chart["lamp"] >= 4 for chart in played_charts):
        return 40.0

    def p_star(a, b, theta):
        exponent = -1.7 * a * (theta - b)
        if exponent > 50:
            return 0.0
        if exponent < -50:
            return 1.0
        return 1.0 / (1.0 + math.exp(exponent))

    def log_likelihood(theta):
        value = 0.0
        for chart in played_charts:
            lamp = chart["lamp"]
            pe = p_star(chart["a"], chart["b_easy"], theta)
            pn = p_star(chart["a"], chart["b_normal"], theta)
            ph = p_star(chart["a"], chart["b_hard"], theta)
            pf = p_star(chart["a"], chart["b_fc"], theta)

            if lamp == 0:
                p_exact = max(1e-10, 1.0 - pe)
            elif lamp == 1:
                p_exact = max(1e-10, pe - pn)
            elif lamp == 2:
                p_exact = max(1e-10, pn - ph)
            elif lamp == 3:
                p_exact = max(1e-10, ph - pf)
            else:
                p_exact = max(1e-10, pf)
            value += math.log(p_exact)
        return value

    low, high = -10.0, 50.0
    for _ in range(60):
        m1 = low + (high - low) / 3.0
        m2 = high - (high - low) / 3.0
        if log_likelihood(m1) < log_likelihood(m2):
            low = m1
        else:
            high = m2
    return (low + high) / 2.0


def format_result(result):
    formatted = {
        "user_skill": result["user_skill"],
        "recommend": [format_row(row) for row in result["recommend"]],
        "weapon": [format_row(row) for row in result["weapon"]],
        "all_charts": [format_row(row) for row in result["all_charts"]],
    }
    formatted["recommend"].sort(key=lambda row: row["recommend_percent"], reverse=True)
    formatted["weapon"].sort(key=lambda row: row["current_lamp_percent"], reverse=True)
    return formatted


def format_row(row):
    return {
        "table": row[0],
        "title": row[1],
        "current_lamp": row[2],
        "estimated_easy_difficulty": row[3],
        "target_difficulty": row[4],
        "discrimination": row[5],
        "recommend_probability": row[6],
        "recommend_percent": row[6] * 100.0,
        "md5": row[7],
        "clear_rate": row[8],
        "current_lamp_difficulty": row[9],
        "details": row[10],
        "current_lamp_probability": row[11],
        "current_lamp_percent": row[11] * 100.0,
    }
