#!/usr/bin/env python3
# To toals with most HID UPS, it work sending controll message with command, and receive reponse from endpoint 1 (0x81).
# This script works using popular protocol: Voltronic-QS
import sys
import usb.core
import usb.util
import argparse
import functools

vid=0x0665
pid=0x5161
defep=0x81
cmdtimeout=1000
version="20230610"

# ------------------------------------------------------------------------------------------------------------------
# ------------------------------------------------------------------------------------------------------------------
# ------------------------------------------------------------------------------------------------------------------
# argparse - handling command line arguments
# ------------------------------------------------------------------------------------------------------------------
# ------------------------------------------------------------------------------------------------------------------

# arguments
parser = argparse.ArgumentParser(prog="hidups-qx.py", description="Script allow for simple query and change some options of UPS that use usb hid device class and Voltronic-QS protocol",epilog="For more details about Voltronic-QS protocol (V variant and H variant seems identical) see NUT documentation: https://networkupstools.org/protocols/voltronic-qs.html#V-protocol-queries ")
parser.add_argument('vid', type=ascii,help="VID of USB (hex 4 digit)", default=f"{vid:04X}") #functools.wraps(int)(lambda x: int(x,0))
parser.add_argument('pid', type=ascii,help="PID of USB (hex 4 digit)", default=f"{pid:04X}") #functools.wraps(int)(lambda x: int(x,0))
parser.add_argument('-ep', type=ascii, help="Endpoint number for reading response (hex 2 digit)",default=f"{defep:02x}")
parser.add_argument('-c', choices=['qs','f','qi','t','q','m','c','s'], required=True, help="Select command to send to UPS. Available commands: qs=query status, f=query ratings, qi=query ?, t=run 10s test, q=toggle beeper, m=query proto variant, c=cancel shutdown, s=shutdown (require parameters -st and -sr to be set)")
parser.add_argument('-st', type=float, help="[float] Shutdown delay before UPS switch OFF output [minutes]. Value below 1.0 is treated as decimal of 1min (0.1=6sec), value <1.0 will be rounded to 1 digit after decimal point. Value >=1.0 will be rounded to an integer. 0=instant shutdown. Use cmd: cancel to cancel delay. (parameter required for shutdown command)")
parser.add_argument('-sr', type=int, help="[int] Shutdown delay before restoring output to ON [minutes]. 0=don't restore. Use cmd: cancel to restore output ON. (parameter required for shutdown command)")
parser.add_argument('-to', type=int, default=cmdtimeout, help="[int] Timeout for command/response in ms. This can be changed if 1000ms is not enough for ups to send complete response.")
args = parser.parse_args()

# ------------------------------------------------------------------------------------------------------------------
# ------------------------------------------------------------------------------------------------------------------
# ------------------------------------------------------------------------------------------------------------------
# Defaults
# ------------------------------------------------------------------------------------------------------------------
# ------------------------------------------------------------------------------------------------------------------

#print(dir(args))
#print(vars(args))
print("UPS HID Voltronic-QS communication script by saper_2 version:",version)
# strip quotes and 0x if user adds
vid=int(args.vid.lower().replace("'","").replace("0x",""),16)
pid=int(args.pid.lower().replace("'","").replace("0x",""),16)
defep=int(args.ep.lower().replace("'","").replace("0x",""),16)
cmdtimeout=int(args.to)
sht=-1.0
shr=-1

# ------------------------------------------------------------------------------------------------------------------
# ------------------------------------------------------------------------------------------------------------------
# ------------------------------------------------------------------------------------------------------------------
# Functions used by script
# ------------------------------------------------------------------------------------------------------------------
# ------------------------------------------------------------------------------------------------------------------

#return shutdown delay in human string
def get_shutdown_delay_string_value(st):
    # seconds
    if (st<1.0):
        v=int(round(st,1)*60)
        return f"{v}s"
    # mins
    v=int(st)
    return f"{v}m"

#return shutdown command paramters in string format
def get_shutdown_params(st,sr):
    res = ""
    # shutdown delay
    if (st<1.0):
        v=int(round(st*10,0))
        res += f".{v}"
    else:
        v=int(round(st,0))
        res += f"{v:02}"
    # restore delay
    v=int(sr)
    res += f"R{v:04}"
    return res

# return array as hex-string with optional byte-separator
def array_to_hexstring(arr, sep=""):
    res=""
    for v in arr:
        res += f"{v:02X}"+sep
    return res.rstrip()

# decode float string value, if it have "--.-" (value not exists/not reported) then it'll return re_error value
def decode_float(floatstr, re_error=0.0):
    try:
        return float(floatstr)
    except:
        return re_error
    return re_error
    
