# Locate functions containing 'HALS'/'SALS' immediates and the IOCTL dispatch, disassemble them
import struct
import pefile
from capstone import Cs, CS_ARCH_X86, CS_MODE_64

PATH = r'C:\Windows\system32\drivers\AcpiVpc.sys'
pe = pefile.PE(PATH)
base = pe.OPTIONAL_HEADER.ImageBase
data = open(PATH, 'rb').read()

sections = []
for s in pe.sections:
    sections.append((s.VirtualAddress, s.Misc_VirtualSize, s.PointerToRawData, s.SizeOfRawData,
                     s.Name.decode().rstrip('\x00')))


def off_to_rva(off):
    for va, vsz, raw, rsz, name in sections:
        if raw <= off < raw + rsz:
            return va + (off - raw)
    return None


def rva_to_off(rva):
    for va, vsz, raw, rsz, name in sections:
        if va <= rva < va + max(vsz, rsz):
            o = raw + (rva - va)
            if o < raw + rsz:
                return o
    return None


# .pdata functions
pdata_off = None
for s in pe.sections:
    if s.Name.decode().rstrip('\x00') == '.pdata':
        pdata_off = s.PointerToRawData
        pdata_sz = s.SizeOfRawData
funcs = []
for i in range(pdata_off, pdata_off + pdata_sz, 12):
    beg, end, _uw = struct.unpack_from('<III', data, i)
    if beg == 0:
        break
    funcs.append((beg, end))


def find_func(rva):
    for beg, end in funcs:
        if beg <= rva < end:
            return (beg, end)
    return None


def disasm(rva_start, rva_end, label):
    o = rva_to_off(rva_start)
    code = data[o:o + (rva_end - rva_start)]
    print('\n===== %s : RVA 0x%X-0x%X VA 0x%X =====' % (label, rva_start, rva_end, base + rva_start))
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    for ins in md.disasm(code, base + rva_start):
        extra = ''
        # annotate rip-relative targets and known immediates
        if '0x534c4148' in ins.op_str:
            extra = '   ; "HALS"'
        if '0x534c4153' in ins.op_str:
            extra = '   ; "SALS"'
        if '0x8310' in ins.op_str:
            extra = '   ; IOCTL'
        print('  0x%06X: %-8s %-40s%s' % (ins.address - base, ins.mnemonic, ins.op_str, extra))


# find immediates
targets = {b'\x48\x41\x4c\x53': 'HALS', b'\x53\x41\x4c\x53': 'SALS'}
seen_funcs = set()
for pat, label in targets.items():
    off = 0
    while True:
        i = data.find(pat, off)
        if i < 0:
            break
        off = i + 1
        rva = off_to_rva(i)
        if rva is None:
            continue
        f = find_func(rva)
        if f and f not in seen_funcs:
            seen_funcs.add(f)
            disasm(f[0], f[1], 'handler containing "%s"' % label)

# IOCTL dispatch: find function containing 0x831020C0 (first known IOCTL)
ioct_off = data.find(struct.pack('<I', 0x831020C0))
rva = off_to_rva(ioct_off)
f = find_func(rva)
if f:
    disasm(f[0], f[1], 'IOCTL dispatch')
