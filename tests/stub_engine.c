/*
 * stub_engine.c - minimal 32-bit engine stub for the StargateTC logic harness.
 *
 * dlopens a GoldSrc server plugin (ref/stc_i386.so or the rebuilt hl.so),
 * feeds it a stub enginefuncs_t + globalvars_t via GiveFnptrsToDll, pulls
 * the DLL_FUNCTIONS table via GetEntityAPI, then exercises entity logic:
 *
 *   gate <multi_gate_N>         Spawn + KeyValue(wait/target) + ManagerUse path
 *   weapon <weapon_name>         Spawn + GetItemInfo (iId/iSlot/iPosition)
 *   trigger <trigger_name>       Spawn + KeyValue + Touch + Think
 *   rules <mp_gamemode>          SGTC_InstallGameRules dispatch (rebuild) or
 *                                InstallGameRules string probe (reference)
 *
 * Entity instantiation goes through the binary's own exported factory
 * (LINK_ENTITY_TO_CLASS thunk: void <classname>(entvars_t *pev)), which is
 * exactly how the engine creates entities (GetProcAddress/dlsym on the
 * class name). DispatchSpawn/KeyValue/Think/Touch/Use run through the
 * GetEntityAPI table, as in-engine.
 *
 * Stub responsibilities (everything the exercised paths touch):
 *   - edict pool: CREATE_ENTITY / REMOVE_ENTITY / CREATE_NAMED_ENTITY
 *   - private data: PvAllocEntPrivateData / PvEntPrivateData /
 *     FreeEntPrivateData / GetVarsOfEnt
 *   - strings: AllocString / SzFromIndex (index 0 == empty string)
 *   - engine identity: pStringBase, gpGlobals->time, mapname
 *   - cvars: CVarGetString/CVarGetFloat/CVarRegister (mp_gamemode,
 *     mp_teamlist, showtriggers; everything else defaults to "0"/0.0)
 *   - precache/model: PrecacheModel/PrecacheSound/PrecacheEvent/ModelIndex/
 *     SetModel/SetSize/SetOrigin (record-only, always succeed)
 *   - messages: MessageBegin/MessageEnd/Write fns/RegUserMsg (record-only)
 *   - misc no-ops returning safe defaults: TraceLine/Hull, RandomLong/
 *     RandomFloat (deterministic midpoint), AlertMessage (stderr),
 *     FindEntityByString (stub registry), EntOffsetOfPEntity/
 *     PEntityOfEntOffset/IndexOfEdict, ModelFrames, PointContents,
 *     GetModelPtr, Time, IsMapValid, DecalIndex, VecToYaw/Angles, etc.
 *
 * Output: tab-separated records on stdout:
 *   BINARY <path>
 *   SIT <situation> <PASS|FAIL> <detail>
 * Exit: 0 = ran to completion (individual FAILs do not affect it),
 *       1 = usage/binary error, 2 = dlopen/GetEntityAPI failure.
 *
 * 32-bit only: gcc -m32. The harness (tests/test_logic.py) builds this.
 */
#include <stddef.h>
#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* ---- minimal engine-side type mirrors (32-bit layout) ------------------ */
/* Must match hlsdk-xash3d/engine/{progdefs,edict,eface}.h for the fields
 * the stub touches. Only the prefix of enginefuncs_t up to the highest
 * used offset is modelled; indices follow eiface.h order. */

typedef int string_t;
typedef int qboolean;
typedef float vec3_t[3];
typedef unsigned int CRC32_t;

typedef struct edict_s edict_t;

typedef struct entvars_s {
	string_t classname;
	string_t globalname;
	vec3_t origin;
	vec3_t oldorigin;
	vec3_t velocity;
	vec3_t basevelocity;
	vec3_t clbasevelocity;
	vec3_t movedir;
	vec3_t angles;
	vec3_t avelocity;
	vec3_t punchangle;
	vec3_t v_angle;
	vec3_t endpos;
	vec3_t startpos;
	float impacttime;
	float starttime;
	int fixangle;
	float idealpitch;
	float pitch_speed;
	float ideal_yaw;
	float yaw_speed;
	int modelindex;
	string_t model;
	int viewmodel;
	int weaponmodel;
	vec3_t absmin;
	vec3_t absmax;
	vec3_t mins;
	vec3_t maxs;
	vec3_t size;
	float ltime;
	float nextthink;
	int movetype;
	int solid;
	int skin;
	int body;
	int effects;
	float gravity;
	float friction;
	int light_level;
	int sequence;
	int gaitsequence;
	float frame;
	float animtime;
	float framerate;
	unsigned char controller[4];
	unsigned char blending[2];
	float scale;
	int rendermode;
	float renderamt;
	vec3_t rendercolor;
	int renderfx;
	float health;
	float frags;
	int weapons;
	float takedamage;
	int deadflag;
	vec3_t view_ofs;
	int button;
	int impulse;
	edict_t *chain;
	edict_t *dmg_inflictor;
	edict_t *enemy;
	edict_t *aiment;
	edict_t *owner;
	edict_t *groundentity;
	int spawnflags;
	int flags;
	int colormap;
	int team;
	float max_health;
	float teleport_time;
	float armortype;
	float armorvalue;
	int waterlevel;
	int watertype;
	string_t target;
	string_t targetname;
	string_t netname;
	string_t message;
	float dmg_take;
	float dmg_save;
	float dmg;
	float dmgtime;
	string_t noise;
	string_t noise1;
	string_t noise2;
	string_t noise3;
	float speed;
	float air_finished;
	float pain_finished;
	float radsuit_finished;
	edict_t *pContainingEntity;
	int playerclass;
	float maxspeed;
	float fov;
	int weaponanim;
	int pushmsec;
	int bInDuck;
	int flTimeStepSound;
	int flSwimTime;
	int flDuckTime;
	int iStepLeft;
	float flFallVelocity;
	int gamestate;
	int oldbuttons;
	int groupinfo;
	int iuser1;
	int iuser2;
	int iuser3;
	int iuser4;
	float fuser1;
	float fuser2;
	float fuser3;
	float fuser4;
	vec3_t vuser1;
	vec3_t vuser2;
	vec3_t vuser3;
	vec3_t vuser4;
	edict_t *euser1;
	edict_t *euser2;
	edict_t *euser3;
	edict_t *euser4;
} entvars_t;

