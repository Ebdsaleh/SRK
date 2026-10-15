/* Minimal freestanding C runtime used by the Sega Sound I/F Direct MIDI path.
 *
 * The accepted sega_snd.a member that owns SND_CtrlDirMidi requires memcpy and
 * memset.  SRK's Saturn standalone image is freestanding, so provide exactly
 * those ISO-C semantics here rather than pulling an unrelated hosted libc.
 */

void *memcpy(void *destination, const void *source, unsigned long count)
{
    unsigned char *dst = (unsigned char *)destination;
    const unsigned char *src = (const unsigned char *)source;
    unsigned long i;

    for (i = 0; i < count; ++i) {
        dst[i] = src[i];
    }
    return destination;
}

void *memset(void *destination, int value, unsigned long count)
{
    unsigned char *dst = (unsigned char *)destination;
    const unsigned char byte_value = (unsigned char)value;
    unsigned long i;

    for (i = 0; i < count; ++i) {
        dst[i] = byte_value;
    }
    return destination;
}
