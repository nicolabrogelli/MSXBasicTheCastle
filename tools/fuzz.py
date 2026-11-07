#!/usr/bin/env python3
"""Tick-locked comparison of the original ROM and the port.

  fuzz.py OUTDIR SEED TICKS DIFFICULTY(0-2) [--mortal]

Both ROMs receive the same pseudo-random keys for the same game tick, and the state is logged tick by tick: room, position, score, time, sprite pattern,
objects and PSG registers. The keys come from a schedule made here. The original reads the keyboard at the end of a tick, at a moment that changes with
the load, so a breakpoint on readInputControl sets the keys right there; the port reads them in the interrupt, so they are set during the previous frame.

Unless --mortal is given, the bot is kept alive in both versions by writing to memory at every frame: a potion in the last inventory slot, the keys and three
lives. Every TOUR ticks all the map becomes door tiles, so that the run goes through the whole castle. A test copy of the port
(in OUTDIR) is built with a signature in RAM that gives the address of its variables.
"""
import os
import random
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OPENMSX = r"C:\Users\nicol\Documents\BACKUP\DOC - RETROCOMPUTER\COMPUTER\MSX\EMULATORI\OPENMSX 22.0\openmsx.exe"
ORIG = os.path.join(os.path.dirname(ROOT), 'emul', 'rom', 'the-castel.rom')
MAP = os.path.join(os.path.dirname(ROOT), 'emul', 'rom', 'the-castel.map')
TOUR = 1500
NAMES = ('gf', 'iv', 'imm', 'nl', 'rm', 'dl', 'mp', 'ms')
NAMES_V = ('gf', 'iv(0)', 'imm', 'nl', 'rm', 'dl(0)', 'mp(0)', 'ms(0)')

TCL = r'''
set throttle off
set out "%(out)s"
set log [open "$out/trace.txt" w]
set mask 0
set lastt -1
set tick 0
set logged 0
set applied 0
set started 0
set menu 0
set target 0
array set sched {%(sched)s}
proc vb {a} { scan [debug read VRAM $a] %%d v; return $v }
proc rb {a} { scan [debug read memory $a] %%d v; return $v }
proc setkeys {m} {
%(setkeys)s
}
# ticks done since the bot started (the counter of the games is a byte)
proc count {} {
  global lastt tick
  if {$lastt < 0} { return 0 }
  set g [rb %(gf)d]
  incr tick [expr {($g - $lastt) & 255}]
  set lastt $g
  return 1
}
proc keysupto {t} {
  global applied sched
  while {$applied < $t} {
    incr applied
    if {[info exists sched($applied)]} { setkeys $sched($applied) }
  }
}
# every TOUR ticks all the map becomes door tiles and the door leads to the next room: the knight falls to the floor and the action key takes it there
proc warp {t} {
  global target
  if {%(tour)d == 0 || $t %% %(tourn)d != 0 || $t == 0} { return }
  set target [expr {$target %% 25 + 1}]
  set room [rb %(room)d]
  if {$room == $target} { set target [expr {$target %% 25 + 1}] }
  debug write_block VRAM 6144 [string repeat "N" 768]
%(warp)s
}
proc atread {} {
  global tick
  if {[count]} {
    keysupto [expr {$tick + 1}]
    warp [expr {$tick + 1}]
  }
}
# port: the counter of the ticks has just been written, at the start of a tick
set wtick 0
proc atgf {} {
  global wtick lastt
  if {$lastt < 0} { return }
  incr wtick
  keysupto [expr {$wtick + 1}]
  warp $wtick
}
proc cheat {} {
%(cheat)s
}
proc step {} {
  global tick lastt logged started menu log
  if {!$started} {
    if {$menu > 0 || [vb 6408] == 243} {
      incr menu
      if {$menu == 2} { keymatrixdown 0 %(diffkey)s }
      if {$menu == 30} { keymatrixup 0 %(diffkey)s; set started 1 }
    }
    after frame later
    return
  }
  cheat
  if {$lastt < 0} {
    if {[rb %(gf)d] != 40} { after frame later; return }
    set lastt 40
  }
  count
  %(backlog)s
  %(cleanup)s
  if {$tick != $logged} {
    set logged $tick
    set y [expr {([vb 6912] + 1) & 255}]
    set x [vb 6913]
    set row {}
    foreach a {6148 6149 6157 6158 6159 6160 6161 6174 6175} { lappend row [vb $a] }
    set en {}
    for {set i %(first)d} {$i < 24} {incr i} {
      set a [expr {6912 + $i * 4}]
      set sy [vb $a]
      if {$sy == 208} break
      if {$sy == 213 || $sy == 209} continue
      lappend en [format "%%d,%%d,%%d" [vb [expr {$a + 1}]] $sy [vb [expr {$a + 2}]]]
    }
    set snd {}
    foreach r {0 1 6 7 8 9 10} { scan [debug read "PSG regs" $r] %%d v; lappend snd $v }
    puts $log "$tick $x $y $row [vb 6914] | [lsort $en] | $snd"
    # the whole screen, a moment before leaving a room
    if {$tick %% %(tourn)d == %(tourn)d - 2} {
      binary scan [debug read_block VRAM 6144 768] cu* names
      set sum 0
      set i 0
      foreach b $names { incr i; set sum [expr {($sum * 31 + $b + $i) & 0xFFFFFF}] }
      puts $log "V $tick $sum"
    }
    if {$tick >= %(ticks)d} { close $log; exit }
  }
  after frame later
}
proc later {} { after time 0.018 guarded }
proc guarded {} { if {[catch step e]} { global log errorInfo; puts $log "ERROR $e $errorInfo"; close $log; exit } }
%(bp)s
after realtime 280 { global log; puts $log "TIMEOUT"; close $log; exit }
after frame later
'''


