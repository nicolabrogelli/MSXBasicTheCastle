#!/usr/bin/env python3
"""Plays the same route on the original ROM and on the port and compares what happens, frame by frame.

  bot.py ROUTE OUTDIR [--easy|--normal|--hard]

A route is a text file of steps, one per line: "<condition> => <action> ; <action> ...", tried in order: a step waits for its condition.
The conditions are Tcl expressions on $x $y (position of the knight), $lvl (room, -1 outside the rooms), $life, $score, $f (frames from the start of the step).
Actions: down ROW MASK, up ROW MASK, shot NAME (saves the VRAM). Shortcuts in the masks: R L U S = row 8 keys right, left, up, space.
Both ROMs read the same data from video memory, so the bot does not depend on where each version keeps its variables.
"""
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OPENMSX = r"C:\Users\nicol\Documents\BACKUP\DOC - RETROCOMPUTER\COMPUTER\MSX\EMULATORI\OPENMSX 22.0\openmsx.exe"
ROMS = {
    'orig': (os.path.join(os.path.dirname(ROOT), 'emul', 'rom', 'the-castel.rom'), 'ASCII16', 0, 6),
    'port': (os.path.join(ROOT, 'CASTL.ROM'), 'ASCII8', 0, 2),
}
KEYS = {'R': '8 0x80', 'L': '8 0x10', 'U': '8 0x20', 'S': '8 0x01'}

TCL = r'''
set throttle off
set out "%(out)s"
set first %(first)d
set log [open "$out/trace.txt" w]
set phase 0
set pf 0
set total 0
set last ""
proc sv {name} { global out; set f [open "$out/$name.bin" wb]; fconfigure $f -translation binary; puts -nonewline $f [debug read_block VRAM 0 16384]; close $f }
proc vb {a} { scan [debug read VRAM $a] %%d v; return $v }
proc digit {a} { set v [expr {[vb $a] - 208}]; if {$v < 0 || $v > 9} { return -1 }; return $v }
proc step {} {
  global phase pf total last log first steps
  incr total
  incr pf
  set y [expr {([vb 6912] + 1) & 255}]
  set x [vb 6913]
  set pat [vb 6914]
  set lvl -1
  if {[vb 6144] == 236} { set lvl [expr {[digit 6148] * 10 + [digit 6149]}] }
  set life 0
  foreach a {6167 6168 6169} { if {[vb $a] == 79} { incr life } }
  set score ""
  foreach a {6157 6158 6159 6160 6161} { set d [digit $a]; if {$d >= 0} { append score $d } }
  if {$score eq ""} { set score 0 }
  set score [scan $score %%d]
  set en {}
  for {set i $first} {$i < 24} {incr i} {
    set a [expr {6912 + $i * 4}]
    set sy [vb $a]
    if {$sy == 208} break
    if {$sy == 213 || $sy == 209} continue
    lappend en [format "%%d,%%d,%%d" [vb [expr {$a + 1}]] $sy [vb [expr {$a + 2}]]]
  }
  set en [lsort $en]
  set s "$lvl $x $y $pat $life $score"
  set e "$s | $en"
  if {$e ne $last} { puts $log "$total $e"; set last $e }
  set f $pf
  if {$phase < [llength $steps]} {
    lassign [lindex $steps $phase] c a
    if $c {
      eval $a
      incr phase
      set pf 0
    }
  } else {
    close $log
    exit
  }
  if {$total > %(limit)d} { puts $log "LIMIT phase $phase"; close $log; exit }
  after frame later
}
proc later {} { after time 0.012 step }
set steps {
%(steps)s
}
after frame later
'''


def tcl_steps(route):
    res = []
    for line in open(route):
        line = line.split('#')[0].strip()
        if not line:
            continue
        cond, acts = [p.strip() for p in line.split('=>')]
        out = []
        for a in acts.split(';'):
            p = a.split()
            if not p:
                continue
            if p[0] in ('down', 'up'):
                out.append('keymatrix%s %s' % (p[0], KEYS.get(p[1], ' '.join(p[1:]))))
            elif p[0] == 'shot':
                out.append('sv %s' % p[1])
            elif p[0] == 'exit':
                out.append('set phase 9999')
        res.append('  {{%s} {%s}}' % (cond, '; '.join(out)))
    return '\n'.join(res)


def run(name, route, out, limit):
    rom, typ, _, first = ROMS[name]
    d = os.path.join(out, name)
    os.makedirs(d, exist_ok=True)
    tcl = os.path.join(d, 'bot.tcl')
    open(tcl, 'w').write(TCL % dict(out=d.replace('\\', '/'), first=first, steps=tcl_steps(route), limit=limit))
    r = subprocess.run([OPENMSX, '-machine', 'Sony_HB-75P', '-cart', rom, '-romtype', typ, '-script', tcl], capture_output=True, text=True, timeout=590)
    return os.path.join(d, 'trace.txt'), (r.stdout + r.stderr)[-300:]


def states(path, with_enemies):
    res = []
    for line in open(path):
        if line.startswith('LIMIT'):
            res.append((0, line.strip()))
            continue
        fr, rest = line.split(' ', 1)
        v = rest.split('|')[0].split()
        if int(v[2]) >= 192 or int(v[2]) == 1 or v[3] == '0' or v[4] == '0' and v[0] != '-1':
            continue  # boot, or sprites hidden while a room is being drawn
        s = ' '.join(v[:3] + v[4:])  # the pattern is left out: for one frame at the start of a room it can be the previous one
        if with_enemies:
            s += ' |' + rest.split('|')[1].rstrip()
        if not res or res[-1][1] != s:
            res.append((int(fr), s))
    return res


def main():
    route, out = sys.argv[1], sys.argv[2]
    limit = int(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[3].isdigit() else 20000
    traces = {}
    for name in ROMS:
        traces[name], msg = run(name, route, out, limit)
        if msg.strip():
            print(name, msg)
    with_enemies = '--enemies' in sys.argv
    a, b = states(traces['orig'], with_enemies), states(traces['port'], with_enemies)
    print('states: original %d, port %d (last frame %d / %d)' % (len(a), len(b), a[-1][0], b[-1][0]))
    print('last original:', a[-1], ' last port:', b[-1])
    for i, (p, q) in enumerate(zip(a, b)):
        if p[1] != q[1]:
            print('first difference at state', i)
            for k in range(max(0, i - 3), min(i + 4, len(a), len(b))):
                print('  orig', a[k], '   port', b[k])
            break
    else:
        print('all the common states are identical')


if __name__ == '__main__':
    main()
