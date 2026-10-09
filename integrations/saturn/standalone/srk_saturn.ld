/*
 * SRK standalone Sega Saturn linker script.
 *
 * The reviewed local vdp1ex template boots its plain first-read binary at
 * 0x06004000.  SRK keeps that load address but owns its own section layout.
 */
OUTPUT_FORMAT("binary")
SECTIONS
{
    . = 0x06004000;

    .text :
    {
        *(.text)
        *(.text.*)
    }

    .rodata ALIGN(4) :
    {
        *(.rodata)
        *(.rodata.*)
    }

    .data ALIGN(4) :
    {
        *(.data)
        *(.data.*)
    }

    __bss_start = .;
    .bss ALIGN(4) (NOLOAD) :
    {
        *(.bss)
        *(.bss.*)
        *(COMMON)
    }
    __bss_end = .;

    /DISCARD/ :
    {
        *(.comment)
        *(.note*)
    }
}