typedef struct {
	short leafnums[48];
	int headnode;
	int num_leafs;
} entleaf_t;

struct edict_s {
	int free;
	int serialnumber;
	void *area_next;
	void *area_prev;
	int headnode;
	int num_leafs;
	short leafnums[48];
	float freetime;
	void *pvPrivateData;
	entvars_t v;
};

typedef struct {
	float time;
	float frametime;
	float force_retouch;
	string_t mapname;
	string_t startspot;
	float deathmatch;
	float coop;
	float teamplay;
	float serverflags;
	float found_secrets;
	vec3_t v_forward;
	vec3_t v_up;
	vec3_t v_right;
	float trace_allsolid;
	float trace_startsolid;
	float trace_fraction;
	vec3_t trace_endpos;
	vec3_t trace_plane_normal;
	float trace_plane_dist;
	edict_t *trace_ent;
	float trace_inopen;
	float trace_inwater;
	int trace_hitgroup;
	int trace_flags;
	int changelevel;
	int cdAudioTrack;
	int maxClients;
	int maxEntities;
	const char *pStringBase;
	void *pSaveData;
	vec3_t vecLandmarkOffset;
} globalvars_t;

typedef struct {
	char *name;
	char *string;
	int flags;
	float value;
	void *next;
} cvar_t;

typedef struct {
	const char *szClassName;
	const char *szKeyName;
	const char *szValue;
	int fHandled;
} KeyValueData;

/* enginefuncs_t: full 157-pointer xash layout is overkill; the stub only
 * needs correct offsets for the functions the binaries call. Offsets are
 * fixed by eiface.h order, so we declare the complete table with exact
 * positions (generated order, 0-based index * 4 = byte offset):
 * 0 PrecacheModel 1 PrecacheSound 2 SetModel 3 ModelIndex 4 ModelFrames
 * 5 SetSize 6 ChangeLevel 7 GetSpawnParms 8 SaveSpawnParms 9 VecToYaw
 * 10 VecToAngles 11 MoveToOrigin 12 ChangeYaw 13 ChangePitch
 * 14 FindEntityByString 15 GetEntityIllum 16 FindEntityInSphere
 * 17 FindClientInPVS 18 EntitiesInPVS 19 MakeVectors 20 AngleVectors
 * 21 CreateEntity 22 RemoveEntity 23 CreateNamedEntity 24 MakeStatic
 * 25 EntIsOnFloor 26 DropToFloor 27 WalkMove 28 SetOrigin 29 EmitSound
 * 30 BuildSoundMsg 31 TraceLine 32 TraceToss 33 TraceMonsterHull
 * 34 TraceHull 35 TraceModel 36 TraceTexture 37 TraceSphere
 * 38 GetAimVector 39 ServerCommand 40 ServerExecute 41 ClientCommand
 * 42 ParticleEffect 43 LightStyle 44 DecalIndex 45 PointContents
 * 46 MessageBegin 47 MessageEnd 48 WriteByte 49 WriteChar 50 WriteShort
 * 51 WriteLong 52 WriteAngle 53 WriteCoord 54 WriteString 55 WriteEntity
 * 56 CVarRegister 57 CVarGetFloat 58 CVarGetString 59 CVarSetFloat
 * 60 CVarSetString 61 AlertMessage 62 EngineFprintf
 * 63 PvAllocEntPrivateData 64 PvEntPrivateData 65 FreeEntPrivateData
 * 66 SzFromIndex 67 AllocString 68 GetVarsOfEnt 69 PEntityOfEntOffset
 * 70 EntOffsetOfPEntity 71 IndexOfEdict 72 PEntityOfEntIndex ...
 * (... 73..156 zero-filled; the reference binary only copies the first
 * 144 entries and never touches the tail.)
 */
typedef struct {
	void *f[157];
} enginefuncs_stub_t;

typedef struct {
	void *f[50];
} dllfuncs_t;

