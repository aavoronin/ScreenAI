import json
import os


class Config:
    _instance = None
    _data = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Config, cls).__new__(cls)
            cls._instance._load_config()
        return cls._instance

    def _load_config(self):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(base_dir, 'config.json')
        with open(config_path, 'r', encoding='utf-8') as f:
            self._data = json.load(f)

    @property
    def paths(self):
        return self._data.get('paths', {})

    def get_path(self, key: str) -> str:
        return self.paths.get(key)