# decode QS (Query Status) command response into JSON'able object :-)
def decode_qs_response(buf):
    # check first character, QS response start with "("
    if (buf[0]!=ord('(')):
        return None
    # decode to string, remove "(" and CR+0x00 from end
    str = buf.decode()[1:][:-2]
    sarr = str.split(" ")
    rj = { "str": str, "inVolt": 0.0, "inVoltFault": 0.0, "outVolt": 0.0, "outLoad": 0, "outFreq": 0.0, "battVolt": 0.0, "intTemp": 0.0, 
            "status": { "utilFail":0, "loBatt": 0, "boostBuckOn": 0, "upsFault": 0, 
                        "lineInter": 0, "selfTest": 0, "upsShdn": 0, "beeper": 0, "raw":"00000000" }}
    try:
        rj["inVolt"]=decode_float(sarr[0])
        rj["inVoltFault"]=decode_float(sarr[1])
        rj["outVolt"]=decode_float(sarr[2])
        rj["outLoad"]=int(sarr[3])
        rj["outFreq"]=decode_float(sarr[4])
        rj["battVolt"]=decode_float(sarr[5])
        rj["intTemp"]=decode_float(sarr[6],-127.0)
        s = int(sarr[7],2) # bin to int/byte
        rj["status"]["utilFail"]    = (1 if ((s&0x80)==0x80) else 0)
        rj["status"]["loBatt"]      = (1 if ((s&0x40)==0x40) else 0)
        rj["status"]["boostBuckOn"] = (1 if ((s&0x20)==0x20) else 0)
        rj["status"]["upsFault"]    = (1 if ((s&0x10)==0x10) else 0)
        rj["status"]["lineInter"]   = (1 if ((s&0x08)==0x08) else 0)
        rj["status"]["selfTest"]    = (1 if ((s&0x04)==0x04) else 0)
        rj["status"]["upsShdn"]     = (1 if ((s&0x02)==0x02) else 0)
        rj["status"]["beeper"]      = (1 if ((s&0x01)==0x01) else 0)
        rj["status"]["raw"] = f"{s:08b}"
    except Exception as e:
        print("Error: ",e)
    # return dict/json :-)
    return rj

# decode F (Query Ratings) command response into JSON'able object :-)
def decode_f_response(buf):
    # check first character, F response start with "#"
    if (buf[0]!=ord('#')):
        return None
    # decode to string, remove "(" and CR+0x00 from end
    str = buf.decode()[1:][:-2].rstrip()
    sarr = str.split(" ")
    rj = { "str": str, "nomVOut": 0.0, "nomIOut": 0.0, "nomVBatt": 0.0, "nomFOut": 0.0 }
    try:
        rj["nomVOut"]=decode_float(sarr[0])
        rj["nomIOut"]=decode_float(sarr[1])
        rj["nomVBatt"]=decode_float(sarr[2])
        rj["nomFOut"]=decode_float(sarr[3])
    except Exception as e:
        print("Error: ",e)
    # return dict/json :-)
    return rj

# decode M (query protocol variant) command response into JSON'able object :-)
def decode_m_response(buf):
    # Get first letter from string - it's protocol variant decode to string, remove "(" and CR+0x00 from end
    str = buf.decode().rstrip('\x00').rstrip()
    rj = { "variant": "?" }
    try:
        rj["variant"]=str
    except Exception as e:
        print("Error: ",e)
    # return dict/json :-)
    return rj

# ------------------------------------------------------------------------------------------------------------------
# ------------------------------------------------------------------------------------------------------------------
# ------------------------------------------------------------------------------------------------------------------
# Script start
# ------------------------------------------------------------------------------------------------------------------
# ------------------------------------------------------------------------------------------------------------------

print(f"VID:PID : {vid:04x}:{pid:04x}")
print(f"Endpoint: 0x{defep:02x}")

if (args.st is not None):
    sht=args.st
    if (sht<0):
        print("\033[31m\033[1m-st\033[0m\033[31m can not be negative number.")
        sys.exit(100)
    if (sht<1.0):
        sht=round(sht,1)
    else:
        sht=round(sht,0)

if (args.sr is not None):
    shr=args.sr
    if (shr<0):
        print("\033[31m\033[1m-sr\033[0m\033[31m can not be negative number.")
        sys.exit(101)
    
# check params for shutdown command    
if ((args.c == "s") and ((args.st is None) or (args.sr is None))):
    print("\033[31mFor shutdown command arguments\033[1m -st \033[0m\033[31m & \033[1m-sr \033[0m\033[31m must be defined\033[0m") 
    sys.exit(102)


