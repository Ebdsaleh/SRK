#include "srk_saturn_host.h"
#include "vga_font.h"


#define SRK_PDR1   (*(volatile srk_u8 *)0x20100075)
#define SRK_PDR2   (*(volatile srk_u8 *)0x20100077)
#define SRK_DDR1   (*(volatile srk_u8 *)0x20100079)
#define SRK_DDR2   (*(volatile srk_u8 *)0x2010007B)
#define SRK_IOSEL  (*(volatile srk_u8 *)0x2010007D)
#define SRK_EXLE   (*(volatile srk_u8 *)0x2010007F)

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
    host->end_frame = srk_saturn_end_frame;
    host->read_vbr = srk_saturn_read_vbr;
}
