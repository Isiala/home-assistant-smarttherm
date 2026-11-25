"""Constants for the OCSTAT SmartTherm cloud integration."""
DOMAIN = "smarttherm"
BASE_URL = "https://www.ocstat-thermostat.com/ocstat/"
CONF_USER_ID = "user_id"
CONF_TOKEN = "token"
CONF_CLIENT_ID = "client_id"
SUPPORTED_MODELS = {"08", "09", "53"}
MODE_SCHEDULE = "0"
MODE_OVERRIDE = "1"
MODE_MANUAL = "5"
PRESETS = {"schedule": MODE_SCHEDULE, "manual": MODE_MANUAL, "override": MODE_OVERRIDE}
