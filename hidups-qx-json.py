#!/usr/bin/env python3
# To toals with most HID UPS, it work sending controll message with command, and receive reponse from endpoint 1 (0x81).
# This script works using popular protocol: Voltronic-QS
# This is variant for JSON responses
import sys
import usb.core
import usb.util
import functools
import json

vid=0x0665
pid=0x5161
defep=0x81
cmdtimeout=1000
version="20230610"

jsonresp={ "version": f"{version}", "result": -1, "resultstr": "-" }

# arguments
# input JSON: {"vid":"<vid>","pid":"<pid>","ep":"<endpoint>","cmd":"xx","st":t.t,"sr":y,"to":zzzz}
# {
#   "vid":"<vid>", -- UPS USB VID 4 hex digit
#   "pid":"<pid>", -- UPS USB PID 4 hex digit
#   "ep":"<endpoint>", -- optional, USB UPS Endpoint number (2 digit hex, default 81)
#   "cmd":"xx", -- Select command to send to UPS
#   "st":t.t, -- Shutdown delay before UPS switch OFF output [minutes]. Value below 1.0 is treated as decimal of 1min (0.1=6sec), value <1.0 will be rounded to 1 digit after decimal point. Value >=1.0 will be rounded to an integer. 0=instant shutdown. Use Cancel command to cancel shutdown. Parameter required for shutdown command.
#   "sr":y, -- Shutdown delay before restoring output to ON [minutes]. 0=don't restore. Use Cancel command to instantly restore output ON. Parameter required for shutdown command.
#   "to":zzzz -- Timeout for command/response in ms. This can be changed if 1000ms is not enough for ups to send complet response.
# }
# Command cmd 'xx' can be:
#  - qs -- query status
#  - f  -- query ratings
#  - qi -- query internals?
#  - t  -- run 10s test
#  - q  -- toggle beeper
#  - m  -- query proto variant
#  - c  -- cancel shutdown
#  - s  -- shutdown (require `st` and `sr` parameters too) 

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
    rj = { "ok": 1, "str": "", "inVolt": 0.0, "inVoltFault": 0.0, "outVolt": 0.0, "outLoad": 0, "outFreq": 0.0, "battVolt": 0.0, "intTemp": 0.0, 
            "status": { "utilFail":0, "loBatt": 0, "boostBuckOn": 0, "upsFault": 0, 
                        "lineInter": 0, "selfTest": 0, "upsShdn": 0, "beeper": 0, "raw":"00000000" }}
    # check first character, QS response start with "("
    if (buf[0]!=ord('(')):
        rj["ok"]=2
        return rj
    # decode to string, remove "(" and CR+0x00 from end
    str = buf.decode()[1:][:-2]
    sarr = str.split(" ")
    rj["str"]=str
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
        rj["ok"] = 0
    except:
        rj["ok"] = 3
    # return dict/json :-)
    return rj

# decode F (Query Ratings) command response into JSON'able object :-)
def decode_f_response(buf):
    rj = { "ok": 1, "str": "", "nomVOut": 0.0, "nomIOut": 0.0, "nomVBatt": 0.0, "nomFOut": 0.0 }
    # check first character, F response start with "#"
    if (buf[0]!=ord('#')):
        rj["ok"]=2
        return rj
    # decode to string, remove "(" and CR+0x00 from end
    str = buf.decode()[1:][:-2].rstrip()
    sarr = str.split(" ")
    rj["str"]=str
    try:
        rj["nomVOut"]=decode_float(sarr[0])
        rj["nomIOut"]=decode_float(sarr[1])
        rj["nomVBatt"]=decode_float(sarr[2])
        rj["nomFOut"]=decode_float(sarr[3])
        rj["ok"]=0
    except Exception as e:
        rj["ok"]=3
    # return dict/json :-)
    return rj

# decode M (query protocol variant) command response into JSON'able object :-)
def decode_m_response(buf):
    rj = {"ok": 1, "variant": "?" }
    # Get first letter from string - it's protocol variant decode to string, remove "(" and CR+0x00 from end
    try:
        str = buf.decode().rstrip('\x00').rstrip()
        rj["variant"]=str
        rj["ok"]=0
    except Exception as e:
        rj["ok"]=2
    # return dict/json :-)
    return rj

