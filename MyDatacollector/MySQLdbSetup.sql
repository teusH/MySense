-- MySQL dump 10.13  Distrib 5.7.35, for Linux (x86_64)
--
-- Host: localhost    Database: luchtmetingen Create database first!
-- ------------------------------------------------------

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `Sensors`
--

DROP TABLE IF EXISTS `Sensors`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `Sensors` (
  `id` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'datum/tijd laatste verandering sensor waarde',
  `datum` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `coordinates` varchar(25) DEFAULT NULL COMMENT 'geolocation latitude,longitude,altitude DEPRECATED',
  `label` varchar(50) DEFAULT NULL COMMENT 'location name',
  `sensors` varchar(384) DEFAULT NULL,
  `description` varchar(512) DEFAULT NULL,
  `first` datetime DEFAULT '2001-01-01 00:00:00' COMMENT 'first activation',
  `active` tinyint(1) DEFAULT '1' COMMENT 'sensor is active',
  `project` varchar(20) DEFAULT NULL,
  `serial` varchar(15) DEFAULT NULL COMMENT 'identifier',
  `street` varchar(50) DEFAULT NULL COMMENT 'location road name',
  `village` varchar(50) DEFAULT NULL COMMENT 'location village name',
  `province` varchar(50) DEFAULT NULL,
  `municipality` varchar(50) DEFAULT NULL,
  `last_check` datetime DEFAULT CURRENT_TIMESTAMP COMMENT 'last date/time check location',
  `pcode` varchar(10) DEFAULT NULL COMMENT 'post code location',
  `comment` varchar(128) DEFAULT NULL COMMENT 'versie nummers, bijzonderheden',
  `notice` varchar(128) DEFAULT NULL,
  `region` varchar(20) DEFAULT NULL COMMENT 'name of the regionb',
  `geohash` varchar(12) DEFAULT NULL COMMENT 'geo hash location',
  `altitude` decimal(7,2) DEFAULT NULL COMMENT 'geo meters above sea level',
  `housenr` varchar(6) DEFAULT NULL COMMENT 'house nr in street'
) ENGINE=InnoDB DEFAULT CHARSET=latin1 COMMENT='Sensor locations, init: 2016/12/16, Version 2 Sept 2021';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `Sensors`
--

