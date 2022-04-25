'''
    Weather Station (c)2022 Effevee
    
    A Battery Powered Weather Station with Temperature, Humidity, Atmosphetic Pressure and Light sensor.
    Weather predictons are fetched from OpenWeatherMap.org, sensor readings are uploaded to a MQTT broker backend.
    The backend Raspberry Pi sends the MQTT data with Telegraf to an Influxdb database. A Influxdb dashboard visualises the weather data.
    All software on the backend is setup with Docker containers.
    
    Hardware : - DOIT ESP32 DEVKit v1 dev board
               - AM2320 temperature and humidity sensor board
               - BMP180 temperature, pressure and altitude sensor board
               - BH1750 light sensor board
    
    Software : MicroPython code developped by Effevee
    
    Wiring :    ESP32     AM2320     BMP180     BH1750FVI     OLED     Debug   18650 battery
                Pin GPIO    Pin        Pin         Pin        Pin       ON     voltage monitor
                --------   -----     ------     ---------     ----     -----   ---------------
                3V           1         VIN         VCC        VCC
                GND          3         GND         GND        GND
                D22  22      4         SCL         SCL        SCL
                D21  21      2         SDA         SDA        SDA
                D5   5                                                  GND
                D33  33                                                        27k/100k divider
                
    More details on https://github.com/effevee/effevees_weerstation
    
'''

####################################################################################
# Libraries
####################################################################################

from machine import Pin, SoftI2C, ADC, deepsleep, reset
import config
import network
import utime
import json
import sys
import urequests
from umqtt.simple import MQTTClient
from am2320 import AM2320
from bmp180 import BMP180
from bh1750 import BH1750

####################################################################################
# Error routine
####################################################################################

def show_error():
    ''' visual display of error condition - flashing onboard LED '''
    
    # led pin object
    led = Pin(config.LED_PIN, Pin.OUT)
    
    # flash 3 times
    for i in range(3):
        led.value(config.LED_ON)
        utime.sleep(0.5)
        led.value(config.LED_OFF)
        utime.sleep(0.5)
    

####################################################################################
# Check debug on
####################################################################################

def debug_on():
    ''' check if debugging is on - debug pin LOW '''
    
    # debug pin object
    debug = Pin(config.DEBUG_PIN, Pin.IN, Pin.PULL_UP)
    
    # check debug pin
    if debug.value() == 0:
        # print('Debug mode detected.')
        return True
    
    return False


####################################################################################
# Connect to Wifi
####################################################################################

def connect_wifi():
    ''' connect the µcontroller to the local wifi network '''
    
    # disable AP mode of µcontroller
    ap_if = network.WLAN(network.AP_IF)
    ap_if.active(False)
    
    # enable STAtion mode of µcontroller
    sta_if = network.WLAN(network.STA_IF) 

    # if no wifi connection exist
    if not sta_if.isconnected():
        
        # debug message
        print('connecting to WiFi network...')
        
        # activate wifi station
        sta_if.active(True)
        
        # try to connect to the wifi network
        sta_if.connect(config.SSID, config.PASS)  
        
        # keep trying for a number of times
        tries = 0
        while not sta_if.isconnected() and tries < config.MAX_TRIES:  
            
            # show progress
            print('.', end='')
            
            # wait
            utime.sleep(1)
            
            # update counter
            tries += 1

    # show network status 
    if sta_if.isconnected():
        print('')
        print('connected to {} network with ip address {}' .format(config.SSID, sta_if.ifconfig()[0]))
        # return WiFi signal strength (Received Signal Strength Indicator)
        return sta_if.status('rssi')

    else:
        print('')
        print('no connection to {} network' .format(config.SSID))
        # no WiFi
        raise RuntimeError('WiFi connection failed')
        return 0

            
####################################################################################
# Get current weather data from OpenWeather.org
####################################################################################

