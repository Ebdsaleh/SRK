from __future__ import annotations

import struct

import pytest

from rikai_kotoba.hardware.saturn.sbl_gm_candidate_contract import (
    SaturnSblGmCandidateError,
    build_sega_sbl_area_map,
    rewrite_sega_sbl_runtime_contract,
)


def test_area_map_packs_sega_sound_driver_bitfields():
    area_map, drum_start = build_sega_sbl_area_map(0x1234, 0x5678)

    assert drum_start == 0xC234
    assert len(area_map) == 20
    assert area_map[:8] == struct.pack(">II", 0x0000B000, 0x00001234)
    assert area_map[8:16] == struct.pack(">II", 0x0100C234, 0x00005678)
    assert area_map[16:20] == struct.pack(">I", 0x80000000)


def test_runtime_contract_namespaces_gfs_and_encodes_20_byte_area_map_size():
    source = "\n".join(
        (
            "#define GFS_OPEN_MAX 2",
            "#define GFS_MAX_DIR 32",
            "static int a[GFS_WORK_SIZE(GFS_OPEN_MAX)];",
            "static int gfs_names[GFS_MAX_DIR];",
            "GFS_DIRTBL_NDIR(&gfs_table)=GFS_MAX_DIR;",
            "g=GFS_Init(GFS_OPEN_MAX,gfs_work,&gfs_table);",
            "SND_INI_ARA_SZ(ini)=(Uint16)SRK_SBL_GM_MAP_BYTES;",
        )
    )

    result = rewrite_sega_sbl_runtime_contract(source)

    assert "#define GFS_OPEN_MAX " not in result
    assert "#define GFS_MAX_DIR " not in result
    assert "#define SRK_GFS_OPEN_MAX 2" in result
    assert "#define SRK_GFS_MAX_DIR 32" in result
    assert "GFS_WORK_SIZE(SRK_GFS_OPEN_MAX)" in result
    assert "gfs_names[SRK_GFS_MAX_DIR]" in result
    assert "GFS_Init(SRK_GFS_OPEN_MAX,gfs_work,&gfs_table)" in result
    assert "SND_INI_ARA_SZ(ini)=(Uint16)((SRK_SBL_GM_MAP_BYTES-4UL)/2UL);" in result

    # Sega SBL's CHG_LONG macro is ((words*2) + (4 - ((words*2)%4))).
    # For our 20-byte map, an encoded value of 8 copies exactly 20 bytes.
    encoded = (20 - 4) // 2
    copied = encoded * 2 + (4 - ((encoded * 2) % 4))
    assert encoded == 8
    assert copied == 20


def test_runtime_contract_refuses_changed_anchor():
    with pytest.raises(SaturnSblGmCandidateError, match="anchor changed"):
        rewrite_sega_sbl_runtime_contract("#define GFS_OPEN_MAX 2\n")
