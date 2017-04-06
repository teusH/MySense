# shared output via Google gspread 
## STATUS
ALPHA, SW ready, credentials not operational 2017/02/08
Not really tested on credentials and longer term use
Not tested on internet connectivity recovery

## DESCRIPTION
Output measurements of a station to a shared spreadsheet Google gspread.

## INSTALLATION
Use `./INSTALL.sh GSPREAD` to install dependencies via the MySense shell script or

INSTALL python oauth and gspread LIBS via:
```bash
    if [ ! -x /usr/bin/pip ] ; then sudo apt-get install python-pip ; fi
    sudo pip install oauth2client
    sudo pip install gspread
```
or
```bash
    git clone https://github.com/burnash/gspread
    cd gspread; python setup.py install
```

Make sure you have the latest openssl version:
```bash
    sudo apt-get update
    sudo apt-get upgrade
    sudo apt-get install python-openssl
```

## CREDENTIALS
For gspread access to use you need credentials signed by Google.
The following is quite complex. Mistakes are easy to be made.

HOW TO obtain the credentials? Use your browser.
For the following this outline is used:
```
http://gspread.readthedocs.io/en/latest/oauth2.html
```

The steps to take:
1. Head to Google Developers Console (https://console.developers.google.com/)
2. Create a new project e.g. Internet of Sense (or select the one you have.)
3. Under “API & auth” (API Beheer), in the API enable “Drive API”.
4. Go to “Credentials” (welke inlog gegevens heeft u nodig?)
    and choose “New Credentials > Service Account Key”.
    ID name and Role: create/maker
    Service account ID
    Create json
5. You will automatically download a JSON file with this data.
    Save this file as it is unique and secret.
    This (2017-02-08) is how this file may look like:

```
    {
    "project_id": "internet-of-sense",
    "private_key_id": "2c9...ba4",
    "private_key": "-----BEGIN PRIVATE KEY-----\nN...=\n-----END PRIVATE KEY-----\n",
    "client_email": "isos-515@internet-of-sense.iam.gserviceaccount.com",
    "client_id": "1109...71",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://accounts.google.com/o/oauth2/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/ios-515%40internet-of-sense.iam.gserviceaccount.com"
    "type": "service_account"
    }
```

Provide the credential json file name in the config file under gspread.

Preparation of the access:
1. sign up with Google Documents (https://docs.google.com/)
2. create a work/spreadsheet with the name e.g. BdP_f46d04af97ab (project_serial nr)
    serial number is taken from cpu serial number or the MAC address without ':':
    cat /proc/cpuinfo | grep Serial and delete leading zero's.
    or: ifconfig | grep HWaddr
    delete all but one row
2a. Delete all rows except the first row.
2b. The standard sheet is called sheet1. Add two new sheets called: 
    info (for node identity information)
    2017-<current month name> (language dependent)
    Also here only one row.
3. lookup in the json file the line:
    "client_email": "14934...habos3qcu@developer.gserviceaccount.com"
4.  Using the File -> Share... menu item share the spreadsheet with
    read and write access to the email address found above.
    Make sure to share your spreadsheet or you will not be able to update it.

See dht.md for some test some tests of this set up:
5. as test adjust the Adafruit code in google_spreadsheet.py:
```
    # Type of sensor, can be Adafruit_DHT.DHT11, Adafruit_DHT.DHT22, or Adafruit_DHT.AM2302.
    DHT_TYPE = Adafruit_DHT.DHT22       <--- change
    # Example of sensor connected to Raspberry Pi pin 23
    DHT_PIN  = 4                        <--- change
    # Example of sensor connected to Beaglebone Black pin P8_11
    #DHT_PIN  = 'P8_11'
    # Google Docs OAuth credential JSON file.  Note that the process for authenticating
    GDOCS_OAUTH_JSON       = 'your SpreadsheetData-*.json file name' <--- change
    # Google Docs spreadsheet name.
    GDOCS_SPREADSHEET_NAME = 'your google docs spreadsheet name' <--- change
```
6. Make sure the Google json file is in the same dir as the google_spreadsheet.py
7. Run: `sudo ./google_spreadsheet.py`
    And some seconds later the readings will appear in the spreadsheet

You will find via Google search some old "how to" which is deprecated sinds April 2015. Google in its security withdom changed a lot to obtain more security on the data access. The route has become quite complex today...
