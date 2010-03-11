# Edit this file to override the default graphite settings, do not edit settings.py!!!

# Turn on debugging and restart apache if you ever see an "Internal Server Error" page
DEBUG = True
CARBONLINK_TIMEOUT = 2.0

# Set your local timezone (django will try to figure this out automatically)
#TIME_ZONE = 'America/Chicago'

# Setting MEMCACHE_HOSTS to be empty will turn off use of memcached entirely
#MEMCACHE_HOSTS = ['10.87.8.198:11211', '10.87.8.199:11211']

# Sometimes you need to do a lot of rendering work but cannot share your storage mount
#REMOTE_RENDERING = True
#RENDERING_HOSTS = ['fastserver01','fastserver02']
#LOG_RENDERING_PERFORMANCE = True
#LOG_CACHE_PERFORMANCE = True

# If you've got more than one backend server they should all be listed here
CARBONLINK_HOSTS = ["localhost:7002"]
CLUSTER_SERVERS = ["localhost", "relay1.graphite.invitemedia.com"]

# Override this if you need to provide documentation specific to your graphite deployment
#DOCUMENTATION_URL = "http://wiki.mycompany.com/graphite"

# Enable email-related features
#SMTP_SERVER = "10.87.2.32"

# LDAP / ActiveDirectory authentication setup
#USE_LDAP_AUTH = True
#LDAP_SERVER = "10.72.247.76"
#LDAP_SEARCH_BASE = "ou=people,o=intra,dc=sears,dc=com"
#LDAP_BASE_USER = ""
#LDAP_BASE_PASS = ""
#LDAP_USER_QUERY = "(uid=%s)"

#DATABASE_ENGINE = 'mysql'
#DATABASE_NAME = 'graphite'
#DATABASE_USER = 'graphite'
#DATABASE_PASSWORD = 'gr4ph1t3'
#DATABASE_HOST = '10.87.22.153'
#DATABASE_PORT = '3306'
