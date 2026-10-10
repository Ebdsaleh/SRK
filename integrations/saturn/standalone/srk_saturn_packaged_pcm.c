#include "srk_saturn_packaged_pcm.h"
#include "SEGA_GFS.H"


#define SRK_GFS_OPEN_MAX 1
#define SRK_GFS_MAX_DIR 16
#define SRK_PCM_HEADER_BYTES 16u
#define SRK_PCM_MAGIC_0 'S'
#define SRK_PCM_MAGIC_1 'R'
#define SRK_PCM_MAGIC_2 'K'
#define SRK_PCM_MAGIC_3 'P'
#define SRK_PCM_VERSION 1u
#define SRK_PCM_ENCODING_PCM16_BE 1u
#define SRK_PCM_CHANNELS_MONO 1u
#define SRK_PCM_LOOP_START 0u
#define SRK_PCM_LOOP_END 511u


/*
 * GFS requires caller-owned work/directory storage.  The file buffer is Uint32
 * backed so the synchronous GFS_Load destination is naturally 4-byte aligned.
 */
static Uint32 srk_gfs_work[GFS_WORK_SIZE(SRK_GFS_OPEN_MAX) / sizeof(Uint32)];
static GfsDirTbl srk_gfs_dirtbl;
static GfsDirName srk_gfs_dirnames[SRK_GFS_MAX_DIR];
static Uint32 srk_pcm_file_words[(SRK_SATURN_PACKAGED_PCM_FILE_BYTES + 3u) / 4u];


static unsigned int srk_pcm_be16(const srk_u8 *bytes)
{
    return ((unsigned int)bytes[0] << 8) | (unsigned int)bytes[1];
}


static unsigned long srk_pcm_be32(const srk_u8 *bytes)
{
    return ((unsigned long)bytes[0] << 24) |
           ((unsigned long)bytes[1] << 16) |
           ((unsigned long)bytes[2] << 8) |
           (unsigned long)bytes[3];
}


static int srk_saturn_packaged_pcm_validate(
    SRK_SATURN_PACKAGED_PCM *pcm,
    const srk_u8 *bytes
)
{
    unsigned long sample_count;
    unsigned int loop_start;
    unsigned int loop_end;
    unsigned int sample;
    unsigned int offset;

    if(!pcm || !bytes)
        return 0;

    if(bytes[0] != SRK_PCM_MAGIC_0 ||
       bytes[1] != SRK_PCM_MAGIC_1 ||
       bytes[2] != SRK_PCM_MAGIC_2 ||
       bytes[3] != SRK_PCM_MAGIC_3)
        return 0;
    if(bytes[4] != SRK_PCM_VERSION ||
       bytes[5] != SRK_PCM_ENCODING_PCM16_BE ||
       bytes[6] != SRK_PCM_CHANNELS_MONO ||
       bytes[7] != 0u)
        return 0;

    sample_count = srk_pcm_be32(&bytes[8]);
    loop_start = srk_pcm_be16(&bytes[12]);
    loop_end = srk_pcm_be16(&bytes[14]);
    if(sample_count != SRK_SATURN_PACKAGED_PCM_SAMPLE_COUNT ||
       loop_start != SRK_PCM_LOOP_START ||
       loop_end != SRK_PCM_LOOP_END)
        return 0;

    for(sample=0u; sample<SRK_SATURN_PACKAGED_PCM_SAMPLE_COUNT; sample++){
        offset = SRK_PCM_HEADER_BYTES + (sample * 2u);
        pcm->samples[sample] = (srk_u16)srk_pcm_be16(&bytes[offset]);
    }

    pcm->sample_count = (unsigned int)sample_count;
    pcm->loop_start = loop_start;
    pcm->loop_end = loop_end;
    pcm->bytes_loaded = SRK_SATURN_PACKAGED_PCM_FILE_BYTES;
    return 1;
}


int srk_saturn_packaged_pcm_load(SRK_SATURN_PACKAGED_PCM *pcm)
{
    Sint32 result;
    Sint32 fid;
    GfsHn handle;
    Sint32 sector_size;
    Sint32 sector_count;
    Sint32 last_size;
    unsigned long file_size;
    srk_u8 *bytes;

    if(!pcm)
        return 0;

    pcm->sample_count = 0u;
    pcm->loop_start = 0u;
    pcm->loop_end = 0u;
    pcm->bytes_loaded = 0u;
    pcm->status = SRK_SATURN_PACKAGED_PCM_NOT_ATTEMPTED;

    GFS_DIRTBL_TYPE(&srk_gfs_dirtbl) = GFS_DIR_NAME;
    GFS_DIRTBL_NDIR(&srk_gfs_dirtbl) = SRK_GFS_MAX_DIR;
    GFS_DIRTBL_DIRNAME(&srk_gfs_dirtbl) = srk_gfs_dirnames;

    /* GFS_Init owns the documented filesystem/CD mounting initialization. */
    result = GFS_Init(SRK_GFS_OPEN_MAX, srk_gfs_work, &srk_gfs_dirtbl);
    if(result < 0){
        pcm->status = SRK_SATURN_PACKAGED_PCM_GFS_INIT_FAILED;
        return 0;
    }

    fid = GFS_NameToId((Sint8 *)"SRKPCM.BIN");
    if(fid < 0){
        pcm->status = SRK_SATURN_PACKAGED_PCM_NAME_LOOKUP_FAILED;
        return 0;
    }

    handle = GFS_Open(fid);
    if(handle == (GfsHn)0){
        pcm->status = SRK_SATURN_PACKAGED_PCM_OPEN_FAILED;
        return 0;
    }

    sector_size = 0;
    sector_count = 0;
    last_size = 0;
    GFS_GetFileSize(handle, &sector_size, &sector_count, &last_size);
    GFS_Close(handle);

    if(sector_size <= 0 || sector_count <= 0 || last_size <= 0 ||
       last_size > sector_size){
        pcm->status = SRK_SATURN_PACKAGED_PCM_SIZE_FAILED;
        return 0;
    }

    file_size =
        ((unsigned long)(sector_count - 1) * (unsigned long)sector_size) +
        (unsigned long)last_size;
    if(file_size != SRK_SATURN_PACKAGED_PCM_FILE_BYTES){
        pcm->status = SRK_SATURN_PACKAGED_PCM_SIZE_FAILED;
        return 0;
    }

    result = GFS_Load(
        fid,
        0,
        srk_pcm_file_words,
        (Sint32)SRK_SATURN_PACKAGED_PCM_FILE_BYTES
    );
    if(result != (Sint32)SRK_SATURN_PACKAGED_PCM_FILE_BYTES){
        pcm->status = SRK_SATURN_PACKAGED_PCM_LOAD_FAILED;
        return 0;
    }

    bytes = (srk_u8 *)srk_pcm_file_words;
    if(!srk_saturn_packaged_pcm_validate(pcm, bytes)){
        pcm->status = SRK_SATURN_PACKAGED_PCM_FORMAT_FAILED;
        return 0;
    }

    pcm->status = SRK_SATURN_PACKAGED_PCM_READY;
    return 1;
}