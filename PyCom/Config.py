# Replace with your own OTAA keys,
# obtainable through the "files" widget in Managed IoT Cloud.
# teus 20180221 TTN register:
#          app id 201802215971az, dev id lopyprototype20180221
#dev_eui = "xxxxxxxxxxxxxxxx"
#app_eui = "yyyyyyyyyyyyyyyy"
#app_key = "zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz"

useSSD = 'I2C'
# I2C pins
S_SDA = 'P7'  # white
S_SCL = 'P8'  # gray

# SPI pins
S_CLK  = 'P19'  # brown D0
S_MOSI = 'P23'  # white D1
S_MISO = 'P18'  # NC
# SSD pins on GPIO
S_DC   = 'P20'  # purple DC
S_RES  = 'P21'  # gray   RES
S_CS   = 'P22'  # blew   CS

