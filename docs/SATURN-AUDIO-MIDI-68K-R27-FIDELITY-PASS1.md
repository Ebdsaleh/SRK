# Saturn MIDI 68K — R27 Fidelity Pass 1

R27 begins musical-fidelity work above the physically accepted R26 FIX1
transport/scheduler baseline.

## In scope

- preserve the exact 9,154-record / 287-batch Space Spectre SRKM stream;
- preserve the FIX1 D4 scheduler repair;
- preserve 16 owned SCSP voices and zero-BUSY allocation policy;
- preserve provisional RR16 and final release drain;
- replace eight coarse 16-program source buckets with sixteen GM eight-program
  family buckets;
- provide distinct generated sources for Space Spectre percussion notes:
  - 35: kick
  - 40: snare
  - 42: closed hi-hat
  - 51: ride/cymbal class
- apply MIDI velocity, channel volume and expression to the Note-On output level;
- apply MIDI channel pan to the SCSP direct-output pan field.

## Deliberately deferred

- active-voice pitch bend;
- sustain-pedal voice-lifetime refinement;
- full GM/GS instrument fidelity;
- sample-accurate drum kit;
- high-quality external/copyright-clean sample bank.

R27 still uses generated copyright-clean periodic waveforms. The purpose of this
pass is to make the physically proven multi-channel player substantially more
musical without mixing transport risk back into the experiment.

## Memory layout

R27 keeps the R26 voice/mixer boundary and uses the free data window immediately
below the resident 68K program:

- `0x2800..0x3BFF`: 20 timbre slots, `0x100` bytes each
- `0x3C00..0x3CFF`: 128-entry pan table
- `0x3D00..0x3DFF`: 128-entry melodic program source table
- `0x3E00..0x3EFF`: 128-entry percussion-note source table
- resident program remains at `0x4000`

The source-address tables keep selection compact across R26's 48 unrolled
allocation paths and avoid expanding a 16-family branch ladder into every path.

## Acceptance rule

Host build acceptance must keep the original Space Spectre transport contract
unchanged. Physical acceptance later requires the same terminal
`PASS - 0 dropped notes` result plus an audible improvement in instrument
separation, percussion identity and stereo placement.
