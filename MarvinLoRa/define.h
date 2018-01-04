
uint8_t statusNow = 0;

const uint8_t dataLength = 200;
uint8_t fifoData[dataLength];

const uint8_t receiveDataLength = 50;
char receiveData[receiveDataLength];

const int sendStringLength = 17;
char sendStrings[sendStringLength] ="";

uint8_t restTime = 0;
uint8_t newThreshold = 0;
uint8_t newThresTime = 0;