# decode QI (query internals) command response into JSON'able object :-)
def decode_qi_response(buf):
    rj = { "ok": 1, "str": "" }
    # decode to string, remove "(" and CR+0x00's from end
    str = buf.decode()[1:][:-2].rstrip('\x00').rstrip()
    rj["str"]=str
    try:
        # nothing to decode
        rj["ok"]=0
    except Exception as e:
        rj["ok"]=2
    # return dict/json :-)
    return rj


jsonresp["dev"]= { "vid": f"{vid:04x}", "pid": f"{pid:04x}", "endpoint": f"{defep:02x}" }

## ------------------------------------------------------------------------------------------
## ------------------------------------------------------------------------------------------
## ------------------------------------------------------------------------------------------

# load default arguments
tmpjs=f'{{"vid":"{vid:04x}","pid":"{pid:04x}","ep":"{defep:02x}","cmd":"?","st":0.0,"sr":0,"to":{cmdtimeout} }}'
args=json.loads(tmpjs)

# check arguments count, if 1 (script filename) then input parameters might be passed from STDIN, otherwise try to load 2nd argument as JSON
stdin_json=0
if (len(sys.argv) < 2):
    stdin_json=1

try:
    if (stdin_json==1):
        args=json.load(sys.stdin)
    else:
        args = json.loads(sys.argv[1])
except Exception as ee:
    jsonresp["result"]=110
    jsonresp["resultstr"]="JSON load error (cmdline param). "+str(ee)
    if (stdin_json==1):
        jsonresp["resultstr"]="JSON load error (STDIN). "+str(ee)
    print(json.dumps(jsonresp))
    sys.exit(110)

# check if there are required keys
# vid,pid,cmd
if (("vid" not in args) or ("pid" not in args) or ("cmd" not in args)):
    jsonresp["result"]=111
    jsonresp["resultstr"]="Missing required keys in JSON."
    print(json.dumps(jsonresp))
    sys.exit(111)

# try to get vid,pid,ep, strip quotes and 0x if user adds
try:
    vid=int(args["vid"].lower().replace("'","").replace("0x",""),16)
    pid=int(args["pid"].lower().replace("'","").replace("0x",""),16)
    if ("ep" in args):
        defep=int(args["ep"].lower().replace("'","").replace("0x",""),16)
    if ("to" in args):
        cmdtimeout=int(args["to"])
except Exception as ee:
    jsonresp["result"]=112
    jsonresp["resultstr"]="Invalid format vid/pid/ep/to. "+str(ee)
    print(json.dumps(jsonresp))
    sys.exit(112) 

sht=-1.0
shr=-1
# check for shutdown command and required params
if (args["cmd"]=="s"):
    if (("st" not in args) or ("sr" not in args)):
        jsonresp["result"]=102
        jsonresp["resultstr"]="cmd: shutdown, but no st and/or sr params"
        print(json.dumps(jsonresp))
        sys.exit(102) 
    # load st/sr values from input
    try:
        # st - shutdown off delay
        sht=float(args["st"])
        if (sht<0):
            jsonresp["result"]=100
            jsonresp["resultstr"]="Param st can't be negative"
            print(json.dumps(jsonresp))
            sys.exit(100)
        if (sht<1.0):
            sht=round(sht,1)
        else:
            sht=round(sht,0)
        # sr - shutdown on delay
        shr=int(args["sr"])
        if (shr<0):
            jsonresp["result"]=101
            jsonresp["resultstr"]="Param sr can't be negative"
            print(json.dumps(jsonresp))
            sys.exit(101)
    except Exception as ee:
        jsonresp["result"]=113
        jsonresp["resultstr"]="Invalid format st/sr. "+str(ee)
        print(json.dumps(jsonresp))
        sys.exit(113) 


