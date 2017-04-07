/**
 * The MySensors Arduino library handles the wireless radio link and protocol
 * between your home built sensors/actuators and HA controller of choice.
 * The sensors forms a self healing radio network with optional repeaters. Each
 * repeater and gateway builds a routing tables in EEPROM which keeps track of the
 * network topology allowing messages to be routed to nodes.
 *
 * Created by Henrik Ekblad <henrik.ekblad@mysensors.org>
 * Copyright (C) 2013-2015 Sensnology AB
 * Full contributor list: https://github.com/mysensors/Arduino/graphs/contributors
 *
 * Documentation: http://www.mysensors.org
 * Support Forum: http://forum.mysensors.org
 *
 * This program is free software; you can redistribute it and/or
 * modify it under the terms of the GNU General Public License
 * version 2 as published by the Free Software Foundation.
 *
 *******************************
 * DESCRIPTION
 * 
 * Dust Sensor for Shinyei ppd42ns
 *  
 * 1 : COMMON(GND)
 * 2 : OUTPUT(P2)
 * 3 : INPUT(5VDC 90mA)
 * 4 : OUTPUT(P1)
 * 5 : INPUT(T1)･･･FOR THRESHOLD FOR [P2] - not used
 *
 * http://www.seeedstudio.com/wiki/images/4/4c/Grove_-_Dust_sensor.pdf
 * 
 *   connect the sensor as follows :
 *    Pin 4 of dust sensor PM1      -> Digital 9
 *    Pin 3 of dust sensor          -> +5V 
 *    Pin 2 of dust sensor PM25    -> Digital 8
 *    Pin 1 of dust sensor          -> Ground
* Contributor: epierre and alexsh1
 * MySense changes: Teus, March 2017
**/

String version = "1.08";

String type = "PPD42NS";
#define DUST_SENSOR_DIGITAL_PIN_PM10  9
#define DUST_SENSOR_DIGITAL_PIN_PM25  8

#define LedPIN 12

// variables
unsigned long interval = 60000; // timing reads (in milliseconds)
unsigned long sampletime_ms = 15000;  // timing one sample synchronous
boolean configured = false;
boolean ack = false;

void setup()
{
  Serial.begin(9600);
  while(!Serial) {
    ;
  }
  pinMode(LedPIN,OUTPUT); // signals configuration mode and sampling mode
  pinMode(DUST_SENSOR_DIGITAL_PIN_PM10,INPUT);
  pinMode(DUST_SENSOR_DIGITAL_PIN_PM25,INPUT);


}

// get interval configuration if available
void configure(char cmd)
{
  unsigned long timing1 = 0;
  unsigned long timing2 = 0;
  unsigned long endTime;
  Serial.setTimeout(60000); // after one minute use defaults
  digitalWrite(LedPIN,HIGH);
  // Serial.println("Configuring");
  Serial.println("");
  sampletime_ms = 15000; // defaults
  interval = 60000;
  ack = false;
  endTime = millis() + 60000;
  if ( cmd != 'C' ) {
    while ( Serial.available() <= 0 ) {
      if ( millis() > endTime ) {
        break;
      }
      delay(300);
    }
  }
  configured = true;
  // configure: C interval sampleTime RequestTiming \n (timeout 15 seconds)
  while ( Serial.available() > 0 ) {
    if ( timing1 == 0 ) {
      timing1 = Serial.parseInt();
      // Serial.print("interval: "); Serial.println(timing1);
      if ( (timing1 >= 0) and (timing1 <= 3600) ) {  // 60 minutes max
        if (timing1 == 0) { ack = true; }
        else { interval = timing1 * 1000; }
      }
      timing1 = 1;
      continue;
    } else if ( timing2 == 0 ) {
      timing2 = Serial.parseInt() * 1000;
      // Serial.print("sample time: "); Serial.println(timing2);
      if ( (timing2 > 0) and (timing2 <= (interval/2)) ) {
        sampletime_ms = timing2;
      }
      timing2 = 1;
      continue;
    } else {
      do {
        cmd = Serial.read();
        if( cmd == 'R' ) {
          ack = true;
          // Serial.println("Request receive");
        } else if ( cmd == '\n' ) {
          break;
        } // else { Serial.println("skipping"); }
      } while ( Serial.available() > 0 );
      continue;
    } 
  }
  // empty serial read buffer
  while ( Serial.available() > 0 ) {
    Serial.read();
  }
  digitalWrite(LedPIN,LOW);
  // Serial.print("interval: "); Serial.println(interval/1000);
  // Serial.print("sample time: "); Serial.println(sampletime_ms/1000);
  // Serial.println("End of configuration");
}