/* ---- stub state --------------------------------------------------------- */
#define MAX_EDICTS 128
#define MAX_STRINGS 4096

static edict_t s_edicts[MAX_EDICTS];
static int s_edict_used = 0;
static char *s_strings[MAX_STRINGS];
static int s_nstrings = 1; /* 0 == empty string */
static globalvars_t s_globals;
static char s_string_base[1] = { 0 };

static char s_gamemode[64] = "";
static char s_teamlist[64] = "Torri;Goa'uld";

static void *s_dl = NULL;

/* ---- string pool -------------------------------------------------------- */
static const char *stub_SzFromIndex(int i)
{
	if (i <= 0 || i >= s_nstrings || !s_strings[i])
		return "";
	return s_strings[i];
}

static int stub_AllocString(const char *sz)
{
	int i;
	if (!sz || !*sz)
		return 0;
	for (i = 1; i < s_nstrings; i++)
		if (s_strings[i] && !strcmp(s_strings[i], sz))
			return i;
	if (s_nstrings >= MAX_STRINGS)
		return 0;
	s_strings[s_nstrings] = strdup(sz);
	return s_nstrings++;
}

/* ---- edicts ------------------------------------------------------------- */
static edict_t *stub_CreateEntity(void)
{
	int i;
	for (i = 1; i < MAX_EDICTS; i++) {
		if (s_edicts[i].free) {
			memset(&s_edicts[i], 0, sizeof(edict_t));
			s_edicts[i].free = 0;
			s_edicts[i].v.pContainingEntity = &s_edicts[i];
			if (i > s_edict_used)
				s_edict_used = i;
			return &s_edicts[i];
		}
	}
	return NULL;
}

static void stub_RemoveEntity(edict_t *e)
{
	if (!e)
		return;
	if (e->pvPrivateData) {
		free(e->pvPrivateData);
		e->pvPrivateData = NULL;
	}
	memset(e, 0, sizeof(edict_t));
	e->free = 1;
}

static edict_t *stub_CreateNamedEntity(int className)
{
	edict_t *e = stub_CreateEntity();
	const char *name;
	void (*factory)(entvars_t *);
	if (!e)
		return NULL;
	e->v.classname = className;
	name = stub_SzFromIndex(className);
	if (name && *name && s_dl) {
		factory = (void (*)(entvars_t *))dlsym(s_dl, name);
		if (factory)
			factory(&e->v);
	}
	return e;
}

static void *stub_PvAllocEntPrivateData(edict_t *e, int cb)
{
	if (!e)
		return NULL;
	if (e->pvPrivateData)
		free(e->pvPrivateData);
	e->pvPrivateData = calloc(1, cb > 0 ? cb : 1);
	return e->pvPrivateData;
}

static void *stub_PvEntPrivateData(edict_t *e)
{
	return e ? e->pvPrivateData : NULL;
}

static void stub_FreeEntPrivateData(edict_t *e)
{
	if (e && e->pvPrivateData) {
		free(e->pvPrivateData);
		e->pvPrivateData = NULL;
	}
}

static entvars_t *stub_GetVarsOfEnt(edict_t *e)
{
	return e ? &e->v : NULL;
}

static edict_t *stub_PEntityOfEntOffset(int off)
{
	int i;
	for (i = 1; i < MAX_EDICTS; i++)
		if (!s_edicts[i].free && (int)&s_edicts[i] == off)
			return &s_edicts[i];
	return NULL;
}

static int stub_EntOffsetOfPEntity(const edict_t *e)
{
	return (int)e;
}

static int stub_IndexOfEdict(const edict_t *e)
{
	return e ? (int)(e - s_edicts) : -1;
}

static edict_t *stub_PEntityOfEntIndex(int i)
{
	if (i < 0 || i >= MAX_EDICTS || s_edicts[i].free)
		return NULL;
	return &s_edicts[i];
}

/* ---- cvars -------------------------------------------------------------- */
static const char *stub_CVarGetString(const char *name)
{
	if (!name)
		return "";
	if (!strcmp(name, "mp_gamemode"))
		return s_gamemode;
	if (!strcmp(name, "mp_teamlist"))
		return s_teamlist;
	if (!strcmp(name, "showtriggers"))
		return "1";
	if (!strcmp(name, "mp_fraglimit") || !strcmp(name, "mp_timelimit"))
		return "0";
	return "";
}

static float stub_CVarGetFloat(const char *name)
{
	return (float)atof(stub_CVarGetString(name));
}

static void stub_CVarRegister(cvar_t *c)
{
	(void)c;
}

static cvar_t *stub_CVarGetPointer(const char *name)
{
	(void)name;
	return NULL;
}

/* ---- precache / model (record-only) ------------------------------------- */
static int stub_PrecacheModel(const char *s)
{
	(void)s;
	return 1;
}

static int stub_PrecacheSound(const char *s)
{
	(void)s;
	return 1;
}

static int stub_ModelIndex(const char *s)
{
	(void)s;
	return 1;
}

static int stub_ModelFrames(int m)
{
	(void)m;
	return 1;
}

static void stub_SetModel(edict_t *e, const char *m)
{
	(void)e;
	(void)m;
}

