import json
import os
import datetime
import threading

CONFIG_DIR = os.path.join(os.path.dirname(__file__), '..', 'configs')
os.makedirs(CONFIG_DIR, exist_ok=True)

_config_cache = {}
_config_lock = threading.Lock()

def get_config_path(guild_id):
    return os.path.join(CONFIG_DIR, f"{guild_id}.json")

def load_config(guild_id):
    with _config_lock:
        if guild_id in _config_cache:
            return _config_cache[guild_id].copy()
        path = get_config_path(guild_id)
        if not os.path.exists(path):
            _config_cache[guild_id] = {}
            return {}
        with open(path, 'r') as f:
            data = json.load(f)
            _config_cache[guild_id] = data
            return data.copy()

def save_config(guild_id, data, guild_name=None):
    path = get_config_path(guild_id)
    with _config_lock:
        # Only add metadata if it's the first time saving
        if not os.path.exists(path):
            data["__meta__"] = {
                "guild_name": guild_name or "Unknown",
                "created_at": datetime.datetime.utcnow().isoformat() + "Z"
            }
        _config_cache[guild_id] = data.copy()
        # Atomic write
        tmp_path = path + ".tmp"
        with open(tmp_path, 'w') as f:
            json.dump(data, f, indent=4)
        os.replace(tmp_path, path)
