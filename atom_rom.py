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

#FIXME this is different from atombios.h version and probably wrong after ucReserved
ATOM_ROM_HEADER=Struct("ATOM_ROM_HEADER",
  Rename("sHeader", ATOM_COMMON_TABLE_HEADER),
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

ATOM_MASTER_DATA_TABLE=Struct("ATOM_MASTER_DATA_TABLE",
  Rename("sHeader", ATOM_COMMON_TABLE_HEADER),
  ULInt16("UtilityPipeLine"),          # Offest for the utility to get parser info,Don't change this position!
  ULInt16("MultimediaCapabilityInfo"), # Only used by MM Lib,latest version 1.1, not configuable from Bios, need to include the table to build Bios
  ULInt16("MultimediaConfigInfo"),     # Only used by MM Lib,latest version 2.1, not configuable from Bios, need to include the table to build Bios
  ULInt16("StandardVESA_Timing"),      # Only used by Bios
  ULInt16("FirmwareInfo"),             # Shared by various SW components,latest version 1.4
  ULInt16("PaletteData"),              # Only used by BIOS
  ULInt16("LCD_Info"),                 # Shared by various SW components,latest version 1.3, was called LVDS_Info
  ULInt16("DIGTransmitterInfo"),       # Internal used by VBIOS only version 3.1
  ULInt16("SMU_Info"),                 # Shared by various SW components,latest version 1.1
  ULInt16("SupportedDevicesInfo"),     # Will be obsolete from R600
  ULInt16("GPIO_I2C_Info"),            # Shared by various SW components,latest version 1.2 will be used from R600
  ULInt16("VRAM_UsageByFirmware"),     # Shared by various SW components,latest version 1.3 will be used from R600
  ULInt16("GPIO_Pin_LUT"),             # Shared by various SW components,latest version 1.1
  ULInt16("VESA_ToInternalModeLUT"),   # Only used by Bios
  ULInt16("GFX_Info"),                 # Shared by various SW components,latest version 2.1 will be used from R600
  ULInt16("PowerPlayInfo"),            # Shared by various SW components,latest version 2.1,new design from R600
  ULInt16("GPUVirtualizationInfo"),    # Will be obsolete from R600
  ULInt16("SaveRestoreInfo"),          # Only used by Bios
  ULInt16("PPLL_SS_Info"),             # Shared by various SW components,latest version 1.2, used to call SS_Info, change to new name because of int ASIC SS info
  ULInt16("OemInfo"),                  # Defined and used by external SW, should be obsolete soon
  ULInt16("XTMDS_Info"),               # Will be obsolete from R600
  ULInt16("MclkSS_Info"),              # Shared by various SW components,latest version 1.1, only enabled when ext SS chip is used
  ULInt16("Object_Header"),            # Shared by various SW components,latest version 1.1
  ULInt16("IndirectIOAccess"),         # Only used by Bios,this table position can't change at all!!
  ULInt16("MC_InitParameter"),         # Only used by command table
  ULInt16("ASIC_VDDC_Info"),           # Will be obsolete from R600
  ULInt16("ASIC_InternalSS_Info"),     # New tabel name from R600, used to be called "ASIC_MVDDC_Info"
  ULInt16("TV_VideoMode"),             # Only used by command table
  ULInt16("VRAM_Info"),                # Only used by command table, latest version 1.3
  ULInt16("MemoryTrainingInfo"),       # Used for VBIOS and Diag utility for memory training purpose since R600. the new table rev start from 2.1
  ULInt16("IntegratedSystemInfo"),     # Shared by various SW components
  ULInt16("ASIC_ProfilingInfo"),       # New table name from R600, used to be called "ASIC_VDDCI_Info" for pre-R600
  ULInt16("VoltageObjectInfo"),        # Shared by various SW components, latest version 1.1
  ULInt16("PowerSourceInfo"),          # Shared by various SW components, latest versoin 1.1
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
  Rename("sHeader", ATOM_COMMON_TABLE_HEADER),
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
