from machine import UART
from time import sleep_ms, ticks_ms

# dflt pins=(Tx-pin,Rx-pin): wiring Tx-pin -> Rx GPS module
# default UART(port=1,baudrate=9600,timeout_chars=2,pins=('P3','P4'))

last_read = 0
def readCR(serial):
  global last_read
  if not last_read:
    serial.readall()
    last_read = ticks_ms()
  last_read = ticks_ms()-last_read
  if last_read < 200 and last_read >= 0:
    sleep_ms(200-last_read)
  try:
    line = serial.readline().decode('utf-8')
  except:
    print('Read line error')
    line = ''
  last_read = ticks_ms()
  return line.strip()

simple = False
try:
  if not simple:
    import GPS_dexter as GPS
    gps = GPS.GROVEGPS(port=2,baud=9600,debug=False,pins=('P11','P12'))
    for cnt in range(25):
      data = gps.MyGPS()
      if data:
        print(data)
        gps.debug = False
      else:
        print('No satellites found for a fit')
        print('Turn on debugging')
        gps.debug = True
      sleep_ms(5000)

  else:
    ser = UART(2,baudrate=9600,timeout_chars=80,pins=('P11','P12'))
    for cnt in range(25):
      try:
        x=readCR(ser)
      except:
        print("Cannot read GPS data")
        break
      print(x)
      sleep_ms(200)

except:
  print("Unable to open GPS on port 2")

  

# output something like
'''
$GPGGA,001929.799,,,,,0,0,,,M,,M,,*4C
$GPGSA,A,1,,,,,,,,,,,,,,,*1E
$GPGSV,1,1,00*79
$GPRMC,001929.799,V,,,,,0.00,0.00,060180,,,N*46
$GPGGA,001930.799,,,,,0,0,,,M,,M,,*44
$GPGSA,A,1,,,,,,,,,,,,,,,*1E
'''