def get_weather_data():
    ''' get current weather data from OpenWeather.org.
        return results in dictionary with following data :
        - 'temp' : current/day temperature
        - 'hum' : humidity
        - 'pres' : pressure  '''
    
    # debug message
    print('Invoking OpenWeather URL webhook')
    
    # webhook url
    url = config.OPENWEATHERMAP_URL.format(lat=config.OPENWEATHERMAP_LAT, lon=config.OPENWEATHERMAP_LON, api=config.OPENWEATHERMAP_API)
    
    # send GET request
    response = urequests.get(url)
    
    # evaluate response
    if response.status_code < 400:
        print('Webhook OpenWeather URL success')

    else:
        print('Webhook OpenWeather URL failed')
        raise RuntimeError('Webhook OpenWeather URL failed')
    
    # get the data in json format
    today = response.json()
    
    # debug message
    if debug_on():
        print('OpenWeather URL data')
        print(today)

    # extract data from OpenWeather dictionary
    ow_temp = temperature_2_unit(today['main']['temp'] - 273.15)  # openweather temperatures in Kelvin 
    ow_hum = today['main']['humidity'] 
    ow_pres = today['main']['pressure']
    
    # debug message
    if debug_on():
        print('')
        print('OpenWeather T: {:.0f} {} - H: {:.0f} % - P: {:.0f} hPa' .format(ow_temp, 'F' if config.FAHRENHEIT else 'C', ow_hum, ow_pres))
    
    return {'ow_temp': ow_temp, 'ow_hum': ow_hum, 'ow_pres': ow_pres}
    
    
####################################################################################
# Temperature in Celsium or Fahrenheit
####################################################################################
def temperature_2_unit(celsius):
    ''' convert the temperature in Celsius to Fahrenheit is necessary '''
    
    # convert if necessary
    if config.FAHRENHEIT:
        return celsius * 9 / 5 + 32
    else:
        return celsius
    

####################################################################################
# Get sensor readings
####################################################################################

def get_sensor_readings():
    ''' get readings from all sensors and return them in a dictionary '''
    
    # debug message
    print('Getting sensor readings')
    
    # I2C object
    i2c = SoftI2C(scl=Pin(config.SCL_PIN), sda=Pin(config.SDA_PIN), freq=100000)
    
    ################################################################################
    # AM2320 temperature and humidity sensor
    ################################################################################
    am2320 = AM2320(i2c)
    
    # check if AM2320 sensor is detected
    i2c.scan()  # first scan to wake up sensor
    if 92 not in i2c.scan():
        raise RuntimeError('Cannot find AM2320 sensor')
    
    # read AM2320 sensor
    am2320.measure()
    am2320_temp = temperature_2_unit(am2320.temperature())
    am2320_hum = am2320.humidity()
    
    if debug_on():
        print('')
        print('AM2320      T: {:.0f} {} - H: {:.0f} %' .format(am2320_temp, 'F' if config.FAHRENHEIT else 'C', am2320_hum))

    ################################################################################
    # BMP180 temperature, pressure and altitude sensor
    ################################################################################
    bmp180 = BMP180(i2c)

    # check if BMP180 sensor is detected
    if 119 not in i2c.scan():
        raise RuntimeError('Cannot find BMP180 sensor')

    # read BMP180 sensor
    bmp180_temp = temperature_2_unit(bmp180.temperature)
    bmp180_pres = bmp180.pressure/100  # values in Pa, divide by 100 for hPa
    bmp180_alt = bmp180.altitude
    
    if debug_on():
        print('BMP180      T: {:.0f} {} - P: {:.0f} hPa - A: {:.0f} m' .format(bmp180_temp, 'F' if config.FAHRENHEIT else 'C', bmp180_pres, bmp180_alt))

    ################################################################################
    # BH1750 light sensor
    ################################################################################
    bh1750 = BH1750(i2c)
    
    # check if BH1750 sensor is detected
    if 35 not in i2c.scan():
        raise RuntimeError('Cannot find BH1750 sensor')
    
    # read BH1750 sensor
    bh1750_lum = bh1750.luminance(BH1750.ONCE_HIRES_1)
    
    if debug_on():
        print('BH1750FVI   L: {:.0f} lux' .format(bh1750_lum))

    ################################################################################
    # battery voltage reading
    ################################################################################
    adc = ADC(Pin(config.VBAT_PIN))
    adc.atten(ADC.ATTN_11DB)  # range 0-3.3V
        
    # read battery voltage (reduce battery voltage from max 4.2V to 3.3V with resistance divider 27k/100k)
    # adc read_u16 returns 16bit value (0-65535)
    bat_volt = 3.3 * 1.27 * (adc.read_u16() / 2**16)
    
    if debug_on():
        print('Battery     V: {:.2f} Volt' .format(bat_volt))
    
    return {'am2320_temp': am2320_temp, 'am2320_hum': am2320_hum, 'bmp180_temp': bmp180_temp, 'bmp180_pres': bmp180_pres, 'bmp180_alt': bmp180_alt, 'bh1750_lum': bh1750_lum, 'bat_volt': bat_volt}
    

