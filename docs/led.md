<img src="images/MySense-logo.png" align=right width=100>

# Grove LED feedback and button
### Status
2017/02/27
Operational 2017/3/17

# How To poweroff Raspberry Pi with button
* Use `INSTALL.sh BUTTON` to install the script.

The script
<img src="images/led-button.png" align=left width=150>
uses Grove led and Grove button modules. Connect both modules e.g. with connector D5 (button) and D6 (led).
Suggest to use a robust led/button from Adafruit and connect the led/button to the both Grove modules.

The script MyLed.py can be used to wait for a pushed button, or psh the led on or off or blink is in a seuence defined on the command line.

The script is used to notify internet connectivity and access point association (blinking).

### hardware
* Grove modules led € 2.25 (Kiwi or SOS Solutions)
* Grove button € 2.50 (Kiwi or SOS Solutions)
* Rugged metal pushbutton with led ring € 8.- (SOS Solutions)

Use of button and resistors:
```
    V ---/ _---------|---<R 1K> ----Gnd
    D ---< R 100 >---|
```
Use of led and resistors:
```
    D ---< R 470 >--<+led-> ---- Gnd
```

