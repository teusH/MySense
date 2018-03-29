# from https://github.com/DexterInd/GrovePi
# Software/Python/dexter_gps
# changed for micropython
# $Id: GPS_dexter.py,v 1.6 2018/03/29 18:18:20 teus Exp teus $

import re
try:
  from machine import UART, RTC
  from time import sleep_ms, ticks_ms
except:
  from const import UART, sleep_ms, ticks_ms  # not micropython
  RTC = None

patterns=["$GPGGA",
  "/[0-9]{6}\.[0-9]{2}/", # timestamp hhmmss.ss
  "/[0-9]{4}.[0-9]{2,/}", # latitude of position
  "/[NS]",  # North or South
  "/[0-9]{4}.[0-9]{2}", # longitude of position
  "/[EW]",  # East or West
  "/[012]", # GPS Quality Indicator
  "/[0-9]+", # Number of satellites
  "/./", # horizontal dilution of precision x.x
  "/[0-9]+\.[0-9]*/" # altitude x.x
  ]

class GROVEGPS:
  # dflt pins=(Tx-pin,Rx-pin): wiring Tx-pin -> Rx GPS module
  def __init__(self,port=1,baud=9600,debug=False,pins=('P3','P4')):
    try:
      self.ser = UART(port,baudrate=baud,pins=pins)
    except:
      self.ser = UART(port,baudrate=baud)
    self.ser.readall()
    self.raw_line = ""
    self.gga = []
    self.validation =[] # contains compiled regex
    self.debug = debug
    self.last_read = 0
    self.date = 0

    # compile regex once to use later
    for i in range(len(patterns)-1):
      self.validation.append(re.compile(patterns[i]))

    self.clean_data()
    # self.get_date()  # attempt to get a date from GPS.

  def DEBUG(self,in_str):
    if self.debug:
      print(in_str)

  # convert to string and if needed wait a little
  def readCR(self,serial):
    if not self.last_read:
      serial.readall()
      self.last_read = ticks_ms()
    self.last_read = ticks_ms()-self.last_read
    if self.last_read < 200 and self.last_read >= 0:
      sleep_ms(200-self.last_read)
    line = ''
    try:
      line = serial.readline().decode('utf-8')
    except:
      if self.debug: print('Read line error')
    self.last_read = ticks_ms()
    return line.strip()


  def clean_data(self):
    '''
    clean_data:
    ensures that all relevant GPS data is set to either empty string
    or -1.0, or -1, depending on appropriate type
    This occurs right after initialisation or
    after 50 attemps to reach GPS
    '''
    self.timestamp = ""
    self.lat = -1.0    # degrees minutes and decimals of minute
    self.NS = ""
    self.lon = -1.0
    self.EW = ""
    self.quality = -1
    self.satellites = -1
    self.altitude = -1.0

    self.latitude = -1.0  #degrees and decimals
    self.longitude = -1.0
    self.fancylat = ""  #

  def read(self):
    '''
    Attempts 50 times at most to get valid data from GPS
    Returns as soon as valid data is found
    If valid data is not found, then clean up data in GPS instance
    '''
    valid = False
    for i in range(50):
      # sleep_ms(500)
      self.raw_line = self.readCR(self.ser)
      if self.validate(self.raw_line):
        valid = True
        break;

    if valid:
      return self.gga
    else:
      self.clean_data()
      return []

  # use GPS date/time to update RTC time
  def UpdateRTC(self):
    for i in range(20):
      if self.date: break
      self.read()
    day = int(self.date)
    if not day:
      return False
    hours = int(float(self.timestamp))
    millis = int(float(self.timestamp)*1000)%1000
    try:
      rtc = RTC()
      rtc.init((2000+(day%100),(day//100)%100,day//10000,hours//10000,(hours//100)%100,hours%100,millis%1000))
    except:
      return False
    return True

  def validate(self,in_line):
    '''
    Runs regex validation on a GPGAA sentence.
    Returns False if the sentence is mangled
    Return True if everything is all right and sets internal
    class members.
    '''
    if in_line == "":
      return False
    if in_line[:6] == "$GPRMC":  # got time/date line
      ind = in_line.split(',')
      if (len(ind) < 9) or (len(ind[9]) != 6): return False
      self.date = ind[9]
      return False
    if in_line[:6] != "$GPGGA":
      return False

    self.gga = in_line.split(",")
    self.DEBUG(self.gga)

    # Sometimes multiple GPS data packets come into the stream.
    # Take the data only after the last '$GPGGA' is seen
    try:
      ind=self.gga.index('$GPGGA',5,len(self.gga))
      self.gga=self.gga[ind:]
    except ValueError:
      pass

    if len(self.gga) != 15:
      self.DEBUG("Failed: wrong number of parameters ")
      self.DEBUG(self.gga)
      return False

    for i in range(len(self.validation)-1):
      if len(self.gga[i]) == 0:
        self.DEBUG("Failed: empty string %d"%i)
        return False
      test = self.validation[i].match(self.gga[i])
      if test == False:
        self.DEBUG("Failed: wrong format on parameter %d"%i)
        return False
      else:
        self.DEBUG("Passed %d"%i)

    try:
      self.timestamp = self.gga[1]
      self.lat = float(self.gga[2])
      self.NS = self.gga[3]
      self.lon = float(self.gga[4])
      self.EW = self.gga[5]
      self.quality = int(self.gga[6])
      self.satellites = int(self.gga[7])
      self.altitude = float(self.gga[9])

      self.latitude = self.lat // 100 + self.lat % 100 / 60
      if self.NS == "S":
        self.latitude = - self.latitude
      self.longitude = self.lon // 100 + self.lon % 100 / 60
      if self.EW == "W":
        self.longitude = -self.longitude
    except ValueError:
      self.DEBUG( "FAILED: invalid value")

    return True

  def MyGPS(self):
    for cnt in range(20):
      self.read()
      if self.quality > 0: break
    if self.quality < 1:
      return None
    self.UpdateRTC()
    # 4 decimals: resolution of ~ 11 meter
    return {
      'date': self.date,
      'timestamp': self.timestamp,
      'longitude': round(self.longitude,4),
      'latitude': round(self.latitude,4),
      'altitude': int(self.altitude) }


# gps = GROVEGPS(port=1,baud=9600,timeout=0,debug=False,pins=('P3','P4'))
# data = gps.read()
# print(data)
