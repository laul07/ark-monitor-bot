import json
import os
import datetime

CONFIG_DIR = os.path.join(os.path.dirname(__file__), '..', 'configs')
os.makedirs(CONFIG_DIR, exist_ok=True)

def get_config_path(guild_id):
    return os.path.join(CONFIG_DIR, f"{guild_id}.json")

def load_config(guild_id):
    path = get_config_path(guild_id)
    if not os.path.exists(path):
        return {}
    with open(path, 'r') as f:
        return json.load(f)

def save_config(guild_id, data, guild_name=None):
    path = get_config_path(guild_id)

    # Only add metadata if it's the first time saving
    if not os.path.exists(path):
        data["__meta__"] = {
            "guild_name": guild_name or "Unknown",
            "created_at": datetime.datetime.utcnow().isoformat() + "Z"
        }

    with open(path, 'w') as f:
        json.dump(data, f, indent=4)
