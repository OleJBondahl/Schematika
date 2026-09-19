# Symbol inventory

Reference list of missing symbols per module, ranked. Names and grouping come from general
knowledge of IEC 60617, ISO 14617 / 10628-2 and ISA 5.1, not from the paywalled texts. Only the
registration numbers marked ✓ were seen in the ISO 10628-2 transcription. Confirm every entry against
its reference during the pilot. Design and method are in [design.md](design.md).

Route: **T** transcribe from an open SVG, **K** author from the kit, **R** reuse an existing symbol.
Priority: 1 = a real cabinet or P&ID needs it now, 2 = common, 3 = niche.

## Electrical (IEC 60617)

Existing: contacts (NO, NC, SPDT), coil, breaker, thermal overload, fuse, motor, contactor, e-stop,
turn switch, terminal, terminal box, PSU, block, ref, CT, connector pin.

| Symbol | Pri | Route | Note |
|---|---|---|---|
| Indicator lamp | 1 | K (check KiCad-IEC) | `H` tag reserved, no symbol. Specced in `symbol-standards.md`. |
| Control transformer | 1 | K (check KiCad-IEC) | `T` tag reserved. Specced there. |
| Earth / PE / chassis | 1 | K | Target for the `motor` PE port. |
| Pushbutton NO / NC | 1 | K | Contact family × pushbutton operator. |
| Isolator / load-break switch | 1 | K | Contact × isolator operator. |
| Timer relay: on-delay, off-delay contact | 1 | K | Contact × delay qualifier. |
| Selector switch, 3-position | 2 | K | Extends `turn_switch`. |
| Limit / position switch | 2 | K | Contact × position operator. |
| Proximity sensor (inductive, capacitive) | 2 | K | `B` tag reserved. |
| Solenoid coil, valve coil | 2 | K | Coil × operator. |
| Latching / polarised relay coil | 2 | K | Coil qualifier. |
| Safety relay | 2 | K | Block variant. |
| Diode, rectifier, bridge | 2 | K | |
| Resistor, capacitor, varistor, potentiometer | 2 | K | Shared with PCB, see below. |
| Terminal variants: fuse, ground, disconnect, two-level | 2 | K | Extends `terminal`. |
| Plug / socket connector | 2 | K | |
| Overload relay with aux contact | 2 | K | |
| Motor variants: 1-phase, DC, servo | 2 | K | Extends `motor`. |
| Frequency drive, soft starter | 2 | K | Block variants. |
| Pressure / temperature / flow / level switch | 2 | K | Contact × process operator. |
| Buzzer, horn | 3 | K | |
| Surge protective device | 3 | K | |
| Meters: ammeter, voltmeter, energy | 3 | K | |
| Battery, heater, fan | 3 | K | |
| Shield, twisted pair | 3 | K | Cable drawing marks. |

## PCB (schematic review)

Existing: connector block, connector pin, power 24 V, ground. Scope needs your confirmation.

| Symbol | Pri | Route | Note |
|---|---|---|---|
| Resistor, capacitor (plain, polarised) | 1 | R from electrical | Requires the shared `symbols` package. |
| Diode, LED, Zener, TVS | 1 | R / K | |
| Transistor: NPN, PNP, N-MOSFET, P-MOSFET | 1 | K | |
| Generic IC block with named pins | 1 | K | |
| Power symbols: +3V3, +5V, GND variants | 1 | K | Generalise `power_24v`. |
| Inductor, ferrite bead | 2 | K | |
| Crystal, oscillator | 2 | K | |
| Fuse, PTC | 2 | R | |
| Switch, pushbutton | 2 | R | |
| Opto-coupler, relay, transformer | 2 | K | |
| Op-amp | 2 | K | |
| Test point, NC marker | 3 | K | |

## P&ID (ISO 14617 / 10628-2, ISA 5.1)

Existing: instrument bubble, pipe (segment, tee, reducer, cap), centrifugal and positive-displacement
pump, gate, globe, control, check, ball and three-way valve, tank, heat exchanger.

| Symbol | Pri | Route | Note |
|---|---|---|---|
| Relief / safety valve | 1 | T | Specced in `symbol-standards.md`. |
| Filter, strainer (Y-type, basket) | 1 | T | |
| Orifice plate | 1 | T | ✓ registration C0096. |
| Compressor, blower | 1 | T | |
| Valve bodies: butterfly, plug, needle, diaphragm, pinch | 1 | T | Body × actuator family. |
| Actuators: diaphragm, piston, motor, solenoid, handwheel, spring-return | 1 | T | Applies to every valve body. |
| Fail-position marks | 2 | K | |
| Rupture disc, flame arrestor | 2 | T | |
| Silencer | 2 | T | ✓ registration 2033. |
| Sight glass | 2 | T | ✓ registration 2034. |
| Mixing nozzle, ejector | 2 | T | ✓ registration C0093 (nozzle). |
| Agitator / mixer | 2 | K | Composes onto `tank`. |
| Vessel types: horizontal drum, sphere, column, reactor | 2 | T | Tank / vessel is ✓ registration 301. |
| Heat exchanger types: shell-and-tube, plate, air cooler | 2 | T | |
| Flange, spectacle blind, hose, expansion joint | 2 | T | |
| Pipeline variants: jacketed, insulated, traced | 2 | T | ✓ registrations X409, X322, C0106. |
| Flow direction arrow, slope, siphon | 2 | T | ✓ registrations 241, 3061, 2038. |
| Signal lines: pneumatic, electric, capillary, data link | 2 | K | ISA 5.1 line types. |
| ISA shared display, computer function | 2 | K | Extends `instrument_bubble`. |
| Off-page connector | 3 | R | Reuse `electrical.symbols.ref`. |

## Overview (icons)

No standard governs these. Icons render existing symbols in a small variant.

| Node kind | Icon source | Note |
|---|---|---|
| Fuse | R `fuse` | |
| Relay / relay contact | R `coil`, `no_contact` | |
| Ground net | R earth | Needs the earth symbol above. |
| Connector | R `connector_pin` | |
| Terminal block | R `terminal` | |
| Power / CAN / interlock / signal net | K | Small colour-coded glyphs, one per net class. |
| Board / device, junction box, PLC, harness | K | Plain glyphs. No standard symbol exists. |
