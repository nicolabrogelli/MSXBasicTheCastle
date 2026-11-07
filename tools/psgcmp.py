#!/usr/bin/env python3
"""Compares the music of the original ROM and of the port: logs the PSG registers at every frame while the menu song plays.

  psgcmp.py OUTDIR [FRAMES]
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OPENMSX = r"C:\Users\nicol\Documents\BACKUP\DOC - RETROCOMPUTER\COMPUTER\MSX\EMULATORI\OPENMSX 22.0\openmsx.exe"
ROMS = {'orig': (os.path.join(os.path.dirname(ROOT), 'emul', 'rom', 'the-castel.rom'), 'ASCII16'), 'port': (os.path.join(ROOT, 'CASTL.ROM'), 'ASCII8')}

TCL = r'''
set throttle off
set log [open "%(out)s" w]
set n 0
proc regs {} {
  set r {}
  for {set i 0} {$i < 14} {incr i} { scan [debug read "PSG regs" $i] %%d v; lappend r $v }
  return $r
}
proc tick {} {
  global n log
  puts $log [regs]
  incr n
  if {$n > %(frames)d} { close $log; exit }
  after frame later
}
proc later {} { after time 0.015 tick }
proc wait {} {
  scan [debug read VRAM 6408] %%d v
  if {$v == 243} { tick } else { after frame wait }
}
after frame wait
'''


def run(name, d, frames):
    rom, typ = ROMS[name]
    out = os.path.join(d, name + '_psg.txt').replace('\\', '/')
    tcl = os.path.join(d, name + '_psg.tcl')
    open(tcl, 'w').write(TCL % dict(out=out, frames=frames))
    subprocess.run([OPENMSX, '-machine', 'Sony_HB-75P', '-cart', rom, '-romtype', typ, '-script', tcl], capture_output=True, timeout=300)
    return [list(map(int, l.split())) for l in open(out)]


def norm(r):
    """Only what can be heard: tone and noise periods of the audible channels, mixer without the port direction bits, volumes, envelope."""
    r = list(r)
    r[7] &= 0x3F
    for k in (1, 3, 5):
        r[k] &= 15  # the coarse tone registers have 4 bits
    r[6] &= 31  # the noise register has 5 bits
    r[13] = 0  # the shape register reads back the last value: it says nothing about when it was written
    return tuple(r)


def main():
    d = sys.argv[1]
    frames = int(sys.argv[2]) if len(sys.argv) > 2 else 1500
    os.makedirs(d, exist_ok=True)
    a = [norm(r) for r in run('orig', d, frames)]
    b = [norm(r) for r in run('port', d, frames)]
    print('frames', len(a), len(b))

    def dedupe(x):
        res = []
        for r in x:
            if not res or res[-1] != r:
                res.append(r)
        return res

    da, db = dedupe(a), dedupe(b)
    # the two songs start at a different moment of the log: look for the best alignment
    best = (0, 0, 0)
    for off in range(-400, 400):
        same = sum(1 for i in range(min(len(da), len(db))) if 0 <= i + off < len(db) and da[i] == db[i + off])
        if same > best[0]:
            best = (same, off, 0)
    print('states: %d / %d; best alignment offset %d: %d identical' % (len(da), len(db), best[1], best[0]))
    for i in range(min(6, len(da))):
        print(' o', da[i + 20])
        print(' p', db[i + 20 + best[1]] if 0 <= i + 20 + best[1] < len(db) else None)


if __name__ == '__main__':
    main()
