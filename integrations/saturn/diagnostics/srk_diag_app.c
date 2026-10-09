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


static void srk_diag_hex32(char out[11], srk_u32 value)
{
    int shift;
    int i;

    out[0] = '0';
    out[1] = 'x';
    for(i=0; i<8; i++){
        shift = 28 - (i * 4);
        out[i + 2] = srk_diag_hex[(value >> shift) & 0x0f];
    }
    out[10] = '\0';
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


static void srk_diag_render_main(SRK_DIAG_APP *app, SRK_DIAG_HOST *host)
{
    int i;

    srk_diag_draw(host, 2, 1, "SRK SATURN DIAGNOSTICS");
    srk_diag_draw(host, 2, 2, "Standalone hardware validation shell");

    for(i=0; i<SRK_DIAG_MENU_ITEM_COUNT; i++){
        srk_diag_draw(host, 2, 4 + i, app->menu.selection == i ? ">" : " ");
        srk_diag_draw(host, 4, 4 + i, srk_diag_menu_label(i));
    }

    srk_diag_draw(host, 2, 14, "UP/DOWN Navigate   A Select");
    srk_diag_draw(host, 2, 15, "Raw hardware values remain visible in tests.");
}


static void srk_diag_render_input(SRK_DIAG_APP *app, SRK_DIAG_HOST *host)
{
    char raw[7];
    char current[7];
    char number[11];
    srk_u32 hold_ms;
    srk_u32 combo_ms;
    srk_u16 mask;
    const char *status;
    int i;

    srk_diag_draw(host, 2, 1, "CONTROLLER / INPUT TEST");
    srk_diag_draw(host, 2, 2, "Connected:");
    srk_diag_draw(host, 13, 2, app->input.connected ? "YES" : "NO");

    srk_diag_hex16(raw, app->input.raw_state);
    srk_diag_hex16(current, app->input.current);
    srk_diag_draw(host, 2, 3, "Raw:");
    srk_diag_draw(host, 8, 3, raw);
    srk_diag_draw(host, 17, 3, "Normalized:");
    srk_diag_draw(host, 29, 3, current);

    for(i=0; i<SRK_DIAG_INPUT_BUTTON_COUNT; i++){
        mask = srk_diag_button_masks[i];
        status = "-";
        if(app->input.pressed & mask)
            status = "PRESSED";
        else if(app->input.current & mask)
            status = "HELD";
        else if(app->input.released & mask)
            status = "RELEASED";

        srk_diag_draw(host, 2, 5 + i, srk_diag_button_names[i]);
        srk_diag_draw(host, 10, 5 + i, status);

        if((app->input.current | app->input.released) & mask){
            hold_ms = srk_diag_input_hold_us(&app->input, mask) / 1000u;
            srk_diag_u32(number, hold_ms);
            srk_diag_draw(host, 20, 5 + i, number);
            srk_diag_draw(host, 31, 5 + i, "ms");
        }
    }

    srk_diag_draw(host, 2, 19, "L+R combination:");
    if(srk_diag_input_is_down(&app->input, SRK_DIAG_INPUT_LR_MASK)){
        combo_ms = srk_diag_input_combination_hold_us(
            &app->input,
            SRK_DIAG_INPUT_LR_MASK
        ) / 1000u;
        srk_diag_u32(number, combo_ms);
        srk_diag_draw(host, 20, 19, "ACTIVE");
        srk_diag_draw(host, 27, 19, number);
        srk_diag_draw(host, 38, 19, "ms");
    }else{
        srk_diag_draw(host, 20, 19, "INACTIVE");
    }

    srk_diag_u32(number, app->input.sample_count);
    srk_diag_draw(host, 2, 20, "Samples:");
    srk_diag_draw(host, 12, 20, number);
    srk_diag_u32(number, app->input.state_change_count);
    srk_diag_draw(host, 2, 21, "State changes:");
    srk_diag_draw(host, 17, 21, number);

    srk_diag_draw(host, 2, 23, "START Return to diagnostics menu");
}


static void srk_diag_render_flight(SRK_DIAG_APP *app, SRK_DIAG_HOST *host)
{
    char number[11];

    srk_diag_draw(host, 2, 1, "APPLICATION FLIGHT RECORDER");
    srk_diag_draw(host, 2, 3, "Rolling window: 30 seconds at up to 60 Hz");
    srk_diag_draw(host, 2, 4, "Frame record: 32 bytes");

    srk_diag_draw(host, 2, 6, "Status:");
    if(app->recorder.frozen)
        srk_diag_draw(host, 12, 6, "FROZEN");
    else if(app->recorder.armed)
        srk_diag_draw(host, 12, 6, "ARMED / RECORDING");
    else
        srk_diag_draw(host, 12, 6, "IDLE");

    srk_diag_u32(number, srk_diag_flight_count(&app->recorder));
    srk_diag_draw(host, 2, 7, "Records:");
    srk_diag_draw(host, 12, 7, number);

    srk_diag_draw(host, 2, 10, "A Arm/reset rolling recorder");
    srk_diag_draw(host, 2, 11, "C Freeze current 30-second window");
    srk_diag_draw(host, 2, 13, "START Return to diagnostics menu");
    srk_diag_draw(host, 2, 15, "Export is intentionally deferred until storage is proven.");
}


static void srk_diag_render_placeholder(SRK_DIAG_APP *app, SRK_DIAG_HOST *host)
{
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
    app->frame = 0;
}


void srk_diag_app_frame(SRK_DIAG_APP *app, SRK_DIAG_HOST *host)
{
    SRK_DIAG_PAD_SAMPLE sample;
    SRK_DIAG_FLIGHT_RECORD record;
    srk_u32 now;
    srk_u32 vbr;
    srk_u16 diagnostic_id;
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

    if(host->begin_frame)
        host->begin_frame(host->context);
    if(host->clear)
        host->clear(host->context);

    if(!app->menu.active)
        srk_diag_render_main(app, host);
    else if(app->menu.active_screen == SRK_DIAG_SCREEN_INPUT_TEST)
        srk_diag_render_input(app, host);
    else if(app->menu.active_screen == SRK_DIAG_SCREEN_FLIGHT_RECORDER)
        srk_diag_render_flight(app, host);
    else
        srk_diag_render_placeholder(app, host);

    if(host->end_frame)
        host->end_frame(host->context);

    app->frame += 1;
}
