import os
import re
import json


class VacancyScoring:
    def __init__(self, resume_json, known_tech_skills, estimator_config, estimation_version, load_config_func,
                 save_config_func):
        self.resume_json = resume_json
        self.known_tech_skills = known_tech_skills
        self.estimator_config = estimator_config
        self.estimation_version = estimation_version
        self.load_config = load_config_func
        self.save_config = save_config_func

        self.TITLE_ADJUSTMENT = 0.6
        self.SCORE_TITLE_EXACT = int(20 * self.TITLE_ADJUSTMENT)
        self.SCORE_TITLE_80 = int(16 * self.TITLE_ADJUSTMENT)
        self.SCORE_TITLE_60 = int(12 * self.TITLE_ADJUSTMENT)
        self.SCORE_INDUSTRY_PENALTY = -100

        self.PROFICIENCY_SCORE_MATRIX = {
            "expert": {"expert": 6, "required": 4, "nice-to-have": 1},
            "required": {"expert": 4, "required": 5, "nice-to-have": 1},
            "nice-to-have": {"expert": 1, "required": 1, "nice-to-have": 2},
        }
        self.MISSING_PENALTY = {
            "expert": -6,
            "required": -5,
            "nice-to-have": -1,
        }
        self.LEVEL_2_MIN_SCORE = 20

    def _safe_str(self, val):
        """Safely convert a value to a stripped string, handling lists by joining them."""
        if isinstance(val, str):
            return val.strip()
        if isinstance(val, list):
            return " ".join(str(v) for v in val).strip()
        return ""

    def _safe_list(self, val):
        """Safely convert a value to a list of stripped strings."""
        if isinstance(val, list):
            return [str(v).strip() for v in val if isinstance(v, (str, int, float))]
        if isinstance(val, str):
            return [val.strip()]
        return []

    def _levenshtein_ratio(self, s1, s2):
        if not s1 and not s2:
            return 1.0
        if not s1 or not s2:
            return 0.0
        s1, s2 = s1.lower(), s2.lower()
        len1, len2 = len(s1), len(s2)
        matrix = [[0] * (len2 + 1) for _ in range(len1 + 1)]
        for i in range(len1 + 1):
            matrix[i][0] = i
        for j in range(len2 + 1):
            matrix[0][j] = j
        for i in range(1, len1 + 1):
            for j in range(1, len2 + 1):
                cost = 0 if s1[i - 1] == s2[j - 1] else 1
                matrix[i][j] = min(
                    matrix[i - 1][j] + 1,
                    matrix[i][j - 1] + 1,
                    matrix[i - 1][j - 1] + cost
                )
        distance = matrix[len1][len2]
        max_len = max(len1, len2)
        return 1.0 - (distance / max_len) if max_len > 0 else 1.0

    def _is_word_bound_substring(self, s1, s2):
        """Check if s1 is a word-bound substring of s2, or vice versa."""
        if re.search(r'\b' + re.escape(s1) + r'\b', s2):
            return True
        if re.search(r'\b' + re.escape(s2) + r'\b', s1):
            return True
        return False

    def _build_synonym_map(self):
        synonyms_section = self.estimator_config.get(
            'synonyms', self.estimator_config.get('synonymns', [])
        )
        synonym_map = {}
        if isinstance(synonyms_section, list):
            for group in synonyms_section:
                if isinstance(group, list) and len(group) > 0:
                    canonical = group[0]
                    for syn in group:
                        if isinstance(syn, str):
                            synonym_map[syn.lower()] = canonical
        return synonym_map

    def _normalize_by_synonyms(self, items, synonym_map):
        if not items:
            return []
        normalized = []
        for item in items:
            if not isinstance(item, str):
                continue
            item_lower = item.strip().lower()
            if item_lower in synonym_map:
                normalized.append(synonym_map[item_lower])
            else:
                normalized.append(item.strip())
        return normalized

    def calculate_score(self, vacancy_json):
        protocol_entries = []
        unknown_skills = []
        required_languages = []
        score = 0
        synonym_map = self._build_synonym_map()

        # --- Title matching ---
        vacancy_title = self._safe_str(vacancy_json.get('Title'))
        resume_titles = self._safe_list(self.resume_json.get('Title', []))

        best_match_rt = None
        best_match_ratio = 0.0
        best_match_points = 0

        for rt in resume_titles:
            if not rt:
                continue
            ratio = self._levenshtein_ratio(vacancy_title, rt)

            if ratio >= 1.0:
                points = self.SCORE_TITLE_EXACT
            elif ratio >= 0.8:
                points = self.SCORE_TITLE_80
            elif ratio >= 0.6:
                points = self.SCORE_TITLE_60
            else:
                points = 0

            if points > best_match_points or (points == best_match_points and ratio > best_match_ratio):
                best_match_points = points
                best_match_ratio = ratio
                best_match_rt = rt

        if best_match_rt and best_match_points > 0:
            score += best_match_points
            if best_match_ratio >= 1.0:
                msg = f"+{best_match_points} points vacancy title exact match: '{vacancy_title}' vs '{best_match_rt}'"
            elif best_match_ratio >= 0.8:
                msg = f"+{best_match_points} points vacancy title 80% match ({int(best_match_ratio * 100)}%): '{vacancy_title}' vs '{best_match_rt}'"
            else:
                msg = f"+{best_match_points} points vacancy title 60% match ({int(best_match_ratio * 100)}%): '{vacancy_title}' vs '{best_match_rt}'"

            protocol_entries.append({
                "left": vacancy_title,
                "left_field": "Title",
                "score": best_match_points,
                "score_percentile": 0.0,
                "right": best_match_rt,
                "right_field": "Title",
                "msg": msg
            })
        elif vacancy_title:
            protocol_entries.append({
                "left": vacancy_title,
                "left_field": "Title",
                "score": 0,
                "score_percentile": 0.0,
                "right": "",
                "right_field": "Title",
                "msg": f"+0 points vacancy title no match: '{vacancy_title}'"
            })

        # --- CompanyNoIndustry penalty ---
        vacancy_industry = self._safe_str(vacancy_json.get('CompanyIndustry'))
        no_industries = self._safe_list(self.resume_json.get('CompanyNoIndustry', []))

        best_ni_match = None
        best_ni_ratio = 0.0

        for ni in no_industries:
            if not ni:
                continue
            ratio = self._levenshtein_ratio(vacancy_industry, ni)
            if ratio >= 0.9:
                if ratio > best_ni_ratio:
                    best_ni_ratio = ratio
                    best_ni_match = ni

        if best_ni_match:
            points = self.SCORE_INDUSTRY_PENALTY
            score += points
            protocol_entries.append({
                "left": vacancy_industry,
                "left_field": "CompanyIndustry",
                "score": points,
                "score_percentile": 0.0,
                "right": best_ni_match,
                "right_field": "CompanyNoIndustry",
                "msg": f"{points} points company industry matches CompanyNoIndustry ({int(best_ni_ratio * 100)}%): '{vacancy_industry}' vs '{best_ni_match}'"
            })

        # --- Security Clearance penalty ---
        vacancy_clearance = self._safe_str(vacancy_json.get('SecurityClearance'))
        if vacancy_clearance and vacancy_clearance.lower() != 'none':
            points = -100
            score += points
            protocol_entries.append({
                "left": vacancy_clearance,
                "left_field": "SecurityClearance",
                "score": points,
                "score_percentile": 0.0,
                "right": "none",
                "right_field": "SecurityClearance",
                "msg": f"{points} points vacancy requires security clearance: '{vacancy_clearance}'"
            })

        # --- RequiredLanguages scoring ---
        vacancy_languages = self._safe_list(vacancy_json.get('RequiredLanguages', []))
        resume_languages = [
            lang.lower()
            for lang in self._safe_list(self.resume_json.get('RequiredLanguages', []))
        ]
        seen_required_languages = set()
        for lang in vacancy_languages:
            lang_display = self._safe_str(lang).strip()
            if not lang_display:
                continue
            lang_key = lang_display.lower()
            if lang_key in {'none', 'n/a', 'na', '-'}:
                continue
            if lang_key in seen_required_languages:
                continue
            seen_required_languages.add(lang_key)
            required_languages.append(lang_display)
            if lang_key in resume_languages:
                points = 5
                score += points
                protocol_entries.append({
                    "left": lang_display,
                    "left_field": "RequiredLanguages",
                    "score": points,
                    "score_percentile": 0.0,
                    "right": lang_display,
                    "right_field": "RequiredLanguages",
                    "msg": f"+{points} points vacancy requires language '{lang_display}' present in resume"
                })
            else:
                points = -50
                score += points
                protocol_entries.append({
                    "left": lang_display,
                    "left_field": "RequiredLanguages",
                    "score": points,
                    "score_percentile": 0.0,
                    "right": "",
                    "right_field": "RequiredLanguages",
                    "msg": f"{points} points vacancy requires language '{lang_display}' not in resume"
                })

        # --- Skills matching (expert / required / nice-to-have) ---
        levels = ["expert", "required", "nice-to-have"]
        vacancy_by_level = {}
        resume_by_level = {}
        for level in levels:
            raw_v = vacancy_json.get(level, [])
            v_list = raw_v if isinstance(raw_v, list) else ([raw_v] if raw_v else [])
            vacancy_by_level[level] = set(
                s.lower() for s in self._normalize_by_synonyms(v_list, synonym_map) if s
            )
            raw_r = self.resume_json.get(level, [])
            r_list = raw_r if isinstance(raw_r, list) else ([raw_r] if raw_r else [])
            resume_by_level[level] = set(
                s.lower() for s in self._normalize_by_synonyms(r_list, synonym_map) if s
            )

        all_vacancy_skills = {}
        for level in levels:
            for skill in vacancy_by_level[level]:
                if skill not in all_vacancy_skills:
                    all_vacancy_skills[skill] = level

        for v_skill, v_level in all_vacancy_skills.items():
            r_level = None
            for level in levels:
                if v_skill in resume_by_level[level]:
                    r_level = level
                    break
            if r_level is not None:
                points = self.PROFICIENCY_SCORE_MATRIX[v_level][r_level]
                score += points
                protocol_entries.append({
                    "left": v_skill,
                    "left_field": v_level,
                    "score": points,
                    "score_percentile": 0.0,
                    "right": v_skill,
                    "right_field": r_level,
                    "msg": f"+{points} points vacancy '{v_skill}' {v_level} vs resume '{v_skill}' {r_level}"
                })
            else:
                # No exact match. Try to find known skills as a word-bound substring.
                max_scores_by_canonical = {}
                best_matches = {}
                for r_level_check in levels:
                    for r_skill in resume_by_level[r_level_check]:
                        canonical = synonym_map.get(r_skill, r_skill)
                        # Ensure the matching resume skill is a known tech skill
                        if canonical in self.known_tech_skills or r_skill in self.known_tech_skills:
                            if self._is_word_bound_substring(v_skill, r_skill):
                                points = self.PROFICIENCY_SCORE_MATRIX[v_level][r_level_check]
                                ratio = self._levenshtein_ratio(v_skill, r_skill)
                                score_val = points * ratio
                                if canonical not in max_scores_by_canonical or score_val > max_scores_by_canonical[
                                    canonical]:
                                    max_scores_by_canonical[canonical] = score_val
                                    best_matches[canonical] = (r_skill, r_level_check, ratio)
                if max_scores_by_canonical:
                    total_sub_score = sum(max_scores_by_canonical.values())
                    score += total_sub_score
                    match_details = []
                    for canonical, (r_skill, r_level_check, ratio) in best_matches.items():
                        match_details.append(f"'{r_skill}' {r_level_check} (ratio: {ratio:.2f})")
                    protocol_entries.append({
                        "left": v_skill,
                        "left_field": v_level,
                        "score": round(total_sub_score, 2),
                        "score_percentile": 0.0,
                        "right": ", ".join([m[0] for m in best_matches.values()]),
                        "right_field": ", ".join([m[1] for m in best_matches.values()]),
                        "msg": f"+{total_sub_score:.2f} points vacancy '{v_skill}' {v_level} partially matches resume {', '.join(match_details)}"
                    })
                else:
                    # No substring match found. Fall back to missing penalty or unknown.
                    if v_skill in self.known_tech_skills:
                        points = self.MISSING_PENALTY[v_level]
                        score += points
                        protocol_entries.append({
                            "left": v_skill,
                            "left_field": v_level,
                            "score": points,
                            "score_percentile": 0.0,
                            "missing": v_skill,
                            "right_field": "missing",
                            "msg": f"{points} points vacancy '{v_skill}' {v_level} does not exist in resume json"
                        })
                    else:
                        unknown_skills.append((v_skill, v_level))
                        protocol_entries.append({
                            "left": v_skill,
                            "left_field": v_level,
                            "score": 0,
                            "score_percentile": 0.0,
                            "missing": v_skill,
                            "right_field": "unknown",
                            "msg": f"0 points vacancy '{v_skill}' {v_level} is unknown (not in tech/synonyms), no penalty"
                        })

        # Calculate score_percentile for each entry
        total_abs_score = sum(abs(e['score']) for e in protocol_entries)
        for entry in protocol_entries:
            if total_abs_score > 0:
                entry['score_percentile'] = round(entry['score'] / total_abs_score, 2)
            else:
                entry['score_percentile'] = 0.0

        return score, protocol_entries, unknown_skills, required_languages

    def save_estimation_result(self, vacancy, estimation_tag, model_id, parsed_json, score, score_percentile, protocol,
                               required_languages=None):
        config = self.load_config(vacancy['json_path'])
        if config is None:
            config = {}
        config[estimation_tag] = {
            'model_id': model_id,
            'score': score,
            'score_percentile': score_percentile,
            'json': parsed_json,
            'scoring_protocol': protocol,
            'required_languages': required_languages or []
        }
        config['estimation_version'] = str(self.estimation_version)
        self.save_config(vacancy['json_path'], config)