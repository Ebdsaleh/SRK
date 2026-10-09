#include "srk_diag_vdp1.h"


#define SRK_DIAG_VDP1_TRIG_SHIFT      14
#define SRK_DIAG_VDP1_CUBE_HALF       40
#define SRK_DIAG_VDP1_CAMERA_DISTANCE 320
#define SRK_DIAG_VDP1_FOCAL_LENGTH    180
#define SRK_DIAG_VDP1_SCREEN_CENTER_X 160
#define SRK_DIAG_VDP1_SCREEN_CENTER_Y 140


typedef struct SRK_DIAG_VDP1_VECTOR3 {
    srk_s16 x;
    srk_s16 y;
    srk_s16 z;
} SRK_DIAG_VDP1_VECTOR3;


typedef struct SRK_DIAG_VDP1_FACE_DEF {
    srk_u8 vertex[4];
    srk_u8 red;
    srk_u8 green;
    srk_u8 blue;
} SRK_DIAG_VDP1_FACE_DEF;


/*
 * Q14 quarter-wave sine values for angles 0..pi/2 inclusive. Full-circle
 * angles use 0..255 so all per-frame rotation stays deterministic on SH-2 and
 * requires no floating-point runtime support.
 */
static const srk_s16 srk_diag_vdp1_sine_quarter[65] = {
        0,   402,   804,  1205,  1606,  2006,  2404,  2801,
     3196,  3590,  3981,  4370,  4756,  5139,  5520,  5897,
     6270,  6639,  7005,  7366,  7723,  8076,  8423,  8765,
     9102,  9434,  9760, 10080, 10394, 10702, 11003, 11297,
    11585, 11866, 12140, 12406, 12665, 12916, 13160, 13395,
    13623, 13842, 14053, 14256, 14449, 14635, 14811, 14978,
    15137, 15286, 15426, 15557, 15679, 15791, 15893, 15986,
    16069, 16143, 16207, 16261, 16305, 16340, 16364, 16379,
    16384
};


static const SRK_DIAG_VDP1_VECTOR3 srk_diag_vdp1_cube_vertices[SRK_DIAG_VDP1_CUBE_VERTEX_COUNT] = {
    { -SRK_DIAG_VDP1_CUBE_HALF, -SRK_DIAG_VDP1_CUBE_HALF, -SRK_DIAG_VDP1_CUBE_HALF },
    {  SRK_DIAG_VDP1_CUBE_HALF, -SRK_DIAG_VDP1_CUBE_HALF, -SRK_DIAG_VDP1_CUBE_HALF },
    {  SRK_DIAG_VDP1_CUBE_HALF,  SRK_DIAG_VDP1_CUBE_HALF, -SRK_DIAG_VDP1_CUBE_HALF },
    { -SRK_DIAG_VDP1_CUBE_HALF,  SRK_DIAG_VDP1_CUBE_HALF, -SRK_DIAG_VDP1_CUBE_HALF },
    { -SRK_DIAG_VDP1_CUBE_HALF, -SRK_DIAG_VDP1_CUBE_HALF,  SRK_DIAG_VDP1_CUBE_HALF },
    {  SRK_DIAG_VDP1_CUBE_HALF, -SRK_DIAG_VDP1_CUBE_HALF,  SRK_DIAG_VDP1_CUBE_HALF },
    {  SRK_DIAG_VDP1_CUBE_HALF,  SRK_DIAG_VDP1_CUBE_HALF,  SRK_DIAG_VDP1_CUBE_HALF },
    { -SRK_DIAG_VDP1_CUBE_HALF,  SRK_DIAG_VDP1_CUBE_HALF,  SRK_DIAG_VDP1_CUBE_HALF }
};


/* All face windings point outwards in object space. */
static const SRK_DIAG_VDP1_FACE_DEF srk_diag_vdp1_cube_faces[SRK_DIAG_VDP1_CUBE_FACE_COUNT] = {
    { { 0, 3, 2, 1 }, 255,  64,  32 },
    { { 4, 5, 6, 7 },  32, 224, 224 },
    { { 0, 4, 7, 3 },  64, 224,  96 },
    { { 1, 2, 6, 5 },  64,  96, 255 },
    { { 0, 1, 5, 4 }, 240, 208,  48 },
    { { 3, 7, 6, 2 }, 224,  64, 224 }
};


static srk_s16 srk_diag_vdp1_sin8(srk_u16 angle)
{
    unsigned int phase;
    unsigned int quadrant;
    unsigned int offset;

    phase = (unsigned int)(angle & 0x00ffu);
    quadrant = phase >> 6;
    offset = phase & 0x3fu;

    switch(quadrant){
        case 0:
            return srk_diag_vdp1_sine_quarter[offset];
        case 1:
            return srk_diag_vdp1_sine_quarter[64u - offset];
        case 2:
            return (srk_s16)-srk_diag_vdp1_sine_quarter[offset];
        default:
            return (srk_s16)-srk_diag_vdp1_sine_quarter[64u - offset];
    }
}


