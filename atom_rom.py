import optparse
import sys
import re
from construct import *

atom_rom_checksum_offset = 0x21
atom_rom_size_offset=0x2
atom_rom_header_ptr = 0x48

def fix_bios_checksum(bios, verbose=False):
  size=bios[atom_rom_size_offset]*512
  checksum=bios[atom_rom_checksum_offset]

  if verbose:
    print "Size %d, checksum %d" % (size, checksum)

  offset=0
  for i in xrange(0,size):
    offset += bios[i]

  if verbose:
    print "New checksum difference %d" % (offset % 256)

  checksum-=offset
  checksum%=256
  bios[atom_rom_checksum_offset]=checksum

def get_bios_version(bios):
    bios_=bios[0:1024]
    version_offset=bios_.find('AMD VER')
    if version_offset==-1:
      version_offset=bios_.find('ATI VER')
    if version_offset==-1:
      return None

    return bios_[version_offset+7:version_offset+30]

ATOM_COMMON_TABLE_HEADER=Struct("ATOM_COMMON_TABLE_HEADER",
  ULInt16("usStructureSize"),
  ULInt8("ucTableFormatRevision"),
  ULInt8("ucTableContentRevision")
)

ATOM_ROM_HEADER=Struct("ATOM_ROM_HEADER",
  ATOM_COMMON_TABLE_HEADER,
  ULInt32("uaFirmWareSignature"),
  ULInt16("usBiosRuntimeSegmentAddress"),
  ULInt16("usProtectedModeInfoOffset"),
  ULInt16("usConfigFilenameOffset"),
  ULInt16("usCRC_BlockOffset"),
  ULInt16("usBIOS_BootupMessageOffset"),
  ULInt16("usInt10Offset"),
  ULInt16("usPciBusDevInitCode"),
  ULInt16("usIoBaseAddress"),
  ULInt16("usSubsystemVendorID"),
  ULInt16("usSubsystemID"),
  ULInt16("usPCI_InfoOffset"),
  ULInt16("usMasterCommandTableOffset"),
  ULInt16("usMasterDataTableOffset"),
  ULInt8("ucExtendedFunctionCode"),
  ULInt8("ucReserved"),
  ULInt32("ulPSPDirTableOffset"),
  ULInt16("usVendorID"),
  ULInt16("usDeviceID")
)

ATOM_DATA_TABLE=Struct("ATOM_DATA_TABLE",
  ATOM_COMMON_TABLE_HEADER,
  ULInt16("UtilityPipeLine"),
  ULInt16("MultimediaCapabilityInfo"),
  ULInt16("MultimediaConfigInfo"),
  ULInt16("StandardVESA_Timing"),
  ULInt16("FirmwareInfo"),
  ULInt16("PaletteData"),
  ULInt16("LCD_Info"),
  ULInt16("DIGTransmitterInfo"),
  ULInt16("SMU_Info"),
  ULInt16("SupportedDevicesInfo"),
  ULInt16("GPIO_I2C_Info"),
  ULInt16("VRAM_UsageByFirmware"),
  ULInt16("GPIO_Pin_LUT"),
  ULInt16("VESA_ToInternalModeLUT"),
  ULInt16("GFX_Info"),
  ULInt16("PowerPlayInfo"),
  ULInt16("GPUVirtualizationInfo"),
  ULInt16("SaveRestoreInfo"),
  ULInt16("PPLL_SS_Info"),
  ULInt16("OemInfo"),
  ULInt16("XTMDS_Info"),
  ULInt16("MclkSS_Info"),
  ULInt16("Object_Header"),
  ULInt16("IndirectIOAccess"),
  ULInt16("MC_InitParameter"),
  ULInt16("ASIC_VDDC_Info"),
  ULInt16("ASIC_InternalSS_Info"),
  ULInt16("TV_VideoMode"),
  ULInt16("VRAM_Info"),
  ULInt16("MemoryTrainingInfo"),
  ULInt16("IntegratedSystemInfo"),
  ULInt16("ASIC_ProfilingInfo"),
  ULInt16("VoltageObjectInfo"),
  ULInt16("PowerSourceInfo"),
  ULInt16("ServiceInfo"),
)

ATOM_VRAM_ENTRY=Struct("ATOM_VRAM_ENTRY",
  ULInt32("ulChannelMapCfg"),
  ULInt16("usModuleSize"),
  ULInt16("usMcRamCfg"),
  ULInt16("usEnableChannels"),
  Byte("ucExtMemoryID"),
  Byte("ucMemoryType"),
  Byte("ucChannelNum"),
  Byte("ucChannelWidth"),
  Byte("ucDensity"),
  Byte("ucBankCol"),
  Byte("ucMisc"),
  Byte("ucVREFI"),
  ULInt16("usReserved"),
  ULInt16("usMemorySize"),
  Byte("ucMcTunningSetId"),
  Byte("ucRowNum"),
  ULInt16("usEMRS2Value"),
  ULInt16("usEMRS3Value"),
  Byte("ucMemoryVenderID"),
  Byte("ucRefreshRateFactor"),
  Byte("ucFIFODepth"),
  Byte("ucCDR_Bandwidth"),
  ULInt32("ulChannelMapCfg1"),
  ULInt32("ulBankMapCfg"),
  ULInt32("ulReserved"),
  #incomplete
)

ATOM_VRAM_INFO_TABLE=Struct("ATOM_VRAM_INFO_TABLE",
  ATOM_COMMON_TABLE_HEADER,
  ULInt16("usMemAdjustTblOffset"),
  ULInt16("usMemClkPatchTblOffset"),
  ULInt16("usMcAdjustPerTileTblOffset"),
  #no not care about other entries
  ULInt16("usMcPhyInitTableOffset"),
  ULInt16("usDramDataRemapTblOffset"),
  ULInt16("usReserved1"),
  Byte("ucNumOfVRAMModule"),
  Byte("ucMemoryClkPatchTblVer"),
  Byte("ucVramModuleVer"),
  Byte("ucMcPhyTileNum"),
)

ATOM_VRAM_TIMING_ENTRY=Struct("ATOM_VRAM_TIMING_ENTRY",
  ULInt32("ulClkRange"), #24 bit clock and 8 bit type
  Bytes("ucLatency", 0x30)
)

ATOM_VRAM_TIMING_TABLE=Struct("ATOM_VRAM_TIMING_TABLE",
  ULInt8("ucRevId"),
  ULInt8("ucNumEntries"),
  Array(lambda ctx: 12, ATOM_VRAM_TIMING_ENTRY)
)
