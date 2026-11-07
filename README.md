# The Castle - port in SamPr Basic

Versione in **SamPr Basic** di *The Castle* di Nicola Brogelli, riscritta dalla versione C/MSXgl. I sorgenti C non fanno parte di questa cartella: i dati sono gia' tutti nei `.BIN`, che ora sono la versione di riferimento.
Stessa grafica, stesse 28 stanze, stessa fisica, stessa musica ed effetti sonori. Cartuccia ASCII8 da 120 KB per MSX1 e superiori.

```
openmsx -machine Sony_HB-75P -cart CASTL.ROM -romtype ASCII8
```

## Controlli
| | |
|---|---|
| Frecce o joystick (porta 1 e 2) | destra e sinistra |
| Freccia su o tasto A | salto |
| Spazio o tasto B | azione: raccogliere oggetti, aprire le porte |
| 0, 1, 2 nel menu | difficolta': Easy, Normal, Hard |

## Compilare
Aprire `CASTL000.SPB` nell'editor SamPr Basic (o in VS Code con l'estensione) e premere F5: il compilatore legge tutti i `CASTLnnn` della cartella e produce `CASTL.ROM`.
Da riga di comando: `node tools/spb_compile.cjs CASTL000.SPB .` (usa il compilatore dell'estensione VS Code).

## File
| File | Contenuto |
|---|---|
| `CASTL000.SPB` | segmento 0: avvio, interrupt (musica, effetti, input), ciclo principale |
| `CASTL001.SPB` | segmento 1: un tick di gioco: fisica del cavaliere, nemici, piattaforme |
| `CASTL002.SPB` | segmento 2: oggetti, inventario, vite, porte, trappole |
| `CASTL003.SPB` | segmento 3: caricamento stanze, HUD, menu, avvio dei brani |
| `CASTL004.BIN` | segmento 4: tile, sprite, colori, tabella dei suoni, effetti |
| `CASTL005-008.BIN` | segmenti 5-8: le 28 stanze (832 byte l'una) |
| `CASTL009-013.BIN` | segmenti 9-13: i due brani come flussi di registri PSG |
| `tools/spb_compile.cjs` | compilazione da terminale, presa da MSX-JETSETWILLY |
| `tools/bot.py`, `fuzz.py`, `psgcmp.py`, `joytest.py`, `test/` | test automatici in openMSX, vedi sotto |

## Dal C al BASIC
| C / MSXgl | SamPr Basic |
|---|---|
| `ROM_ASCII16`, 256 KB | `ROM_ASCII8`, 120 KB: con ASCII8 codice (8000h) e dati (A000h) stanno in finestre separate |
| `GamePawn` di MSXgl | `hero` e `phys`: stesso algoritmo, compresi gli overflow dei byte e la divisione che tronca verso lo zero |
| `getTile` legge la VRAM | la mappa e' copiata in RAM (`mp`): `PEEK` costa molto meno di `VPEEK`; ogni scrittura a video aggiorna anche la RAM |
| scansione delle 768 tile a ogni cambio stanza | fatta una volta sul PC durante la conversione: il record della stanza contiene gia' posizioni e nemici |
| struct dei nemici | tabelle di byte in RAM lette con `PEEK`/`POKE` |
| player PT3 e ayFX | routine di interrupt in `__ASM`: i brani sono decodificati sul PC in flussi di registri, gli effetti sono i flussi ayFX originali |
| `Print_DrawText` | `pt`: la tile di un carattere e' il suo codice ASCII + 160 |
| punteggio a 16 bit senza segno | conteggiato in centinaia: i numeri di SamPr Basic hanno il segno |

Come nell'originale il gioco salta un frame ogni sei: su una macchina PAL fa 41,7 tick al secondo.

## Differenze dall'originale
* **Effetto "vita persa":** il C chiama `playEffect(9)` anche quando si muore su una trappola, ma nell'originale in quel caso non si sente nulla (probabilmente perche' `drawLevel` richiama `SetActiveSegment(4)` a ogni riga e perde il segmento di ritorno). Il port lo suona.
* **Effetti sonori:** partono 2 tick prima, senza il ritardo che l'originale ha tra `PlayBankSFX` e il PSG.
* **Stanza 7:** la configurazione dichiara 2 piattaforme orizzontali ma la mappa ne ha una: il port usa solo quelle realmente presenti.
* **Oggetti raccolti:** ogni stanza ha 8 posti, ne servono al massimo 7. Nel C `g_CountItem` riparte dal conteggio dei soli primi 5 posti quando si rientra in una stanza.
* **Sprite dei nemici:** arrivano alla VRAM all'inizio del tick successivo: stessa posizione, un tick dopo. Usano piani consecutivi invece dei numeri fissi dell'originale.
* **Tastiera e joystick:** sono letti nell'interrupt invece che alla fine del tick.
* **Stanza 0:** la barra con la scritta MSXgl (4 tile, colonne 23-26 della riga 21) e' diventata SamprBasic (10 colonne, 19-28, tile 175-183: le due "a" sono la stessa tile). Resta una piattaforma solida, ma piu' lunga: per questo stanza 0 e tile 175-183 non coincidono piu' con la ROM originale.

## Test
Il port e' stato confrontato con la ROM originale in openMSX (Sony HB-75P), senza finestra:
* `tools/fuzz.py`: stessi tasti pseudo-casuali per ogni tick sulle due ROM, con vite, chiavi e pozione forzate in RAM e teletrasporto tra le stanze. Tre run, uno per difficolta', circa 92.000 tick su 27 stanze: posizione, punteggio, tempo, animazione e nemici coincidono, a meno di 1-2 tick dovuti al momento del campionamento.
* `tools/bot.py` con `test/route3.txt`: partita senza aiuti in NORMAL: tempo scaduto, tre vite, Game Over, menu, nuova partita. 138 stati identici; menu, stanza 0 e Game Over identici byte per byte in VRAM.
* `tools/psgcmp.py`: la musica del menu coincide in tutti i registri del PSG per 1495 frame.
* `tools/joytest.py`: joystick nelle porte 1 e 2, simulato con un breakpoint nell'interrupt.
* Avvio e movimento provati anche su Sony HB-F1XD (60 Hz: 50 tick al secondo come l'originale), Philips NMS 8250 e VG 8020.

Non provato su macchine reali.

## Licenze
La parte musicale dell'interrupt in `CASTL000.SPB` e i flussi di registri dei brani sono stati ottenuti con il codice di MSX-CHRONORUNNER, distribuito con licenza GPLv3: chi distribuisce il port deve tenerne conto.
Musica ed effetti sono quelli dell'originale: `Ghost.pt3` e `CGameOver.pt3`, oltre al banco ayFX.
