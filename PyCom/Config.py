# Replace with your own OTAA keys,
# obtainable through the "files" widget in Managed IoT Cloud.
# TTN register:
#          app id  ???, dev id ???
Network = 'TTN' # or 'WiFi'
dev_eui = "xxxxxxxxxxxxxxxx"
app_eui = "yyyyyyyyyyyyyyyy"
app_key = "zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz"

# wifi AP or Node
W_SSID = 'MySense-PyCom'
W_PASS = 'acacadabra'

# define 0 if not used (GPS may overwrite this)
thisGPS = [0.0,0.0,0.0] # (LAT,LON,ALT)

useSSD = 'I2C'
# I2C pins
S_SDA = 'P7'  # white shared
S_SCL = 'P8'  # gray shared

#useSSD = 'SPI'
# SPI pins
#S_CLKI = 'P19'  # brown D0
#S_MOSI = 'P23'  # white D1
#S_MISO = 'P18'  # NC
# SSD pins on GPIO
#S_DC   = 'P20'  # purple DC
#S_RES  = 'P21'  # gray   RES
#S_CS   = 'P22'  # blew   CS

useGPS = 'UART'      # uart
G_Tx = 'P11'    # white GPS Rx
G_Rx = 'P12'    # gray GPS Tx

Dust = ['','PPD42NS','SDS011','PMS7003']
useDust = 'UART'     # UART
dust = Dust.index('PMS7003')        # define 0 if not
D_Tx = 'P3'     # white Rx module
D_Rx = 'P4'     # yellow Tx module

Meteo = ['','DHT11','DHT22','BME280','BME680']
useMeteo = 'I2C'# I2C bus
meteo = Meteo.index('BME680')       # define 0 if not
M_SDA = 'P7'    # gray SDA shared
M_SCL = 'P8'    # white SCL shared
M_gBase = 231865.4 # BME680 gas base line (dflt None: recalculate)
