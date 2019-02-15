# Replace with your own OTAA keys,
# obtainable through the "files" widget in Managed IoT Cloud.

# TTN register:
#          app id  ???, dev id ???
Network = 'TTN' # or 'WiFi'
# OTAA keys
dev_eui = "AAxxxxxxxxxxxxE4"
app_eui = "70xxxxxxxxxxxxD3"
app_key = "E5xxxxxxxxxxxxxxxxxxxxxxxxxxxx36"
# ABP keys
# dev_addr  = "26xxxxF1"
# nwk_swkey = "E8xxxxxxxxxxxxxxxxxxxxxxxxxxxx9C"
# app_swkey = "03xxxxxxxxxxxxxxxxxxxxxxxxxxxx02"

# wifi AP or Node
W_SSID = 'MySense-PyCom'
W_PASS = 'acacadabra'

# define 0 if not used (GPS may overwrite this)
# thisGPS = [0.0,0.0,0.0] # (LAT,LON,ALT)

# uncomment if calibration is known
# # date, reference to ?
# calibrate = {
#     "temperature": [0,1],
#     "humidity": [0,1],
#     "pressure": [0,1],
#     "gas": [0,1],
#     "gas base": 0+1.0*178644.6, # use gas calibration
#     "pm1": [0,1],
#     "pm25": [0,1],
#     "pm10": [0,1],
#}

# auto detect I2C address if module is wired/connected
# Meteo: BME280, BME680, SHT31
# meteo module is auto detected
# useMeteo = 'I2C'# I2C bus, None: disabled
# if BME680 is used:
# M_gBase = 430940.4 # BME680 gas base line (dflt None or missing: recalculate)

# use oled display None: disabled
#useSSD = 'I2C' # deprecated
#useSSD = 'SPI' # if not on I2C bus
# useDisplay = True  # or 'I2C'
# SPI pins
#S_CLKI = 'P19'  # brown D0
#S_MOSI = 'P18'  # white D1
#S_MISO = 'P16'  # NC
# SSD pins on GPIO
#S_DC   = 'P20'  # purple DC
#S_RES  = 'P21'  # gray   RES
#S_CS   = 'P17'  # blew   CS

# SDA wire is white, SCL wire is yellow or gray
# I2Cpins = [('P23','P22')] # I2C pins [(SDA,SCL), ...]
# I2Cdevices = [
#         ('BME280',0x76),('BME280',0x77), # BME serie Bosch
#         ('SHT31',0x44),('SHT31',0x45),   # Sensirion serie
#         ('SSD1306',0x3c)                 # oled display
#    ]

# uart allocations number from 0 (0,1,2) PCB nr TTL 3, 2, 1
# uart = [-1] # leave 0 free (USB TTL expansion board)  (Tx, Rx), ...
# UARTpins=[('P4','P3'),('P11','P10')] # default UART pins used by auto detect device

# useGPS = 'UART'      # None or False if not present
# G_Tx = 'P11'    # white GPS Rx
# G_Rx = 'P10'    # yellow GPS Tx

#sampling = 60   # sample time for dust
#sleep_time = 5  # interval time between samples
# calibration Taylor factors
#calibrate = None # or e.g. { 'temperature': [-6.2,1], 'pm1': [-20.0,0.5], ...}

# useDust = 'UART'     # UART, use False if not present
#dust = 'PMS7003'     # define 0 if not
# D_Tx = 'P4'     # yellow Rx module
# D_Rx = 'P3'     # white Tx module
#sampling = 60  # secs, default dust sampling timing
# Dext = '' # only Plantower/Sensirion: '_cnt' for pcs/0.1 dm3 (dflt: ug/m3)
#Dext = True   # send PM count PMnn_cnt to database server
