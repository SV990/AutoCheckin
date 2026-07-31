"""项目常量。"""

from datetime import timedelta, timezone

CST = timezone(timedelta(hours=8))

HTTP_OK = 200
HTTP_VALIDATION_ERROR = 422
HTTP_TEMPORARY_ERRORS = (429, 502, 503)

CHECKIN_START_HOUR = 0
CHECKIN_END_HOUR = 6

REQUEST_TIMEOUT_SECONDS = 15
NOTIFICATION_TIMEOUT_SECONDS = 10
IP_REQUEST_TIMEOUT_SECONDS = 10
IP_MAX_RETRIES = 2
CHECKIN_MAX_RETRIES = 2
RETRY_SLEEP_SECONDS = 2
MAX_RANDOM_DELAY_SECONDS = 3600

IP_API_ENDPOINTS = (
    ("api.ip.sb", "https://api.ip.sb/geoip"),
    ("ipapi.co", "https://ipapi.co/json/"),
    ("api.myip.com", "https://api.myip.com"),
)