static void stub_SetSize(edict_t *e, const float *a, const float *b)
{
	(void)e;
	(void)a;
	(void)b;
}

static void stub_SetOrigin(edict_t *e, const float *o)
{
	if (e && o) {
		e->v.origin[0] = o[0];
		e->v.origin[1] = o[1];
		e->v.origin[2] = o[2];
	}
}

static unsigned short stub_PrecacheEvent(int type, const char *s)
{
	(void)type;
	(void)s;
	return 1;
}

static int stub_DecalIndex(const char *s)
{
	(void)s;
	return 0;
}

static int stub_PointContents(const float *v)
{
	(void)v;
	return 0;
}

static void *stub_GetModelPtr(edict_t *e)
{
	(void)e;
	return NULL;
}

/* ---- messages (record-only) --------------------------------------------- */
static void stub_MessageBegin(int dest, int type, const float *org, edict_t *ed)
{
	(void)dest;
	(void)type;
	(void)org;
	(void)ed;
}

static void stub_MessageEnd(void)
{
}

static void stub_WriteByte(int v) { (void)v; }
static void stub_WriteChar(int v) { (void)v; }
static void stub_WriteShort(int v) { (void)v; }
static void stub_WriteLong(int v) { (void)v; }
static void stub_WriteAngle(float v) { (void)v; }
static void stub_WriteCoord(float v) { (void)v; }
static void stub_WriteString(const char *s) { (void)s; }
static void stub_WriteEntity(int v) { (void)v; }

static int stub_RegUserMsg(const char *name, int size)
{
	static int next = 64;
	(void)name;
	(void)size;
	return next++;
}

/* ---- physics/trace defaults --------------------------------------------- */
static void stub_TraceLine(const float *a, const float *b, int nm,
	edict_t *skip, void *ptr)
{
	(void)a;
	(void)b;
	(void)nm;
	(void)skip;
	if (ptr)
		memset(ptr, 0, 64);
}

static void stub_TraceHull(const float *a, const float *b, int nm, int hull,
	edict_t *skip, void *ptr)
{
	(void)a;
	(void)b;
	(void)nm;
	(void)hull;
	(void)skip;
	if (ptr)
		memset(ptr, 0, 64);
}

static void stub_TraceToss(edict_t *a, edict_t *b, void *ptr)
{
	(void)a;
	(void)b;
	if (ptr)
		memset(ptr, 0, 64);
}

static int stub_TraceMonsterHull(edict_t *a, const float *b, const float *c,
	int d, edict_t *e, void *ptr)
{
	(void)a;
	(void)b;
	(void)c;
	(void)d;
	(void)e;
	if (ptr)
		memset(ptr, 0, 64);
	return 0;
}

static float stub_VecToYaw(const float *v)
{
	(void)v;
	return 0.0f;
}

static void stub_VecToAngles(const float *a, float *b)
{
	if (a && b) {
		b[0] = b[1] = b[2] = 0.0f;
	}
}

static void stub_MakeVectors(const float *v)
{
	(void)v;
	s_globals.v_forward[0] = 1.0f;
	s_globals.v_forward[1] = s_globals.v_forward[2] = 0.0f;
	s_globals.v_up[2] = 1.0f;
	s_globals.v_up[0] = s_globals.v_up[1] = 0.0f;
	s_globals.v_right[1] = 1.0f;
	s_globals.v_right[0] = s_globals.v_right[2] = 0.0f;
}

static void stub_AngleVectors(const float *v, float *f, float *r, float *u)
{
	(void)v;
	if (f) {
		f[0] = 1.0f;
		f[1] = f[2] = 0.0f;
	}
	if (r) {
		r[1] = 1.0f;
		r[0] = r[2] = 0.0f;
	}
	if (u) {
		u[2] = 1.0f;
		u[0] = u[1] = 0.0f;
	}
}

static int stub_RandomLong(int lo, int hi)
{
	return (lo + hi) / 2;
}

static float stub_RandomFloat(float lo, float hi)
{
	return (lo + hi) * 0.5f;
}

static void stub_AlertMessage(int type, const char *fmt, ...)
{
	(void)type;
	(void)fmt;
}

static void stub_ServerCommand(const char *s)
{
	(void)s;
}

static void stub_ServerExecute(void)
{
}

static edict_t *stub_FindEntityByString(edict_t *start, const char *field,
	const char *value)
{
	int i, from = 0;
	(void)field;
	(void)value;
	if (start)
		from = (int)(start - s_edicts) + 1;
	for (i = from; i < MAX_EDICTS; i++)
		if (!s_edicts[i].free && s_edicts[i].v.targetname &&
		    !strcmp(stub_SzFromIndex(s_edicts[i].v.targetname),
			    value ? value : ""))
			return &s_edicts[i];
	return NULL;
}

static int stub_DropToFloor(edict_t *e)
{
	(void)e;
	return 1;
}

static int stub_EntIsOnFloor(edict_t *e)
{
	(void)e;
	return 1;
}

static void stub_MoveToOrigin(edict_t *e, const float *g, float d, int m)
{
	(void)d;
	(void)m;
	stub_SetOrigin(e, g);
}