argsc=args["cmd"]
cmd="?" # command for UPS ['qs','f','qi','t','q','m','c','s']
cmdre=0 # command have response to get?
cmdstr="" # command decription
if argsc == "qs":
    cmd="QS"
    cmdstr="Query status"
    cmdre=1
elif argsc == "f":
    cmd="F"
    cmdstr="Query ratings"
    cmdre=1
elif argsc == "qi":
    cmd="QI"
    cmdstr="Query internals?"
    cmdre=1
elif argsc == "t":
    cmd="T"
    cmdstr="Test 10sec"
    cmdre=0
elif argsc == "q":
    cmd="Q"
    cmdstr="Toggle beeper"
    cmdre=0
elif argsc == "m":
    cmd="M"
    cmdstr="Query Voltronic protocol variant"
    cmdre=1
elif argsc == "c":
    cmd="C"
    cmdstr="Cancel test/shutdown/restore delay/OFF"
    cmdre=0
elif argsc == "s":
    cmd="S"+get_shutdown_params(sht,shr)
    st=get_shutdown_delay_string_value(sht)
    cmdstr=f"Shutdown (delay: {st}, restore: {shr}m)"
    cmdre=0
else:
    jsonresp["result"]=114
    jsonresp["resultstr"]=f"Invalid ups command '{argsc}'. "
    print(json.dumps(jsonresp))
    sys.exit(114) 

jsonresp["cmd"]= { "cmd": cmd, "res": cmdre }
#print(f"Command : {cmdstr} [{cmd}]")
jsonresp["tout"]=cmdtimeout

# find device on usb bus
dev = usb.core.find(idVendor=vid, idProduct=pid)
# Was it found?
if dev is None:
    jsonresp["result"]=103
    jsonresp["resultstr"]="no usb device found"
    print(json.dumps(jsonresp))
    sys.exit(103)
    #raise ValueError('Device not found')

# selected endpoint
sep = None
# show some info
selintf=-1
#print("Selected device basic info:")
ic=0
jsonresp["dev"]["cfg"] = []
for cfg in dev:
    #print(f'Configuration: {cfg.bConfigurationValue}')
    jsonresp["dev"]["cfg"] += [{"cv": cfg.bConfigurationValue, "if": []}]
    jf=0
    for intf in cfg:
        #print(f'  - Interface: #{intf.bInterfaceNumber} (alt: {intf.bAlternateSetting})')
        jsonresp["dev"]["cfg"][ic]["if"] += [ {"n": intf.bInterfaceNumber, "alt": intf.bAlternateSetting, "ep": []} ]
        ke=0
        for ep in intf:
            #print(f'    - Endpoint adr: 0x{ep.bEndpointAddress:02x}' )
            jsonresp["dev"]["cfg"][ic]["if"][jf]["ep"] += [ {"ad": f"{ep.bEndpointAddress:02x}" } ]
            if (ep.bEndpointAddress == defep):
                sep=ep
                selintf=intf.bInterfaceNumber
            ke+=1
        jf+=1
    #
    ic+=1
    #

if (sep is None):
    jsonresp["result"]=104
    jsonresp["resultstr"]="USBEndpoint not found."
    print(json.dumps(jsonresp))
    sys.exit(104)
    #raise ValueError(f'Endpoint 0x{defep:02x} not found.');

if (selintf == -1):
    jsonresp["result"]=105
    jsonresp["resultstr"]="USBIntf not found."
    print(json.dumps(jsonresp))
    sys.exit(105)
    #raise ValueError(f'No interface selected, seems like Endpoint might not be found too.');

#device name
# bug: from time-to-time it throws error :/
# force langid
#dev._langids=(1033,)
# and get device name
#devname=usb.util.get_string(dev,dev.iProduct)
#print(f"iProduct: {devname}")

jsonresp["dev"]["sel"] = { "if": selintf, "ep": f"{defep:02x}", "epidx": sep.index }
#print(f"Selecting device <{vid:04X}:{pid:04X}> '{devname}', configuration, interface ({selintf}) & endpoint 0x{defep:02x} (IN, #{sep.index})")
#print(f"Selecting device <{vid:04X}:{pid:04X}>, configuration, interface ({selintf}) & endpoint 0x{defep:02x} (IN, #{sep.index})")
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