def schedule(seed, ticks, tour):
    """Tick -> keys; during the first ticks of a tour step only the action key is held, to go through the door"""
    r = random.Random(seed)
    res = {}
    t = 5
    while t < ticks:
        k = r.randrange(100)
        m = 0x80 if k < 45 else 0x10 if k < 75 else 0
        if r.randrange(100) < 30:
            m |= 0x20
        if r.randrange(100) < 60:
            m |= 0x01
        res[t] = m
        t += 8 + r.randrange(40)
    if tour:
        for w in range(tour, ticks, tour):
            for k in [k for k in res if w <= k < w + 150]:
                del res[k]
            res[w + 1] = 1
            res[w + 150] = 0
    return res


KEYS_ORIG = '''  global mask
  foreach b {0x80 0x10 0x20 0x01} {
    if {($m & $b) && !($mask & $b)} { keymatrixdown 8 $b }
    if {!($m & $b) && ($mask & $b)} { keymatrixup 8 $b }
  }
  set mask $m'''
KEYS_PORT = '''  set v 0
  if {$m & 0x80} { incr v 1 }
  if {$m & 0x10} { incr v 2 }
  if {$m & 0x20} { incr v 4 }
  if {$m & 0x01} { incr v 8 }
  debug write memory %d $v'''


def run(rom, typ, d, cheat, gf, first, sched, ticks, diff, tour, room, warp, bp, setkeys, backlog, cleanup=''):
    os.makedirs(d, exist_ok=True)
    tcl = os.path.join(d, 'fuzz.tcl')
    s = ' '.join('%d %d' % kv for kv in sorted(sched.items()))
    open(tcl, 'w').write(TCL % dict(out=d.replace('\\', '/'), sched=s, cheat=cheat, gf=gf, first=first, ticks=ticks, diffkey=hex(1 << diff), tour=tour, tourn=tour or 1, room=room, warp=warp, bp=bp, setkeys=setkeys, backlog=backlog, cleanup=cleanup))
    subprocess.run([OPENMSX, '-machine', 'Sony_HB-75P', '-cart', rom, '-romtype', typ, '-script', tcl], capture_output=True, text=True, timeout=295)
    return [l.rstrip() for l in open(os.path.join(d, 'trace.txt'))]


def symbols():
    t = open(MAP, errors='replace').read()
    names = ('g_GameFrame', 'g_Inventory', 'g_Lives', 'g_ImmunityCount', 'g_CurrRoomIdx', 'g_Levels', 'readInputControl')
    return {n: int(re.search(r'([0-9A-F]{8})  _' + n + r'\s', t).group(1), 16) & 0xFFFF for n in names}


