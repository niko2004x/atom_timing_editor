import optparse
import sys
import re
from construct import *
from atom_rom import atom_rom_header_ptr, ATOM_ROM_HEADER, fix_bios_checksum, ATOM_VRAM_TIMING_ENTRY, ATOM_DATA_TABLE, ATOM_VRAM_INFO_TABLE, get_bios_version
from atom_rom_timings import format_register_string, set_register_in_string

def hexify(a):
  return  "".join("%02x" % int(b) for b in a)

def parse_patch_string(patch):
  erx='([0-3]+:[0-9]+00|[0-9]+)' #endpont regex
  rrx='([A-Z0-9_]+[-+]?=[0-9]+)' #register regex

  def split_endpoint(e):
    if ':' in e:
      e_=[int(a) for a in e.split(':')]
      return {'type': e_[0], 'freq': e_[1]}
    else:
      return {'id': int(e)}

  regex_string="^(%s(-%s?)?)=%s(\[((%s,)*%s)\])?$" % (erx, erx, erx, rrx, rrx)
  m=re.match(regex_string, patch)
  patch_={}
  if m is not None:
    #destination
    if m.group(1) is not None:
      patch_['dest_start']=split_endpoint(m.group(2))
      if '-' in m.group(1):
        if m.group(4) is not None:
          patch_['dest_end']=split_endpoint(m.group(4))
        else:
          patch_['dest_end']=None
    #source
    if m.group(5) is not None:
      patch_['src']=split_endpoint(m.group(5))
    #registers to change
    if m.group(7) is not None:
      change=[]
      for p in m.group(7).split(','):
        if '+=' in p:
          change+=[p.split('+=')+['+=']]
        if '-=' in p:
          change+=[p.split('-=')+['-=']]
        else:
          change+=[p.split('=')+['=']]
      patch_['change']=change
  else:
    sys.exit("Could not parse patch string '%s'" % patch)

  return patch_

def load_text_timing_table(f):
  timing_table=[]
  for l in f.readlines():
    m=re.match(' *([0-9]+)00 ([0-9]) ([0-9a-zA-Z]+)', l)
    if m:
      c,t,s=m.group(1),m.group(2),m.group(3)
      timing_table+=[(int(c+'00'),int(t),s)]
    else:
      sys.exit('Timing table parser error on "%s"' % l)
  return timing_table

def save_text_timing_table(f, timing_table, registers=False, bios_type=None):
  for c,t,s in timing_table:
    timing_entry_string="%6s %d %s" % (c, t, s)
    if registers:
      registers=['MC_SEQ_RAS_TIMING', 'MC_SEQ_CAS_TIMING', 'MC_SEQ_MISC_TIMING', 'MC_SEQ_MISC_TIMING2', 'MC_SEQ_PMG_TIMING', 'MC_ARB_DRAM_TIMING', 'MC_ARB_DRAM_TIMING2']
      timing_entry_string+=' '+','.join([format_register_string(bios_type, s, r) for r in registers])
    print >>f, timing_entry_string

def detect_timing_table_offset(bios, offset, verbose=False):
  atom_rom_header_offset=ULInt16("atom_rom_header_offset").parse(bios[atom_rom_header_ptr:atom_rom_header_ptr+2])

  atom_rom_header=ATOM_ROM_HEADER.parse(bios[atom_rom_header_offset:])
  if verbose:
    print "atom_rom_header_offset is", atom_rom_header_offset
    print "atom_rom_header is", atom_rom_header

  atom_data_table_offset=atom_rom_header.usMasterDataTableOffset
  atom_data_table = ATOM_DATA_TABLE.parse(bios[atom_data_table_offset:])

  if verbose:
    print "atom_data_table_offset is", atom_data_table_offset
    print "atom_data_table is", atom_data_table

  atom_vram_info_table_offset=atom_data_table.VRAM_Info
  atom_vram_info_table = ATOM_VRAM_INFO_TABLE.parse(bios[atom_vram_info_table_offset:])

  if verbose:
    print "atom_vram_info_table_offset is", atom_vram_info_table_offset
    print "atom_vram_info_table is", atom_vram_info_table

  atom_vram_info_table_header=atom_vram_info_table.ATOM_COMMON_TABLE_HEADER
  atom_vram_info_table_revision=(atom_vram_info_table_header.ucTableFormatRevision, atom_vram_info_table_header.ucTableContentRevision)

  #if atom_vram_info_table_revision not in [(2,1), (2,2), (1,4)]:
  #  sys.exit("Unknown not vram info revision")

  atom_vram_timing_table_offset=atom_data_table.VRAM_Info+atom_vram_info_table.usMemClkPatchTblOffset+0x2c+offset #entries starts 2 bytes later

  return atom_vram_timing_table_offset

