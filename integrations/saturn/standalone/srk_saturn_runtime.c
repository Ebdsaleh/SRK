/*
 * Minimal freestanding C runtime surface required by the reviewed Saturn SBL
 * libraries used by SRK's standalone diagnostics.
 *
 * The standalone image intentionally links with -nostdlib.  Mjolnir's SDK-wide
 * symbol index proved that sega_gfs.a requires the standard C ABI symbols
 * memcmp, memset, strncmp, and strncpy, while the existing startup assembly
 * already supplies memcpy.  Keep these implementations tiny, deterministic,
 * allocation-free, and independent of hosted headers/runtime support.
 */


typedef unsigned long srk_size_t;


void *memset(void *destination, int value, srk_size_t count)
{
    unsigned char *cursor;
    unsigned char byte_value;

    cursor = (unsigned char *)destination;
    byte_value = (unsigned char)value;
    while(count != 0u){
        *cursor++ = byte_value;
        count--;
    }
    return destination;
}


int memcmp(const void *left, const void *right, srk_size_t count)
{
    const unsigned char *lhs;
    const unsigned char *rhs;

    lhs = (const unsigned char *)left;
    rhs = (const unsigned char *)right;
    while(count != 0u){
        if(*lhs != *rhs)
            return (int)*lhs - (int)*rhs;
        lhs++;
        rhs++;
        count--;
    }
    return 0;
}


int strncmp(const char *left, const char *right, srk_size_t count)
{
    unsigned char lhs;
    unsigned char rhs;

    while(count != 0u){
        lhs = (unsigned char)*left;
        rhs = (unsigned char)*right;
        if(lhs != rhs)
            return (int)lhs - (int)rhs;
        if(lhs == 0u)
            return 0;
        left++;
        right++;
        count--;
    }
    return 0;
}


char *strncpy(char *destination, const char *source, srk_size_t count)
{
    char *result;
    char value;

    result = destination;
    while(count != 0u){
        value = *source;
        *destination++ = value;
        count--;
        if(value == '\0'){
            while(count != 0u){
                *destination++ = '\0';
                count--;
            }
            break;
        }
        source++;
    }
    return result;
}
