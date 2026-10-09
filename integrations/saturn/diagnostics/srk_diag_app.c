#include "srk_diag_app.h"


static const char srk_diag_hex[] = "0123456789ABCDEF";

static const srk_u16 srk_diag_button_masks[SRK_DIAG_INPUT_BUTTON_COUNT] = {
    SRK_DIAG_BUTTON_UP,
    SRK_DIAG_BUTTON_DOWN,
    SRK_DIAG_BUTTON_LEFT,
    SRK_DIAG_BUTTON_RIGHT,
    SRK_DIAG_BUTTON_A,
    SRK_DIAG_BUTTON_B,
    SRK_DIAG_BUTTON_C,
    SRK_DIAG_BUTTON_X,
    SRK_DIAG_BUTTON_Y,
    SRK_DIAG_BUTTON_Z,
    SRK_DIAG_BUTTON_L,
    SRK_DIAG_BUTTON_R,
    SRK_DIAG_BUTTON_START
};

static const char *srk_diag_button_names[SRK_DIAG_INPUT_BUTTON_COUNT] = {
    "UP", "DOWN", "LEFT", "RIGHT", "A", "B", "C",
    "X", "Y", "Z", "L", "R", "START"
};

#define SRK_DIAG_INPUT_EXIT_MASK \
    (SRK_DIAG_BUTTON_L | SRK_DIAG_BUTTON_R | SRK_DIAG_BUTTON_START)


static void srk_diag_hex16(char out[7], srk_u16 value)
{
    out[0] = '0';
    out[1] = 'x';
    out[2] = srk_diag_hex[(value >> 12) & 0x0f];
    out[3] = srk_diag_hex[(value >> 8) & 0x0f];
    out[4] = srk_diag_hex[(value >> 4) & 0x0f];
    out[5] = srk_diag_hex[value & 0x0f];
    out[6] = '\0';
}


static void srk_diag_u32(char out[11], srk_u32 value)
{
    char reversed[10];
    int count;
    int i;

    if(value == 0){
        out[0] = '0';
        out[1] = '\0';
        return;
    }

    count = 0;
    while(value && count < 10){
        reversed[count++] = (char)('0' + (value % 10));
        value /= 10;
    }

    for(i=0; i<count; i++)
        out[i] = reversed[count - i - 1];
    out[count] = '\0';
}


static void srk_diag_draw(SRK_DIAG_HOST *host, int x, int y, const char *text)
{
    if(host->draw_text)
        host->draw_text(host->context, x, y, text);
}


static void srk_diag_draw_field(
    SRK_DIAG_HOST *host,
    int x,
    int y,
    int width,
    const char *text
)
{
    char field[41];
    int i;

    if(width < 1)
        return;
    if(width > 40)
        width = 40;

    for(i=0; i<width; i++)
        field[i] = ' ';
    field[width] = '\0';

    if(text){
        for(i=0; i<width && text[i]; i++)
            field[i] = text[i];
    }

    srk_diag_draw(host, x, y, field);
}


static void srk_diag_render_main(
    SRK_DIAG_APP *app,
    SRK_DIAG_HOST *host,
    int full_render
)
{
    int i;

    if(full_render){
        srk_diag_draw(host, 2, 1, "SRK SATURN DIAGNOSTICS");
        srk_diag_draw(host, 2, 2, "Standalone hardware validation shell");

        for(i=0; i<SRK_DIAG_MENU_ITEM_COUNT; i++)
            srk_diag_draw(host, 4, 4 + i, srk_diag_menu_label(i));

        srk_diag_draw(host, 2, 14, "UP/DOWN Navigate   A Select");
        srk_diag_draw(host, 2, 15, "Raw hardware values remain visible in tests.");
    }

    for(i=0; i<SRK_DIAG_MENU_ITEM_COUNT; i++)
        srk_diag_draw(host, 2, 4 + i, app->menu.selection == i ? ">" : " ");
}


