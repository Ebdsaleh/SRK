#include "srk_saturn_host.h"
#include "vga_font.h"


#define SRK_PDR1   (*(volatile srk_u8 *)0x20100075)
#define SRK_PDR2   (*(volatile srk_u8 *)0x20100077)
#define SRK_DDR1   (*(volatile srk_u8 *)0x20100079)
#define SRK_DDR2   (*(volatile srk_u8 *)0x2010007B)
#define SRK_IOSEL  (*(volatile srk_u8 *)0x2010007D)
#define SRK_EXLE   (*(volatile srk_u8 *)0x2010007F)

#define SRK_VDP1_VRAM ((volatile srk_u16 *)0x25C00000)
#define SRK_VDP1_TVMR (*(volatile srk_u16 *)0x25D00000)
#define SRK_VDP1_FBCR (*(volatile srk_u16 *)0x25D00002)
#define SRK_VDP1_PTMR (*(volatile srk_u16 *)0x25D00004)
#define SRK_VDP1_EWDR (*(volatile srk_u16 *)0x25D00006)
#define SRK_VDP1_EWLR (*(volatile srk_u16 *)0x25D00008)
#define SRK_VDP1_EWRR (*(volatile srk_u16 *)0x25D0000A)
#define SRK_VDP1_EDSR (*(volatile srk_u16 *)0x25D00010)
#define SRK_VDP1_LOPR (*(volatile srk_u16 *)0x25D00012)
#define SRK_VDP1_COPR (*(volatile srk_u16 *)0x25D00014)
#define SRK_VDP1_MODR (*(volatile srk_u16 *)0x25D00016)

#define SRK_VDP2_VRAM ((volatile srk_u8 *)0x25E00000)
#define SRK_VDP2_CRAM ((volatile srk_u16 *)0x25F00000)
#define SRK_TVMD      (*(volatile srk_u16 *)0x25F80000)
#define SRK_TVSTAT    (*(volatile srk_u16 *)0x25F80004)
#define SRK_RAMCTL    (*(volatile srk_u16 *)0x25F8000E)
#define SRK_BGON      (*(volatile srk_u16 *)0x25F80020)
#define SRK_CHCTLA    (*(volatile srk_u16 *)0x25F80028)
#define SRK_MPOFN     (*(volatile srk_u16 *)0x25F8003C)
#define SRK_SCXIN0    (*(volatile srk_u16 *)0x25F80070)
#define SRK_SCXDN0    (*(volatile srk_u16 *)0x25F80072)
#define SRK_SCYIN0    (*(volatile srk_u16 *)0x25F80074)
#define SRK_SPCTL     (*(volatile srk_u16 *)0x25F800E0)
#define SRK_PRISA     (*(volatile srk_u16 *)0x25F800F0)

#define SRK_PAD_DELAY 16
#define SRK_BITMAP_STRIDE 1024
#define SRK_VISIBLE_WIDTH 320
#define SRK_VISIBLE_HEIGHT 224
#define SRK_TEXT_COLUMNS 40
#define SRK_TEXT_ROWS 28

#define SRK_COLOR_BLACK   0
#define SRK_COLOR_RED     1
#define SRK_COLOR_GREEN   2
#define SRK_COLOR_BLUE    3
#define SRK_COLOR_YELLOW  4
#define SRK_COLOR_CYAN    5
#define SRK_COLOR_MAGENTA 6
#define SRK_COLOR_GRAY    7
#define SRK_COLOR_WHITE   15
#define SRK_GRAY_BASE     16
#define SRK_GRAY_COUNT    16

#define SRK_VDP1_COMMAND_WORDS 16
#define SRK_VDP1_CMDCTRL 0
#define SRK_VDP1_CMDLINK 1
#define SRK_VDP1_CMDPMOD 2
#define SRK_VDP1_CMDCOLR 3
#define SRK_VDP1_CMDXA   6
#define SRK_VDP1_CMDYA   7
#define SRK_VDP1_CMDXB   8
#define SRK_VDP1_CMDYB   9
#define SRK_VDP1_CMDXC   10
#define SRK_VDP1_CMDYC   11
#define SRK_VDP1_CMDXD   12
#define SRK_VDP1_CMDYD   13