def build_port(d):
    """Copy of the sources with the addresses of the variables left in RAM (after a signature, in the free end of the sprite buffer)."""
    b = os.path.join(d, 'build')
    shutil.rmtree(b, ignore_errors=True)
    os.makedirs(b)
    for f in os.listdir(ROOT):
        if re.fullmatch(r'CASTL\d\d\d\.(SPB|BIN)', f):
            shutil.copy(os.path.join(ROOT, f), b)
    p = os.path.join(b, 'CASTL000.SPB')
    s = open(p, encoding='latin1', newline='').read()
    # the test copy takes the keys from a byte written by the bot at the start of each tick
    p1 = os.path.join(b, 'CASTL001.SPB')
    t = open(p1, encoding='latin1', newline='').read()
    assert 'ip = PEEK(msb + 56)' in t
    open(p1, 'w', encoding='latin1', newline='').write(t.replace('ip = PEEK(msb + 56)', 'ip = PEEK(msb + 61)'))
    add = ['POKE sa + 42, 202 : POKE sa + 43, 87 : POKE sa + 44, 30']
    for i, v in enumerate(NAMES_V):
        add.append('k = VARPTR(%s) : POKE sa + %d, k AND 255 : POKE sa + %d, ((k AND 32512) \\ 256) + 128' % (v, 45 + i * 2, 46 + i * 2))
    nl = '\r\n' if '\r\n' in s else '\n'
    s = s.replace('mainmenu:', nl.join(add) + nl + 'mainmenu:', 1)
    open(p, 'w', encoding='latin1', newline='').write(s)
    subprocess.run(['node', os.path.join(HERE, 'spb_compile.cjs'), 'CASTL000.SPB', '.'], cwd=b, check=True, capture_output=True)
    rom = os.path.join(b, 'CASTL.ROM')
    tcl = os.path.join(b, 'addr.tcl')
    o = b.replace('\\', '/')
    open(tcl, 'w').write('set throttle off\nafter time 9 { set f [open "%s/ram.bin" wb]; fconfigure $f -translation binary; puts -nonewline $f [debug read_block memory 0xC000 0x3000]; close $f; exit }\n' % o)
    subprocess.run([OPENMSX, '-machine', 'Sony_HB-75P', '-cart', rom, '-romtype', 'ASCII8', '-script', tcl], capture_output=True, timeout=120)
    ram = open(os.path.join(b, 'ram.bin'), 'rb').read()
    i = ram.index(bytes([202, 87, 30]))
    a = [ram[i + 3 + k * 2] | ram[i + 4 + k * 2] << 8 for k in range(len(NAMES))]
    return rom, dict(zip(NAMES, a))


def effects(trace):
    """Sounds heard in the rooms, where there is no music: tone, noise (-1 when off) and volume of channel A"""
    res, loud = [], 0
    for t in sorted(trace):
        p = trace[t].split('|')
        if p[0].split()[3:5] == ['0', '0']:
            continue
        v = list(map(int, p[2].split()))
        loud += 1 if v[5] or v[6] else 0
        if v[4] == 0:
            continue
        s = (v[0] | (v[1] & 15) << 8 if not v[3] & 1 else -1, v[2] & 31 if not v[3] & 8 else -1, v[4] & 15)
        if not res or res[-1] != s:
            res.append(s)
    return res, loud


def wr(addrs, key1):
    """key1 is not given in room 1, where it opens the way out and ends the game"""
    lines = ['  debug write memory %d %d' % (a, v) for a, v in addrs]
    lines.append('  if {[vb 6148] == 208 && [vb 6149] == 209} { debug write memory %d 0 } else { debug write memory %d 96 }' % (key1, key1))
    return chr(10).join(lines)


