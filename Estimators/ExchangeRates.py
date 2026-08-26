import os
import urllib.request
import json
import glob
from datetime import datetime
from cfg.cfg import Config

try:
    import pandas as pd
except ImportError:
    pd = None


class ExchangeRates:
    @staticmethod
    def download_exchange_rates():
        """
        Download exchange rates for USD and EUR against major currencies.
        Saves the result as a CSV file in the summary output path.
        Uses free, no-key-required REST APIs.
        If file for today already exists, skips download.
        """
        config = Config()
        output_dir = config.get_path('summary_output_path')
        if not output_dir:
            output_dir = r"C:\Py\ScreenAI\out\Summary"
        os.makedirs(output_dir, exist_ok=True)

        date_str = datetime.now().strftime("%Y-%m-%d")
        filename_csv = f"exchange_rates_{date_str}.csv"
        filepath_csv = os.path.join(output_dir, filename_csv)

        # Check if file for today already exists
        if os.path.exists(filepath_csv):
            print(f"✅ Exchange rates for {date_str} already exist at: {filepath_csv}")
            return filepath_csv

        # Free, reliable, no-API-key required sources
        urls = [
            "https://open.er-api.com/v6/latest/USD",
            "https://open.er-api.com/v6/latest/EUR"
        ]

        all_rates = {}
        for url in urls:
            try:
                req = urllib.request.Request(
                    url, headers={'User-Agent': 'Mozilla/5.0'}
                )
                with urllib.request.urlopen(req, timeout=10) as response:
                    data = json.loads(response.read().decode('utf-8'))
                    # The API returns 'base_code' instead of 'base'
                    base = data.get('base_code') or data.get('base')
                    rates = data.get('rates', {})
                    if base and rates:
                        all_rates[base] = rates
                        print(f"✅ Downloaded {len(rates)} rates for {base}")
                    else:
                        print(f"⚠️ Missing base_code/rates from {url}")
            except Exception as e:
                print(f"⚠️ Failed to download from {url}: {e}")

        if not all_rates:
            print("❌ Failed to download exchange rates from all sources.")
            return None

        currencies = set()
        for base in all_rates:
            currencies.update(all_rates[base].keys())

        # Ensure specifically requested currencies are tracked
        required_currencies = [
            'RUB', 'GBP', 'ZAR', 'MXN', 'AUD', 'TWD', 'JPY', 'USD', 'EUR'
        ]
        currencies.update(required_currencies)

        rows = []
        for curr in sorted(list(currencies)):
            row = {'Currency': curr}
            row['Rate_USD'] = all_rates.get('USD', {}).get(curr)
            row['Rate_EUR'] = all_rates.get('EUR', {}).get(curr)

            # Cross-calculate missing rates if one base is available
            if row['Rate_USD'] is None and row['Rate_EUR'] is not None:
                usd_to_eur = all_rates.get('USD', {}).get('EUR')
                if usd_to_eur:
                    row['Rate_USD'] = round(row['Rate_EUR'] / usd_to_eur, 6)

            if row['Rate_EUR'] is None and row['Rate_USD'] is not None:
                eur_to_usd = all_rates.get('EUR', {}).get('USD')
                if eur_to_usd:
                    row['Rate_EUR'] = round(row['Rate_USD'] * eur_to_usd, 6)

            rows.append(row)

        if pd is not None:
            df = pd.DataFrame(rows)
            df.to_csv(filepath_csv, index=False)
            print(f"✅ Saved exchange rates to: {filepath_csv}")
            return filepath_csv
        else:
            print("⚠️ pandas is not installed. Cannot save as DataFrame/CSV.")
            return None

    @staticmethod
    def get_currencies():
        """
        Finds the latest exchange rates file in the summary output path
        and loads it into a pandas DataFrame.
        """
        if pd is None:
            print("⚠️ pandas is not installed. Cannot load DataFrame.")
            return None

        config = Config()
        output_dir = config.get_path('summary_output_path')
        if not output_dir:
            output_dir = r"C:\Py\ScreenAI\out\Summary"

        if not os.path.exists(output_dir):
            print(f"⚠️ Output directory does not exist: {output_dir}")
            return None

        # Search for CSV files only
        files = glob.glob(os.path.join(output_dir, "exchange_rates_*.csv"))

        if not files:
            print("⚠️ No exchange rates files found.")
            return None

        # Sort descending (YYYY-MM-DD ensures correct chronological order)
        files.sort(reverse=True)
        latest_file = files[0]

        try:
            df = pd.read_csv(latest_file)
            print(f"✅ Loaded latest exchange rates from: {latest_file}")
            return df
        except Exception as e:
            print(f"⚠️ Failed to load from {latest_file}: {e}")
            return None