#define SRK_PAD_L      (1u << 15)
#define SRK_PAD_START  (1u << 11)
#define SRK_PAD_A      (1u << 10)
#define SRK_PAD_C      (1u << 9)
#define SRK_PAD_B      (1u << 8)
#define SRK_PAD_RIGHT  (1u << 7)
#define SRK_PAD_LEFT   (1u << 6)
#define SRK_PAD_DOWN   (1u << 5)
#define SRK_PAD_UP     (1u << 4)
#define SRK_PAD_R      (1u << 3)
#define SRK_PAD_X      (1u << 2)
#define SRK_PAD_Y      (1u << 1)
#define SRK_PAD_Z      (1u << 0)


static void srk_saturn_pad_delay(void)
{
    int count;
    for(count=0; count<SRK_PAD_DELAY; count++)
        __asm__ volatile ("nop");
}


static srk_u16 srk_saturn_read_pad_raw(void)
{
    srk_u16 raw;

    SRK_PDR1 = 0x60;
    srk_saturn_pad_delay();
    raw = (srk_u16)((SRK_PDR1 & 0x08) << 12);

    SRK_PDR1 = 0x40;
    srk_saturn_pad_delay();
    raw |= (srk_u16)((SRK_PDR1 & 0x0F) << 8);

    SRK_PDR1 = 0x20;
    srk_saturn_pad_delay();
    raw |= (srk_u16)((SRK_PDR1 & 0x0F) << 4);

    SRK_PDR1 = 0x00;
    srk_saturn_pad_delay();
    raw |= (srk_u16)(SRK_PDR1 & 0x0F);

    return raw;
}


static srk_u16 srk_saturn_normalize_pad(srk_u16 active)
{
    srk_u16 buttons;

    buttons = SRK_DIAG_BUTTON_NONE;
    if(active & SRK_PAD_UP)     buttons |= SRK_DIAG_BUTTON_UP;
    if(active & SRK_PAD_DOWN)   buttons |= SRK_DIAG_BUTTON_DOWN;
    if(active & SRK_PAD_LEFT)   buttons |= SRK_DIAG_BUTTON_LEFT;
    if(active & SRK_PAD_RIGHT)  buttons |= SRK_DIAG_BUTTON_RIGHT;
    if(active & SRK_PAD_A)      buttons |= SRK_DIAG_BUTTON_A;
    if(active & SRK_PAD_B)      buttons |= SRK_DIAG_BUTTON_B;
    if(active & SRK_PAD_C)      buttons |= SRK_DIAG_BUTTON_C;
    if(active & SRK_PAD_X)      buttons |= SRK_DIAG_BUTTON_X;
    if(active & SRK_PAD_Y)      buttons |= SRK_DIAG_BUTTON_Y;
    if(active & SRK_PAD_Z)      buttons |= SRK_DIAG_BUTTON_Z;
    if(active & SRK_PAD_L)      buttons |= SRK_DIAG_BUTTON_L;
    if(active & SRK_PAD_R)      buttons |= SRK_DIAG_BUTTON_R;
    if(active & SRK_PAD_START)  buttons |= SRK_DIAG_BUTTON_START;
    return buttons;
}


static srk_u32 srk_saturn_time_us(void *context)
{
    SRK_SATURN_HOST_STATE *state;
    state = (SRK_SATURN_HOST_STATE *)context;
    return state ? state->now_us : 0;
}


static int srk_saturn_poll_pad(
    void *context,
    unsigned int port,
    SRK_DIAG_PAD_SAMPLE *sample
)
{
    srk_u16 raw;
    srk_u16 active;

    (void)context;
    if(!sample || port != 0)
        return 0;

    raw = srk_saturn_read_pad_raw();
    active = (srk_u16)(raw ^ 0x8FFFu);

    sample->raw_state = raw;
    sample->buttons = srk_saturn_normalize_pad(active);
    sample->connected = 1;
    return 1;
}


static void srk_saturn_wait_vblank_out(void)
{
    while((SRK_TVSTAT & 0x0008u) == 0x0008u)
        ;
}


static void srk_saturn_wait_vblank_in(void)
{
    while((SRK_TVSTAT & 0x0008u) == 0)
        ;
}


static void srk_saturn_begin_frame(void *context)
{
    (void)context;
    srk_saturn_wait_vblank_out();
    srk_saturn_wait_vblank_in();
}


