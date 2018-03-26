# simple test script for dust sensors
# $Id: dust_test.py,v 1.1 2018/03/26 13:25:10 teus Exp teus $
# standalone test loop
from time import time, sleep
Dust = ['','PPD42NS','SDS011','PMS7003']
try:
    from Config import useDust, dust, D_Tx, D_Rx
except:
    print("No dust module configured. Taking defaults")
    dust = 2
    useDust = 1
    D_Tx = 'P3'
    D_Rx = 'P4'
try:
  if dust == 2:
    from SDS011 import SDS011 as senseDust
  elif dust == 3:
    from PMSx003 import PMSx003 as senseDust
  else: raise OSError("unknow dust sensor index %d" % dust)
except:
  raise OSError("No dust sensor lib %s found", Dust[dust])
sampling = 60    # each sampling time take average of values
interval = 5*60  # take very 5 minutes a sample over 60 seconds

print("Using dust sensor %s, UART Rx on pin %s, Tx on pin %s" % (Dust[dust],D_Tx, D_Rx))
print("Dust module sampling %d secs, interval of measurement %d minutes" % (sampling, interval))

sensor = senseDust(port=useDust, debug=True, sample=sampling, interval=0, pins=(D_Tx,D_Rx))
errors = 0
for cnt in range(15):
    timings = time()
    try:
      # sensor.GoActive() # fan on wait 60 secs
      data = sensor.getData()
    except Exception as e:
      print("%s read error raised as: %s" % (Dust[dust],e))
      if errors > 20: break
      errors += 1
      sleep(30)
      sensor.ser.readall()
      continue
    errors = 0
    print("%s record:" % Dust[dust])
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
