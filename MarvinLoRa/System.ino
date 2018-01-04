void systemInitialize(void)
{
  Serial.begin(115200);
  Serial1.begin(57600);
  Serial.println("Opgestart");
    
   loraInitialize();
 
}