cmd="?" # command for UPS ['qs','f','qi','t','q','m','c','s']
cmdre=0 # command have response to get?
cmdstr="" # command decription
if args.c == "qs":
    cmd="QS"
    cmdstr="Query status"
    cmdre=1
elif args.c == "f":
    cmd="F"
    cmdstr="Query ratings"
    cmdre=1
elif args.c == "qi":
    cmd="QI"
    cmdstr="Query internals?"
    cmdre=1
elif args.c == "t":
    cmd="T"
    cmdstr="Test 10sec"
    cmdre=0
elif args.c == "q":
    cmd="Q"
    cmdstr="Toggle beeper"
    cmdre=0
elif args.c == "m":
    cmd="M"
    cmdstr="Query VoltronicQS protocol variant"
    cmdre=1
elif args.c == "c":
    cmd="C"
    cmdstr="Cancel test/shutdown/restore delay/OFF"
    cmdre=0
elif args.c == "s":
    cmd="S"+get_shutdown_params(sht,shr)
    st=get_shutdown_delay_string_value(sht)
    cmdstr=f"Shutdown (delay: {st}, restore: {shr}m)"
    cmdre=0


print(f"Command : {cmdstr} [{cmd}]")
print(f"Timeout : {cmdtimeout}ms")

# ------------------------------------------------------------------------------------------------------------------
# Find USB & select handles/objects/etc...
# ------------------------------------------------------------------------------------------------------------------
# find device on usb bus
dev = usb.core.find(idVendor=vid, idProduct=pid)
# Was it found?
if dev is None:
    print('Device not found')
    sys.exit(103)

# selected endpoint
sep = None
# show some info
selintf=-1
print("Selected device basic info:")
for cfg in dev:
    print(f'Configuration: {cfg.bConfigurationValue}')
    for intf in cfg:
        print(f'  - Interface: #{intf.bInterfaceNumber} (alt: {intf.bAlternateSetting})')
        for ep in intf:
            print(f'    - Endpoint adr: 0x{ep.bEndpointAddress:02x}' )
            if (ep.bEndpointAddress == defep):
                sep=ep
                selintf=intf.bInterfaceNumber

if (sep is None):
    print(f'Endpoint 0x{defep:02x} not found.');
    sys.exit(104)

if (selintf == -1):
    print('No interface selected, seems like Endpoint might not be found too.')
    sys.exit(105)

#device name
# bug: from time-to-time it throws error :/
# force langid
#dev._langids=(1033,)
# and get device name
#devname=usb.util.get_string(dev,dev.iProduct)
#print(f"iProduct: {devname}")

print()
print()
#print(f"Selecting device <{vid:04X}:{pid:04X}> '{devname}', configuration, interface ({selintf}) & endpoint 0x{defep:02x} (IN, #{sep.index})")
print(f"Selecting device <{vid:04X}:{pid:04X}>, configuration, interface ({selintf}) & endpoint 0x{defep:02x} (IN, #{sep.index})")
#print(dir(sep))

cfg = dev[0]
#print("Device:")
#print(cfg)
#print(dir(cfg.interfaces()))
#print("----------------------------------------------------")
#print("----------------------------------------------------")
intf = cfg[(selintf,0)] #(1,0) / (0,0)
#print("print intf:")
#print(intf)
#print("----------------------------------------------------")
#print("----------------------------------------------------")
#ep = intf[0]
#print("Endpoint:")
#print(sep)
#print(dir(ep))
#print("----------------------------------------------------")
#print("----------------------------------------------------")

print(f"Checking if kernel_driver is attached to interface #{intf.bInterfaceNumber}, and removing it in case...")
if dev.is_kernel_driver_active(intf.bInterfaceNumber):
    print("Detaching kernel-driver...")
    try:
        dev.detach_kernel_driver(intf.bInterfaceNumber)
        print("Detached.")
    except Exception as ee:
        print("Detaching kernel driver failed.",str(ee))
        sys.exit(106)
else:
    print("Nope - OK.")

print();

# ------------------------------------------------------------------------------------------------------------------
# ------------------------------------------------------------------------------------------------------------------
# ------------------------------------------------------------------------------------------------------------------
# Comm. with UPS
# ------------------------------------------------------------------------------------------------------------------
# ------------------------------------------------------------------------------------------------------------------

