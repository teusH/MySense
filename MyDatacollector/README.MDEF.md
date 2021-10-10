# measurement data exchange format
* WORK in PROGRESS*
Based on the proposal dd 25 May 2021 in Meet je Stad, Amersfoort meeting.

do not wait till it is too late
The following only smells like Open Data Format (O-DF) from ‘the Open Group’

# Draft/proposal of Measurement Data Exchange Format for air quality measurements

The (Open) Measurement Data Exchange Format (draft MDEF 2021) is a proposal to uniform the measurement data exchange between organisations as well to be used as internal format within data acquision software modules like MySense MyDatacollector data acquision software.

The process to come with the MDEF format is just in a phase of draft: initial definition via the route of real world implementation.

The format needs to be highly optional and probably staefull. Exchange data only when needed so. Probably on request and asynchronously.

Use defaults.

# MDEF format prerequisites

data format requirements
human readable, easy to implement, dynamic

## what is needed:
- timestamp
- version
- key translation table toobtain freedom of namencalture,
- definition of defaults,
- and ???

## Secondly the meta information of sensors, sensor types, location of measurement kit, etc.

Meta data:
- home location (preferably geohash)
- kit identifaction (project, serial nr)
- version
- sensor configuration
- sample and timing,
- definition of defaults defaults
- calibration, corrections,
- artifacts encountered
...

## Thirdly the measurements:

Measurement data:
- timestamps,
- sensor types, measurements, unit of measurement
- 1+ sensors of one type
- measurement location
- timestamp
...

# MDEF format description by real life examples

A real world example to start with?
The following  examples uses Python data format. The json data format is similar but it will loose some object language functionality as eg the difference between a list and tuple.
The implementation should be able to mix dict type data formats with list/tuple type of data formats.

## header data part (optional):
`
{
"id”: { “project”: “SAN”, “serial”: “78CECEA5167524” },
"timestamp": 1621862416, // or “dateTime”: “2021-05-24T15:20+02:00”,
“keys”: { “timestamp”: “unixTime”, “rv”: “RH”, “lat”: “latitude”, “, … },  // and/or “keyID”: “nl”,
“units”: { “temperature”: “C”, “altitude”: “m”, … },                                // and/or “unitsID”:”nl”, ...
``

## meta data part:
`{
"meta": {
      "dust": "PMSx003",
      "geolocation": { "lat": 51.54046, "lon": 5.85306, "alt": 31.3, },  // “geohash”: “u1hjjnwhfn”
      "version": 0.5,
      "meteo": [ "BME680", ”SHT31” ],
      “energy”: { “solar”: “5W”, “accu”: “Li-Ion” },
      "gps": "NEO-6"
}
`

##  measuement data part:
`{
"data": {
      "version": 0.2,
      "NEO-6":      { "geohash": "u1hjjnwhfn", "alt": 23 },
      // alternative, notice the optional length of the tuples:
      // "BME680": [("aqi",29.9 optional ,'%', [0,1.5]), ...
      "BME680":   {
            "aqi": (29.9,”%”), "rv": None, "luchtdruk": (1019,”hPa”), "voc": 169, "temp": (293.7,”K”) },
      “SHT31”: [ { “temp”: 20.1, “rv”: 70.1 }, { “temp”: 20.3, “rv”: 67.3 } ],    // 1+ sensors
      "PMSx003": {
            "pm05_cnt": 1694.1, "pm10": 29.4, "pm25_cnt": 2396.9,
            "grain": 0.5,
            "pm1_cnt": 2285.7, "pm25": 20.4, "pm10_cnt": 2.4, "pm1": 13.0 },
      “level”: (89.5,”%”)
  }
`

For more examples see the details the MyDatacollector software and comments with real life examples of MDEF format use in real life practice.

This MDEF format draft is WORK in PROGRESS