static void srk_diag_render_input(
    SRK_DIAG_APP *app,
    SRK_DIAG_HOST *host,
    int full_render
)
{
    char raw[7];
    char current[7];
    char number[11];
    srk_u32 hold_ms;
    srk_u32 combo_ms;
    srk_u16 mask;
    const char *status;
    int i;

    if(full_render){
        srk_diag_draw(host, 2, 1, "CONTROLLER / INPUT TEST");
        srk_diag_draw(host, 2, 2, "Connected:");
        srk_diag_draw(host, 2, 3, "Raw:");
        srk_diag_draw(host, 17, 3, "Normalized:");

        for(i=0; i<SRK_DIAG_INPUT_BUTTON_COUNT; i++)
            srk_diag_draw(host, 2, 5 + i, srk_diag_button_names[i]);

        srk_diag_draw(host, 2, 19, "L+R combination:");
        srk_diag_draw(host, 2, 20, "Samples:");
        srk_diag_draw(host, 2, 21, "State changes:");
        srk_diag_draw(host, 2, 23, "L+R+START Return to diagnostics menu");
    }

    srk_diag_draw_field(host, 13, 2, 3, app->input.connected ? "YES" : "NO");

    srk_diag_hex16(raw, app->input.raw_state);
    srk_diag_hex16(current, app->input.current);
    srk_diag_draw_field(host, 8, 3, 6, raw);
    srk_diag_draw_field(host, 29, 3, 6, current);

    for(i=0; i<SRK_DIAG_INPUT_BUTTON_COUNT; i++){
        mask = srk_diag_button_masks[i];
        status = "-";
        if(app->input.pressed & mask)
            status = "PRESSED";
        else if(app->input.current & mask)
            status = "HELD";
        else if(app->input.released & mask)
            status = "RELEASED";

        srk_diag_draw_field(host, 10, 5 + i, 9, status);

        if((app->input.current | app->input.released) & mask){
            hold_ms = srk_diag_input_hold_us(&app->input, mask) / 1000u;
            srk_diag_u32(number, hold_ms);
            srk_diag_draw_field(host, 20, 5 + i, 10, number);
            srk_diag_draw_field(host, 31, 5 + i, 2, "ms");
        }else{
            srk_diag_draw_field(host, 20, 5 + i, 10, "");
            srk_diag_draw_field(host, 31, 5 + i, 2, "");
        }
    }

    if(srk_diag_input_is_down(&app->input, SRK_DIAG_INPUT_LR_MASK)){
        combo_ms = srk_diag_input_combination_hold_us(
            &app->input,
            SRK_DIAG_INPUT_LR_MASK
        ) / 1000u;
        srk_diag_u32(number, combo_ms);
        srk_diag_draw_field(host, 20, 19, 7, "ACTIVE");
        srk_diag_draw_field(host, 27, 19, 10, number);
        srk_diag_draw_field(host, 38, 19, 2, "ms");
    }else{
        srk_diag_draw_field(host, 20, 19, 7, "INACTIVE");
        srk_diag_draw_field(host, 27, 19, 10, "");
        srk_diag_draw_field(host, 38, 19, 2, "");
    }

    srk_diag_u32(number, app->input.sample_count);
    srk_diag_draw_field(host, 12, 20, 10, number);
    srk_diag_u32(number, app->input.state_change_count);
    srk_diag_draw_field(host, 17, 21, 10, number);
}


static void srk_diag_render_video(
    SRK_DIAG_APP *app,
    SRK_DIAG_HOST *host,
    int full_render
)
{
    if(!full_render)
        return;

    if(host->draw_video_pattern)
        host->draw_video_pattern(host->context, (unsigned int)app->video.pattern);

    srk_diag_draw(host, 1, 1, "VIDEO PATTERN TEST");
    srk_diag_draw(host, 1, 2, srk_diag_video_label(app->video.pattern));
    srk_diag_draw(host, 1, 25, "LEFT/RIGHT Change pattern");
    srk_diag_draw(host, 1, 26, "START Return to diagnostics menu");
}


