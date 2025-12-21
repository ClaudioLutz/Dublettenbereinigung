# dedupe_splink/settings.py
from __future__ import annotations

def build_splink_settings(unique_id_col: str = "unique_id") -> dict:
    # NOTE: comparison objects below are representative.
    # You may need to adjust imports based on your installed Splink version.
    settings = {
        "link_type": "dedupe_only",
        "unique_id_column_name": unique_id_col,

        # Keep it minimal: name + plz + year first
        "comparisons": [
            # First name fuzzy levels
            {
                "output_column_name": "first_name_norm",
                "comparison_levels": [
                    {"sql_condition": "l.first_name_norm = r.first_name_norm", "label_for_charts": "Exact"},
                    {"sql_condition": "jaro_winkler_similarity(l.first_name_norm, r.first_name_norm) >= 0.92", "label_for_charts": "JW>=0.92"},
                    {"sql_condition": "jaro_winkler_similarity(l.first_name_norm, r.first_name_norm) >= 0.88", "label_for_charts": "JW>=0.88"},
                    {"sql_condition": "1=1", "label_for_charts": "Else"},
                ],
            },
            # Surname fuzzy levels + TF adjustment
            {
                "output_column_name": "surname_norm",
                "comparison_levels": [
                    {"sql_condition": "l.surname_norm = r.surname_norm", "label_for_charts": "Exact"},
                    {"sql_condition": "jaro_winkler_similarity(l.surname_norm, r.surname_norm) >= 0.94", "label_for_charts": "JW>=0.94"},
                    {"sql_condition": "jaro_winkler_similarity(l.surname_norm, r.surname_norm) >= 0.90", "label_for_charts": "JW>=0.90"},
                    {"sql_condition": "1=1", "label_for_charts": "Else"},
                ],
                "term_frequency_adjustments": True,
            },
            # Birth year exact (cheap, strong)
            {
                "output_column_name": "birth_year",
                "comparison_levels": [
                    {"sql_condition": "l.birth_year = r.birth_year AND l.birth_year != 0", "label_for_charts": "ExactYear"},
                    {"sql_condition": "(l.birth_year = 0 OR r.birth_year = 0)", "label_for_charts": "Missing"},
                    {"sql_condition": "1=1", "label_for_charts": "Different"},
                ],
            },
            # PLZ exact or prefix match (cheap)
            {
                "output_column_name": "plz_norm",
                "comparison_levels": [
                    {"sql_condition": "l.plz_norm = r.plz_norm AND l.plz_norm != ''", "label_for_charts": "ExactPLZ"},
                    {"sql_condition": "l.plz_prefix3 = r.plz_prefix3 AND l.plz_prefix3 != ''", "label_for_charts": "PLZPrefix3"},
                    {"sql_condition": "(l.plz_norm = '' OR r.plz_norm = '')", "label_for_charts": "Missing"},
                    {"sql_condition": "1=1", "label_for_charts": "Different"},
                ],
            },
        ],

        # Strict blocking to keep runtime small
        "blocking_rules_to_generate_predictions": [
            # Primary: same PLZ prefix3 + year + surname initial
            "l.plz_prefix3 = r.plz_prefix3 AND l.birth_year = r.birth_year AND l.surname_initial = r.surname_initial",
            # Secondary: exact PLZ + house + surname prefix
            "l.plz_norm = r.plz_norm AND l.house_norm = r.house_norm AND l.surname_prefix4 = r.surname_prefix4",
            # For missing PLZ: same birth_year + surname_prefix4 + first_initial
            "(l.plz_norm = '' OR r.plz_norm = '') AND l.birth_year = r.birth_year AND l.surname_prefix4 = r.surname_prefix4 AND l.first_initial = r.first_initial",
        ],

        # Helpful defaults for performance
        "retain_intermediate_calculation_columns": False,
        "additional_columns_to_retain": [
            "first_name_norm", "surname_norm", "street_norm", "plz_norm", "birth_year"
        ],
    }
    return settings
