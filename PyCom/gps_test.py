from machine import UART
from time import sleep_ms, ticks_ms

__version__ = "0." + "$Revision: 1.8 $"[11:-2]
__license__ = 'GPLV4'

# dflt pins=(Tx-pin,Rx-pin): wiring Tx-pin -> Rx GPS module
# default UART(port=1,baudrate=9600,timeout_chars=2,pins=('P3','P4'))

try:
  from Config import useGPS
except:
  useGPS = False

uart = [-1]
try:
  from Config import uart
except: pass

try:
  from Config import G_Tx, G_Rx
except:
  import whichUART
  which = whichUART.identifyUART(uart=uart,debug=True)
  try:
    G_Tx = which.G_TX; G_Rx = which.G_RX
    useGPS = which.GPS
  except:
    useGPS = False

if not useGPS: raise OSError("GPS not configured")

print('GPS: using %s nr %d: Rx->pin %s, Tx->pin %s' % (useGPS,len(uart),G_Tx,G_Rx))

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

try:
    print("test GPS raw:")
    ser = UART(1,baudrate=9600,timeout_chars=80,pins=(G_Tx,G_Rx))
    for cnt in range(10):
      try:
        x=readCR(ser)
      except:
        print("Cannot read GPS data")
        break
      print(x)
      sleep_ms(200)

    print("test using GPS Dexter:")
    import GPS_dexter as GPS
    # UART Pins pins=(Tx,Rx) default Tx=P3 and Rx=P4
    gps = GPS.GROVEGPS(port=1,baud=9600,debug=False,pins=(G_Tx,G_Rx))
    for cnt in range(10):
      data = gps.MyGPS()
      if data:
        print("Date/time: %s/%s" % (data['date'],data['timestamp']))
        print("lon %.6f, lat %.6f, alt %.2f m" % (data['longitude'],data['latitude'],data['altitude']))
        # print(data)
        gps.debug = False
      else:
        print('No satellites found for a fit')
        print('Turn on debugging')
        gps.debug = True
      sleep_ms(5000)

except:
    print("Unable to get GPS data  on port %s" % useGPS)



# raw  GPS output something like
'''
$GPGGA,001929.799,,,,,0,0,,,M,,M,,*4C
$GPGSA,A,1,,,,,,,,,,,,,,,*1E
$GPGSV,1,1,00*79
$GPRMC,001929.799,V,,,,,0.00,0.00,060180,,,N*46
$GPGGA,001930.799,,,,,0,0,,,M,,M,,*44
$GPGSA,A,1,,,,,,,,,,,,,,,*1E
'''
