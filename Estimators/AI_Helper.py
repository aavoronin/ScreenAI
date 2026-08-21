import os
import re
import json
import time
import sys
import hashlib
import zipfile
from datetime import datetime
from ai_clients.start_server import start_wsl_server, stop_wsl_server
from ai_clients.TextToTextClient import TextToTextClient


class AI_Helper:
    LEVEL_1_MODELS = [
        "matrixportalx/Llama-3.3-8B-Instruct-128K-Q5_K_M-GGUF|GPU|32768",
        "NikolayKozloff/gemma-3-4b-it-Q8_0-GGUF|GPU|32768",
        "rktmeister/Meta-Llama-3.1-8B-Instruct-Q5_K_M-GGUF|GPU|32768",
    ]

    LEVEL_2_MODELS = [
        "Brunobkr/OFFELLIA_Q6_K_gemma-4-26B-A4B-it-ultra-uncensored-heretic.gguf|CPU|32768",
        "majentik/gemma-4-12B-it-RotorQuant-GGUF-Q5_K_M|CPU|32768",
    ]

    def __init__(self, cache_dir, prompt_text, vacancy_timeout, warmup_timeout):
        self.cache_dir = cache_dir
        os.makedirs(self.cache_dir, exist_ok=True)
        self.prompt_text = prompt_text
        self.vacancy_timeout = vacancy_timeout
        self.warmup_timeout = warmup_timeout
        self.client = None
        self._server_started = False

    def _ensure_server_and_client(self):
        if not self._server_started:
            print("\n🚀 Starting AI server...")
            start_wsl_server()
            time.sleep(5)
            self.client = TextToTextClient()
            self._server_started = True

    def stop_server(self):
        if self._server_started:
            print("\n🛑 Stopping AI server...")
            stop_wsl_server()
            self._server_started = False
            self.client = None

    @staticmethod
    def _parse_json_safely(text):
        if not text or not isinstance(text, str):
            return None
        text = text.strip()
        try:
            return json.loads(text)
        except (json.JSONDecodeError, ValueError):
            pass
        match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL | re.IGNORECASE)
        if match:
            try:
                return json.loads(match.group(1))
            except (json.JSONDecodeError, ValueError):
                pass
        start = text.find('{')
        if start != -1:
            depth = 0
            in_string = False
            escape = False
            for i in range(start, len(text)):
                ch = text[i]
                if escape:
                    escape = False
                    continue
                if ch == '\\':
                    escape = True
                    continue
                if ch == '"':
                    in_string = not in_string
                    continue
                if in_string:
                    continue
                if ch == '{':
                    depth += 1
                elif ch == '}':
                    depth -= 1
                    if depth == 0:
                        try:
                            return json.loads(text[start:i + 1])
                        except (json.JSONDecodeError, ValueError):
                            break
        return None

    def _get_cache_file_path(self, model_id: str, prompt: str) -> str:
        key = f"{model_id}|{prompt}"
        md5_hash = hashlib.md5(key.encode('utf-8')).hexdigest()
        return os.path.join(self.cache_dir, f"{md5_hash}.zip")

    def _load_from_cache(self, cache_path: str) -> dict:
        with zipfile.ZipFile(cache_path, 'r') as zf:
            with zf.open('response.json') as f:
                return json.load(f)

    def _save_to_cache(self, cache_path: str, response: dict):
        with zipfile.ZipFile(cache_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr('response.json', json.dumps(response))

    def _warmup_model(self, model_id):
        start_time = time.time()
        max_retries = 5
        for attempt in range(1, max_retries + 1):
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"  🔥 [{ts}] Warming up {model_id} (Attempt {attempt}/{max_retries})")
            try:
                self.client.generate(model_id, "2+2", model_limit_seconds=self.warmup_timeout)
                duration = time.time() - start_time
                ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                print(f"  ✅ [{ts}] Warmup done in {duration:.2f}s")
                return
            except Exception as e:
                print(f"  ⚠️ Warmup failed on attempt {attempt}: {e}")
                if attempt < max_retries:
                    print("  🔄 Restarting server and waiting 30 seconds before retrying...")
                    try:
                        stop_wsl_server()
                    except Exception as stop_e:
                        print(f"  ⚠️ Error stopping server: {stop_e}")
                    time.sleep(30)
                    try:
                        start_wsl_server()
                    except Exception as start_e:
                        print(f"  ⚠️ Error starting server: {start_e}")
                    time.sleep(30)
                else:
                    print(f"  ❌ Warmup failed after {max_retries} attempts. Exiting.")
                    sys.exit(1)

    def _apply_prompt_to_vacancy(self, model_id: str, prompt_text: str, cleaned_vacancy_text: str):
        full_prompt = prompt_text + "\n" + cleaned_vacancy_text
        cache_path = self._get_cache_file_path(model_id, full_prompt)

        if os.path.exists(cache_path):
            print(f"  💾 Loading from cache: {os.path.basename(cache_path)}")
            try:
                response = self._load_from_cache(cache_path)
                generated_text = response.get("generated_text", "")
                if not isinstance(generated_text, str):
                    generated_text = str(generated_text)
                parsed = self._parse_json_safely(generated_text)
                return {
                    'success': True,
                    'duration': 0.0,
                    'prompt_size': len(full_prompt),
                    'vacancy_size': len(cleaned_vacancy_text),
                    'generated_text': generated_text,
                    'parsed_json': parsed,
                    'error': None,
                    'from_cache': True
                }
            except Exception as e:
                print(f"  ⚠️ Cache read error: {e}. Regenerating...")

        total_start_time = time.time()
        try:
            response = self.client.generate(model_id, full_prompt, model_limit_seconds=self.vacancy_timeout)
            duration = time.time() - total_start_time

            self._save_to_cache(cache_path, response)

            generated_text = response.get("generated_text", "")
            if not isinstance(generated_text, str):
                generated_text = str(generated_text)
            parsed = self._parse_json_safely(generated_text)
            return {
                'success': True,
                'duration': duration,
                'prompt_size': len(full_prompt),
                'vacancy_size': len(cleaned_vacancy_text),
                'generated_text': generated_text,
                'parsed_json': parsed,
                'error': None,
                'from_cache': False
            }
        except Exception as e:
            duration = time.time() - total_start_time
            return {
                'success': False,
                'duration': duration,
                'prompt_size': len(full_prompt),
                'vacancy_size': len(cleaned_vacancy_text),
                'generated_text': '',
                'parsed_json': None,
                'error': str(e),
                'from_cache': False
            }

    def _apply_model_to_vacancies(self, model_id, prepared_vacancies, prompt_text):
        results = []
        for v in prepared_vacancies:
            vid = v['vacancy_id']
            print(f"  📄 Vacancy {vid} -> {model_id}")

            cleaned_text = v.get('cleaned_text', '')
            if not cleaned_text:
                results.append({
                    'vacancy_id': vid,
                    'txt_name': v.get('txt_name', ''),
                    'model_id': model_id,
                    'success': False,
                    'duration': 0.0,
                    'prompt_size': 0,
                    'vacancy_size': 0,
                    'error': 'empty_text',
                    'from_cache': False
                })
                print(f"    ❌ Time: 0.00s | Error: empty_text")
                continue

            result = self._apply_prompt_to_vacancy(model_id, prompt_text, cleaned_text)
            result['vacancy_id'] = vid
            result['txt_name'] = v.get('txt_name', '')
            result['model_id'] = model_id
            results.append(result)

            status = "✅" if result['success'] else "❌"
            cache_info = " (Cache)" if result.get('from_cache') else ""
            err = f" | Error: {result['error']}" if result['error'] else ""
            print(
                f"    {status}{cache_info} Time: {result['duration']:.2f}s | "
                f"Prompt: {result['prompt_size']} chars | "
                f"Vacancy: {result['vacancy_size']} chars{err}"
            )
        return results

    def _apply_level_models_to_vacancies(self, prepared_vacancies, level_n, level_name):
        self._ensure_server_and_client()
        if self.prompt_text is None:
            print("⚠️ Could not load prompt. Aborting level estimation.")
            return [], [], prepared_vacancies, 0.0, {}

        models = self.LEVEL_1_MODELS if level_n == 1 else self.LEVEL_2_MODELS

        print(f"\n{'=' * 70}")
        print(f"🎯 {level_name} - {len(prepared_vacancies)} vacancies, {len(models)} model(s)")
        print(f"{'=' * 70}")

        all_results = []
        model_times = {}
        remaining = list(prepared_vacancies)
        successful = []
        level_start = time.time()

        for model_id in models:
            if not remaining:
                break
            print(f"\n🔄 Model: {model_id}")
            print(f"   Vacancies to process: {len(remaining)}")
            self._warmup_model(model_id)

            model_start = time.time()
            results = self._apply_model_to_vacancies(model_id, remaining, self.prompt_text)
            model_duration = time.time() - model_start
            model_times[model_id] = model_duration
            all_results.extend(results)

            new_remaining = []
            for r, v in zip(results, remaining):
                if r['success']:
                    successful.append(v)
                else:
                    new_remaining.append(v)

            succeeded_this_round = len(remaining) - len(new_remaining)
            print(f"\n--- {level_name} Model Summary: {model_id} ---")
            print(f"  Succeeded: {succeeded_this_round}/{len(remaining)} | Model Time: {model_duration:.2f}s")

            remaining = new_remaining

            if not remaining:
                print(f"\n✅ All vacancies succeeded with {model_id}. Stopping {level_name}.")
                break

        level_time = time.time() - level_start

        if remaining:
            print(f"\n⚠️ {len(remaining)} vacancy(ies) still failed after all {level_name} models.")

        return all_results, successful, remaining, level_time, model_times

    @staticmethod
    def _print_level_summary(level_name, all_results, successful, failed, level_time):
        print(f"\n{'=' * 70}")
        print(f"📊 {level_name} SUMMARY")
        print(f"{'=' * 70}")
        header = f"{'Vacancy':<15} | {'Model':<45} | {'Score':>6} | {'Pct':>5} | {'Time':>8} | Status"
        print(header)
        print("-" * 70)

        by_vacancy = {}
        for r in all_results:
            vid = r['vacancy_id']
            by_vacancy.setdefault(vid, []).append(r)

        for vid, results in by_vacancy.items():
            successful_r = next((r for r in results if r['success']), None)
            display_r = successful_r if successful_r else results[-1]
            model_short = display_r['model_id']
            if len(model_short) > 45:
                model_short = "..." + model_short[-42:]
            status = "✅" if display_r['success'] else "❌"
            score_str = f"{display_r.get('score', 0):>6.2f}"
            pct_str = f"{display_r.get('score_percentile', 0.0):>5.2f}"
            print(
                f"{vid:<15} | {model_short:<45} | {score_str} | {pct_str} | {display_r['duration']:>7.2f}s | {status}")

        print("-" * 70)
        print(f"Total {level_name}: {len(successful)} succeeded, {len(failed)} failed | Time: {level_time:.2f}s")

    @staticmethod
    def _print_model_usage_table(level_name, all_results, model_times):
        print(f"\n📈 {level_name} - Model Usage")
        print("-" * 70)
        print(f"{'Model':<55} | {'Time':>8} | Calls")
        print("-" * 70)

        by_model = {}
        for r in all_results:
            mid = r['model_id']
            if mid not in by_model:
                by_model[mid] = {'count': 0, 'success': 0, 'time': 0.0}
            by_model[mid]['count'] += 1
            by_model[mid]['time'] += r['duration']
            if r['success']:
                by_model[mid]['success'] += 1

        for mid, stats in by_model.items():
            total_time = model_times.get(mid, stats['time'])
            model_short = mid if len(mid) <= 55 else "..." + mid[-52:]
            print(f"{model_short:<55} | {total_time:>7.2f}s | {stats['success']}/{stats['count']}")
        print("-" * 70)

    @staticmethod
    def _print_unknown_skills_summary(level_name, all_results):
        print(f"\n{'=' * 70}")
        print(f"🔍 {level_name} - UNKNOWN SKILLS (grouped by skill)")
        print(f"{'=' * 70}")
        skill_counts = {}
        for r in all_results:
            if r.get('unknown_skills'):
                for skill, level in r['unknown_skills']:
                    key = f"{skill} ({level})"
                    skill_counts[key] = skill_counts.get(key, 0) + 1

        if skill_counts:
            sorted_skills = sorted(skill_counts.items(), key=lambda x: (-x[1], x[0]))
            for skill_key, count in sorted_skills:
                print(f"  {skill_key}: {count} vacancy(ies)")
            print(f"\nTotal unique unknown skills: {len(skill_counts)}")
        else:
            print("  No unknown skills found.")
        print("-" * 70)