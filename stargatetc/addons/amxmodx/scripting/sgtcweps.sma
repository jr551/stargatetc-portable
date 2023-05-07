#include <amxmodx>
#include <fakemeta>
#include <hamsandwich>
#include <fun>
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
	if(is_user_alive(id) && is_user_bot(id) ) 
	{	
		if ( get_user_team(id) == 1 ) //tauri
		{
			new iChance = random_num(0, 6);
			if (iChance == 0)
			{
			   give_item(id, "weapon_m16")
			}
			else if (iChance == 1)
			{
			   give_item(id, "weapon_mp5")
			}
			else if (iChance == 2)
			{
			   give_item(id, "weapon_zat")
			}
			else if (iChance == 3)
			{
			   give_item(id, "weapon_psg1")
			}
			else
			{
			   give_item(id, "weapon_p90")
			}

		}
		else // goauld
		{
			new iChance = random_num(0, 6);
			if (iChance == 0)
			{
			   give_item(id, "weapon_zat")
			}
			else if (iChance == 1)
			{
			   give_item(id, "weapon_lance")
			}
			else if (iChance == 2)
			{
			   give_item(id, "weapon_zatarc")
			}
			else if (iChance == 3)
			{
			   give_item(id, "weapon_reetou")
			}
			else
			{
			   give_item(id, "weapon_lance")
			}		
		}
	}
}
/* AMXX-Studio Notes - DO NOT MODIFY BELOW HERE
*{\\ rtf1\\ ansi\\ deff0{\\ fonttbl{\\ f0\\ fnil Tahoma;}}\n\\ viewkind4\\ uc1\\ pard\\ lang2057\\ f0\\ fs16 \n\\ par }
*/
