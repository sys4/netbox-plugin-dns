###################################################################
#  This file serves as a base configuration for testing the       #
#  NetBox Branching integration only. It is not intended for       #
#  production use.                                                 #
###################################################################

from netbox_branching.utilities import DynamicSchemaDict

ALLOWED_HOSTS = ["*"]

# netbox-branching requires DATABASES (not the singular DATABASE) to be a
# DynamicSchemaDict, plus its database router — otherwise the plugin refuses to
# start.
DATABASES = DynamicSchemaDict(
    {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": "netbox",
            "USER": "netbox",
            "PASSWORD": "netbox",
            "HOST": "localhost",
            "PORT": "",
            "CONN_MAX_AGE": 300,
        }
    }
)

DATABASE_ROUTERS = ["netbox_branching.database.BranchAwareRouter"]

PLUGINS = [
    "netbox_dns",
    "netbox_branching",
]

REDIS = {
    "tasks": {
        "HOST": "localhost",
        "PORT": 6379,
        "PASSWORD": "",
        "DATABASE": 2,
        "SSL": False,
    },
    "caching": {
        "HOST": "localhost",
        "PORT": 6379,
        "PASSWORD": "",
        "DATABASE": 3,
        "SSL": False,
    },
}

RQ = {
    "COMMIT_MODE": "auto",
}

SECRET_KEY = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
API_TOKEN_PEPPERS = {
    1: "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
}

DEBUG_TOOLBAR_CONFIG = {
    "IS_RUNNING_TESTS": False,
}
