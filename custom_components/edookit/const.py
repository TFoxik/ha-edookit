from datetime import timedelta

DOMAIN = "edookit"

CONF_SCHOOL = "school"
CONF_SESSION = "session"
CAPTURE_ENV = "EDOOKIT_CAPTURE_PAGES"
CONF_MESSAGES_ADMIN_ONLY = "messages_admin_only"

CAPTURE_DIR = "edookit_captures"

DEFAULT_UPDATE_INTERVAL = timedelta(minutes=30)
SCHOOL_UPDATE_INTERVAL = timedelta(hours=3)
CAPTURE_INTERVAL = timedelta(days=1)
