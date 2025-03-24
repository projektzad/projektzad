import json
import os

CONFIG_PATH = os.path.join("app", "config", "user_defaults.json")

def load_config() -> dict:
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, 'r') as f:
            return json.load(f)
    return {}

def get_default_attributes() -> dict:
    config = load_config()
    return config.get("attributes", {})

def get_default_ou() -> str:
    config = load_config()
    return config.get("default_ou") or "CN=Users"

def save_user_defaults(data: dict):
    config = load_config()
    config["default_ou"] = data.get("default_ou", config.get("default_ou", "CN=Users"))
    config["attributes"] = data.get("attributes", config.get("attributes", {}))

    with open(CONFIG_PATH, 'w') as f:
        json.dump(config, f, indent=2)

