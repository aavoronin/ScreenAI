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
        score = 0
        synonym_map = self._build_synonym_map()

        vacancy_title = (vacancy_json.get('Title') or '').strip()
        resume_titles = self.resume_json.get('Title', []) or []
        title_matched = False
        for rt in resume_titles:
            if not isinstance(rt, str):
                continue
            ratio = self._levenshtein_ratio(vacancy_title, rt)
            if ratio >= 1.0:
                points = self.SCORE_TITLE_EXACT
                score += points
                protocol_entries.append({
                    "left": vacancy_title,
                    "left_field": "Title",
                    "score": points,
                    "score_percentile": 0.0,
                    "right": rt,
                    "right_field": "Title",
                    "msg": f"+{points} points vacancy title exact match: '{vacancy_title}' vs '{rt}'"
                })
                title_matched = True
                break
            elif ratio >= 0.8:
                points = self.SCORE_TITLE_80
                score += points
                protocol_entries.append({
                    "left": vacancy_title,
                    "left_field": "Title",
                    "score": points,
                    "score_percentile": 0.0,
                    "right": rt,
                    "right_field": "Title",
                    "msg": f"+{points} points vacancy title 80% match ({int(ratio * 100)}%): '{vacancy_title}' vs '{rt}'"
                })
                title_matched = True
                break
            elif ratio >= 0.6:
                points = self.SCORE_TITLE_60
                score += points
                protocol_entries.append({
                    "left": vacancy_title,
                    "left_field": "Title",
                    "score": points,
                    "score_percentile": 0.0,
                    "right": rt,
                    "right_field": "Title",
                    "msg": f"+{points} points vacancy title 60% match ({int(ratio * 100)}%): '{vacancy_title}' vs '{rt}'"
                })
                title_matched = True
                break

        if not title_matched and vacancy_title:
            protocol_entries.append({
                "left": vacancy_title,
                "left_field": "Title",
                "score": 0,
                "score_percentile": 0.0,
                "right": "",
                "right_field": "Title",
                "msg": f"+0 points vacancy title no match: '{vacancy_title}'"
            })

        vacancy_industry = (vacancy_json.get('CompanyIndustry') or '').strip()
        no_industries = self.resume_json.get('CompanyNoIndustry', []) or []
        for ni in no_industries:
            if not isinstance(ni, str):
                continue
            ratio = self._levenshtein_ratio(vacancy_industry, ni)
            if ratio >= 0.9:
                points = self.SCORE_INDUSTRY_PENALTY
                score += points
                protocol_entries.append({
                    "left": vacancy_industry,
                    "left_field": "CompanyIndustry",
                    "score": points,
                    "score_percentile": 0.0,
                    "right": ni,
                    "right_field": "CompanyNoIndustry",
                    "msg": f"{points} points company industry matches CompanyNoIndustry ({int(ratio * 100)}%): '{vacancy_industry}' vs '{ni}'"
                })
                break

        levels = ["expert", "required", "nice-to-have"]
        vacancy_by_level = {}
        resume_by_level = {}
        for level in levels:
            vacancy_by_level[level] = set(
                s.lower() for s in self._normalize_by_synonyms(
                    vacancy_json.get(level, []) or [], synonym_map
                )
            )
            resume_by_level[level] = set(
                s.lower() for s in self._normalize_by_synonyms(
                    self.resume_json.get(level, []) or [], synonym_map
                )
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

        total_abs_score = sum(abs(e['score']) for e in protocol_entries)
        for entry in protocol_entries:
            if total_abs_score > 0:
                entry['score_percentile'] = round(entry['score'] / total_abs_score, 2)
            else:
                entry['score_percentile'] = 0.0

        return score, protocol_entries, unknown_skills

    def save_estimation_result(self, vacancy, estimation_tag, model_id, parsed_json, score, score_percentile, protocol):
        config = self.load_config(vacancy['json_path'])
        if config is None:
            config = {}
        config[estimation_tag] = {
            'model_id': model_id,
            'score': score,
            'score_percentile': score_percentile,
            'json': parsed_json,
            'scoring_protocol': protocol,
        }
        config['estimation_version'] = str(self.estimation_version)
        self.save_config(vacancy['json_path'], config)