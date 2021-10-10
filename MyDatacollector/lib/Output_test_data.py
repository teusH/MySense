# data record example: info (dict), record (dict), artifacts (list)
data = [
 {
 'info': {
    'count': 1,
    'id': {'project': u'ABC', 'serial': u'123456756711'},
    'last_seen': 1627828712,
    'interval': 240,
    'DATAid': u'ABC_123456767311',
    'MQTTid': u'201123456771az/1234567311',
    'valid': 1,   # null in repair
    'SensorsID': 1593163787, 'TTNtableID': 1590665967,
    'active': 1,  # kit active
    'Luftdaten': u'b41234567311',
    'WEBactive': 1,
    'sensors': [
      {  'category': u'dust',
         'fields': ((u'pm1', u'ug/m3'), (u'grain', u'um')),
         'type': u'PMS7003', 'match': u'PMS.003',
         'producer': u'Plantower',
         'ttl': 1630373493},
      {  'category': u'meteo',
         'fields': ((u'temp', u'C'), (u'aqi', u'%')),
         'type': u'BME680', 'match': u'BME680',
         'producer': u'Bosch',
         'ttl': 1630373493},
      {  'category': u'location',
         'fields': ((u'geohash', u'geohash'), (u'altitude', u'm')),
         'type': u'NEO-6', 'match': u'NEO(-[5-8])*',
         'producer': u'NEO',
         'ttl': 1630373493},
      ],
    'location': u'u1hjtzwmqd',
    'unknown_fields': ['ToDo'],
    'FromFILE': True,
    'gtw': [[u'gateway_sint_anthonis_001', [-103, -103, -103], [7.75, 7.75, 7.75]]],
    'check': {'rv': [20,100.0],'temp': 0 },
    'CalRefs': ['SDS011'],
    'ttl': 1630351881,
  },
 'record': {
    'timestamp': 1629463231, 'version': '2.0.1',
    'data': {
       'BME680':  [(u'temp', 12.8)],
       'PMS7003': [(u'pm1', 1.8),(u'pm25', 2.5)],   # has unknown field pm25
    },
  },
 'artifacts': [  # all known ones
    'Forward data',                   'Start throttling kit: %%s',
    'Skip data. Throttling kit.',     'Unknown kit: %%s',
    'Unregistered kit: %%s',           'MQTT id:%%s, %%s kit. Skipped.',
    'Raised event: %%s.',              'Updated home location',
    'Kit removed from home location', 'New kit',
    'Restarted kit',                  'Out of Range sensors: %%s',
    'Static value sensors: %%s',       'Change of sensor types: %%s -> %%s',
    'Measurement data format error',  'No input resources',
    'End of iNput Data',              'Fatal error on subscriptions',],
 },
 {
  'info':
    {'count': 1, 'calRefs':['SDS011'],'DATAid': u'ABC_12345674b311', 'check': {u'rv': [69.3, 0], u'luchtdruk': [1000, 0], u'pm10': [4.8, 0], u'temp': [12.8, 0], u'pm25': [4.8, 0]}, 'TTNtableID': 1590665967, 'valid': 1, 'ttl': 1630679363, 'WEBactive': 1, 'id': {'project': u'ABC', 'serial': u'12345674b311'}, 'interval': 240, 'SensorsID': 1593163787, 'MQTTid': u'201802215971az/bwlvc-b311', 'location': u'u1hjtzwmqd', 'gtw': [[u'gateway_sint_anthonis_001', [-103, -103, -103], [7.75, 7.75, 7.75]]], 'active': 1, 'Luftdaten': u'b4e62df4b311', 'unknown_fields': [], 'sensors': [{'category': u'location', 'fields': ((u'geohash', u'geohash'), (u'altitude', u'm')), 'type': u'NEO-6','match': u'NEO(-[5-8])*','producer': u'NEO', 'ttl': 1630700963}, {'category': u'meteo', 'fields': ((u'temp', u'C'), (u'rv', u'%'), (u'luchtdruk', u'hPa'), (u'gas', u'kOhm'), (u'aqi', u'%')), 'type': u'BME680','match':u'BME680','producer': u'Bosch', 'ttl': 1630700963}, {'category': u'dust', 'fields': ((u'pm1', u'ug/m3'), (u'pm25', u'ug/m3', [-1.619,1/1.545]), (u'pm10', u'ug/m3',[-3.76,1/1.157]), (u'pm03_cnt', u'pcs/dm3'), (u'pm05_cnt', u'pcs/dm3'), (u'pm1_cnt', u'pcs/dm3'), (u'pm25_cnt', u'pcs/dm3'), (u'pm5_cnt', u'pcs/dm3'), (u'pm10_cnt', u'pcs/dm3'), (u'grain', u'um')), 'type':u'PMS7003','match':u'PMS.003','producer': u'Plantower', 'ttl': 1630700963}], 'FromFILE': True, 'last_seen': 1627828712},
  'record':
    {'timestamp': 1629463231, 'data': {'BME680': [(u'rv', 69.3), (u'luchtdruk', 1000), (u'gas', 32644), (u'temp', 12.8)], 'PMS7003': [('pm05_cnt', 465.4), (u'pm10', 4.8), ('pm25_cnt', 660.4), ('pm5_cnt', 666.0), (u'grain', 0.5), ('pm1_cnt', 639.2), (u'pm25', 4.8), ('pm10_cnt', 666.0), (u'pm1', 1.8)]}, 'id': {'project': u'ABC', 'serial': u'12345674b311'}},
  'artifacts':
    ['Forward data'],
},
{
  'info':
    {'count': 1,'calRefs':['SDS011'],'DATAid': u'ABC_1234567c8cc4', 'check': {u'rv': [45.0, 0], u'luchtdruk': [1015, 0], u'pm10': [6.6, 0], u'temp': [27.4, 0], u'pm25': [6.6, 0]}, 'TTNtableID': 1590665975, 'valid': 1, 'ttl': 1630679466, 'WEBactive': 1, 'id': {'project': u'ABC', 'serial': u'1234567c8cc4'}, 'interval': 240, 'SensorsID': 1592422622, 'MQTTid': u'201802215971az/bwlvc-8cc4', 'location': u'u1hjy0dvxm', 'gtw': [[u'gateway_sint_anthonis_001', [-113, -113, -113], [6.5, 6.5, 6.5]]], 'active': 1, 'Luftdaten': u'cc50e39c8cc4', 'unknown_fields': [], 'sensors': [{'category': u'dust', 'fields': ((u'pm1', u'ug/m3'), (u'pm25', u'ug/m3',[-1.619,1/1.545]), (u'pm10', u'ug/m3',[-3.76,1/1.157]), (u'pm03_cnt', u'pcs/dm3'), (u'pm05_cnt', u'pcs/dm3'), (u'pm1_cnt', u'pcs/dm3'), (u'pm25_cnt', u'pcs/dm3'), (u'pm5_cnt', u'pcs/dm3'), (u'pm10_cnt', u'pcs/dm3'), (u'grain', u'um')), 'type': u'PMS7003','match':u'PMS.003','producer': u'Plantower', 'ttl': 1630701066}, {'category': u'meteo', 'fields': ((u'temp', u'C'), (u'rv', u'%'), (u'luchtdruk', u'hPa')), 'type': u'BME280','match':u'BME280','producer': u'Bosch', 'ttl': 1630701066}, {'category': u'location', 'fields': ((u'geohash', u'geohash'), (u'altitude', u'm')), 'type': u'NEO-6','match':u'NEO(-[5-8])*','producer': u'NEO', 'ttl': 1630701066}], 'FromFILE': True, 'last_seen': 1627828671},
  'record':
    {'timestamp': 1629463216, 'data': {'BME280': [(u'rv', 45.0), (u'luchtdruk', 1015), (u'temp', 27.4)], 'NEO-6': [(u'altitude', 19.5), ('geohash', 'u1hjy0dwgy4')], 'PMS7003': [('pm05_cnt', 802.8), (u'pm10', 6.6), ('pm25_cnt', 1141.7), ('pm5_cnt', 1143.0), (u'grain', 0.5), ('pm1_cnt', 1135.0), (u'pm25', 6.6), ('pm10_cnt', 1143.0), (u'pm1', 5.4)]}, 'id': {'project': u'ABC', 'serial': u'1234567c8cc4'}},
  'artifacts':
    ['Forward data'],
},
{
  'info':
    {'count': 1,'calRefs':['SDS011'],'DATAid': u'ABC_123456735cb8', 'check': {u'luchtdruk': [745, 0], u'pm10': [4.0, 0], u'temp': [21.3, 0], u'pm25': [3.9, 0]}, 'TTNtableID': 1584611241, 'valid': 1, 'ttl': 1630679505, 'WEBactive': 1, 'id': {'project': u'ABC', 'serial': u'123456735cb8'}, 'interval': 240, 'SensorsID': 1584611845, 'MQTTid': u'201802215971az/salk-20190614', 'location': u'u1hjx4xukm', 'gtw': [], 'active': 1, 'Luftdaten': u'807d3a935cb8', 'unknown_fields': [], 'sensors': [{'category': u'dust', 'fields': ((u'pm1', u'ug/m3'), (u'pm25', u'ug/m3',[-1.619,1/1.545]), (u'pm10', u'ug/m3',[-3.76,1/1.157]), (u'pm03_cnt', u'pcs/dm3'), (u'pm05_cnt', u'pcs/dm3'), (u'pm1_cnt', u'pcs/dm3'), (u'pm25_cnt', u'pcs/dm3'), (u'pm5_cnt', u'pcs/dm3'), (u'pm10_cnt', u'pcs/dm3'), (u'grain', u'um')), 'type': u'PMS7003','match':u'PMS.003','producer': u'Plantower', 'ttl': 1630701105}, {'category': u'meteo', 'fields': ((u'temp', u'C'), (u'rv', u'%'), (u'luchtdruk', u'hPa'), (u'gas', u'kOhm'), (u'aqi', u'%')), 'type': u'BME680','match':u'BME680','producer': u'Bosch', 'ttl': 1630701105}, {'category': u'location', 'fields': ((u'geohash', u'geohash'), (u'altitude', u'm')), 'type': u'NEO-6','match':u'NEO(-[5-8])*','producer': u'NEO', 'ttl': 1630701105}], 'FromFILE': True, 'last_seen': 1627828746},
  'record':
    {'timestamp': 1629463251, 'net': {'TTN_id': u'1234567190614', 'TTN_app': u'201802215971az', 'type': 'TTNV2', 'gateways': [{'geohash': 'u1hjx4xkt72', 'rssi': -64, 'gtw_id': u'eui-000080029c641f55', 'snr': 11}]}, 'data': {'NEO-6': [(u'altitude', 18.4), ('geohash', 'u1hjx4xkjur')], 'BME680': [(u'aqi', 8.5), (u'luchtdruk', 745), (u'gas', 278), (u'temp', 21.3)], 'PMS7003': [('pm05_cnt', 2479.4), (u'pm10', 4.0), ('pm25_cnt', 2900.7), ('pm5_cnt', 6179.3), (u'grain', 0.2), ('pm1_cnt', 2880.2), (u'pm25', 3.9), ('pm10_cnt', 6179.7), (u'pm1', 3.6)]}, 'id': {'project': u'ABC', 'serial': u'123456735cb8'}},
  'artifacts':
    ['Forward data'],
},
]
