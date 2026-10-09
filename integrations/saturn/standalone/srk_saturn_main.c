#include "srk_diag_app.h"
#include "srk_saturn_audio.h"
#include "srk_saturn_host.h"


static SRK_DIAG_APP srk_app;
static SRK_DIAG_HOST srk_host;
static SRK_SATURN_HOST_STATE srk_host_state;


/*
 * The reviewed GNUSH Saturn startup convention calls C function `_main`, whose
 * external symbol is `__main` for the historical SH-ELF toolchain.
 */
void _main(void)
{
    srk_saturn_host_init(&srk_host, &srk_host_state);
    srk_saturn_audio_bind(&srk_host, &srk_host_state);
    srk_diag_app_reset(&srk_app);

    for(;;)
        srk_diag_app_frame(&srk_app, &srk_host);
}
