
set throttle off
set out "test/out/orig"
set first 6
set log [open "$out/trace.txt" w]
set phase 0
set pf 0
set total 0
set last ""
proc sv {name} { global out; set f [open "$out/$name.bin" wb]; fconfigure $f -translation binary; puts -nonewline $f [debug read_block VRAM 0 16384]; close $f }
proc vb {a} { scan [debug read VRAM $a] %d v; return $v }
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
  set score [scan $score %d]
  set en {}
  for {set i $first} {$i < 24} {incr i} {
    set a [expr {6912 + $i * 4}]
    set sy [vb $a]
    if {$sy == 208} break
    if {$sy == 213 || $sy == 209} continue
    lappend en [format "%d,%d,%d" [vb [expr {$a + 1}]] $sy [vb [expr {$a + 2}]]]
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
  if {$total > 20000} { puts $log "LIMIT phase $phase"; close $log; exit }
  after frame later
}
proc later {} { after time 0.012 step }
set steps {
  {{[vb 6408] == 243} {keymatrixdown 0 0x02}}
  {{$f > 20} {keymatrixup 0 0x02}}
  {{$y == 170 && $x == 32} {keymatrixdown 8 0x80}}
  {{$x >= 114 && $y == 170} {keymatrixup 8 0x80; keymatrixdown 8 0x01}}
  {{$lvl == 1} {keymatrixup 8 0x01}}
  {{$life == 2} {sv life2}}
  {{$life == 1} {sv life1}}
  {{[vb 6144] != 236 && $f > 100} {keymatrixup 8 0x01}}
  {{$f > 80} {sv over}}
  {{$f > 100} {keymatrixdown 8 0x01}}
  {{$f > 20} {keymatrixup 8 0x01}}
  {{[vb 6408] == 243} {sv menu2; keymatrixdown 0 0x01}}
  {{$f > 20} {keymatrixup 0 0x01}}
  {{$y == 170 && $x == 32 && $f > 20} {sv again}}
  {{$f > 20} {set phase 9999}}
}
after frame later
