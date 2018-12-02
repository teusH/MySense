# simple test script for dust sensors
# $Id: dust_test.py,v 1.8 2018/12/02 15:45:12 teus Exp teus $
# standalone test loop

__version__ = "0." + "$Revision: 1.8 $"[11:-2]
__license__ = 'GPLV4'

from time import time, sleep
uart = [-1]
try:
    from Config import uart
except: pass
try:
    from Config import useDust, dust, D_Tx, D_Rx
except:
    import whichUART
    which = whichUART.identifyUART(uart=uart, debug=True)
    try:
        D_Tx = which.D_TX; D_Rx = which.D_Rx
        dust = which.DUST; useDust = True
    except: useDust = False
if not useDust: raise ValueError("Dust sensor is disabled")
try:
  if dust[:3] == 'SDS':
    from SDS011 import SDS011 as senseDust
  elif dust[:3] == 'PMS':
    from PMSx003 import PMSx003 as senseDust
  else: raise OSError("unknow dust sensor index %d" % dust)
except:
  raise OSError("No dust sensor lib %s found" % dust)

sampling = 60    # each sampling time take average of values
interval = 5*60  # take very 5 minutes a sample over 60 seconds

try:
  from Config import calibrate
except:
  calibrate = None

print("Dust: using sensor %s, UART %d Rx on pin %s, Tx on pin %s" % (dust,len(uart),D_Tx, D_Rx))
print("Dust module sampling %d secs, interval of measurement %d minutes" % (sampling, interval/60))

sensor = senseDust(port=len(uart), debug=True, sample=sampling, interval=0, pins=(D_Tx,D_Rx), calibrate=calibrate)
if sensor and (sensor.mode != sensor.NORMAL): sensor.Normal()
errors = 0
for cnt in range(15):
    timings = time()
    try:
      # sensor.GoActive() # fan on wait 60 secs
      data = sensor.getData()
    except Exception as e:
      print("%s read error raised as: %s" % (dust,e))
      if errors > 20: break
      errors += 1
      sleep(30)
      sensor.ser.readall()
      continue
    errors = 0
    print("%s record:" % dust)
    print(data)
    timings = interval -(time()-timings)
    if timings > 0:
        print("Sleep now for %d seconds" % timings)
        try:
            sensor.Standby()
            if timings > 60: sleep(timings-60)
            sensor.Normal() # fan on measuring
            sleep(60)
            sensor.mode = 0 # active
        except:
            errors += 1
            sleep(60)