####################################################################################
# Upload readings to MQTT broker
####################################################################################

def log_readings(ow_data, sensor_data, wifi_rssi):
    ''' upload sensor readings to MQTT broker '''
    
    # debug message
    print('Upload readings to MQTT broker')
    
    # extract readings to upload
    ow_temp = ow_data['ow_temp']
    ow_hum  = ow_data['ow_hum']
    ow_pres = ow_data['ow_pres']
    ac_temp = sensor_data['am2320_temp']
    ac_hum  = sensor_data['am2320_hum']
    ac_pres = sensor_data['bmp180_pres']
    ac_lum  = sensor_data['bh1750_lum']
    ac_batv = sensor_data['bat_volt']
    ac_rssi = wifi_rssi
    
    # construct the payload for influxdb_v2
    # <measurement>[,<tag_key>=<tag_value>[,<tag_key>=<tag_value>]] <field_key>=<field_value>[,<field_key>=<field_value>] [<timestamp>]
    payload = ''
    payload += 'forecasts,source={},location={} ow_temp={},ow_hum={},ow_pres={} \r\n' .format('OpenWeatherMap', str(config.OPENWEATHERMAP_CITY), str(ow_temp), str(ow_hum), str(ow_pres))
    payload += 'actuals,source={},location={} ac_temp={},ac_hum={},ac_pres={},ac_lum={},ac_batv={},ac_rssi={} \r\n' .format(config.STATION_ID, str(config.OPENWEATHERMAP_CITY), str(ac_temp), str(ac_hum), str(ac_pres), str(ac_lum), str(ac_batv), str(ac_rssi))
   
    try:
        # instantiate MQTT object
        client = MQTTClient('effevees_weerstation', config.MQTT_HOST, keepalive=30)
    
        # connect to MQTT broker
        client.connect()
        
        # publish payload
        client.publish(config.MQTT_TOPIC, payload)
        
        # disconnect client
        client.disconnect()
        
    except Exception as exc:
        sys.print_exception(exc)
        show_error()
        
    # debug message
    if debug_on():
        print('MQTT publish : {}' .format(payload))
    

####################################################################################
# deepsleep to save battery
####################################################################################

def deepsleep_till_next_cycle():
    ''' put the µcontroller into deepsleep to save battery power for config.INTERVAL seconds. '''
    
    # debug message
    print('Going into deepsleep for {} seconds...' .format(config.INTERVAL))
    utime.sleep(2)
   
    # goto deepsleep - time in milliseconds !
    deepsleep(config.INTERVAL * 1000)
    
    
####################################################################################
# Main program
####################################################################################

def run():
    ''' main program logic '''
    
    try:
        
        # connect to WiFi network
        wifi_rssi = connect_wifi()
        
        # get OpenWeatherMap data
        ow_data = get_weather_data()
        
        # get sensor readings
        sensor_data = get_sensor_readings()
        
        # upload readings to MQTT broker
        log_readings(ow_data, sensor_data, wifi_rssi)

    except Exception as exc:
        sys.print_exception(exc)
        show_error()
        # reset to try again
        utime.sleep(5)
        reset()
    
    # goto deepsleep if not in debugging mode
    if not debug_on():
        deepsleep_till_next_cycle()
        

run()