def detect_timing_table_length(bios, atom_vram_timing_table_offset, timing_entry_length=0x30, verbose=False):
  if verbose:
    print "atom_vram_timing_table_offset is", atom_vram_timing_table_offset

  timing_table_length=0
  for i in xrange(12*3): #yes saw table that long
    t=ATOM_VRAM_TIMING_ENTRY.parse(bios[atom_vram_timing_table_offset+2+(timing_entry_length+4)*i:])
    if t.ulClkRange==0:
      timing_table_length=i
      break
  return timing_table_length

if __name__ == '__main__':
  parser = optparse.OptionParser()
  parser.add_option("-i", "--input", dest="input", help="Input bios file")
  parser.add_option("-o", "--output", dest="output", help="Output bios file")
  parser.add_option("-I", "--inputtable", dest="input_table", help="Input timings table file in format <freq> <type> <timings>")
  parser.add_option("-O", "--outputtable", dest="output_table", help="Output timings table file/stdout in format <freq> <type> <timings>")
  parser.add_option("-v", "--verbose", dest="verbose", action="store_true", default=False, help="Be verbose")
  parser.add_option("--offset", dest="timing_table_offset", default=0, help="Timing table offset in bios relative to vram_info_table_offset+usMemClkPatchTblOffset+44 (default 0)")
  parser.add_option("--length", dest="timing_table_length", default=None, help="Number of timings entries in bios to read (default autodetect)")
  parser.add_option("--elength", dest="timing_entry_length", default=None, help="Lenght of timing string")
  parser.add_option("--type", dest="timing_entry_type", default=None, help="Type of timing entriy to decode (default autodetect)")
  parser.add_option("-p", "--patch", dest="patch", action="append", help="Copy timings from given frequency to all higher")
  parser.add_option("-r", "--registers", dest="registers", action="store_true", default=False, help="Show/use timing registers in patch/inputtable/outputtable")

  (options, args) = parser.parse_args()

  if options.input is None and options.input_table is None:
    parser.error("Eigher option 'input' or option 'inputtable' is required")
  if options.input is not None and options.input_table is not None:
    parser.error("Only one of option 'input' or option 'inputtable' should be present")
  if options.output is not None and options.input is None:
    parser.error("Option 'output' works only if option 'input'")

  timing_entry_type=options.timing_entry_type

  if options.input is not None:
    bios=None
    with open(options.input) as bios_file:
      if options.verbose:
        print "Reading bios form %s" % options.input
      bios = bytearray(bios_file.read())
    if bios is None:
      sys.exit('Could not load bios')

    bios_version=get_bios_version(bios)
    if timing_entry_type is None:

      #autodetect hacks
      if bios_version is None:
        sys.exit('Could not detect timing entry type')
      if bios_version[0:6] in ['015.04', '015.03', '015.02', '015.01', '015.00']:
        timing_entry_type='R9'
      elif bios_version[0:6] in ['015.05']:
        timing_entry_type='RX'
      elif bios[0:1024].find('GV-R938XG1 GAMING-4GD/F2/0347') == -1:
        timing_entry_type='R9'
      elif bios[0:1024].find('113-C3340400-101.TURKS.PCI_EXPRESS.GDDR5') == -1:
        timing_entry_type='R9'
      else:
        sys.exit('Could not detect timing entry type')

    if timing_entry_type not in ['R9', 'RX']:
      sys.exit('Unsupported timing entry type')

    if options.verbose:
      print 'Using timing entry type', timing_entry_type

    if options.timing_entry_length is None:
      timing_entry_length=0x30
    else:
      timing_entry_length=int(options.timing_entry_length)

    ATOM_VRAM_TIMING_ENTRY=Struct("ATOM_VRAM_TIMING_ENTRY",
      ULInt32("ulClkRange"), #24 bit clock and 8 bit type
      Bytes("ucLatency", timing_entry_length)
    )

    atom_vram_timing_table_offset=detect_timing_table_offset(bios, int(options.timing_table_offset), options.verbose)
    if options.timing_table_length is None:
      timing_table_length=detect_timing_table_length(bios, atom_vram_timing_table_offset, timing_entry_length, options.verbose)
    else:
      timing_table_length=int(options.timing_table_length)

    ATOM_VRAM_TIMING_TABLE=Struct("ATOM_VRAM_TIMING_TABLE",
      ULInt8("ucRevId"),
      ULInt8("ucNumEntries"),
      Array(lambda ctx: timing_table_length, ATOM_VRAM_TIMING_ENTRY)
    )

    tt=ATOM_VRAM_TIMING_TABLE.parse(bios[atom_vram_timing_table_offset:])
    parsed_timing_table=[]
    for i in xrange(timing_table_length):
      clck=tt.ATOM_VRAM_TIMING_ENTRY[i].ulClkRange
      parsed_timing_table+=[[clck & 0xffffff, (clck & 0xff000000) >> 24, hexify(bytearray(tt.ATOM_VRAM_TIMING_ENTRY[i].ucLatency))]]

  if options.input_table is not None:
    with open(options.input_table) as timing_table_file:
      if options.verbose:
        print "Reading timing table from %s" % options.input_table
      parsed_timing_table=load_text_timing_table(timing_table_file)
    if parsed_timing_table is None:
      sys.exit('Could not load timing table')

  if options.verbose:
    print "Readed timing table"
    save_text_timing_table(sys.stdout, parsed_timing_table)

  new_parsed_timing_table=list(parsed_timing_table)

  if options.patch:
    for p in options.patch:
      p_=parse_patch_string(p)

      id_src=None
      if 'freq' in p_['src']:
        for id_, t in enumerate(new_parsed_timing_table):
          if t[0]==p_['src']['freq'] and t[1]==p_['src']['type']:
            id_src=id_
      elif 'id' in p_['src']:
        if p_['src']['id']<len(new_parsed_timing_table):
          id_src=p_['src']['id']
      else:
        sys.exit("Could not decode source entry id")
      if id_src is None:
        sys.exit("Could not find source entry id")

      id_dest_start=None
      if 'freq' in p_['dest_start']:
        for id_, t in enumerate(new_parsed_timing_table):
          if t[0]==p_['dest_start']['freq'] and t[1]==p_['dest_start']['type']:
            id_dest_start=id_
      elif 'id' in p_['dest_start']:
        if p_['dest']['id']<len(new_parsed_timing_table):
          id_dest_start=p_['dest_start']['id']
      else:
        sys.exit("Could not decode start destination entry id")
      if id_dest_start is None:
        sys.exit("Could not find start destination entry id")

      id_dest_end=None
      if 'dest_end' not in p_:
        id_dest_end=id_dest_start
      elif p_['dest_end'] is None:
        if 'freq' in p_['dest_start']:
          for id_, t in enumerate(new_parsed_timing_table):
            if t[1]==p_['dest_start']['type']:
              id_dest_end=id_
        elif 'id' in p_['dest_start']:
          id_dest_end=len(new_parsed_timing_table)-1
      else:
        if 'freq' in p_['dest_end']:
          for id_, t in enumerate(new_parsed_timing_table):
            if t[0]==p_['dest_end']['freq'] and t[1]==p_['dest_end']['type']:
              id_dest_end=id_
        elif 'id' in p_['dest_end']:
          if p_['dest']['id']<len(new_parsed_timing_table):
            id_dest_end=p_['dest_end']['id']
        else:
          sys.exit("Could not decode end destination entry id")
        if id_dest_end is None:
          sys.exit("Could not find end destination entry id")

      src_parsed_timings=new_parsed_timing_table[id_src][2]
      for id_ in xrange(len(new_parsed_timing_table)):
        if id_>=id_dest_start and id_<=id_dest_end and new_parsed_timing_table[id_][1]==new_parsed_timing_table[id_src][1]: #same type
          new_parsed_timing_table[id_][2]=src_parsed_timings
          if 'change' in p_ and options.registers is not None:
            for rfix in p_['change']:
              new_parsed_timing_table[id_][2]=set_register_in_string(timing_entry_type, rfix[0], rfix[1], rfix[2], src_parsed_timings)

  if options.verbose:
    print "New timing table"
    save_text_timing_table(sys.stdout, new_parsed_timing_table, options.registers, timing_entry_type)

  if options.output_table:
    if options.verbose:
      print "Writing timing table to %s" % options.output_table

    if options.output_table=='-':
      save_text_timing_table(sys.stdout, new_parsed_timing_table, options.registers, timing_entry_type)
    else:
      with open(options.output_table, 'w') as f:
        save_text_timing_table(f, new_parsed_timing_table, options.registers, timing_entry_type)

  if options.output is not None:
    if bios is None:
      sys.exit('Could not output bios file')
    for i in xrange(len(new_parsed_timing_table)):
      tt.ATOM_VRAM_TIMING_ENTRY[i].ucLatency=new_parsed_timing_table[i][2].decode("hex")
      tt.ATOM_VRAM_TIMING_ENTRY[i].ulClkRange=new_parsed_timing_table[i][0]+new_parsed_timing_table[i][1]*0x1000000
    tt_raw=ATOM_VRAM_TIMING_TABLE.build(tt)
    bios[atom_vram_timing_table_offset:atom_vram_timing_table_offset+len(tt_raw)]=tt_raw

    fix_bios_checksum(bios)
    with open(options.output, 'w') as new_bios_file:
      if options.verbose:
        print "Writing bios to %s" % options.output
      new_bios_file.write(bios)