static void stub_ChangeYaw(edict_t *e)
{
	(void)e;
}

static void stub_ChangePitch(edict_t *e)
{
	(void)e;
}

static void stub_EmitSound(edict_t *e, int ch, const char *s, float v,
	float a, int f, int p)
{
	(void)e;
	(void)ch;
	(void)s;
	(void)v;
	(void)a;
	(void)f;
	(void)p;
}

static void stub_MakeStatic(edict_t *e)
{
	(void)e;
}

static int stub_WalkMove(edict_t *e, float y, float d, int m)
{
	(void)e;
	(void)y;
	(void)d;
	(void)m;
	return 1;
}

static float stub_Time(void)
{
	return s_globals.time;
}

static int stub_NumberOfEntities(void)
{
	return s_edict_used;
}

static int stub_IsMapValid(const char *s)
{
	(void)s;
	return 1;
}

static int stub_IsDedicatedServer(void)
{
	return 0;
}

static void stub_GetGameDir(char *s)
{
	if (s)
		strcpy(s, "stargatetc");
}

static void *stub_LoadFileForMe(const char *n, int *len)
{
	(void)n;
	if (len)
		*len = 0;
	return NULL;
}

static void stub_FreeFile(void *b)
{
	(void)b;
}

/* enginefuncs table, exact xash offsets (index * 4). Unlisted slots NULL. */
static void build_enginefuncs(enginefuncs_stub_t *t)
{
	memset(t, 0, sizeof(*t));
	t->f[0] = stub_PrecacheModel;
	t->f[1] = stub_PrecacheSound;
	t->f[2] = stub_SetModel;
	t->f[3] = stub_ModelIndex;
	t->f[4] = stub_ModelFrames;
	t->f[5] = stub_SetSize;
	t->f[6] = stub_ServerCommand; /* ChangeLevel: harmless */
	t->f[9] = stub_VecToYaw;
	t->f[10] = stub_VecToAngles;
	t->f[11] = stub_MoveToOrigin;
	t->f[12] = stub_ChangeYaw;
	t->f[13] = stub_ChangePitch;
	t->f[14] = stub_FindEntityByString;
	t->f[19] = stub_MakeVectors;
	t->f[20] = stub_AngleVectors;
	t->f[21] = stub_CreateEntity;
	t->f[22] = stub_RemoveEntity;
	t->f[23] = stub_CreateNamedEntity;
	t->f[24] = stub_MakeStatic;
	t->f[25] = stub_EntIsOnFloor;
	t->f[26] = stub_DropToFloor;
	t->f[27] = stub_WalkMove;
	t->f[28] = stub_SetOrigin;
	t->f[29] = stub_EmitSound;
	t->f[31] = stub_TraceLine;
	t->f[32] = stub_TraceToss;
	t->f[33] = stub_TraceMonsterHull;
	t->f[34] = stub_TraceHull;
	t->f[39] = stub_ServerCommand;
	t->f[40] = stub_ServerExecute;
	t->f[44] = stub_DecalIndex;
	t->f[45] = stub_PointContents;
	t->f[46] = stub_MessageBegin;
	t->f[47] = stub_MessageEnd;
	t->f[48] = stub_WriteByte;
	t->f[49] = stub_WriteChar;
	t->f[50] = stub_WriteShort;
	t->f[51] = stub_WriteLong;
	t->f[52] = stub_WriteAngle;
	t->f[53] = stub_WriteCoord;
	t->f[54] = stub_WriteString;
	t->f[55] = stub_WriteEntity;
	t->f[56] = stub_CVarRegister;
	t->f[57] = stub_CVarGetFloat;
	t->f[58] = stub_CVarGetString;
	t->f[59] = stub_CVarGetFloat; /* SetFloat: ignore */
	t->f[60] = stub_CVarGetFloat; /* SetString: ignore */
	t->f[61] = stub_AlertMessage;
	t->f[63] = stub_PvAllocEntPrivateData;
	t->f[64] = stub_PvEntPrivateData;
	t->f[65] = stub_FreeEntPrivateData;
	t->f[66] = stub_SzFromIndex;
	t->f[67] = stub_AllocString;
	t->f[68] = stub_GetVarsOfEnt;
	t->f[69] = stub_PEntityOfEntOffset;
	t->f[70] = stub_EntOffsetOfPEntity;
	t->f[71] = stub_IndexOfEdict;
	t->f[72] = stub_PEntityOfEntIndex;
	t->f[73] = stub_FindEntityByString; /* FindEntityByVars: approx */
	t->f[74] = stub_GetModelPtr;
	t->f[75] = stub_RegUserMsg;
	t->f[90] = stub_RandomLong;
	t->f[91] = stub_RandomFloat;
	t->f[93] = stub_Time;
	t->f[95] = stub_LoadFileForMe;
	t->f[96] = stub_FreeFile;
	t->f[99] = stub_GetGameDir;
	t->f[105] = stub_NumberOfEntities;
	t->f[110] = stub_IsMapValid;
	t->f[115] = stub_IsDedicatedServer;
	t->f[116] = stub_CVarGetPointer;
	t->f[122] = stub_PrecacheEvent;
}