static void srk_diag_render_vdp1(
    SRK_DIAG_APP *app,
    SRK_DIAG_HOST *host,
    int full_render
)
{
    SRK_DIAG_VDP1_STATUS status;
    char value[7];
    char number[11];
    int status_ok;
    int submitted;

    if(full_render){
        submitted = 0;
        if(host->present_vdp1_quad)
            submitted = host->present_vdp1_quad(host->context, &app->vdp1.quad);
        srk_diag_vdp1_mark_submitted(&app->vdp1, submitted);

        srk_diag_draw(host, 2, 1, "VDP1 / 3D TEST");
        srk_diag_draw(host, 2, 2, "Stage 1: static RGB quadrilateral");
        srk_diag_draw(host, 2, 4, "Host submit:");
        srk_diag_draw(host, 2, 5, "Submissions:");
        srk_diag_draw(host, 2, 7, "EDSR:");
        srk_diag_draw(host, 2, 8, "LOPR:");
        srk_diag_draw(host, 2, 9, "COPR:");
        srk_diag_draw(host, 2, 10, "MODR:");
        srk_diag_draw(host, 2, 24, "Primitive should appear near screen center.");
        srk_diag_draw(host, 2, 26, "START Return to diagnostics menu");
    }

    srk_diag_draw_field(host, 16, 4, 12, app->vdp1.submitted ? "OK" : "UNAVAILABLE");
    srk_diag_u32(number, app->vdp1.submit_count);
    srk_diag_draw_field(host, 16, 5, 10, number);

    status.edsr = 0;
    status.lopr = 0;
    status.copr = 0;
    status.modr = 0;
    status_ok = 0;
    if(host->read_vdp1_status)
        status_ok = host->read_vdp1_status(host->context, &status);

    if(status_ok){
        srk_diag_hex16(value, status.edsr);
        srk_diag_draw_field(host, 10, 7, 6, value);
        srk_diag_hex16(value, status.lopr);
        srk_diag_draw_field(host, 10, 8, 6, value);
        srk_diag_hex16(value, status.copr);
        srk_diag_draw_field(host, 10, 9, 6, value);
        srk_diag_hex16(value, status.modr);
        srk_diag_draw_field(host, 10, 10, 6, value);
    }else{
        srk_diag_draw_field(host, 10, 7, 12, "UNAVAILABLE");
        srk_diag_draw_field(host, 10, 8, 12, "UNAVAILABLE");
        srk_diag_draw_field(host, 10, 9, 12, "UNAVAILABLE");
        srk_diag_draw_field(host, 10, 10, 12, "UNAVAILABLE");
    }
}


static void srk_diag_render_flight(
    SRK_DIAG_APP *app,
    SRK_DIAG_HOST *host,
    int full_render
)
{
    char number[11];

    if(full_render){
        srk_diag_draw(host, 2, 1, "APPLICATION FLIGHT RECORDER");
        srk_diag_draw(host, 2, 3, "Rolling window: 30 seconds at up to 60 Hz");
        srk_diag_draw(host, 2, 4, "Frame record: 32 bytes");
        srk_diag_draw(host, 2, 6, "Status:");
        srk_diag_draw(host, 2, 7, "Records:");
        srk_diag_draw(host, 2, 10, "A Arm/reset rolling recorder");
        srk_diag_draw(host, 2, 11, "C Freeze current 30-second window");
        srk_diag_draw(host, 2, 13, "START Return to diagnostics menu");
        srk_diag_draw(host, 2, 15, "Export is intentionally deferred until storage is proven.");
    }

    if(app->recorder.frozen)
        srk_diag_draw_field(host, 12, 6, 18, "FROZEN");
    else if(app->recorder.armed)
        srk_diag_draw_field(host, 12, 6, 18, "ARMED / RECORDING");
    else
        srk_diag_draw_field(host, 12, 6, 18, "IDLE");

    srk_diag_u32(number, srk_diag_flight_count(&app->recorder));
    srk_diag_draw_field(host, 12, 7, 10, number);
}


static void srk_diag_render_placeholder(
    SRK_DIAG_APP *app,
    SRK_DIAG_HOST *host,
    int full_render
)
{
    if(!full_render)
        return;

    srk_diag_draw(host, 2, 1, srk_diag_menu_label((int)app->menu.active_screen));
    srk_diag_draw(host, 2, 3, "Diagnostic module not implemented in this core tranche.");
    srk_diag_draw(host, 2, 5, "START Return to diagnostics menu");
}


void srk_diag_app_reset(SRK_DIAG_APP *app)
{
    if(!app)
        return;

    srk_diag_menu_reset(&app->menu);
    srk_diag_input_reset(&app->input);
    srk_diag_flight_reset(&app->recorder);
    srk_diag_video_reset(&app->video);
    srk_diag_vdp1_reset(&app->vdp1);
    app->frame = 0;
    app->rendered_screen = 0xffffu;
    app->rendered_screen_valid = 0;
}