static srk_s16 srk_diag_vdp1_cos8(srk_u16 angle)
{
    return srk_diag_vdp1_sin8((srk_u16)(angle + 64u));
}


static srk_s16 srk_diag_vdp1_q14_pair(
    srk_s16 a,
    srk_s16 b,
    srk_s16 c,
    srk_s16 d
)
{
    srk_s32 value;
    value = (srk_s32)a * (srk_s32)b + (srk_s32)c * (srk_s32)d;
    return (srk_s16)(value >> SRK_DIAG_VDP1_TRIG_SHIFT);
}


static SRK_DIAG_VDP1_VECTOR3 srk_diag_vdp1_rotate_vertex(
    const SRK_DIAG_VDP1_VECTOR3 *source,
    srk_s16 sin_x,
    srk_s16 cos_x,
    srk_s16 sin_y,
    srk_s16 cos_y,
    srk_s16 sin_z,
    srk_s16 cos_z
)
{
    SRK_DIAG_VDP1_VECTOR3 result;
    srk_s16 x1;
    srk_s16 y1;
    srk_s16 z1;
    srk_s16 x2;
    srk_s16 y2;
    srk_s16 z2;

    x1 = source->x;
    y1 = srk_diag_vdp1_q14_pair(source->y, cos_x, source->z, (srk_s16)-sin_x);
    z1 = srk_diag_vdp1_q14_pair(source->y, sin_x, source->z, cos_x);

    x2 = srk_diag_vdp1_q14_pair(x1, cos_y, z1, sin_y);
    y2 = y1;
    z2 = srk_diag_vdp1_q14_pair(x1, (srk_s16)-sin_y, z1, cos_y);

    result.x = srk_diag_vdp1_q14_pair(x2, cos_z, y2, (srk_s16)-sin_z);
    result.y = srk_diag_vdp1_q14_pair(x2, sin_z, y2, cos_z);
    result.z = z2;
    return result;
}


static SRK_DIAG_VDP1_POINT srk_diag_vdp1_project(
    const SRK_DIAG_VDP1_VECTOR3 *vertex
)
{
    SRK_DIAG_VDP1_POINT point;
    srk_s32 depth;
    srk_s32 projected;

    depth = (srk_s32)SRK_DIAG_VDP1_CAMERA_DISTANCE + (srk_s32)vertex->z;
    if(depth < 1)
        depth = 1;

    projected = ((srk_s32)vertex->x * SRK_DIAG_VDP1_FOCAL_LENGTH) / depth;
    point.x = (srk_s16)(SRK_DIAG_VDP1_SCREEN_CENTER_X + projected);

    projected = ((srk_s32)vertex->y * SRK_DIAG_VDP1_FOCAL_LENGTH) / depth;
    point.y = (srk_s16)(SRK_DIAG_VDP1_SCREEN_CENTER_Y - projected);
    return point;
}


static srk_s32 srk_diag_vdp1_face_normal_z(
    const SRK_DIAG_VDP1_VECTOR3 transformed[SRK_DIAG_VDP1_CUBE_VERTEX_COUNT],
    const SRK_DIAG_VDP1_FACE_DEF *face
)
{
    const SRK_DIAG_VDP1_VECTOR3 *a;
    const SRK_DIAG_VDP1_VECTOR3 *b;
    const SRK_DIAG_VDP1_VECTOR3 *c;
    srk_s32 ab_x;
    srk_s32 ab_y;
    srk_s32 ac_x;
    srk_s32 ac_y;

    a = &transformed[face->vertex[0]];
    b = &transformed[face->vertex[1]];
    c = &transformed[face->vertex[2]];

    ab_x = (srk_s32)b->x - (srk_s32)a->x;
    ab_y = (srk_s32)b->y - (srk_s32)a->y;
    ac_x = (srk_s32)c->x - (srk_s32)a->x;
    ac_y = (srk_s32)c->y - (srk_s32)a->y;
    return ab_x * ac_y - ab_y * ac_x;
}


static srk_s32 srk_diag_vdp1_face_depth(
    const SRK_DIAG_VDP1_VECTOR3 transformed[SRK_DIAG_VDP1_CUBE_VERTEX_COUNT],
    const SRK_DIAG_VDP1_FACE_DEF *face
)
{
    srk_s32 depth;
    int i;

    depth = 0;
    for(i=0; i<4; i++)
        depth += transformed[face->vertex[i]].z;
    return depth / 4;
}


