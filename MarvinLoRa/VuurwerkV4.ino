// SDS011 dust sensor example
// for use with SoftSerial
// -----------------------------

#include <SDS011-select-serial.h>
#include <SoftwareSerial.h>
#include <rn2xx3.h>
#include "define.h"
#include "DHT.h"

#define DHTPIN A0     // what pin we're connected to
#define DHTTYPE DHT22   // DHT 22  (AM2302)

DHT dht(DHTPIN, DHTTYPE);

float p10,p25;
uint16_t sPM10 = 0, sPM25 = 0;
int error;

SoftwareSerial mySerial(15, 16); // RX, TX
SDS011 my_sds(mySerial);

void setup() {
	// initialize normal Serial port
	systemInitialize();
	// initalize SDS Serial Port
	mySerial.begin(9600);
}

void loop() {
	error = my_sds.read(&p25,&p10);

sPM10 = round(p10*10);
sPM25 = round(p25*10);


   uint16_t h = round(dht.readHumidity()*10);
   uint16_t t = round((dht.readTemperature()*10)+200);

    // check if returns are valid, if they are NaN (not a number) then something went wrong!
    while (isnan(t) || isnan(h)) 
    {
        Serial.println("Failed to read from DHT");
        h = round(dht.readHumidity()*10);
        t = round((dht.readTemperature()*10)+200);
    } 
    Serial.print("Humidity: "); 
    Serial.print(h);
    Serial.print(" %\t");
    Serial.print("Temperature: "); 
    Serial.print(t);
    Serial.println(" *C");

 
	if (! error) {
		Serial.println("P2.5: "+String(p25));
		Serial.println("P10:  "+String(p10));

   createSendstring(sPM25, sPM10, t, h);
   LoRa_Send();
   delay(120000);

   
	}
	delay(6000);
  //Serial.println(error);
}