void srk_diag_app_frame(SRK_DIAG_APP *app, SRK_DIAG_HOST *host)
{
    SRK_DIAG_PAD_SAMPLE sample;
    SRK_DIAG_FLIGHT_RECORD record;
    srk_u32 now;
    srk_u32 vbr;
    srk_u16 diagnostic_id;
    srk_u16 render_screen;
    int full_render;
    int poll_ok;

    if(!app || !host)
        return;

    now = host->time_us ? host->time_us(host->context) : app->frame * 16667u;
    vbr = host->read_vbr ? host->read_vbr(host->context) : 0;

    sample.raw_state = 0;
    sample.buttons = 0;
    sample.connected = 0;
    poll_ok = 0;
    if(host->poll_pad)
        poll_ok = host->poll_pad(host->context, 0, &sample);
    if(!poll_ok){
        sample.raw_state = 0;
        sample.buttons = 0;
        sample.connected = 0;
    }

    srk_diag_input_update(&app->input, &sample, now);

    if(!app->menu.active){
        if(srk_diag_input_was_pressed(&app->input, SRK_DIAG_BUTTON_UP))
            srk_diag_menu_move(&app->menu, -1);
        if(srk_diag_input_was_pressed(&app->input, SRK_DIAG_BUTTON_DOWN))
            srk_diag_menu_move(&app->menu, 1);
        if(srk_diag_input_was_pressed(&app->input, SRK_DIAG_BUTTON_A))
            srk_diag_menu_enter(&app->menu);
    }else if(app->menu.active_screen == SRK_DIAG_SCREEN_INPUT_TEST){
        if((app->input.current & SRK_DIAG_INPUT_EXIT_MASK) == SRK_DIAG_INPUT_EXIT_MASK &&
           (app->input.pressed & SRK_DIAG_INPUT_EXIT_MASK) != 0){
            srk_diag_menu_back(&app->menu);
        }
    }else if(app->menu.active_screen == SRK_DIAG_SCREEN_VIDEO_PATTERN_TEST){
        if(srk_diag_input_was_pressed(&app->input, SRK_DIAG_BUTTON_START)){
            srk_diag_menu_back(&app->menu);
        }else{
            if(srk_diag_input_was_pressed(&app->input, SRK_DIAG_BUTTON_LEFT)){
                srk_diag_video_move(&app->video, -1);
                app->rendered_screen_valid = 0;
            }
            if(srk_diag_input_was_pressed(&app->input, SRK_DIAG_BUTTON_RIGHT)){
                srk_diag_video_move(&app->video, 1);
                app->rendered_screen_valid = 0;
            }
        }
    }else if(app->menu.active_screen == SRK_DIAG_SCREEN_VDP1_3D_TEST){
        if(srk_diag_input_was_pressed(&app->input, SRK_DIAG_BUTTON_START)){
            if(host->hide_vdp1)
                host->hide_vdp1(host->context);
            srk_diag_menu_back(&app->menu);
        }
    }else{
        if(srk_diag_input_was_pressed(&app->input, SRK_DIAG_BUTTON_START)){
            srk_diag_menu_back(&app->menu);
        }else if(app->menu.active_screen == SRK_DIAG_SCREEN_FLIGHT_RECORDER){
            if(srk_diag_input_was_pressed(&app->input, SRK_DIAG_BUTTON_A))
                srk_diag_flight_arm(&app->recorder);
            if(srk_diag_input_was_pressed(&app->input, SRK_DIAG_BUTTON_C))
                srk_diag_flight_freeze(&app->recorder);
        }
    }

    diagnostic_id = app->menu.active ? (srk_u16)app->menu.active_screen : 0xffffu;
    record.timestamp_us = now;
    record.frame = app->frame;
    record.raw_pad = app->input.raw_state;
    record.normalized_pad = app->input.current;
    record.pressed = app->input.pressed;
    record.released = app->input.released;
    record.held = app->input.current;
    record.diagnostic_id = diagnostic_id;
    record.vbr = vbr;
    record.value0 = srk_diag_input_combination_hold_us(
        &app->input,
        SRK_DIAG_INPUT_LR_MASK
    );
    record.value1 = app->input.state_change_count;
    srk_diag_flight_append(&app->recorder, &record);

    render_screen = app->menu.active ? (srk_u16)app->menu.active_screen : 0xffffu;
    full_render = !app->rendered_screen_valid || app->rendered_screen != render_screen;

    if(host->begin_frame)
        host->begin_frame(host->context);
    if(full_render && host->clear)
        host->clear(host->context);

    if(!app->menu.active)
        srk_diag_render_main(app, host, full_render);
    else if(app->menu.active_screen == SRK_DIAG_SCREEN_INPUT_TEST)
        srk_diag_render_input(app, host, full_render);
    else if(app->menu.active_screen == SRK_DIAG_SCREEN_VIDEO_PATTERN_TEST)
        srk_diag_render_video(app, host, full_render);
    else if(app->menu.active_screen == SRK_DIAG_SCREEN_VDP1_3D_TEST)
        srk_diag_render_vdp1(app, host, full_render);
    else if(app->menu.active_screen == SRK_DIAG_SCREEN_FLIGHT_RECORDER)
        srk_diag_render_flight(app, host, full_render);
    else
        srk_diag_render_placeholder(app, host, full_render);

    if(host->end_frame)
        host->end_frame(host->context);

    app->rendered_screen = render_screen;
    app->rendered_screen_valid = 1;
    app->frame += 1;
}