def main():
    out, seed, ticks, diff = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
    mortal = '--mortal' in sys.argv
    sy = symbols()
    rom, pa = build_port(out)
    inv = sy['g_Inventory']
    co = [(inv + 1, 97), (inv + 2, 98), (inv + 4, 95), (sy['g_ImmunityCount'], 0), (sy['g_Lives'], 79), (sy['g_Lives'] + 1, 79), (sy['g_Lives'] + 2, 79)]
    iv = pa['iv']
    cp = [(iv + 1, 0), (iv + 2, 97), (iv + 3, 0), (iv + 4, 98), (iv + 5, 0), (iv + 8, 95), (iv + 9, 0), (pa['imm'], 0), (pa['imm'] + 1, 0), (pa['nl'], 3), (pa['nl'] + 1, 0)]
    tour = 0 if mortal else TOUR
    sched = schedule(seed, ticks, tour)
    # warp: tile 78 is the letter N
    # the door table of the original lives in RAM: the changed entry is put back as soon as the knight has left the room
    lv = sy['g_Levels']
    wo = '  global oldroom oldnext; set oldroom $room; set oldnext [rb [expr {%d + $room * 55 + 4}]]; debug write memory [expr {%d + $room * 55 + 4}] $target' % (lv, lv)
    clean = 'global oldroom oldnext; if {[info exists oldroom] && [rb %d] != $oldroom} { debug write memory [expr {%d + $oldroom * 55 + 4}] $oldnext; unset oldroom }' % (sy['g_CurrRoomIdx'], lv)
    wp = '  debug write_block memory %d [string repeat "N" 768]; debug write memory %d $target' % (pa['mp'], pa['dl'])
    bp = 'debug set_bp %d {} atread' % sy['readInputControl']
    a = run(ORIG, 'ASCII16', os.path.join(out, 'orig'), '' if mortal else wr(co, inv), sy['g_GameFrame'], 6, sched, ticks, diff, tour, sy['g_CurrRoomIdx'], wo, bp, KEYS_ORIG, '', clean)
    b = run(rom, 'ASCII8', os.path.join(out, 'port'), '' if mortal else wr(cp, iv), pa['gf'], 2, sched, ticks, diff, tour, pa['rm'], wp, 'debug set_watchpoint write_mem %d {} atgf' % pa['gf'], KEYS_PORT % (pa['ms'] + 61), 'puts $log "B [rb %d]"' % (pa['ms'] + 59))
    ta = {int(l.split()[0]): l for l in a if l[0].isdigit()}
    tb = {int(l.split()[0]): l for l in b if l[0].isdigit()}
    backlog = {}
    for l in b:
        if l.startswith('B '):
            backlog[l] = backlog.get(l, 0) + 1
    print('port, ticks waiting at each frame:', sorted(backlog.items()))
    b = [l for l in b if not l.startswith('B ')]
    va = [l for l in a if l.startswith('V ')]
    vb_ = [l for l in b if l.startswith('V ')]
    print('screens compared: %d / %d, identical %d' % (len(va), len(vb_), len(set(va) & set(vb_))))
    rooms = sorted({' '.join(l.split()[3:5]) for l in ta.values()})
    common = sorted(set(ta) & set(tb))
    print('ticks logged: original %d, port %d, in common %d; rooms seen %d' % (len(ta), len(tb), len(common), len(rooms)))
    for l in (a[-1], b[-1]):
        if not l[0].isdigit():
            print(l[:300])

    # the port sends the sprites to VRAM at the start of the next tick, and a sample can fall early or late: a difference
    # counts only when it lasts (the player compared at the same tick, the objects with the port one tick later)
    def split(l):
        p = l.split('|')
        return p[0].split()[1:], p[1].strip()

    def near(d, t, value, part):
        return any(t + k in d and split(d[t + k])[part] == value for k in (-2, -1, 0, 1, 2))

    run_p = run_e = worst_p = worst_e = 0
    bad = None
    for t in common:
        pa_, ea = split(ta[t])
        if int(pa_[1]) >= 192 or int(split(tb[t])[0][1]) >= 192:
            run_p = run_e = 0
            continue  # sprites hidden while a room is drawn
        run_p = 0 if near(tb, t, pa_, 0) else run_p + 1
        run_e = 0 if near(tb, t, ea, 1) else run_e + 1
        worst_p = max(worst_p, run_p)
        worst_e = max(worst_e, run_e)
        if bad is None and (run_p > 3 or run_e > 3):
            bad = t
    print('longest difference: player %d ticks, objects %d ticks' % (worst_p, worst_e))
    sa, la = effects(ta)
    sb, lb = effects(tb)
    print('sound states in the rooms: %d / %d, identical in order %d; ticks with channels B or C audible %d / %d' % (len(sa), len(sb), sum(1 for p, q in zip(sa, sb) if p == q), la, lb))
    if bad is None:
        print('SAME GAME')
    else:
        print('DIVERGED at tick', bad)
        for k in common:
            if bad - 9 <= k <= bad:
                print(' o', ta[k][:150])
                print(' p', tb[k][:150])


if __name__ == '__main__':
    main()