cmd2=cmd+"\x0d"
cmdbuf=bytearray(bytes(cmd2,"ascii"))
print(f"Command to send: {array_to_hexstring(cmdbuf,' ')} >>> {bytes(cmd2,'ascii')} <<<")
#buf=bytes([0x51,0x53,0x0D]) # QS - query status
#buf=bytes([0x46,0x0D]) # F - query ratings
#buf=bytes([0x51,0x49,0x0D]) # QI - ??
#buf=bytes([0x54,0x0D]) # T - 10sec test (nothing is returned)
#buf=bytes([0x51,0x0D]) # Q - toggle beeper  (nothing is returned)
#buf=bytes([0x4D,0x0D]) # M - query for protocol 
#buf=bytes([0x51,0x0D]) # C - cancel shutdown (nothing is returned)
#buf=bytes([0x53,0x2E,0x35,0x52,0x30,0x30,0x30,0x31,0x0D]) # S - shutdown "S.5R0001" (nothing is returned ; shutdown in 30sec, restore output after 1min)
#dev.ctrl_transfer(bmRequestType, bRequest, wValue=0, wIndex=0, data_or_wLength=None, timeout=None)
# send command to UPS
try:
    dev.ctrl_transfer(0x21,9, 0x200, 0, cmdbuf,cmdtimeout);
except Exception as ee:
    print("Sending command to UPS failed.",str(ee))
    sys.exit(107)

# ------------------------------------------------------------------------------------------------------------------
# handling response from UPS
# ------------------------------------------------------------------------------------------------------------------
if (cmdre>0):
    re=None
    try:
        re=dev.read(sep.bEndpointAddress, 64, cmdtimeout).tobytes()
        print(f"UPS response: (len={len(re)}bytes)")
        print(f"  HEX:  {array_to_hexstring(re,' ')}")
        print(f"  STR: {re}")
    except usb.core.USBTimeoutError:
        print("Nothing to read <timeout>")
        sys.exit(108)
    except Exception as err:
        print("Exception reading data from Endpint: ", str(err))
        sys.exit(109)
    # try decoding
    if (re is not None):
        # try QS
        if (cmd == "QS"):
            resp=decode_qs_response(re)
            if (resp is not None):
                print("Decoded:")
                print(f"  - Input voltage       : {resp['inVolt']}V")
                print(f"  - Input fault voltage : {resp['inVoltFault']}V")
                print(f"  - Output voltage      : {resp['outVolt']}V")
                print(f"  - Output load         : {resp['outLoad']}%")
                print(f"  - Output frequency    : {resp['outFreq']}Hz")
                print(f"  - Battery voltage     : {resp['battVolt']}V")
                print(f"  - Internal temperature: {resp['intTemp']}\u00b0C")
                print( "  - Status:")
                print(f"    - Utility fail            : {('yes' if resp['status']['utilFail']    else 'no')}")
                print(f"    - Battery low             : {('yes' if resp['status']['loBatt']      else 'no')}")
                print(f"    - Boost/Buck mode active  : {('yes' if resp['status']['boostBuckOn'] else 'no')}")
                print(f"    - UPS fauilure            : {('yes' if resp['status']['upsFault']    else 'no')}")
                print(f"    - UPS is Line-interactive : {('yes' if resp['status']['lineInter']   else 'no')}")
                print(f"    - Running Self-test now   : {('yes' if resp['status']['selfTest']    else 'no')}")
                print(f"    - UPS is in shutdown state: {('yes' if resp['status']['upsShdn']     else 'no')}")
                print(f"    - Beeper is active        : {('yes' if resp['status']['beeper']      else 'no')}")
                #print("DecodedQS: ",resp)
        # try F
        elif (cmd == "F"):
            resp=decode_f_response(re)
            if (resp is not None):
                #rj = { "str": str, "nomVOut": 0.0, "nomIOut": 0.0, "nomVBatt": 0.0, "nomFOut": 0.0 }
                print("Decoded:")
                print(f"  - Nominal output voltage  : {resp['nomVOut']}V")
                print(f"  - Nominal output current  : {resp['nomIOut']}A")
                print(f"  - Nominal battery voltage : {resp['nomVBatt']}V")
                print(f"  - Nominal output frequency: {resp['nomFOut']}Hz")
                #print("DecodedF: ",resp)
        # M
        elif (cmd == "M"):
            resp=decode_m_response(re)
            print("Decoded:")
            print("  Protocol variant:",resp["variant"])
            #print("DecodedM:",resp)
    
else:
    print("Nothing to read.")

# ------------------------------------------------------------------------------------------------------------------
# ------------------------------------------------------------------------------------------------------------------
# Script end.
# ------------------------------------------------------------------------------------------------------------------
# ------------------------------------------------------------------------------------------------------------------
sys.exit(0)