LOCK TABLES `Sensors` WRITE;
/*!40000 ALTER TABLE `Sensors` DISABLE KEYS */;
INSERT INTO `Sensors` VALUES ('2016-12-16 20:47:37','2020-05-01 13:49:31','6.16635,50.4027,0','Plaats','pm','operationele test','2016-12-12 22:05:00',0,'VW2016','13033927','Straat','Plaats','Provincie','Gemeente','2016-12-24 21:08:10',NULL,NULL,NULL,NULL,'u1h8gkeg71',NULL,'28');
/*!40000 ALTER TABLE `Sensors` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `SensorTypes`
--

DROP TABLE IF EXISTS `SensorTypes`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `SensorTypes` (
  `id` datetime DEFAULT CURRENT_TIMESTAMP COMMENT 'date/time row creation',
  `datum` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'date/time on row update',
  `product` varchar(16) DEFAULT NULL COMMENT 'sensor product name',
  `matching` varchar(16) DEFAULT NULL COMMENT 'sensor product name in wild card',
  `producer` varchar(16) DEFAULT NULL COMMENT 'sensor manufacturer name',
  `category` varchar(16) DEFAULT NULL COMMENT 'sensor category type: dust, meteo, energy, wind, ...',
  `fields` varchar(512) DEFAULT NULL COMMENT 'e.g. DB column name 1,unit,calibration;name 2,unit;name3...',
  UNIQUE KEY `type_id` (`product`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1 COMMENT='TTN info input table, output';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `SensorTypes` information of sensors hardware
--

LOCK TABLES `SensorTypes` WRITE;
/*!40000 ALTER TABLE `SensorTypes` DISABLE KEYS */;
INSERT INTO `SensorTypes` VALUES ('2021-09-28 20:51:17','2021-09-28 18:51:17','SDS011','SDS011','Nova','dust','pm25,ug/m3,PMSx003/1.6190/1.5450|SPS30/2.1630/0.7645|BAM1020/5.7590/0.3769;pm10,ug/m3,PMSx003/3.7600/1.1570|SPS30/1.6890/0.6322|BAM1020/1.4370/0.4130'),('2021-09-28 20:51:17','2021-09-28 18:51:17','SPS30','SPS30','Sensirion','dust','pm1,ug/m3;pm25,ug/m3,PMSx003/-1.0990/1.8350|SDS011/-2.1630/1.3080|BAM1020/4.2550/0.5371;pm10,ug/m3,PMSx003/2.3970/1.6660|SDS011/-1.6890/1.5817|BAM1020/13.1300/0.6438;pm05_cnt,pcs/cm3;pm1_cnt,pcs/cm3;pm25_cnt,pcs/cm3;pm4_cnt,pcs/cm3;pm10_cnt,pcs/cm3;grain,um'),('2021-09-28 20:51:17','2021-09-28 18:51:17','PMSx003','PMS[57X]003','Plantower','dust','pm1,ug/m3,SDS011/-1.6190/0.6472|SPS30/1.0990/0.5450|BAM1020/-4.7860/3.8476;pm25,ug/m3,SDS011/-1.6190/0.6472|SPS30/1.0990/0.5450|BAM1020/-4.7860/3.8476;pm10,ug/m3,SDS011/-3.7600/0.8643|SPS30/-2.3970/0.6002|BAM1020/-13.6900/3.8417;pm03_cnt,pcs/dm3;pm05_cnt,pcs/dm3;pm1_cnt,pcs/dm3;pm25_cnt,pcs/dm3;pm5_cnt,pcs/dm3;pm10_cnt,pcs/dm3;grain,um'),('2021-09-28 20:51:17','2021-09-28 18:51:17','PMS7003','PMS[57X]003','Plantower','dust','pm1,ug/m3,SDS011/-1.6190/0.6472|SPS30/1.0990/0.5450|BAM1020/-4.7860/3.8476;pm25,ug/m3,SDS011/-1.6190/0.6472|SPS30/1.0990/0.5450|BAM1020/-4.7860/3.8476;pm10,ug/m3,SDS011/-3.7600/0.8643|SPS30/-2.3970/0.6002|BAM1020/-13.6900/3.8417;pm03_cnt,pcs/dm3;pm05_cnt,pcs/dm3;pm1_cnt,pcs/dm3;pm25_cnt,pcs/dm3;pm5_cnt,pcs/dm3;pm10_cnt,pcs/dm3;grain,um'),('2021-09-28 20:51:17','2021-09-28 18:51:17','PMS5003','PMS[57X]003','Plantower','dust','pm1,ug/m3,SDS011/-1.6190/0.6472|SPS30/1.0990/0.5450|BAM1020/-4.7860/3.8476;pm25,ug/m3,SDS011/-1.6190/0.6472|SPS30/1.0990/0.5450|BAM1020/-4.7860/3.8476;pm10,ug/m3,SDS011/-3.7600/0.8643|SPS30/-2.3970/0.6002|BAM1020/-13.6900/3.8417;pm03_cnt,pcs/dm3;pm05_cnt,pcs/dm3;pm1_cnt,pcs/dm3;pm25_cnt,pcs/dm3;pm5_cnt,pcs/dm3;pm10_cnt,pcs/dm3;grain,um'),('2021-09-28 20:51:17','2021-09-28 18:51:17','PMS7003_PCS','PMS[57X]003','Plantower','dust','pm03_pcs,pcs/0.1dm3;pm05_pcs,pcs/0.1dm3;pm1_pcs,pcs/0.1dm3;pm25_pcs,pcs/0.1dm3;pm5_pcs,pcs/0.1dm3;pm10_pcs,pcs/0.1dm3;grain,um'),('2021-09-28 20:51:17','2021-09-28 18:51:17','PPD42NS','PPD42NS','Shiney','dust','pm25,pcs/0.01qft;pm10,pcs/0.01qft'),('2021-09-28 20:51:17','2021-09-28 18:51:17','DC1100 PRO','DC1100.*','Dylos','dust','pm25,pcs/0.01qft;pm10,pcs/0.01qft'),('2021-09-28 20:51:17','2021-09-28 18:51:17','DHT11','DHT(11|22)','Adafruit','meteo','temp,C;rv,%'),('2021-09-28 20:51:17','2021-09-28 18:51:17','DHT22','DHT(11|22)','Adafruit','meteo','temp,C;rv,%'),('2021-09-28 20:51:17','2021-09-28 18:51:17','BME280','BME280','Bosch','meteo','temp,C;rv,%;luchtdruk,hPa'),('2021-09-28 20:51:17','2021-09-28 18:51:17','BME680','BME680','Bosch','meteo','temp,C;rv,%;luchtdruk,hPa;gas,kOhm;aqi,%'),('2021-09-28 20:51:17','2021-09-28 18:51:17','SHT31','SHT[23]1','Sensirion','meteo','temp,C;rv,%'),('2021-09-28 20:51:17','2021-09-28 18:51:17','SHT85','SHT85','Sensirion','meteo','temp,C;rv,%'),('2021-09-28 20:51:17','2021-09-28 18:51:17','HYT221','HYT221','IST AG','meteo','temp,C;rv,%'),('2021-09-28 20:51:17','2021-09-28 18:51:17','NEO-6','NEO-6','NEO','location','geohash,geohash;altitude,m'),('2021-09-28 20:51:17','2021-09-28 18:51:17','PYCOM','PYCOM','ESP','controller','time,sec'),('2021-09-28 20:51:17','2021-09-28 18:51:17','ToDo','TODO','Spect','gas','NO2,ppm;CO2,ppm;O3,ppm;NH3,ppm'),('2021-09-28 20:51:17','2021-09-28 18:51:17','energy','ENERGY','accu','energy','accu,%'),('2021-09-28 20:51:17','2021-09-28 18:51:17','WASPMOTE','WASPMOTE','Libelium','weather','accu,%;temp,C;rv,%;luchtdruk,hPa;rain,mm;prevrain,mm;dayrain,mm;wr,degrees;ws,m/sec'),('2021-09-28 20:51:17','2021-09-28 18:51:17','WASPrain','WASPRAIN','Libelium','rain','rain,mm/h;prevrain,mm/h;dayrain,mm/24h'),('2021-09-28 20:51:17','2021-09-28 18:51:17','WASPwind','WASPWIND','Libelium','wind','wr,degrees;ws,m/sec'),('2021-09-28 20:51:17','2021-09-28 18:51:17','DIY1','DIY1','Jos','weather','rain,mm/h;wr,degrees;ws,m/sec;accu,V'),('2021-09-28 20:51:17','2021-09-28 18:51:17','RainCounter','RAINCOUNTER','unknown','rain','rain,mm/h'),('2021-09-28 20:51:17','2021-09-28 18:51:17','windDIY1','WINDDIY1','WindSonic','wind','wr,degrees;ws,m/sec'),('2021-09-28 20:51:17','2021-09-28 18:51:17','Argent','ARGENT','Argentdata','wind','wr,degrees;ws,m/sec'),('2021-09-28 20:51:17','2021-09-28 18:51:17','Ultrasonic','ULTRASONIC','Darrera','wind','wr,degrees;ws,m/sec');
/*!40000 ALTER TABLE `SensorTypes` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `TTNtable` forwarding information
--

DROP TABLE IF EXISTS `TTNtable`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `TTNtable` (
  `id` datetime DEFAULT CURRENT_TIMESTAMP COMMENT 'date/time creation',
  `project` varchar(16) DEFAULT NULL COMMENT 'project id',
  `serial` varchar(16) DEFAULT NULL COMMENT 'serial kit hex',
  `TTN_id` varchar(32) DEFAULT NULL COMMENT 'TTN device topic name',
  `luftdatenID` varchar(16) DEFAULT NULL COMMENT 'if null use TTN-serial',
  `luftdaten` tinyint(1) DEFAULT '0' COMMENT 'POST to luftdaten',
  `datum` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `DevAdd` varchar(10) DEFAULT NULL COMMENT 'ABP device id Hex',
  `NwkSKEY` varchar(32) DEFAULT NULL COMMENT 'ABP network secret key Hex',
  `AppEui` varchar(16) DEFAULT NULL COMMENT 'OTAA application id TTN',
  `DevEui` varchar(16) DEFAULT NULL COMMENT 'OTAA device eui Hex',
  `AppSKEY` varchar(32) DEFAULT NULL COMMENT 'OTAA/ABP secret key Hex',
  `website` tinyint(1) DEFAULT '0' COMMENT 'publish measurements on website',
  `refresh` datetime DEFAULT NULL COMMENT 'date from which kit is in repair',
  `valid` tinyint(1) DEFAULT '1' COMMENT 'validate measurements, if NULL then in repair, False omit in DB',
  `TTN_app` varchar(32) DEFAULT '20108225197a1z' COMMENT 'TTN application ID',
  `DBactive` tinyint(1) DEFAULT '1' COMMENT 'Forward measurements to measurements DB',
  UNIQUE KEY `id` (`id`),
  UNIQUE KEY `kit_id` (`project`,`serial`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1 COMMENT='forwarding info table, output, V2.0';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `TTNtable`
--

LOCK TABLES `TTNtable` WRITE;
/*!40000 ALTER TABLE `TTNtable` DISABLE KEYS */;
INSERT INTO `TTNtable` VALUES ('2020-03-19 09:32:52','VW2016','13033927','MySense-3927',NULL,0,'2020-06-15 10:23:19',NULL,NULL,'7012345E123454D3','D4912345E1234516','68B5A12345DE12345B81234512345581',1,NULL,1,'201234515971az',0);
/*!40000 ALTER TABLE `TTNtable` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for measurements data table `VW2016_13033927`
--

DROP TABLE IF EXISTS `VW2016_13033927`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `VW2016_13033927` (
  `id` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'date/time latest change',
  `datum` datetime DEFAULT NULL COMMENT 'date/time measurement',
  `temp` decimal(7,2) DEFAULT NULL COMMENT 'type: C; added on 2019-04-16 12:54',
  `temp_valid` tinyint(1) DEFAULT '1' COMMENT 'value validated',
  `rv` decimal(7,2) DEFAULT NULL COMMENT 'type: %; added on 2019-04-16 12:54',
  `rv_valid` tinyint(1) DEFAULT '1' COMMENT 'value validated',
  `luchtdruk` decimal(7,2) DEFAULT NULL COMMENT 'type: hPa; added on 2019-04-16 12:54',
  `luchtdruk_valid` tinyint(1) DEFAULT '1' COMMENT 'value validated',
  `gas` decimal(9,3) DEFAULT NULL COMMENT 'type: kOhm; added on 2019-04-16 12:54',
  `gas_valid` tinyint(1) DEFAULT '1' COMMENT 'value validated',
  `aqi` decimal(5,2) DEFAULT NULL COMMENT 'type: %; added on 2019-04-16 12:54',
  `aqi_valid` tinyint(1) DEFAULT '1' COMMENT 'value validated',
  `pm1` decimal(9,2) DEFAULT NULL COMMENT 'type: ug/m3; added on 2019-04-16 12:54',
  `pm1_valid` tinyint(1) DEFAULT '1' COMMENT 'value validated',
  `pm25` decimal(7,2) DEFAULT NULL COMMENT 'type: ug/m3; added on 2019-04-16 12:54',
  `pm25_valid` tinyint(1) DEFAULT '1' COMMENT 'value validated',
  `pm10` decimal(7,2) DEFAULT NULL COMMENT 'type: ug/m3; added on 2019-04-16 12:54',
  `pm10_valid` tinyint(1) DEFAULT '1' COMMENT 'value validated',
  `pm03_cnt` decimal(9,2) DEFAULT NULL COMMENT 'type: pcs/dm3; added on 2019-04-16 12:54',
  `pm03_cnt_valid` tinyint(1) DEFAULT '1' COMMENT 'value validated',
  `pm05_cnt` decimal(9,2) DEFAULT NULL COMMENT 'type: pcs/dm3; added on 2019-04-16 12:54',
  `pm05_cnt_valid` tinyint(1) DEFAULT '1' COMMENT 'value validated',
  `pm1_cnt` decimal(9,2) DEFAULT NULL COMMENT 'type: pcs/dm3; added on 2019-04-16 12:54',
  `pm1_cnt_valid` tinyint(1) DEFAULT '1' COMMENT 'value validated',
  `pm25_cnt` decimal(7,2) DEFAULT NULL COMMENT 'type: pcs/dm3; added on 2019-04-16 12:54',
  `pm25_cnt_valid` tinyint(1) DEFAULT '1' COMMENT 'value validated',
  `pm5_cnt` decimal(7,2) DEFAULT NULL COMMENT 'type: pcs/dm3; added on 2019-04-16 12:54',
  `pm5_cnt_valid` tinyint(1) DEFAULT '1' COMMENT 'value validated',
  `pm10_cnt` decimal(7,2) DEFAULT NULL COMMENT 'type: pcs/dm3; added on 2019-04-16 12:54',
  `pm10_cnt_valid` tinyint(1) DEFAULT '1' COMMENT 'value validated',
  `grain` decimal(7,2) DEFAULT NULL COMMENT 'type: um; added on 2019-04-16 12:54',
  `grain_valid` tinyint(1) DEFAULT '1' COMMENT 'value validated',
  `rssi` smallint(4) DEFAULT NULL COMMENT 'type: dB; added on 2019-04-16 12:54',
  `rssi_valid` tinyint(1) DEFAULT '1' COMMENT 'value validated',
  UNIQUE KEY `datum` (`datum`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1 COMMENT='Sensor located at: 6.13559,51.42067,16.9';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `HadM_30aea44e1934`
--

LOCK TABLES `HadM_30aea44e1934` WRITE;
/*!40000 ALTER TABLE `VW2016_13033927` DISABLE KEYS */;
INSERT INTO `VW2016_13033927` VALUES ('2019-05-07 07:35:28','2019-05-07 09:35:07',14.10,1,57.10,1,1017.00,1,43467.000,1,NULL,1,17.80,1,29.30,1,45.30,1,309.50,1,309.50,1,309.50,1,23.70,1,23.70,1,23.70,1,NULL,1,NULL,1);
/*!40000 ALTER TABLE `HadM_30aea44e1934` ENABLE KEYS */;
UNLOCK TABLES;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed
