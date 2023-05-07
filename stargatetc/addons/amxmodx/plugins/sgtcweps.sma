#include <amxmodx>
#include <fakemeta>
#include <hamsandwich>
#include < amxmisc >
#include <engine>

#define PLUGIN "SGTC BOTS GIVE WEAPONS"
#define VERSION "1.0"
#define AUTHOR "Freeman"

public plugin_init()
{
	register_plugin(PLUGIN,VERSION,AUTHOR)
	RegisterHam(Ham_Spawn, "player", "player_spawn", 1)
}

public player_spawn(id) 
{	

	new theWeapon[90] = "";



			new iChance = random_num(0, 6);
			if (iChance == 0)
			{
			  theWeapon = "weapon_m16";
			}
			else if (iChance == 1)
			{
			   theWeapon = "weapon_mp5";
			}
			else if (iChance == 2)
			{
			   theWeapon = "weapon_zat";
			}
			else if (iChance == 3)
			{
			   theWeapon = "weapon_psg1";
			}
			else
			{
			   theWeapon = "weapon_p90";
			}



	//server_print(theWeapon);

	new Float:flPlayerOrigin[ 3 ];
	pev( id, pev_origin, flPlayerOrigin );
	new iEntity = create_entity( theWeapon );
	
	if( !pev_valid( iEntity ) )
	{
		return PLUGIN_HANDLED;
	}

	set_pev( iEntity, pev_classname, theWeapon );
	set_pev( iEntity, pev_origin, flPlayerOrigin );
	DispatchKeyValue(iEntity, "classname", theWeapon);
	DispatchSpawn(iEntity);

{
		     iChance = random_num(0, 6);
			if (iChance == 0)
			{
			   theWeapon = "weapon_zat";
			}
			else if (iChance == 1)
			{
			   theWeapon = "weapon_lance";
			}
			else if (iChance == 2)
			{
			   theWeapon = "weapon_zatarc";
			}
			else if (iChance == 3)
			{
			   theWeapon = "weapon_reetou";
			}
			else
			{
			   theWeapon = "weapon_lance";
			}		
		

	//server_print(theWeapon);

	new Float:flPlayerOrigin[ 3 ];
	pev( id, pev_origin, flPlayerOrigin );
	new iEntity = create_entity( theWeapon );
	
	if( !pev_valid( iEntity ) )
	{
		return PLUGIN_HANDLED;
	}

	set_pev( iEntity, pev_classname, theWeapon );
	set_pev( iEntity, pev_origin, flPlayerOrigin );
	DispatchKeyValue(iEntity, "classname", theWeapon);
	DispatchSpawn(iEntity);
}
}