static void srk_saturn_fill_visible(srk_u8 color)
{
    volatile srk_u8 *row;
    int x;
    int y;

    for(y=0; y<SRK_VISIBLE_HEIGHT; y++){
        row = SRK_VDP2_VRAM + (y * SRK_BITMAP_STRIDE);
        for(x=0; x<SRK_VISIBLE_WIDTH; x++)
            row[x] = color;
    }
}


static void srk_saturn_clear(void *context)
{
    (void)context;
    srk_saturn_fill_visible(SRK_COLOR_BLACK);
}


static void srk_saturn_draw_text(
    void *context,
    int x,
    int y,
    const char *text
)
{
    volatile srk_u8 *row;
    srk_u8 bits;
    srk_u8 glyph;
    int column;
    int pixel;
    int scanline;

    (void)context;
    if(!text || x < 0 || y < 0 || y >= SRK_TEXT_ROWS)
        return;

    column = x;
    while(*text && column < SRK_TEXT_COLUMNS){
        glyph = (srk_u8)*text++;
        for(scanline=0; scanline<8; scanline++){
            bits = font[((unsigned int)glyph << 3) | (unsigned int)scanline];
            row = SRK_VDP2_VRAM
                + ((y * 8 + scanline) * SRK_BITMAP_STRIDE)
                + (column * 8);
            for(pixel=0; pixel<8; pixel++)
                row[pixel] = (bits & (0x80u >> pixel)) ? SRK_COLOR_WHITE : SRK_COLOR_BLACK;
        }
        column++;
    }
}


static void srk_saturn_draw_color_bars(void)
{
    static const srk_u8 colors[8] = {
        SRK_COLOR_WHITE,
        SRK_COLOR_YELLOW,
        SRK_COLOR_CYAN,
        SRK_COLOR_GREEN,
        SRK_COLOR_MAGENTA,
        SRK_COLOR_RED,
        SRK_COLOR_BLUE,
        SRK_COLOR_BLACK
    };
    volatile srk_u8 *row;
    int x;
    int y;
    int index;

    for(y=0; y<SRK_VISIBLE_HEIGHT; y++){
        row = SRK_VDP2_VRAM + (y * SRK_BITMAP_STRIDE);
        for(x=0; x<SRK_VISIBLE_WIDTH; x++){
            index = (x * 8) / SRK_VISIBLE_WIDTH;
            if(index > 7)
                index = 7;
            row[x] = colors[index];
        }
    }
}


static void srk_saturn_draw_grayscale(void)
{
    volatile srk_u8 *row;
    int x;
    int y;
    int level;

    for(y=0; y<SRK_VISIBLE_HEIGHT; y++){
        row = SRK_VDP2_VRAM + (y * SRK_BITMAP_STRIDE);
        for(x=0; x<SRK_VISIBLE_WIDTH; x++){
            level = (x * SRK_GRAY_COUNT) / SRK_VISIBLE_WIDTH;
            if(level >= SRK_GRAY_COUNT)
                level = SRK_GRAY_COUNT - 1;
            row[x] = (srk_u8)(SRK_GRAY_BASE + level);
        }
    }
}


static void srk_saturn_draw_checkerboard(void)
{
    volatile srk_u8 *row;
    int x;
    int y;

    for(y=0; y<SRK_VISIBLE_HEIGHT; y++){
        row = SRK_VDP2_VRAM + (y * SRK_BITMAP_STRIDE);
        for(x=0; x<SRK_VISIBLE_WIDTH; x++)
            row[x] = (((x >> 4) + (y >> 4)) & 1) ? SRK_COLOR_WHITE : SRK_COLOR_BLACK;
    }
}


static void srk_saturn_draw_grid(void)
{
    volatile srk_u8 *row;
    int x;
    int y;

    for(y=0; y<SRK_VISIBLE_HEIGHT; y++){
        row = SRK_VDP2_VRAM + (y * SRK_BITMAP_STRIDE);
        for(x=0; x<SRK_VISIBLE_WIDTH; x++){
            if((x & 15) == 0 || (y & 15) == 0)
                row[x] = SRK_COLOR_WHITE;
            else if((x & 7) == 0 || (y & 7) == 0)
                row[x] = SRK_COLOR_GRAY;
            else
                row[x] = SRK_COLOR_BLACK;
        }
    }
}


