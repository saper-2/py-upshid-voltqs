# Intro
Those scripts was created to talk with UPS that use show up as HID UPS in system, while HID have some basic support for UPS, but there is no detailed information, and no special drivers are required (USB HID devices are supported by default in all OSes). So to get more options & control manufacturers adapted popular serial (RS232) protocols to new popular USB interface, and used HID device class since it doesn't need for additional drivers. Communication with UPS utilize USB & HID protocol control messages that have a space for additional data. And that space is used for communication, since protocols don't need much data to be sent/received. 

Those scripts use Voltronic-QS protocol, **V** variant, and there is also **M** variation of it - I guess the only difference is: the `M` don't report temperature, instead field is always empty ```--.-```.

Many UPS with USB uses this protocol (VoltronicQS) - I feel like it's more popular even than blazer.

Scripts allow for querying UPS status and parameters/ratings and execute commands (self-test, beeper on/off, shutdown, cancel shutdown...).

For more info about Voltronic-QS check Network UPS Tools (a.k.a. NUT) documentation: https://networkupstools.org/protocols/voltronic-qs.html#V-protocol-queries

There is 2 scripts that works almost identical, difference is how they take parameters/arguments & how data is returned. Each script have a section of this README.

- [hidups-qs.py](#hidups-qs) - This script takes command line arguments and return UPS responses in human readable format :smile:
- [hidups-qs-json.py](#hidups-qs-json) - This script take as 1st argument JSON string , or if no argument is passwd, then use STDIN to read JSON with parameters. It returns JSON too.

----
# hidups-qs
This script was created first and it more human friendly :smiley:

## Script parameters
Script takes minimum 3 parameters that are required:
- UPS USB VID
- UPS USB PID
- Command

To get USB VID & PID use ```lsusb``` and look for values separated `:` after `ID` .

Use ```-h```/```--help``` parameter to get help.

```
saper@t620:~/hid $ ./hidups-qx.py -h
usage: hidups-qx.py [-h] [-ep EP] -c {qs,f,qi,t,q,m,c,s} [-st ST] [-sr SR] [-to TO] vid pid

Script allow for simple query and change some options of UPS that use usb hid device class and Voltronic-QS protocol

positional arguments:
  vid                   VID of USB (hex 4 digit)
  pid                   PID of USB (hex 4 digit)

optional arguments:
  -h, --help            show this help message and exit
  -ep EP                Endpoint number for reading response (hex 2 digit)
  -c {qs,f,qi,t,q,m,c,s}
                        Select command to send to UPS. Available commands: qs=query status, f=query ratings, qi=query ?,
                        t=run 10s test, q=toggle beeper, m=query proto variant, c=cancel shutdown, s=shutdown (require
                        parameters -st and -sr to be set)
  -st ST                [float] Shutdown delay before UPS switch OFF output [minutes]. Value below 1.0 is treated as
                        decimal of 1min (0.1=6sec), value <1.0 will be rounded to 1 digit after decimal point. Value >=1.0
                        will be rounded to an integer. 0=instant shutdown. Use cmd: cancel to cancel delay. (parameter
                        required for shutdown command)
  -sr SR                [int] Shutdown delay before restoring output to ON [minutes]. 0=don't restore. Use cmd: cancel to
                        restore output ON. (parameter required for shutdown command)
  -to TO                [int] Timeout for command/response in ms. This can be changed if 1000ms is not enough for ups to
                        send complete response.

For more details about Voltronic-QS protocol (V variant and H variant seems identical) see NUT documentation:
https://networkupstools.org/protocols/voltronic-qs.html#V-protocol-queries
```

**Parameters:**
- ```vid``` - UPS USB VID in 4 digit hex (without 0x)
- ```pid``` - UPS USB PID in 4 digit hex (without 0x)
- ```-c xxx``` - command where xxx can be:
   - ```m```  - Query UPS for protocol variant
   - ```f```  - Query UPS for it's ratings,
   - ```qs``` - Query UPS for it's status,
   - ```qi``` - Query UPS for internal status(?) - *no info about response fields*
   - ```t``` - Run Self-Test by UPS,
   - ```c``` - Cancel self-test or Shutdown command,
   - ```s``` - Start shutdown sequence (requires ```-st``` & ```-sr``` parameters), can be canceled by **Cancel** command in any moment,
- ```-st t.t``` - Delay for shutdown before output is switched off (value is float with 1 decimal place - or will be rounded to 1 decimal(if t.t<1.0)/full integer (if t.t>=1.0); e.g.: *0.1=6sec/0.7=42sec/1.0=1min/2.5=3min* )
- ```-sr y``` - Delay y min before output is switched back ON ,
- ```-ep xx``` - Endpoint number from which command response should be read (2 digit hex , default ```81```)
- ```-to ssss``` - timeout for command send/read response in ms (default ```1000```ms)

### Script returns exit code in case of error
- 0 - OK
- 100 - Parameter -st (Shutdown delay) can not be negative.
- 101 - Parameter -sr (Shutdown delay before restore output) can not be negative.
- 102 - Parameters -st and -sr have to be defined when using Shutdown [s] command.
- 103 - Device not found.
- 104 - Endpoint not found in device.
- 105 - No interface selected.
- 106 - Failed to detach kernel driver from interface.
- 107 - Failed to write data to USB Device (ctrl_transfer failed).
- 108 - USBTimeoutError while trying to read response from USB device.
- 109 - General error while trying to read response from USB device.

## Quick UPS commands description
In commands replace ```<vid>``` & ```<pid>``` with 4 hex digit of USB VID & PID respectively of UPS.

### Query protocol variant

Command: ```hidups-qx.py <vid> <pid> -c qs```

Example result:
```
saper@t620:~/hid $ ./hidups-qx.py 0665 5161 -c m
UPS HID Voltronic-QS communication script by saper_2 version: 20230610
VID:PID : 0665:5161
Endpoint: 0x81
Command : Query Voltronic protocol variant [M]
Timeout : 1000ms
Selected device basic info:
Configuration: 1
  - Interface: #0 (alt: 0)
    - Endpoint adr: 0x81
  - Interface: #1 (alt: 0)
    - Endpoint adr: 0x82


Selecting device <0665:5161>, configuration, interface (0) & endpoint 0x81 (IN, #0)
Checking if kernel_driver is attached to interface #0, and removing it in case...
Nope - OK.

Command to send: 4D 0D >>> b'M\r' <<<
UPS response: (len=8bytes)
  HEX:  48 0D 00 00 00 00 00 00
  STR: b'H\r\x00\x00\x00\x00\x00\x00'
Decoded:
  Protocol variant: H
```

### Query ratings
Read from UPS it's nominal ratings (VAC, current, V-battery...)

Command: ```hidups-qx.py <vid> <pid> -c f```

Example result:
```
saper@t620:~/hid $ ./hidups-qx.py 0665 5161 -c f
UPS HID Voltronic-QS communication script by saper_2 version: 20230610
VID:PID : 0665:5161
Endpoint: 0x81
Command : Query ratings [F]
Timeout : 1000ms
Selected device basic info:
Configuration: 1
  - Interface: #0 (alt: 0)
    - Endpoint adr: 0x81
  - Interface: #1 (alt: 0)
    - Endpoint adr: 0x82


Selecting device <0665:5161>, configuration, interface (0) & endpoint 0x81 (IN, #0)
Checking if kernel_driver is attached to interface #0, and removing it in case...
Nope - OK.

Command to send: 46 0D >>> b'F\r' <<<
UPS response: (len=24bytes)
  HEX:  23 32 33 30 2E 30 20 30 30 33 20 31 32 2E 30 30 20 35 30 2E 30 0D 00 00
  STR: b'#230.0 003 12.00 50.0\r\x00\x00'
Decoded:
  - Nominal output voltage  : 230.0V
  - Nominal output current  : 3.0A
  - Nominal battery voltage : 12.0V
  - Nominal output frequency: 50.0Hz
```

### Query status
Query UPS for it's current status (V AC input, V AC out, V out freq, V-battery, status flags (buck/boost mode on, beeper on/off, etc...))

Command: ```hidups-qx.py <vid> <pid> -c qs```

Example output:
```
saper@t620:~/hid $ ./hidups-qx.py 0665 5161 -c qs
UPS HID Voltronic-QS communication script by saper_2 version: 20230610
VID:PID : 0665:5161
Endpoint: 0x81
Command : Query status [QS]
Timeout : 1000ms
Selected device basic info:
Configuration: 1
  - Interface: #0 (alt: 0)
    - Endpoint adr: 0x81
  - Interface: #1 (alt: 0)
    - Endpoint adr: 0x82


Selecting device <0665:5161>, configuration, interface (0) & endpoint 0x81 (IN, #0)
Checking if kernel_driver is attached to interface #0, and removing it in case...
Nope - OK.

Command to send: 51 53 0D >>> b'QS\r' <<<
UPS response: (len=48bytes)
  HEX:  28 32 32 38 2E 36 20 32 32 38 2E 37 20 32 32 38 2E 36 20 30 30 30 20 35 30 2E 30 20 31 33 2E 35 20 2D 2D 2E 2D 20 30 30 30 30 31 30 30 30 0D 00
  STR: b'(228.6 228.7 228.6 000 50.0 13.5 --.- 00001000\r\x00'
Decoded:
  - Input voltage       : 228.6V
  - Input fault voltage : 228.7V
  - Output voltage      : 228.6V
  - Output load         : 0%
  - Output frequency    : 50.0Hz
  - Battery voltage     : 13.5V
  - Internal temperature: -127.0°C
  - Status:
    - Utility fail            : no
    - Battery low             : no
    - Boost/Buck mode active  : no
    - UPS fauilure            : no
    - UPS is Line-interactive : yes
    - Running Self-test now   : no
    - UPS is in shutdown state: no
    - Beeper is active        : no
```

### Toggle beeper

Toggle beeper on/off in UPS in most actions (like: test, working from battery mode, ...)

Beeper status is reported in flags in **Query Status** command response

Command: ```hidups-qx.py <vid> <pid> -c q```

Example result:
```
saper@t620:~/hid $ ./hidups-qx.py 0665 5161 -c q
UPS HID Voltronic-QS communication script by saper_2 version: 20230610
VID:PID : 0665:5161
Endpoint: 0x81
Command : Toggle beeper [Q]
Timeout : 1000ms
Selected device basic info:
Configuration: 1
  - Interface: #0 (alt: 0)
    - Endpoint adr: 0x81
  - Interface: #1 (alt: 0)
    - Endpoint adr: 0x82


Selecting device <0665:5161>, configuration, interface (0) & endpoint 0x81 (IN, #0)
Checking if kernel_driver is attached to interface #0, and removing it in case...
Nope - OK.

Command to send: 51 0D >>> b'Q\r' <<<
Nothing to read.
```

### Run Self-Test

Start 10sec self-test - switch to battery mode for 10sec. Monitoring Vbatt while test and after it, can tell in what condition is battery.

Command: ```hidups-qx.py <vid> <pid> -c t```

Example output:
```
UPS HID Voltronic-QS communication script by saper_2 version: 20230610
VID:PID : 0665:5161
Endpoint: 0x81
Command : Test 10sec [T]
Timeout : 1000ms
Selected device basic info:
Configuration: 1
  - Interface: #0 (alt: 0)
    - Endpoint adr: 0x81
  - Interface: #1 (alt: 0)
    - Endpoint adr: 0x82


Selecting device <0665:5161>, configuration, interface (0) & endpoint 0x81 (IN, #0)
Checking if kernel_driver is attached to interface #0, and removing it in case...
Nope - OK.

Command to send: 54 0D >>> b'T\r' <<<
Nothing to read.
```

### Query internals (?)
This command return some more information about UPS, but there is no information what field contains what kind of information...

Command: ```hidups-qx.py <vid> <pid> -c qs```

Example response:
```
UPS HID Voltronic-QS communication script by saper_2 version: 20230610
VID:PID : 0665:5161
Endpoint: 0x81
Command : Query internals? [QI]
Timeout : 1000ms
Selected device basic info:
Configuration: 1
  - Interface: #0 (alt: 0)
    - Endpoint adr: 0x81
  - Interface: #1 (alt: 0)
    - Endpoint adr: 0x82


Selecting device <0665:5161>, configuration, interface (0) & endpoint 0x81 (IN, #0)
Checking if kernel_driver is attached to interface #0, and removing it in case...
Nope - OK.

Command to send: 51 49 0D >>> b'QI\r' <<<
UPS response: (len=56bytes)
  HEX:  28 30 39 39 20 30 32 39 32 30 20 35 30 2E 31 20 30 30 30 2E 30 20 31 36 39 20 32 37 39 20 30 20 30 30 30 30 30 31 30 30 30 30 31 30 32 30 30 30 0D 00 00 00 00 00 00 00
  STR: b'(099 02920 50.1 000.0 169 279 0 0000010000102000\r\x00\x00\x00\x00\x00\x00\x00'
```

### Shutdown command

This command make UPS to switch off output after specified time, and restore it's output. This command require 2 more parameter to be specified:
- ```-st x.x``` - *[float number]* shutdown delay in 6sec units (if value is below 1.0) or 1min units if value is  equal/over 1.0 (decimal part is ignored, only integer part is used) . Value will be always rounded to 1 decimal place. e.g. values: ```0.2```=12sec, ```0.7```=42sec, ```1.0```=1min, ```4.5```=5min (value will be rounded to integer 5), ```0.0```=instant switch off output.
- ```-sr y``` - *[integer number]* delay in min. before output is switched back on. If value is ```0``` then output can be switched back on only by **Cancel** command. 

Command: ```hidups-qx.py <vid> <pid> -c s -st x.x -sr y``` (switch off output in ```x.x``` (sec/min) and restore after ```y``` min.)

Example output (shutdown output after 12sec, then restore after 1min):
```
saper@t620:~/hid $ ./hidups-qx.py 0665 5161 -c s -st 0.2 -sr 1
UPS HID Voltronic-QS communication script by saper_2 version: 20230610
VID:PID : 0665:5161
Endpoint: 0x81
Command : Shutdown (delay: 12s, restore: 1m) [S.2R0001]
Timeout : 1000ms
Selected device basic info:
Configuration: 1
  - Interface: #0 (alt: 0)
    - Endpoint adr: 0x81
  - Interface: #1 (alt: 0)
    - Endpoint adr: 0x82


Selecting device <0665:5161>, configuration, interface (0) & endpoint 0x81 (IN, #0)
Checking if kernel_driver is attached to interface #0, and removing it in case...
Nope - OK.

Command to send: 53 2E 32 52 30 30 30 31 0D >>> b'S.2R0001\r' <<<
Nothing to read.

```

### Cancel test/shutdown
Instantly cancel: self-test or shutdown command. If UPS out was switched off by shutdown command it cancel restore timer and switch output back **on** instantly.

Command: ```hidups-qx.py <vid> <pid> -c c```

Example output:
```
saper@t620:~/hid $ ./hidups-qx.py 0665 5161 -c c
UPS HID Voltronic-QS communication script by saper_2 version: 20230610
VID:PID : 0665:5161
Endpoint: 0x81
Command : Cancel test/shutdown/restore delay/OFF [C]
Timeout : 1000ms
Selected device basic info:
Configuration: 1
  - Interface: #0 (alt: 0)
    - Endpoint adr: 0x81
  - Interface: #1 (alt: 0)
    - Endpoint adr: 0x82


Selecting device <0665:5161>, configuration, interface (0) & endpoint 0x81 (IN, #0)
Checking if kernel_driver is attached to interface #0, and removing it in case...
Nope - OK.

Command to send: 43 0D >>> b'C\r' <<<
Nothing to read.
```

----
----
----

# hidups-qs-json
This is variation of ```hidups-qs.py``` script that take instead of multiple command line parameters, it take either one command line parameter (string) in JSON format or read JSON from STDIN. 
Script return JSON to STDOUT.

```bash
saper@t620:~/hid $ ./hidups-qx-json.py '{"vid":"0665","pid":"5161","cmd":"c"}'
{
  "version": "20230610", 
  "result": 0, 
  "resultstr": "ok", 
  "dev": {"vid": "0665", "pid": "5161", "endpoint": "81", "cfg": [{"cv": 1, "if": [{"n": 0, "alt": 0, "ep": [{"ad": "81"}]}, {"n": 1, "alt": 0, "ep": [{"ad": "82"}]}]}], 
  "sel": {"if": 0, "ep": "81", "epidx": 0}}, 
  "cmd": {"cmd": "C", "res": 0, "rlen": 0, "rhex": "", "r": {}}, 
  "tout": 1000, 
  "kernel": {"d": 0, "r": 0}
}
```

STDIN method (`^D` is `Ctrl+D` for signalizing close stream/file):
```bash
saper@t620:~/hid $ ./hidups-qx-json.py
{"vid":"0665","pid":"5161","cmd":"qs"}^D
{
  "version": "20230610", 
  "result": 0, 
  "resultstr": "ok", 
  "dev": {"vid": "0665", "pid": "5161", "endpoint": "81", 
    "cfg": [{"cv": 1, "if": [{"n": 0, "alt": 0, "ep": [{"ad": "81"}]}, {"n": 1, "alt": 0, "ep": [{"ad": "82"}]}]}], "sel": {"if": 0, "ep": "81", "epidx": 0}
  }, 
  "cmd": {
    "cmd": "QS", 
    "res": 1, 
    "rlen": 48, 
    "rhex": "283233302E38203233302E38203233302E38203030302035302E302031332E36202D2D2E2D2030303030313030300D00", 
    "r": {
      "ok": 0, 
      "str": "230.8 230.8 230.8 000 50.0 13.6 --.- 00001000", 
      "inVolt": 230.8, "inVoltFault": 230.8, 
      "outVolt": 230.8, "outLoad": 0, 
      "outFreq": 50.0, "battVolt": 13.6, 
      "intTemp": -127.0, 
      "status": {
        "utilFail": 0, "loBatt": 0, 
        "boostBuckOn": 0, "upsFault": 0, 
        "lineInter": 1, "selfTest": 0, 
        "upsShdn": 0, "beeper": 0, 
        "raw": "00000000"
      }
    }
  }, 
  "tout": 1000, 
  "kernel": {"d": 0, "r": 0}
}
```

## Input JSON
It can be read as first command line argument (enclosed in quotes as string argument), or entered from STDIN (if is used terminal then end of JSON string must be _confirmed_ with ```Ctrl+D``` that signalize "closing" STDIN and ending input).

It's elements are basically identical to parameters of command line.

Full input JSON: 
```JSON
{"vid":"0000","pid":"0000","ep":"00","cmd":"xx","st":0.0,"sr":0,"to":0}
```

Like in command line version, some keys must be always, while other depends on command. For `shutdown` command details check it's paragraph.

|Key|Value type|Mandatory?|Default value|Description|
|-|-|-|-|-|
|`vid`|4 digit hex|**mandatory**|`0665`|UPS USB VendorID (VID)|
|`pid`|4 digit hex|**mandatory**|`5161`|UPS USB ProductID (PID)|
|`ep`|2 digit hex|*optional*|`81`|UPS HID Descriptor endpoint, optional, default|
|`cmd`|string|**mandatory**|none|Command for UPS|
|`st`|float|required by shutdown|none|Shutdown delay before switching output OFF|
|`sr`|int|required by shutdown|none|Delay before switching output back ON|
|`to`|int|optional|`1000`|Command send/receive data to/from UPS timeout in [ms]|

Minimum input JSON:
```JSON
{"vid":"0000","pid":"0000","cmd":"xx"}
```

## Available commands
- ```m```  - Query UPS for protocol variant
- ```f```  - Query UPS for it's ratings,
- ```qs``` - Query UPS for it's status,
- ```qi``` - Query UPS for internal status(?) - *no info about response fields*
- ```t``` - Run Self-Test by UPS,
- ```c``` - Cancel self-test or Shutdown command,
- ```s``` - Start shutdown sequence (requires `st` & `sr` keys), can be canceled by **Cancel** command in any moment,

### Command: Shutdown

This command make UPS to switch OFF output after specified time, and restore it's output state back ON. This command require 2 more keys to be specified: **st** and **sr**.

- ```st``` - *[float number]* shutdown delay in 6sec units (if value is below 1.0) or 1min units if value is  equal/over 1.0 (decimal part is ignored, only integer part is used) . Value will be always rounded to 1 decimal place. 
e.g. values: 
  - ```0.2```=12sec *(2x6sec=12sec)*, 
  - ```0.7```=42sec *(7x6sec=42sec)*, 
  - ```1.0```=1min *(1x1min=1min)*, 
  - ```4.5```=5min *(`round(4.5)=5` 5x1min=5min)*, 
  - ```3.2```=3min *(`round(3.2)=3` 3x1min=3min)*, 
  - ```0.0```=instant switch off output.
- ```sr``` - *[integer number]* delay in min. before output is switched back ON. 
  If value is ```0``` then output can be switched back ON only by **Cancel** command. 

Example input JSON (switch OFF after 36sec, and switch back ON after 3min): 
```JSON
{"vid":"0665","pid":"5161","cmd":"s","st":0.6,"sr":3}
```

## Output JSON

Output JSON have few keys that are always present, and reading them can tell if script failed or succeeded.

There will be always those keys in JSON:
- `version` - script version
- `result` - non-0 value means error. Most errors starts from 100. **0** is OK :heavy_check_mark:, See paragraph [Result codes and script exit codes](#result-codes-and-script-exit-codes)
- `resultstr` - error in text format (for human to understand :smiley: ),

Other fields depends, usually there will be :
- `dev` - Device information (VID,PID,Selected endpoint, read config fro device...)
- `cmd` - Command information and optional result
- `tout` - Timeout value used for communication [ms]
- `kernel` - Information about attempt to detach default kernel driver from endpoint.

### Output JSON - Field: `kernel`
```JSON
"kernel": {"d": 0, "r": 0}
```

- `d` - tell if default kernel driver was detached: 0=not needed, 1=detached OK, -1=error while trying to detach,
- `r` - detach function result code (0=OK)

### Output JSON - Field: `dev`
```JSON
"vid": "0665", "pid": "5161", "endpoint": "81", 
"cfg": [
  {"cv": 1, "if": 
    [
      {"n": 0, "alt": 0, "ep": 
      [
        {"ad": "81"}
      ]}, 
      {"n": 1, "alt": 0, "ep": 
      [
        {"ad": "82"}
      ]}
    ]
  }
], 
"sel": {
  "if": 0, "ep": "81", "epidx": 0
}
```

In `dev` there are keys:
- `vid` - Selected USB device VID (hex 4 digit),
- `pid` - Selected USB device PID (hex 4 digit),
- `endpoint` - Selected Endpoint address (hex 2 digit),
- `cfg` - Array of device configurations read from USB Descriptor: 
  - `cv` - descriptor bConfigurationValue (int)
  - `if` - Array of interfaces in this configuration:
    - `n` - Interface bInterfaceNumber
    - `alt` - Interface bAlternateSetting
    - `ep` - Array of interface endpoints:
      - `ad` - Endpoint address bEndpointAddress
- `sel` - Information about selected interface and endpoint
  - `if` - selected bInterfaceNumber
  - `ep` - selected bEndpointAddress
  - `epidx` - selected endpoint index in interface

### Output JSON - Field: `cmd`
```JSON
"cmd": {
  "cmd": "M", "res": 1, "rlen": 8, "rhex": "480D000000000000", 
  "r": {"ok": 0, "variant": "H"}
  }
```

In cmd there are always keys:
- `cmd` - command that was sent to UPS,
- `res` - tell if there should be response for command (0=no/1=yes),
- `rlen` - length of response,
- `rhex` - response converted from byte-array to hex-string.
- `r` -  empty object (if no response for command) or decoded response - depending on command will have different keys.

#### Decoded response for `M` - Query protocol variant
```JSON
"r": {"ok": 0, "variant": "H"}
```

More about protocol variants: https://networkupstools.org/protocols/voltronic-qs.html#V-protocol-queries

- `ok` - response decode result: `0` = **OK**, any other value means error,
- `variant` - string, one letter indicating protocol variants, variants:
  - `V`
  - `H` - almost identical like `V`, for details see `V` protocol
  - There are others variants too, but this script don't support those:
    - `P`
    - `T`


#### Decoded response for `F` - Query for ratings
```JSON
"r": {
  "ok": 0, "str": "230.0 003 12.00 50.0", 
  "nomVOut": 230.0, "nomIOut": 3.0, "nomVBatt": 12.0, "nomFOut": 50.0
  }
```

- `ok` - response decode result: `0` = **OK**, any other value means error,
- `str` - read response string from UPS,
- `nomVOut` - nominal output voltage,
- `nomIOut` - nominal output current,
- `nomVBatt` - nominal battery voltage,
- `nomFOut` - nominal output frequency.

#### Decoded response for `QS` - Query status
```JSON
"r": {
  "ok": 0, "str": "237.1 237.1 237.1 000 50.0 13.6 --.- 00001000", 
  "inVolt": 237.1, "inVoltFault": 237.1, 
  "outVolt": 237.1, "outLoad": 0, "outFreq": 50.0, "battVolt": 13.6, "intTemp": -127.0, 
  "status": {
    "utilFail": 0, "loBatt": 0, 
    "boostBuckOn": 0, "upsFault": 0, 
    "lineInter": 1, "selfTest": 0, 
    "upsShdn": 0, "beeper": 0, 
    "raw": "00000000"
    }
  }
```

- `ok` - response decode result: `0` = **OK**, any other value means error,
- `str` - read response string from UPS,
- `inVolt` - input voltage,
- `inVoltFault` - input fault voltage,
- `outVolt` - output voltage,
- `outLoad` - output load in %,
- `outFreq` - output frequency,
- `battVolt` - battery voltage,
- `intTemp` - internal temperature, if value is `-127.0` that means field was empty (`--.-`) - ups don't report this,
- `status` - object with decoded status flags, flag can be 0=false/off or 1=true/on: 
  - `utilFail` - Utility fail,
  - `loBatt` - Low battery,
  - `boostBuckOn` - Boost/Buck mode is active (it means that UPS is working from battery),
  - `upsFault` - error inside UPS,
  - `lineInter` - UPS is Line-Interactive,
  - `selfTest` - Self-test status,
  - `upsShdn` - UPS is in Shutdown state (shutdown command is active),
  - `beeper` - Beeper/buzzer status on/off,
  - `raw` - string with raw flags values.


#### Decoded response for `QI` - Query internals (?)
It's unknown what this commands returns :disappointed: so there is no decoder for it.
```JSON
 "r": {"ok": 0, "str": "100 02921 50.0 000.0 169 279 0 0000010000112000"}
```

### Result codes and script exit codes
- ``0`` - OK
- ``100`` - Key value `st` (Shutdown delay) can not be negative
- ``101`` - key value `sr` (Shutdown delay before restore output) can not be negative
- ``102`` - Keys `st` and `sr` have to be defined when using Shutdown `s` command.
- ``103`` - Device not found.
- ``104`` - Endpoint not found in device.
- ``105`` - No interface selected.
- ``106`` - Failed to detach kernel driver from interface.
- ``107`` - Failed to write data to USB Device (ctrl_transfer failed).
- ``108`` - USBTimeoutError while trying to read response from USB device.
- ``109`` - General error while trying to read response from USB device.
- ``110`` - Loading input parameters in JSON format failed (JSON string parsing error).
- ``111`` - Missing required keys in input JSON (required: vid, pid, cmd).
- ``112`` - Invalid format of value VID,PID,Endpoint,timeout in input JSON.
- ``113`` - Invalid format of value st(float)/sr(int) in input JSON.
- ``114`` - Invalid UPS command `xx` in input JSON.
- ``115`` - Decoding CMD response from UPS failed.
- ``116`` - No response for CMD from UPS but expected one.