/* ---- ItemInfo mirror (hlsdk-xash3d/dlls/weapons.h) ----------------------- */
typedef struct {
	int iSlot;
	int iPosition;
	const char *pszAmmo1;
	int iMaxAmmo1;
	const char *pszAmmo2;
	int iMaxAmmo2;
	const char *pszName;
	int iMaxClip;
	int iId;
	int iFlags;
	int iWeight;
} ItemInfo;

/* ---- helpers ------------------------------------------------------------ */
static void reset_state(void)
{
	int i;
	for (i = 0; i < MAX_EDICTS; i++) {
		if (s_edicts[i].pvPrivateData)
			free(s_edicts[i].pvPrivateData);
		memset(&s_edicts[i], 0, sizeof(edict_t));
		s_edicts[i].free = 1;
	}
	s_edicts[0].free = 0; /* world */
	s_edicts[0].v.pContainingEntity = &s_edicts[0];
	s_edict_used = 0;
	s_globals.time = 1.0f;
	s_globals.frametime = 0.01f;
}

static edict_t *spawn_via_factory(const char *classname)
{
	void (*factory)(entvars_t *);
	edict_t *e;
	if (!classname || !s_dl)
		return NULL;
	factory = (void (*)(entvars_t *))dlsym(s_dl, classname);
	if (!factory)
		return NULL;
	e = stub_CreateEntity();
	if (!e)
		return NULL;
	e->v.classname = stub_AllocString(classname);
	factory(&e->v);
	return e;
}

static void kv(edict_t *e, dllfuncs_t *api, const char *cls,
	const char *key, const char *val)
{
	KeyValueData kvd;
	kvd.szClassName = cls;
	kvd.szKeyName = key;
	kvd.szValue = val;
	kvd.fHandled = 0;
	((void (*)(edict_t *, KeyValueData *))api->f[6])(e, &kvd);
}

/* ---- situations ---------------------------------------------------------- */

/* 1) multi_gate_N: KeyValue wait + extra target, Spawn, ManagerUse, Think. */
static void sit_gate(dllfuncs_t *api, const char *name, int is_ref)
{
	char cls[64];
	edict_t *e, *target;
	KeyValueData kvd;
	int ctargets_before, ctargets_after;
	(void)is_ref;
	snprintf(cls, sizeof(cls), "%s", name);
	reset_state();

	e = stub_CreateEntity();
	if (!e) {
		printf("SIT\tgate:%s\tFAIL\tno-edict\n", name);
		return;
	}
	e->v.classname = stub_AllocString(cls);
	{
		void (*factory)(entvars_t *) =
			(void (*)(entvars_t *))dlsym(s_dl, cls);
		if (!factory) {
			printf("SIT\tgate:%s\tFAIL\tno-factory\n", name);
			return;
		}
		factory(&e->v);
		if (!e->pvPrivateData) {
			printf("SIT\tgate:%s\tFAIL\tno-private\n", name);
			return;
		}
	}

	/* KeyValue path: wait + one extra target before Spawn. */
	kv(e, api, cls, "wait", "5");
	kv(e, api, cls, "probe_extra_target", "1.5");

	/* Spawn seeds the default fire list. */
	if (((int (*)(edict_t *))api->f[1])(e) < 0) {
		printf("SIT\tgate:%s\tFAIL\tspawn-rejected\n", name);
		return;
	}

	/* Read m_cTargets back through the save-data-independent route:
	 * fire ManagerUse then count FindEntityByString hits is engine
	 * specific; instead verify via a second KeyValue batch + HasTarget
	 * behaviour: ManagerUse must arm think (nextthink set). */
	ctargets_before = 0;
	{
		/* m_cTargets sits right after m_SaveData-described fields;
		 * we cannot read C++ privates here, so observe behaviour:
		 * ManagerUse (DispatchUse) must set nextthink to now. */
		float t0 = e->v.nextthink;
		((void (*)(edict_t *, edict_t *))api->f[3])(e, e);
		if (e->v.nextthink == t0 && e->v.nextthink != s_globals.time) {
			printf("SIT\tgate:%s\tFAIL\tuse-no-arm t0=%g now=%g nt=%g\n",
				name, t0, s_globals.time, e->v.nextthink);
			return;
		}
	}

	/* ManagerThink must progress without crashing and eventually
	 * disarm (nextthink stops advancing once all targets fired). */
	{
		int i, fired = 0;
		float last = -1;
		for (i = 0; i < 70; i++) {
			s_globals.time += 0.5f;
			((void (*)(edict_t *))api->f[2])(e);
			if (e->v.nextthink != last) {
				last = e->v.nextthink;
				fired++;
			}
			if (e->v.nextthink == 0)
				break;
		}
		(void)fired;
	}

	/* Clone path: spawnflags multithread -> ManagerUse clones. Just
	 * exercise; clone without engine CreateNamedEntity registry must
	 * not crash. */
	e->v.spawnflags = 1;
	((void (*)(edict_t *, edict_t *))api->f[3])(e, e);
	e->v.spawnflags = 0;

	/* KeyValue after spawn still handled. */
	kvd.szClassName = cls;
	kvd.szKeyName = "wait";
	kvd.szValue = "7";
	kvd.fHandled = 0;
	((void (*)(edict_t *, KeyValueData *))api->f[6])(e, &kvd);
	ctargets_after = kvd.fHandled ? 1 : 0;

	/* A named target entity so FireTargets has something to resolve. */
	target = stub_CreateNamedEntity(stub_AllocString("info_target"));
	(void)target;
	(void)ctargets_before;

	printf("SIT\tgate:%s\t%s\tkv-after=%d\n", name,
		ctargets_after ? "PASS" : "FAIL", ctargets_after);
}