void loop()
{
  long sleepTime;
  unsigned long timing;
  char cmd;
  
  if ( not configured ) {
    configure('R');
  }
  
  Serial.print("{");
  Serial.print("\"version\": \"" + version + "\",\"type\": \"" + type + "\"");
  
  sleepTime = millis();
  Serial.print(",");
  printPM((int)DUST_SENSOR_DIGITAL_PIN_PM25,(String)"pm25");
  
  if ( not ack ) {
    sleepTime = (interval/2) - (millis()-sleepTime);
    if ( sleepTime > 0 ) {
      delay(sleepTime);
    }
  }
  
  sleepTime = millis();
  Serial.print(",");
  printPM((int)DUST_SENSOR_DIGITAL_PIN_PM10,(String)"pm10");
  
  Serial.println("}");
  
  if ( not ack ) { //sleep to save on radio
    sleepTime = interval/2 - (millis() - sleepTime);
    if ( sleepTime > 0 ) {
      Serial.print("sleep2: "); Serial.print(sleepTime/1000);
      delay(sleepTime);
    }
  }
  if ( ack or (Serial.available() > 0 ) ) {
    sleepTime = millis() + 3600000; // max wait time one hour
    do {
      while ( Serial.available() <= 0 ) {
        if ( millis() > sleepTime ) {
          break;
        }
        delay(1000);
      }
      cmd = Serial.read();
      if ( cmd == '\n' ) {
        break;
      } else if ( cmd == 'C' ) {
        configured = false;
        configure((char)cmd);
      }
    } while (Serial.available() > 0 );
  }    
}

void printPM(int pin, String name){
  long concentrationPM;
  
  //get PM density of particles over x μm.
  concentrationPM=(long)getPM((int)pin,(String)name);
  Serial.print(",\"" + name + "_pcs/qf\":");
  if ( concentrationPM > 0 ) {
    Serial.print(concentrationPM/100);
  } else { 
    Serial.print("null");
  }
  Serial.print(",\"" + name + "_ug/m3\":");
  if ( concentrationPM > 0 ) {
    Serial.print((float)conversion(concentrationPM,name));
  } else {
    Serial.print("null");
  }
}

// ref: https://github.com/andy-pi/weather-monitor/blob/master/air_quality.py
float conversion(long concentrationPM, String name) {
  double pi = 3.14159;
  double density = 1.65 * pow (10, 12);
  // ref art.: Air Quality Sensor Network for Philadelphia, Arling a.o.
  double r = 0.44;
  if ( name.equals("pm10") ) { r = 2.60; }
  r *= pow (10, -6);
  double vol = (4/3) * pi * pow (r, 3);
  double mass = density * vol;
  double K = 3531.5;
  return (concentrationPM) * K * mass;
}

long getPM(int DUST_SENSOR_DIGITAL_PIN, String name) {
  unsigned long starttime;
  unsigned long endtime;
  unsigned long duration;
  float ratio = 0;
  unsigned long lowpulseoccupancy = 0;
  float concentration = 0;
  boolean ledState = LOW;
  
  starttime = millis();
  if ( ledState == LOW ) {
    digitalWrite(LedPIN,HIGH); ledState = HIGH;
  }

  while (true) {
    
    duration = pulseIn(DUST_SENSOR_DIGITAL_PIN, LOW);
    lowpulseoccupancy += duration;
    endtime = millis();

    if ((endtime-starttime) > sampletime_ms)
    {
      if ( ledState == HIGH ) {
        digitalWrite(LedPIN,LOW); ledState = LOW;
      }
      ratio = (lowpulseoccupancy-endtime+starttime)/(sampletime_ms*10.0);
      // Integer percentage 0=>100
      if ( (ratio > 100) or (ratio < 0) ) {
        ratio = 0;
      }
      concentration = 1.1*pow(ratio,3)-3.8*pow(ratio,2)+520*ratio+0.62; // using spec sheet curve
    
      Serial.print("\"" + name + "_count\":");
      if ( ratio > 0 ) {
        Serial.print(lowpulseoccupancy);
      } else {
        Serial.print("null");
      }
      Serial.print(",\"" + name + "_ratio\":");
      if ( ratio > 0 ) {
        Serial.print(ratio);
      } else {
        Serial.print("null");
        return(0);
      }
      return(concentration);
    }
  }
}
