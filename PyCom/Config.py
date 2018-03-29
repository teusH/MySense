# Replace with your own OTAA keys,
# obtainable through the "files" widget in Managed IoT Cloud.
# TTN register:
#          app id  ???, dev id ???
Network = 'TTN' # or 'WiFi'
dev_eui = "xxxxxxxxxxxxxxxx"
app_eui = "yyyyyyyyyyyyyyyy"
app_key = "zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz"

# wifi AP or Node
W_SSID = 'MySense-IOS-1'
W_PASS = 'BehoudDeParel'

# define 0 if not used
latitude  = 11.123456
longitude = 6.123456
altitude  = 23.5

useSSD = 'I2C'
# I2C pins
S_ID  = 0     # nr of I2C bus
S_SDA = 'P7'  # white shared
S_SCL = 'P8'  # gray shared

#useSSD = 'SPI'
# SPI pins
S_CLKI = 'P19'  # brown D0
S_MOSI = 'P23'  # white D1
S_MISO = 'P18'  # NC
# SSD pins on GPIO
S_DC   = 'P20'  # purple DC
S_RES  = 'P21'  # gray   RES
S_CS   = 'P22'  # blew   CS

useGPS = 2      # second uart
G_Tx = 'P11'    # white GPS Rx
G_Rx = 'P12'    # gray GPS Tx

Dust = ['','PPD42NS','SDS011','PMS7003']
useDust = 1     # first UART
dust = 3        # define 0 if not
D_Tx = 'P3'     # white Rx module
D_Rx = 'P4'     # yellow Tx module

Meteo = ['','DHT11','DHT22','BME280','BME680']
useMeteo = 'I2C'# I2C bus
meteo = 4       # define 0 if not
M_ID  = 0       # number I2C bus
M_SDA = 'P7'    # gray SDA shared
M_SCL = 'P8'    # white SCL shared
M_gBase = 231865.4 # BME680 gas base line (dflt None recalculate)