static void srk_saturn_draw_safe_area(void)
{
    volatile srk_u8 *row;
    int x;
    int y;
    int border;
    int center;

    for(y=0; y<SRK_VISIBLE_HEIGHT; y++){
        row = SRK_VDP2_VRAM + (y * SRK_BITMAP_STRIDE);
        for(x=0; x<SRK_VISIBLE_WIDTH; x++){
            border = x == 0 || y == 0 || x == SRK_VISIBLE_WIDTH - 1 || y == SRK_VISIBLE_HEIGHT - 1;
            border = border || x == 8 || y == 8 || x == SRK_VISIBLE_WIDTH - 9 || y == SRK_VISIBLE_HEIGHT - 9;
            center = x == (SRK_VISIBLE_WIDTH / 2) || y == (SRK_VISIBLE_HEIGHT / 2);
            if(border)
                row[x] = SRK_COLOR_WHITE;
            else if(center)
                row[x] = SRK_COLOR_GRAY;
            else
                row[x] = SRK_COLOR_BLACK;
        }
    }
}


static void srk_saturn_draw_video_pattern(void *context, unsigned int pattern_id)
{
    (void)context;

    switch(pattern_id){
        case 0:
            srk_saturn_fill_visible(SRK_COLOR_BLACK);
            break;
        case 1:
            srk_saturn_fill_visible(SRK_COLOR_WHITE);
            break;
        case 2:
            srk_saturn_fill_visible(SRK_COLOR_RED);
            break;
        case 3:
            srk_saturn_fill_visible(SRK_COLOR_GREEN);
            break;
        case 4:
            srk_saturn_fill_visible(SRK_COLOR_BLUE);
            break;
        case 5:
            srk_saturn_draw_color_bars();
            break;
        case 6:
            srk_saturn_draw_grayscale();
            break;
        case 7:
            srk_saturn_draw_checkerboard();
            break;
        case 8:
            srk_saturn_draw_grid();
            break;
        case 9:
            srk_saturn_draw_safe_area();
            break;
        default:
            srk_saturn_fill_visible(SRK_COLOR_BLACK);
            break;
    }
}


static srk_u16 srk_saturn_vdp1_rgb(srk_u8 red, srk_u8 green, srk_u8 blue)
{
    return (srk_u16)(
        0x8000u |
        (((srk_u16)(blue >> 3) & 31u) << 10) |
        (((srk_u16)(green >> 3) & 31u) << 5) |
        ((srk_u16)(red >> 3) & 31u)
    );
}


static volatile srk_u16 *srk_saturn_vdp1_command(unsigned int index)
{
    return SRK_VDP1_VRAM + (index * SRK_VDP1_COMMAND_WORDS);
}


static void srk_saturn_vdp1_clear_command(volatile srk_u16 *command)
{
    int i;
    for(i=0; i<SRK_VDP1_COMMAND_WORDS; i++)
        command[i] = 0;
}


static void srk_saturn_vdp1_write_polygon(
    volatile srk_u16 *polygon,
    const SRK_DIAG_VDP1_QUAD *quad
)
{
    srk_saturn_vdp1_clear_command(polygon);
    polygon[SRK_VDP1_CMDCTRL] = 0x0004;
    polygon[SRK_VDP1_CMDLINK] = 0x0000;
    polygon[SRK_VDP1_CMDPMOD] = 0x00C0;
    polygon[SRK_VDP1_CMDCOLR] = srk_saturn_vdp1_rgb(
        quad->red,
        quad->green,
        quad->blue
    );
    polygon[SRK_VDP1_CMDXA] = (srk_u16)quad->vertex[0].x;
    polygon[SRK_VDP1_CMDYA] = (srk_u16)quad->vertex[0].y;
    polygon[SRK_VDP1_CMDXB] = (srk_u16)quad->vertex[1].x;
    polygon[SRK_VDP1_CMDYB] = (srk_u16)quad->vertex[1].y;
    polygon[SRK_VDP1_CMDXC] = (srk_u16)quad->vertex[2].x;
    polygon[SRK_VDP1_CMDYC] = (srk_u16)quad->vertex[2].y;
    polygon[SRK_VDP1_CMDXD] = (srk_u16)quad->vertex[3].x;
    polygon[SRK_VDP1_CMDYD] = (srk_u16)quad->vertex[3].y;
}