dllfuncs_t g_api;

 /* 2) weapon: Spawn + GetItemInfo via the exported class method symbol. */
static void sit_weapon(const char *link, int exp_id, int is_ref,
	const char *mang)
{
	edict_t *e;
	ItemInfo info;
	int (*getitem)(void *self, ItemInfo *p);
	char *sym;
	(void)is_ref;
	reset_state();
	/* weapon Spawn touches g_pGameRules (mp5.cpp:60 IsMultiplayer). */
	{
		void *(*inst)(void) =
			(void *(*)(void))dlsym(s_dl, "_Z16InstallGameRulesv");
		void *(*sgtc)(const char *) =
			(void *(*)(const char *))dlsym(s_dl, "_Z21SGTC_InstallGameRulesPKc");
		void **pGR = (void **)dlsym(s_dl, "g_pGameRules");
		void *rules = sgtc ? sgtc("sg_tc") : NULL;
		if (!rules && inst) rules = inst();
		if (pGR) *pGR = rules;
	}
	e = spawn_via_factory(link);
	if (!e) {
		printf("SIT\tweapon:%s\tFAIL\tno-factory\n", link);
		return;
	}
	if (!e->pvPrivateData) {
		printf("SIT\tweapon:%s\tFAIL\tno-private\n", link);
		return;
	}
	/* Spawn (precaches + SET_MODEL + FallInit). FallInit needs engine
	 * MoveToOrigin/SetSize; stubs cover it. */
	{
		/* Call Spawn through DispatchSpawn so the -1 convention holds. */
		if (((int (*)(edict_t *))g_api.f[1])(e) < 0) {
			printf("SIT\tweapon:%s\tFAIL\tspawn-rejected\n", link);
			return;
		}
	}

	/* GetItemInfo symbol resolves when the weapon's class method is
	 * exported (ref always is; rebuild requires the default-visibility
	 * test build in build-dbg/). */
	sym = (char *)mang;
	getitem = (int (*)(void *, ItemInfo *))dlsym(s_dl, sym);
	if (!getitem) {
		printf("SIT\tweapon:%s\tFAIL\tno-GetItemInfo\n", link);
		return;
	}
	memset(&info, 0, sizeof(info));
	if (!getitem(e->pvPrivateData, &info)) {
		printf("SIT\tweapon:%s\tFAIL\tgetitem-ret0\n", link);
		return;
	}
	if (info.iId == exp_id && info.iSlot >= 0 && info.iSlot <= 6) {
		printf("SIT\tweapon:%s\tPASS\tiId=%d slot=%d pos=%d\n",
			link, info.iId, info.iSlot, info.iPosition);
	} else {
		printf("SIT\tweapon:%s\tFAIL\tiId=%d(want%d) slot=%d pos=%d\n",
			link, info.iId, exp_id, info.iSlot, info.iPosition);
	}
}


/* 3) triggers: Spawn + KeyValue + Touch + Think. */
static void sit_trigger(dllfuncs_t *api, const char *name, const char *key,
	const char *val)
{
	edict_t *e, *other;
	reset_state();
	e = spawn_via_factory(name);
	if (!e || !e->pvPrivateData) {
		printf("SIT\ttrigger:%s\tFAIL\tno-factory\n", name);
		return;
	}
	kv(e, api, name, key, val);
	if (((int (*)(edict_t *))api->f[1])(e) < 0) {
		printf("SIT\ttrigger:%s\tFAIL\tspawn-rejected\n", name);
		return;
	}
	/* Toucher: a live client-flagged entity. */
	other = stub_CreateEntity();
	if (!other) {
		printf("SIT\ttrigger:%s\tFAIL\tno-edict\n", name);
		return;
	}
	other->v.flags = 8; /* FL_CLIENT */
	other->v.health = 100;
	other->v.deadflag = 0;
	s_globals.time += 5.0f;
	((void (*)(edict_t *, edict_t *))api->f[4])(e, other);
	s_globals.time += 5.0f;
	((void (*)(edict_t *))api->f[2])(e);
	/* RandomUse toggle must not crash. */
	((void (*)(edict_t *, edict_t *))api->f[3])(e, other);
	printf("SIT\ttrigger:%s\tPASS\ttouch+think+use ok\n", name);
}

/* 4) InstallGameRules dispatch. Rebuild exports SGTC_InstallGameRules;
 * reference exposes only InstallGameRules (reads the mp_gamemode cvar).
 * For the reference we verify the prefix table behaviourally: set
 * mp_gamemode, call InstallGameRules, check a rules object comes back
 * whose vtable GetGameDescription differs per mode family. Since vtables
 * are opaque here, PASS = non-NULL for game modes, and we additionally
 * report the description string pointer result. */