static void srk_diag_vdp1_build_scene(SRK_DIAG_VDP1_STATE *state)
{
    SRK_DIAG_VDP1_VECTOR3 transformed[SRK_DIAG_VDP1_CUBE_VERTEX_COUNT];
    srk_s32 depth[SRK_DIAG_VDP1_CUBE_FACE_COUNT];
    srk_u8 face_index[SRK_DIAG_VDP1_CUBE_FACE_COUNT];
    const SRK_DIAG_VDP1_FACE_DEF *face;
    SRK_DIAG_VDP1_QUAD *quad;
    srk_s16 sin_x;
    srk_s16 cos_x;
    srk_s16 sin_y;
    srk_s16 cos_y;
    srk_s16 sin_z;
    srk_s16 cos_z;
    srk_s32 swap_depth;
    srk_u8 swap_index;
    unsigned int visible;
    int i;
    int j;

    sin_x = srk_diag_vdp1_sin8(state->angle_x);
    cos_x = srk_diag_vdp1_cos8(state->angle_x);
    sin_y = srk_diag_vdp1_sin8(state->angle_y);
    cos_y = srk_diag_vdp1_cos8(state->angle_y);
    sin_z = srk_diag_vdp1_sin8(state->angle_z);
    cos_z = srk_diag_vdp1_cos8(state->angle_z);

    for(i=0; i<SRK_DIAG_VDP1_CUBE_VERTEX_COUNT; i++){
        transformed[i] = srk_diag_vdp1_rotate_vertex(
            &srk_diag_vdp1_cube_vertices[i],
            sin_x,
            cos_x,
            sin_y,
            cos_y,
            sin_z,
            cos_z
        );
    }

    visible = 0;
    for(i=0; i<SRK_DIAG_VDP1_CUBE_FACE_COUNT; i++){
        face = &srk_diag_vdp1_cube_faces[i];
        if(srk_diag_vdp1_face_normal_z(transformed, face) < 0){
            face_index[visible] = (srk_u8)i;
            depth[visible] = srk_diag_vdp1_face_depth(transformed, face);
            visible++;
        }
    }

    /* Painter order: larger view-space Z is farther from the camera. */
    for(i=0; i<(int)visible; i++){
        for(j=i+1; j<(int)visible; j++){
            if(depth[j] > depth[i]){
                swap_depth = depth[i];
                depth[i] = depth[j];
                depth[j] = swap_depth;
                swap_index = face_index[i];
                face_index[i] = face_index[j];
                face_index[j] = swap_index;
            }
        }
    }

    state->scene.count = visible;
    state->visible_face_count = (srk_u16)visible;

    for(i=0; i<(int)visible; i++){
        face = &srk_diag_vdp1_cube_faces[face_index[i]];
        quad = &state->scene.quad[i];
        for(j=0; j<4; j++)
            quad->vertex[j] = srk_diag_vdp1_project(&transformed[face->vertex[j]]);
        quad->red = face->red;
        quad->green = face->green;
        quad->blue = face->blue;
    }
}


void srk_diag_vdp1_reset(SRK_DIAG_VDP1_STATE *state)
{
    if(!state)
        return;

    /* Keep the physically proven R7 primitive as an explicit recovery reference. */
    state->quad.vertex[0].x = 96;
    state->quad.vertex[0].y = 104;
    state->quad.vertex[1].x = 224;
    state->quad.vertex[1].y = 112;
    state->quad.vertex[2].x = 208;
    state->quad.vertex[2].y = 176;
    state->quad.vertex[3].x = 112;
    state->quad.vertex[3].y = 168;
    state->quad.red = 255;
    state->quad.green = 64;
    state->quad.blue = 32;

    state->angle_x = 16;
    state->angle_y = 24;
    state->angle_z = 8;
    state->visible_face_count = 0;
    state->animation_frame = 0;
    state->submit_count = 0;
    state->submitted = 0;
    srk_diag_vdp1_build_scene(state);
}


void srk_diag_vdp1_advance(SRK_DIAG_VDP1_STATE *state)
{
    if(!state)
        return;

    state->angle_x = (srk_u16)((state->angle_x + 1u) & 0x00ffu);
    state->angle_y = (srk_u16)((state->angle_y + 1u) & 0x00ffu);
    state->angle_z = (srk_u16)((state->angle_z + 1u) & 0x00ffu);
    state->animation_frame += 1;
    srk_diag_vdp1_build_scene(state);
}


void srk_diag_vdp1_mark_submitted(SRK_DIAG_VDP1_STATE *state, int submitted)
{
    if(!state)
        return;

    state->submitted = submitted ? 1 : 0;
    if(state->submitted)
        state->submit_count += 1;
}
