import optparse
import sys
import re
from construct import *

def hexify(a):
  return  "".join("%02x" % int(b) for b in a)

#register structures borrowed from gmc_8_1_sh_mask.h

MC_SEQ_WR_CTL_Dx=BitStruct("MC_SEQ_WR_CTL_Dx", #last field is lowest bits
  BitField("unused2", 1),    #Unused
  BitField("CMD_DLY", 1),
  BitField("ADR_DLY", 1),
  BitField("ODT_EXT", 1),
  BitField("ODT_DLY", 4),
  BitField("unused1", 2),    #Unused
  BitField("OEN_SEL", 2),
  BitField("OEN_EXT", 4),
  BitField("OEN_DLY", 4),
  BitField("CMD_2Y_DLY", 1),
  BitField("ADR_2Y_DLY", 1),
  BitField("DAT_2Y_DLY", 1),
  BitField("DQS_XTR", 1),
  BitField("DQS_DLY", 4),
  BitField("DAT_DLY", 4),
)

#some bioses with GDDR3 memory have non zero values consistant with this structure
MC_SEQ_WR_CTL_2=BitStruct("MC_SEQ_WR_CTL_2", #last field is lowest bits
  BitField("unused2", 25),     #Unused
  BitField("WCDR_EN", 1),
  BitField("OEN_DLY_H_D1", 1),
  BitField("DQS_DLY_H_D1", 1),
  BitField("DAT_DLY_H_D1", 1),
  BitField("OEN_DLY_H_D0", 1),
  BitField("DQS_DLY_H_D0", 1),
  BitField("DAT_DLY_H_D0", 1),
)

MC_SEQ_RAS_TIMING=BitStruct("MC_SEQ_RAS_TIMING", #last field is lowest bits
  BitField("unused1", 1), #Unused
  BitField("TRC", 7),     #Number of cycles from active to active/auto refresh -1
  BitField("TRRD", 4),    #Number of cycles from active bank a to active bank b -1
  BitField("TRCDRA", 5),  #Number of cycles from active to read with auto-precharge -1
  BitField("TRCDR", 5),   #Number of cycles from active to read -1
  BitField("TRCDWA", 5),  #Number of cycles from active to write with auto-precharge -1
  BitField("TRCDW", 5),   #Number of cycles from active to write -1
)

MC_SEQ_CAS_TIMING=BitStruct("MC_SEQ_CAS_TIMING", #last field is lowest bits
  Bits("unused2", 3), #Unused
  Bits("TCL", 5),     #CAS to data return latency
  Bits("unused1", 3), #Unused
  Bits("TW2R", 5),    #Write to read turn
  Bits("TR2R", 4),    #Read to read time
  Bits("TCCDL", 3),   #Cycles between r/w from bank A to r/w bank B.
  Bits("TR2W", 5),    #Read to write turn -1
  Bits("TNOPR", 2),   #Extra cycle(s) between successive read bursts
  Bits("TNOPW", 2),   #Extra cycle(s) between successive write bursts
)

MC_SEQ_MISC_TIMING_R9=BitStruct("MC_SEQ_MISC_TIMING_R9", #last field is lowest bits
  Bits("unused3", 3), #Unused
  Bits("TRFC", 9),    #Auto-refresh command period - 1
  Bits("TRP", 5),     #Precharge command period - 1
  Bits("unused2", 1), #Unused but defined as 1
  Bits("TRP_RDA", 6), #From read with auto-precharge to active - 1
  Bits("unused1", 2), #Unused
  Bits("TRP_WRA", 6), #From write with auto-precharge to active - 1
)

MC_SEQ_MISC_TIMING_RX=BitStruct("MC_SEQ_MISC_TIMING_RX", #last field is lowest bits
  Bits("unused3", 3), #Unused
  Bits("TRFC", 9),    #Auto-refresh command period - 1
  Bits("unused2", 1), #Unused
  Bits("TRP", 5),     #Precharge command period - 1
  Bits("unused1", 1), #Unused
  Bits("TRP_RDA", 6), #From read with auto-precharge to active - 1
  Bits("TRP_WRA", 7), #From write with auto-precharge to active - 1
)

MC_SEQ_MISC_TIMING2=BitStruct("MC_SEQ_MISC_TIMING2", #last field is lowest bits
  Bits("TWDATATR", 4),
  Bits("unused3", 3), #Unused
  Bits("T32AW", 4),
  Bits("TWEDC", 5),
  Bits("TREDC", 3),
  Bits("FAW", 5),
  Bits("unused2", 1), #Unused
  Bits("PA2WDATA", 3),
  Bits("unused1", 1), #Unused
  Bits("PA2RDATA", 3),
)