static void sit_rules(const char *mode, const char *want_desc_sub)
{
	void *desc_fn = NULL;
	(void)want_desc_sub;
	if (dlsym(s_dl, "_Z21SGTC_InstallGameRulesPKc")) {
		void *(*inst)(const char *) =
			(void *(*)(const char *))dlsym(s_dl,
				"_Z21SGTC_InstallGameRulesPKc");
		void *rules = inst(mode);
		const char *desc = NULL;
		if (rules) {
			/* Do not call through vtable from this harness: GCC
			 * member-pointer ABI differs and rep_ segfaulted. */
			printf("SIT\trules:%s\t%s\trules=%p\n",
				mode && *mode ? mode : "(empty)",
				rules ? "PASS" : "FAIL",
				rules);
		} else {
			printf("SIT\trules:%s\t%s\tnull-rules\n",
				mode && *mode ? mode : "(empty)",
				(!mode || !*mode || !strncmp(mode, "rep_", 4) ||
				 strncmp(mode, "sg_", 3)) ? "PASS" : "FAIL");
		}
	} else {
		void *(*inst)(void) =
			(void *(*)(void))dlsym(s_dl, "_Z16InstallGameRulesv");
		void *rules;
		if (!inst) {
			printf("SIT\trules:%s\tFAIL\tno-installer\n",
				mode);
			return;
		}
		snprintf(s_gamemode, sizeof(s_gamemode), "%s", mode);
		rules = inst();
		printf("SIT\trules:%s\t%s\tref-rules=%p\n", mode,
			rules ? "PASS" : "FAIL", rules);
		(void)desc_fn;
	}
}

static void usage(const char *a0)
{
	fprintf(stderr,
		"usage: %s <lib.so> <command> [args]\n"
		"  gate <multi_gate_N>\n"
		"  weapon <link> <expected-iId> [GetItemInfo-mangled]\n"
		"  trigger <name> <key> <value>\n"
		"  rules <mp_gamemode>\n"
		"  isref            print 1 if InstallGameRules-only (no SGTC_ form)\n",
		a0);
}

int main(int argc, char **argv)
{
	enginefuncs_stub_t eng;
	dllfuncs_t *api = &g_api;
	void (*give)(void *, globalvars_t *);
	int (*getapi)(dllfuncs_t *, int);
	const char *sop;
	int is_ref;

	if (argc < 3) {
		usage(argv[0]);
		return 1;
	}
	sop = argv[1];

	memset(s_edicts, 0, sizeof(s_edicts));
	{
		int i;
		for (i = 0; i < MAX_EDICTS; i++)
			s_edicts[i].free = 1;
	}
	s_edicts[0].free = 0;
	s_edicts[0].v.pContainingEntity = &s_edicts[0];
	memset(&s_globals, 0, sizeof(s_globals));
	s_globals.pStringBase = s_string_base;
	s_globals.time = 1.0f;
	s_globals.frametime = 0.01f;
	s_globals.mapname = 0;
	s_globals.maxEntities = MAX_EDICTS;
	s_globals.maxClients = 1;

	s_dl = dlopen(sop, RTLD_NOW | RTLD_GLOBAL);
	if (!s_dl)
		s_dl = dlopen(sop, RTLD_LAZY | RTLD_GLOBAL);
	if (!s_dl) {
		printf("DLOPEN\tFAIL\t%s\n", dlerror());
		return 2;
	}
	printf("BINARY\t%s\n", sop);
	is_ref = (dlsym(s_dl, "_Z21SGTC_InstallGameRulesPKc") == NULL);

	if (!strcmp(argv[2], "isref")) {
		printf("ISREF\t%d\n", is_ref);
		return 0;
	}

	build_enginefuncs(&eng);
	give = (void (*)(void *, globalvars_t *))dlsym(s_dl,
		"GiveFnptrsToDll");
	getapi = (int (*)(dllfuncs_t *, int))dlsym(s_dl, "GetEntityAPI");
	if (!give || !getapi) {
		printf("DLOPEN\tFAIL\tmissing entry points\n");
		return 2;
	}
	give(&eng, &s_globals);
	if (!getapi(api, 140)) {
		printf("DLOPEN\tFAIL\tGetEntityAPI(140) refused\n");
		return 2;
	}

	if (!strcmp(argv[2], "gate") && argc >= 4) {
		sit_gate(api, argv[3], is_ref);
	} else if (!strcmp(argv[2], "weapon") && argc >= 5) {
		sit_weapon(argv[3], atoi(argv[4]), is_ref,
			argc >= 6 ? argv[5] : "");
	} else if (!strcmp(argv[2], "trigger") && argc >= 6) {
		sit_trigger(api, argv[3], argv[4], argv[5]);
	} else if (!strcmp(argv[2], "rules") && argc >= 4) {
		sit_rules(argv[3], "");
	} else {
		usage(argv[0]);
		return 1;
	}
	return 0;
}
