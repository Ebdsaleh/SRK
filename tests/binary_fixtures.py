"""Shared synthetic binary fixtures for Mjolnir object/archive tests.

These fixtures model structurally valid SH ELF/COFF objects closely enough to
exercise the production parsers without depending on test-module import order.
"""


def ar_member(name: str, payload: bytes) -> bytes:
    header = (
        name.encode("ascii").ljust(16, b" ")
        + b"0".ljust(12, b" ")
        + b"0".ljust(6, b" ")
        + b"0".ljust(6, b" ")
        + b"100644".ljust(8, b" ")
        + str(len(payload)).encode("ascii").ljust(10, b" ")
        + b"`\n"
    )
    if len(header) != 60:
        raise AssertionError("ar fixture header must be 60 bytes")
    return header + payload + (b"\n" if len(payload) & 1 else b"")


def _elf_section_header(
    name: int,
    section_type: int,
    flags: int,
    offset: int,
    size: int,
    *,
    link: int = 0,
    info: int = 0,
    align: int = 1,
    entsize: int = 0,
) -> bytes:
    values = (
        name,
        section_type,
        flags,
        0,
        offset,
        size,
        link,
        info,
        align,
        entsize,
    )
    return b"".join(value.to_bytes(4, "big") for value in values)


def elf32_sh_fixture() -> bytes:
    data = bytearray(0x300)
    data[0:4] = b"\x7fELF"
    data[4] = 1
    data[5] = 2
    data[6] = 1
    data[16:18] = (1).to_bytes(2, "big")
    data[18:20] = (42).to_bytes(2, "big")
    data[20:24] = (1).to_bytes(4, "big")
    data[32:36] = (0x200).to_bytes(4, "big")
    data[40:42] = (52).to_bytes(2, "big")
    data[46:48] = (40).to_bytes(2, "big")
    data[48:50] = (5).to_bytes(2, "big")
    data[50:52] = (4).to_bytes(2, "big")

    data[0x100:0x104] = b"\x00\x09\x00\x09"
    strings = b"\x00foo\x00bar\x00"
    data[0x110 : 0x110 + len(strings)] = strings
    shstrings = b"\x00.text\x00.strtab\x00.symtab\x00.shstrtab\x00"
    data[0x180 : 0x180 + len(shstrings)] = shstrings

    symbols = bytearray(48)
    symbols[16:20] = (1).to_bytes(4, "big")
    symbols[24:28] = (4).to_bytes(4, "big")
    symbols[28] = 0x12
    symbols[30:32] = (1).to_bytes(2, "big")
    symbols[32:36] = (5).to_bytes(4, "big")
    symbols[44] = 0x10
    data[0x140:0x170] = symbols

    sections = bytearray()
    sections += bytes(40)
    sections += _elf_section_header(1, 1, 0x6, 0x100, 4, align=4)
    sections += _elf_section_header(7, 3, 0, 0x110, len(strings))
    sections += _elf_section_header(15, 2, 0, 0x140, 48, link=2, info=1, align=4, entsize=16)
    sections += _elf_section_header(23, 3, 0, 0x180, len(shstrings))
    data[0x200 : 0x200 + len(sections)] = sections
    return bytes(data)


def coff_sh_fixture(*, defined_name: str = "bar", undefined_name: str = "baz") -> bytes:
    """Return one structurally valid big-endian Hitachi SH COFF object.

    Symbol names longer than eight bytes use the real COFF string-table form,
    which is required for Saturn SDK-style names such as ``DMA_ScuStart``.
    """

    symptr = 0x80
    symbol_count = 2
    symbol_table_end = symptr + symbol_count * 18

    long_names = bytearray()

    def symbol_name_field(name: str) -> bytes:
        encoded = name.encode("ascii")
        if len(encoded) <= 8:
            return encoded.ljust(8, b"\x00")
        offset = 4 + len(long_names)
        long_names.extend(encoded)
        long_names.append(0)
        return b"\x00\x00\x00\x00" + offset.to_bytes(4, "big")

    def symbol(name: str, section_number: int) -> bytes:
        return b"".join(
            (
                symbol_name_field(name),
                (0).to_bytes(4, "big"),
                section_number.to_bytes(2, "big", signed=True),
                (0x20).to_bytes(2, "big"),
                bytes((2, 0)),
            )
        )

    defined = symbol(defined_name, 1)
    undefined = symbol(undefined_name, 0)
    string_table = (4 + len(long_names)).to_bytes(4, "big") + bytes(long_names)
    data = bytearray(symbol_table_end + len(string_table))

    data[0:2] = (0x0500).to_bytes(2, "big")
    data[2:4] = (1).to_bytes(2, "big")
    data[4:8] = (0x30E308FD).to_bytes(4, "big")
    data[8:12] = symptr.to_bytes(4, "big")
    data[12:16] = symbol_count.to_bytes(4, "big")

    section = bytearray(40)
    section[0:8] = b".text\x00\x00\x00"
    section[16:20] = (4).to_bytes(4, "big")
    section[20:24] = (0x60).to_bytes(4, "big")
    section[36:40] = (0x20).to_bytes(4, "big")
    data[20:60] = section
    data[0x60:0x64] = b"\x00\x09\x00\x09"

    data[symptr : symptr + 18] = defined
    data[symptr + 18 : symptr + 36] = undefined
    data[symbol_table_end : symbol_table_end + len(string_table)] = string_table
    return bytes(data)