MC_SEQ_PMG_TIMING=BitStruct("MC_SEQ_PMG_TIMING", #last field is lowest bits
  Bits("SEQ_IDLE_SS", 8),
  Bits("TCKE_PULSE_MSB", 1),
  Bits("unused3", 2), #Unused
  Bits("SEQ_IDLE", 3),
  Bits("TCKE", 6),
  Bits("TCKE_PULSE", 4),
  Bits("unused2", 1), #Unused
  Bits("TCKSRX", 3),
  Bits("unused1", 1), #Unused
  Bits("TCKSRE", 3),
)

MC_ARB_DRAM_TIMING=BitStruct("MC_ARB_DRAM_TIMING", #last field is lowest bits
  Bits("RASMACTWR", 8),
  Bits("RASMACTRD", 8),
  Bits("ACTWR", 8),
  Bits("ACTRD", 8)
)

MC_ARB_DRAM_TIMING2=BitStruct("MC_ARB_DRAM_TIMING2", #last field is lowest bits
  Bits("BUS_TURN", 8),
  Bits("WRPLUSRP", 8),
  Bits("RP", 8),
  Bits("RAS2RAS", 8),
)

mc_offsets={
  'RX': {
    'MC_SEQ_WR_CTL_Dx': 0x00,
    'MC_SEQ_WR_CTL_2':  0x04,
    'MC_SEQ_PMG_TIMING': 0x08,
    'MC_SEQ_RAS_TIMING': 0x0c,
    'MC_SEQ_CAS_TIMING': 0x10,
    'MC_SEQ_MISC_TIMING': 0x14,
    'MC_SEQ_MISC_TIMING2': 0x18,
    'MC_ARB_DRAM_TIMING': 0x28,
    'MC_ARB_DRAM_TIMING2': 0x2c
  },
  'R9': {
    'MC_SEQ_WR_CTL_Dx': 0x00,
    'MC_SEQ_WR_CTL_2':  0x04,
    'MC_SEQ_RAS_TIMING': 0x08,
    'MC_SEQ_CAS_TIMING': 0x0c,
    'MC_SEQ_MISC_TIMING': 0x10,
    'MC_SEQ_MISC_TIMING2': 0x14,
    'MC_SEQ_PMG_TIMING': 0x18,
    'MC_ARB_DRAM_TIMING': 0x28,
    'MC_ARB_DRAM_TIMING2': 0x2c
  }
}

timing_register_names=[
  'MC_SEQ_RAS_TIMING', 'MC_SEQ_CAS_TIMING',
  'MC_SEQ_MISC_TIMING', 'MC_SEQ_MISC_TIMING2',
  'MC_SEQ_PMG_TIMING',
  'MC_ARB_DRAM_TIMING', 'MC_ARB_DRAM_TIMING2'
]

def format_register_string(bios_type, timing, register_name=None):
  if bios_type not in ['RX', 'R9']:
    sys.exit('Wrong bios type')

  if type(register_name) is list:
    return ','.join([format_register_string(bios_type, timing, r) for r in register_name])

  if register_name is None:
    return format_register_string(bios_type, timing, timing_register_names)

  if register_name not in mc_offsets[bios_type].keys():
    sys.exit('Wrong register')

  offset=mc_offsets[bios_type][register_name]
  timing_raw=bytearray(timing.decode("hex"))
  r_raw=timing_raw[offset:offset+4][::-1]

  if register_name in timing_register_names:
    var_name=register_name
    if register_name=='MC_SEQ_MISC_TIMING':
      var_name+='_'+bios_type
    r=globals()[var_name].parse(r_raw)
    attrs=list(reversed(r.keys()))
    r_string=(','.join([a+'=%03d' for a in attrs])) % tuple ([getattr(r,a) for a in attrs])
  else:
    sys.exit('Wrong register, should not happen')

  return '['+r_string+']'

def set_register_in_string(bios_type, register_subname, register_value, eqop, timing):
  if register_subname[0:6]=='unused':
    sys.exit("Unused does not allowed in registers")

  timing_raw=bytearray(timing.decode("hex"))

  found=False
  for r_name in timing_register_names:
    var_name=r_name
    if r_name=='MC_SEQ_MISC_TIMING':
      var_name+='_'+bios_type
    cnst=globals()[var_name]
    offset=mc_offsets[bios_type][r_name]
    attrs=cnst.parse('0000').keys()
    if register_subname in attrs:
      found=True
      break

  if not found:
    sys.exit("Unknown subregister")

  r_raw=timing_raw[offset:offset+4][::-1]
  r=cnst.parse(r_raw)
  if eqop=='=':
    r.__setattr__(register_subname, int(register_value))
  elif eqop=='-=':
    r.__setattr__(register_subname, int(r.__getattr__(register_subname))-int(register_value))
  elif eqop=='+=':
    r.__setattr__(register_subname, int(r.__getattr__(register_subname))+int(register_value))
  else:
    sys.exit("Bad set operation %s for register" % eqop)
  r_raw=cnst.build(r)
  timing_raw[offset:offset+4]=r_raw[::-1]

  return hexify(timing_raw)
