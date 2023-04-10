# Station ID
STATION_ID = "<Your Station ID>"

# I2C pins
SCL_PIN = 22   # D22
SDA_PIN = 21   # D21

# Error led pin
LED_PIN = 2    # onboard led
LED_ON = 0     # inverse logic     
LED_OFF = 1

# Debug (LOW for debugging)
DEBUG_PIN = 5  # D5

# Battery voltage monitoring pin
VBAT_PIN = 33

# temperature units (Fahrenheit or Celsius)
FAHRENHEIT = False

# interval between measurements (seconds)
INTERVAL = 900

# wifi credentials
SSID = "<Your network SSID>"
PASS = "<Your network password>"
MAX_TRIES = 20

# OpenWeather service
OPENWEATHERMAP_API = "<Your OpenWeather API key>"
OPENWEATHERMAP_CITY = "<Your OpenWeather City\,2-letter landcode"  # escape comma with backslash
OPENWEATHERMAP_LAT = "<Your OpenWeather City latitude>"      
OPENWEATHERMAP_LON = "<Your OpenWeather City longitude>"      
OPENWEATHERMAP_URL = "https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={api}"

# MQTT variables
MQTT_HOST = "<IP address MQTT host>"
MQTT_TOPIC = "weatherdata"
MQTT_USER = "<Your MQTT user>"
MQTT_PASS = "<Your MQTT password>"