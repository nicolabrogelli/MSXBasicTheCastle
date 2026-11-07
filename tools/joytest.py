#!/usr/bin/env python3
"""Tests the joystick code of the interrupt routine: a breakpoint right after the IN from the PSG port replaces the value read, as if a joystick
were plugged in port 1 or 2, and the position of the knight shows if the game has seen it.

  joytest.py OUTDIR
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OPENMSX = r"C:\Users\nicol\Documents\BACKUP\DOC - RETROCOMPUTER\COMPUTER\MSX\EMULATORI\OPENMSX 22.0\openmsx.exe"
ROM = os.path.join(ROOT, 'CASTL.ROM')

TCL = r'''
set throttle off
set log [open "%(out)s" w]
set port 0
set val 0x3F
set phase 0
set f 0
proc vb {a} { scan [debug read VRAM $a] %%d v; return $v }
# in a,(0A2h) has just been executed: the port selected in register 15 (bit 6) says which joystick is being read
proc joy {} {
  global port val
  scan [debug read "PSG regs" 15] %%d r
  set p [expr {($r & 64) ? 2 : 1}]
  if {$p == $port} { reg a $val } else { reg a 0x3F }
}
debug set_bp %(addr)d {} joy
proc tick {} {
  global phase f port val log
  incr f
  set x [vb 6913]
  set y [expr {([vb 6912] + 1) & 255}]
  switch $phase {
    0 { if {[vb 6408] == 243} { keymatrixdown 0 1; set phase 1; set f 0 } }
    1 { if {$f == 30} { keymatrixup 0 1 }; if {$y == 170 && $x == 32} { set phase 2; set f 0 } }
    2 { puts $log "start x=$x y=$y"; set port 1; set val 0x37; set phase 3; set f 0 }
    3 { if {$f == 40} { puts $log "port 1 right: x=$x"; set val 0x3B; set phase 4; set f 0 } }
    4 { if {$f == 20} { puts $log "port 1 left: x=$x"; set port 2; set val 0x37; set phase 5; set f 0 } }
    5 { if {$f == 40} { puts $log "port 2 right: x=$x"; set val 0x33; set phase 6; set f 0 } }
    6 { if {$f == 20} { puts $log "port 2 right+left (diagonal-like, ignored): x=$x"; set val 0x2F; set phase 7; set f 0 } }
    7 { if {$f == 12} { puts $log "port 2 trigger A, jump: y=$y"; set val 0x3F; set phase 8; set f 0 } }
    8 { if {$f == 60} { puts $log "landed: y=$y"; set port 1; set val 0x1F; set phase 9; set f 0 } }
    9 { if {$f == 12} { puts $log "port 1 trigger B alone, action: y=$y"; close $log; exit } }
  }
  after frame later
}
proc later {} { after time 0.01 tick }
after realtime 60 { exit }
after frame later
'''


def main():
    d = sys.argv[1]
    os.makedirs(d, exist_ok=True)
    rom = open(ROM, 'rb').read()
    i = rom.find(bytes([0xDB, 0xA2, 0x2F, 0xE6, 0x3F]))
    assert i >= 0
    out = os.path.join(d, 'joy.txt').replace('\\', '/')
    tcl = os.path.join(d, 'joy.tcl')
    open(tcl, 'w').write(TCL % dict(out=out, addr=0x4000 + i + 2))
    subprocess.run([OPENMSX, '-machine', 'Sony_HB-75P', '-cart', ROM, '-romtype', 'ASCII8', '-script', tcl], capture_output=True, timeout=90)
    print(open(out).read())


if __name__ == '__main__':
    main()
