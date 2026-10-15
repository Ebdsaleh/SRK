# Saturn Audio — R28 Physical Interpretation

R28 (`Space Spectre R28 P1 - 9154 / 16v`) completed the full physical song on Saturn and reached terminal PASS with the complete event stream consumed and no dropped notes.

This closes the intended R28 transport question: the R26 FIX1 scheduler/queue path remains stable through the R27/R28 fidelity experiments.

It does **not** close musical fidelity.

Physical listening showed the percussion layer was present only as weak, muffled synthetic hits described by the user as sounding like muted bongos. The source MIDI uses a drum kit. Therefore the R28 synthetic percussion model is rejected as a fidelity solution even though transport passed.

Do not respond to this result by tuning the same tiny generated percussion waveforms again. The next musical backend must be based on the exact installed Sega sound-driver/sequence/tone-bank contract or, if required, a proper sample-bank implementation with distinct drum samples.

The existing R26-R28 MC68EC000/SRKM path remains accepted as a deterministic transport and hardware-diagnostic reference.
