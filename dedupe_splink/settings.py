import splink.comparison_library as cl

def get_settings():
    return {
        "link_type": "dedupe_only",
        "unique_id_column_name": "unique_id",
        "blocking_rules_to_generate_predictions": [
            "l.plz_prefix3 = r.plz_prefix3 AND l.birth_year = r.birth_year AND l.surname_initial = r.surname_initial",
            "l.plz_norm = r.plz_norm AND l.house_norm = r.house_norm AND substring(l.surname_norm, 1, 4) = substring(r.surname_norm, 1, 4)",
            "l.surname_phonetic = r.surname_phonetic AND l.birth_year = r.birth_year",
        ],
        "comparisons": [
            cl.JaroWinklerAtThresholds("first_name_norm", [0.9, 0.8]),
            cl.JaroWinklerAtThresholds("surname_norm", [0.9, 0.8]).configure(term_frequency_adjustments=True),
            cl.ExactMatch("plz_norm"),
            cl.ExactMatch("birth_year"),
        ],
        "retain_intermediate_calculation_columns": False,
        "additional_columns_to_retain": ["shard_key"],
    }