static int srk_saturn_present_vdp1_scene(
    void *context,
    const SRK_DIAG_VDP1_SCENE *scene
)
{
    volatile srk_u16 *skip;
    volatile srk_u16 *clip;
    volatile srk_u16 *polygon;
    volatile srk_u16 *end;
    unsigned int i;

    (void)context;
    if(!scene || scene->count > SRK_DIAG_VDP1_MAX_QUADS)
        return 0;

    /* Disable the automatic trigger while replacing this frame's bounded list. */
    SRK_VDP1_PTMR = 0x0000;

    for(i=0; i<SRK_DIAG_VDP1_MAX_QUADS + 3u; i++)
        srk_saturn_vdp1_clear_command(srk_saturn_vdp1_command(i));

    skip = srk_saturn_vdp1_command(0);
    clip = srk_saturn_vdp1_command(1);

    /* Match the reviewed vdp1ex list guard: skip slot zero, then process slot one. */
    skip[SRK_VDP1_CMDCTRL] = 0x4000;

    /* Sega VDP1 manual: system clipping must be initialized before drawing. */
    clip[SRK_VDP1_CMDCTRL] = 0x0009;
    clip[SRK_VDP1_CMDLINK] = 0x0000;
    clip[SRK_VDP1_CMDXC] = (srk_u16)(SRK_VISIBLE_WIDTH - 1);
    clip[SRK_VDP1_CMDYC] = (srk_u16)(SRK_VISIBLE_HEIGHT - 1);

    for(i=0; i<scene->count; i++){
        polygon = srk_saturn_vdp1_command(2u + i);
        srk_saturn_vdp1_write_polygon(polygon, &scene->quad[i]);
    }

    /* Sega VDP1 manual: CMDCTRL=0x8000 is the drawing-end command. */
    end = srk_saturn_vdp1_command(2u + scene->count);
    end[SRK_VDP1_CMDCTRL] = 0x8000;

    /* RGB sprite data uses sprite register zero; non-zero priority makes it visible. */
    SRK_SPCTL = 0x0020;
    SRK_PRISA = 0x0001;

    SRK_VDP1_TVMR = 0x0000;
    SRK_VDP1_FBCR = 0x0000;
    SRK_VDP1_EWDR = 0x0000;
    SRK_VDP1_EWLR = 0x0000;
    SRK_VDP1_EWRR = 0x50DF;

    /* PTM=10B: automatically start drawing at frame-buffer switching. */
    SRK_VDP1_PTMR = 0x0002;
    return 1;
}


static int srk_saturn_present_vdp1_quad(
    void *context,
    const SRK_DIAG_VDP1_QUAD *quad
)
{
    SRK_DIAG_VDP1_SCENE scene;

    if(!quad)
        return 0;

    scene.quad[0] = *quad;
    scene.count = 1;
    return srk_saturn_present_vdp1_scene(context, &scene);
}


static void srk_saturn_hide_vdp1(void *context)
{
    volatile srk_u16 *first;
    unsigned int i;
    (void)context;

    SRK_PRISA = 0x0000;
    SRK_VDP1_PTMR = 0x0000;
    for(i=0; i<SRK_DIAG_VDP1_MAX_QUADS + 3u; i++)
        srk_saturn_vdp1_clear_command(srk_saturn_vdp1_command(i));
    first = srk_saturn_vdp1_command(0);
    first[SRK_VDP1_CMDCTRL] = 0x8000;
}


static int srk_saturn_read_vdp1_status(
    void *context,
    SRK_DIAG_VDP1_STATUS *status
)
{
    (void)context;
    if(!status)
        return 0;

    status->edsr = SRK_VDP1_EDSR;
    status->lopr = SRK_VDP1_LOPR;
    status->copr = SRK_VDP1_COPR;
    status->modr = SRK_VDP1_MODR;
    return 1;
}


static void srk_saturn_end_frame(void *context)
{
    SRK_SATURN_HOST_STATE *state;
    state = (SRK_SATURN_HOST_STATE *)context;
    if(state)
        state->now_us += state->frame_period_us;
}