jsonresp["kernel"]={"d": 0, "r": 0}
#print(f"Checking if kernel_driver is attached to interface #{intf.bInterfaceNumber}, and removing it in case...")
if dev.is_kernel_driver_active(intf.bInterfaceNumber):
    #print("Detaching kernel-driver...")
    try:
        #print(dev.detach_kernel_driver(intf.bInterfaceNumber))
        re=dev.detach_kernel_driver(intf.bInterfaceNumber)
        jsonresp["kernel"]={"d": 1, "r": re}
    except Exception as ee:
        jsonresp["kernel"]={"d": -1, "r": re}
        jsonresp["result"]=106
        jsonresp["resultstr"]=str(ee)
        print(json.dumps(jsonresp))
        sys.exit(106)
    #print("Detached.")

# -----------------------------------------------------

cmd2=cmd+"\x0d"
cmdbuf=bytearray(bytes(cmd2,"ascii"))
#print(f"Command to send: {array_to_hexstring(cmdbuf,' ')} >>> {bytes(cmd2,'ascii')} <<<")
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
    jsonresp["result"]=107
    jsonresp["resultstr"]=str(ee)
    print(json.dumps(jsonresp))
    sys.exit(107)

jsonresp["cmd"]["rlen"]=0
jsonresp["cmd"]["rhex"]=""
jsonresp["cmd"]["r"]= {}
resp_ok=1 # is response expected and ok?
if (cmdre>0):
    jsonresp["cmd"]["rlen"] = -1;
    re=None
    try:
        re=dev.read(sep.bEndpointAddress, 64, cmdtimeout).tobytes()
        jsonresp["cmd"]["rlen"] = len(re)
        jsonresp["cmd"]["rhex"] = array_to_hexstring(re,'')
        #print(f"UPS response: (len={len(re)}bytes)")
        #print(f"  HEX:  {array_to_hexstring(re,' ')}")
        #print(f"  STR: {re}")
    except usb.core.USBTimeoutError:
        jsonresp["result"]=108
        print(json.dumps(jsonresp))
        sys.exit(108)
    except Exception as ee:
        jsonresp["result"]=109
        jsonresp["resultstr"]=str(ee)
        print(json.dumps(jsonresp))
        sys.exit(109)
    # try decoding
    if (re is not None):
        # QS
        if (cmd == "QS"):
            resp=decode_qs_response(re)
            jsonresp["cmd"]["r"]=resp
            #print("DecodedQS: ",resp)
        elif (cmd == "F"):
            resp=decode_f_response(re)
            jsonresp["cmd"]["r"]=resp
            #print("DecodedF: ",resp)
        elif (cmd == "M"):
            resp=decode_m_response(re)
            jsonresp["cmd"]["r"]=resp
            #print("DecodedM:",resp)
        elif (cmd == "QI"):
            resp=decode_qi_response(re)
            jsonresp["cmd"]["r"] = resp
        # check response code, OK=0
        if (jsonresp["cmd"]["r"]["ok"] == 0):
            resp_ok=0
        else:
            resp_ok=2
    else:
        resp_ok=3
#re=dev.ctrl_transfer(0x53,0,0x200,0,16)
#print(re)
#dev.write(128,buf)

# it there should be response for CMD check if it's ok or failed
if (resp_ok!=1):
    if (resp_ok==0):
        jsonresp["result"]=0
        jsonresp["resultstr"]="ok"
    elif (resp_ok==2):
        # decode error
        jsonresp["result"]=115
        jsonresp["resultstr"]=f"CMD[{cmd}] response decode error."
    elif (resp_ok==3):
        # no response, but expected one
        jsonresp["result"]=116
        jsonresp["resultstr"]=f"CMD[{cmd}] no response (but expected one)."
else:
    # No response for CMD, OK
    jsonresp["result"]=0
    jsonresp["resultstr"]="ok"
        
print(json.dumps(jsonresp))
sys.exit(0)
