void loraInitialize(void)
{
  Serial.println("StartLoRa");
  delay(1000);

  while (!Serial1) {
    delay(100);
    Serial.print("wachten op LoRa");
  }

  if(0)
  {
  Serial.println("Reset");
  sendCmd("sys factoryRESET");
  delay(2000);

  delay(1000);

  delay(1000);
  delay(5000);
  }
  sendCmd("sys get hweui");
  delay(100);
  //sendCmd("mac set dr 3");
  delay(100);
  sendCmd("mac set adr on");
  delay(100);
  //sendCmd("mac set dr 5");
  delay(100);
  //sendCmd("mac set deveui AAAAAAAAAAAAAAAB");
  //delay(100);
  sendCmd("mac set devaddr XX");//Addr for device #1:02E00A10 #2:02E00A11 #3:02E00A12
  delay(100);
  sendCmd("mac set appskey XX");
  delay(100);
  sendCmd("mac set nwkskey XX");
  delay(100);
  sendCmd("mac set appeui XX");
  delay(100);
  sendCmd("mac get upctr");
  delay(100);
  sendCmd("mac get dnctr");
  delay(100);
  sendCmd("mac set pwridx 1");
  delay(100);
  sendCmd("mac save");
  delay(1000);

}


void LoRa_Send()
{
  
  char * tChar;
  while (Serial1.available()) {
    *tChar = Serial1.read();
    Serial.write(*tChar);
    if (*tChar == '\n' && Serial1.available()) { // checks for not end of message
      Serial.write(" >> ");
    }
  }
  //sendCmd("mac set dr 5");
  delay(100);
  sendCmd("mac join abp");
  delay(100);
  sendCmd("mac get upctr");
  delay(50);
  //sendCmd("mac get dr");
  //delay(100);
  //LoRa.write("mac tx uncnf 1 AA\r\n");
  //LoRa.write("\r\n");
  //sendCmd("mac tx uncnf 1 01000200000042");
  //sendData(sendStrings, 1);
  Serial1.write("mac tx uncnf 1 ");
  Serial1.write(sendStrings);
  Serial1.write("\r\n");

  Serial.write("mac tx uncnf 1 ");
  Serial.write(sendStrings);
  Serial.write("\r\n");
  delay(1000);
  
  delay(6000);
  int receiving = 0;
  while (Serial1.available()) {
    receiveData[receiving] = Serial1.read();
    Serial.print(receiving);
    Serial.print(" ");
    Serial.println(receiveData[receiving]);
    receiving++;
  }
  if(receiveData[8] == 'r')
  {
    Serial.println("Downlink Received: ");
    processDownlink();
  }
  else
  {
    Serial.println("No Downlink");
  }
  //sendCmd("mac set adr on");
  delay(100);
  sendCmd("mac save");
  delay(1000);
}

char getHexHi( char ch ) {
  char nibble = (ch & 0xF0) >> 4;
  return (nibble > 9) ? nibble + 'A' - 10 : nibble + '0';
}

char getHexLo( char ch ) {
  char nibble = ch & 0x0F;
  return (nibble > 9) ? nibble + 'A' - 10 : nibble + '0';
}

void sendCmd( char *cmd) {
  int i=0;
  Serial.write("!!  ");
  Serial.write( cmd );
  Serial.write("\r\n");
  Serial1.write(cmd);
  Serial1.write("\r\n");
  while (!Serial1.available() ) {
    delay(100);
    Serial.write("wait");
    i++;
    if(i>100){
      break;
    }
  }
  Serial.write(" >> ");
  char * tChar;
  while (Serial1.available()) {
    *tChar = Serial1.read();
    Serial.write(*tChar);
    if (*tChar == '\n' && Serial1.available()) { // checks for not end of message
      Serial.write(" >> ");
    }
  }
  Serial.write("\r\n");
}

void createSendstring(uint16_t PM25, uint16_t PM10, uint16_t temp, uint16_t hum)
{
  int16ToHexString((&sendStrings[0]), PM25);
  int16ToHexString((&sendStrings[4]), PM10);
  int16ToHexString((&sendStrings[8]), temp);
  int16ToHexString((&sendStrings[12]), hum);

  Serial.write("Lora_String");
  Serial.write(sendStrings);
  Serial.write(" ");
}

void intToHexString(char * pBuffer, int8_t f) {
  uint8_t * fBytes = (uint8_t *)&f;
  *pBuffer = getHexHi(*(fBytes));
  pBuffer++;
  *(pBuffer) = getHexLo(*(fBytes));
  pBuffer++;
}

void int16ToHexString(char * pBuffer, int16_t ul) {
  uint8_t * ulBytes = (uint8_t *)&ul;
  for (int i = 1; i >= 0; i--) {
    *pBuffer = getHexHi(*(ulBytes + i));
    pBuffer++;
    *(pBuffer) = getHexLo(*(ulBytes + i));
    pBuffer++;
  }
}

void processDownlink(void)
{
  unsigned int i, t, hn, ln;

  restTime = 0;

  hn = receiveData[13] > '9' ? receiveData[13] - 'A' + 10 : receiveData[13] - '0';
  ln = receiveData[14] > '9' ? receiveData[14] - 'A' + 10 : receiveData[14] - '0';
  restTime = (hn << 4 ) | ln;
  
  hn = receiveData[15] > '9' ? receiveData[15] - 'A' + 10 : receiveData[15] - '0';
  ln = receiveData[16] > '9' ? receiveData[16] - 'A' + 10 : receiveData[16] - '0';
  newThreshold = (hn << 4 ) | ln;
  
  hn = receiveData[17] > '9' ? receiveData[17] - 'A' + 10 : receiveData[17] - '0';
  ln = receiveData[18] > '9' ? receiveData[18] - 'A' + 10 : receiveData[18] - '0';
  newThresTime = (hn << 4 ) | ln;

/*
  Serial.println("Slaap stand voor: ");
  Serial.println(restTime, DEC);
  Serial.print("Nieuwe Threshold: "); 
  Serial.println(newThreshold, DEC);
  Serial.print("Nieuwe duratie tijd: ");
  Serial.println(newThresTime, DEC);

   wireWrite(chipAddress, 50, newThreshold);
   wireWrite(chipAddress, 51, newThresTime);
  Serial.println("Nieuwe waardes Downlink toegepast");
  */
}