static srk_u32 srk_saturn_read_vbr(void *context)
{
    srk_u32 value;
    (void)context;
    __asm__ volatile ("stc vbr,%0" : "=r" (value));
    return value;
}


static srk_u16 srk_saturn_rgb555(unsigned int red, unsigned int green, unsigned int blue)
{
    return (srk_u16)((red & 31u) | ((green & 31u) << 5) | ((blue & 31u) << 10));
}


static void srk_saturn_video_init(void)
{
    unsigned long i;
    unsigned int level;
    unsigned int gray;

    SRK_TVMD = 0x0000;
    SRK_RAMCTL = (srk_u16)(SRK_RAMCTL & (srk_u16)~0x3000u);
    SRK_MPOFN = 0x0000;
    SRK_CHCTLA = 0x001A;
    SRK_SCXIN0 = 0x0000;
    SRK_SCXDN0 = 0x0000;
    SRK_SCYIN0 = 0x0000;
    SRK_BGON = 0x0001;

    for(i=0; i<0x80000ul; i++)
        SRK_VDP2_VRAM[i] = 0;
    for(i=0; i<0x1000ul; i++)
        ((volatile srk_u8 *)SRK_VDP2_CRAM)[i] = 0;

    SRK_VDP2_CRAM[SRK_COLOR_BLACK] = srk_saturn_rgb555(0, 0, 0);
    SRK_VDP2_CRAM[SRK_COLOR_RED] = srk_saturn_rgb555(31, 0, 0);
    SRK_VDP2_CRAM[SRK_COLOR_GREEN] = srk_saturn_rgb555(0, 31, 0);
    SRK_VDP2_CRAM[SRK_COLOR_BLUE] = srk_saturn_rgb555(0, 0, 31);
    SRK_VDP2_CRAM[SRK_COLOR_YELLOW] = srk_saturn_rgb555(31, 31, 0);
    SRK_VDP2_CRAM[SRK_COLOR_CYAN] = srk_saturn_rgb555(0, 31, 31);
    SRK_VDP2_CRAM[SRK_COLOR_MAGENTA] = srk_saturn_rgb555(31, 0, 31);
    SRK_VDP2_CRAM[SRK_COLOR_GRAY] = srk_saturn_rgb555(16, 16, 16);
    SRK_VDP2_CRAM[SRK_COLOR_WHITE] = srk_saturn_rgb555(31, 31, 31);

    for(level=0; level<SRK_GRAY_COUNT; level++){
        gray = (level * 31u) / (SRK_GRAY_COUNT - 1u);
        SRK_VDP2_CRAM[SRK_GRAY_BASE + level] = srk_saturn_rgb555(gray, gray, gray);
    }

    SRK_TVMD = 0x8000;
}


static void srk_saturn_pad_init(void)
{
    SRK_DDR1 = 0x60;
    SRK_DDR2 = 0x60;
    SRK_IOSEL = 0x03;
    SRK_EXLE = 0x00;
    (void)SRK_PDR2;
}


void srk_saturn_host_init(
    SRK_DIAG_HOST *host,
    SRK_SATURN_HOST_STATE *state
)
{
    if(!host || !state)
        return;

    srk_saturn_video_init();
    srk_saturn_pad_init();
    srk_saturn_hide_vdp1(state);

    state->now_us = 0;
    /* VDP2 TVSTAT bit 0 identifies PAL timing; input is sampled once/frame. */
    state->frame_period_us = (SRK_TVSTAT & 0x0001u) ? 20000u : 16667u;

    host->context = state;
    host->time_us = srk_saturn_time_us;
    host->poll_pad = srk_saturn_poll_pad;
    host->begin_frame = srk_saturn_begin_frame;
    host->clear = srk_saturn_clear;
    host->draw_text = srk_saturn_draw_text;
    host->draw_video_pattern = srk_saturn_draw_video_pattern;
    host->present_vdp1_quad = srk_saturn_present_vdp1_quad;
    host->present_vdp1_scene = srk_saturn_present_vdp1_scene;
    host->hide_vdp1 = srk_saturn_hide_vdp1;
    host->read_vdp1_status = srk_saturn_read_vdp1_status;
    host->end_frame = srk_saturn_end_frame;
    host->read_vbr = srk_saturn_read_vbr;
}
