
import json
import importlib
import os
from SQLconnector import connectToSource
from SQLHelper import getTop5PlayersRoster
from FetchIndividual import fetchIndividualWithID
import ConfigHelper as cfg
from DBG import DBG


def buildPlayerBlob (startDate,endDate,targetID):
	cachedconfig = cfg.getConfig()
	infoQuery = """
		with PlayersInGame as (
		SELECT 
		Count (Players.GamerTag) as playersInGame, 
		Games.GameUUID as gameID
		FROM Games
		join Participation on participation.GameUUID = Games.GameUUID
		join Players on Participation.PlayerID = Players.PlayerID
		where GameTimestamp >= %s
		and GameTimeStamp < %s 
		and Games.ArenaName = %s
		group by Games.GameUUID ),
	averageOpponents as 
	(
		select avg(cast(playersInGame as float)) as AverageOpponents,  players.PlayerID from Participation 
		join PlayersInGame on Participation.GameUUID = PlayersInGame.gameID
		join Games on Games.GameUUID = PlayersInGame.gameID
		join Players on Participation.PlayerID = players.PlayerID
		group by  players.PlayerID

	),
	totalGamesPlayed as 
	(
		select count(*) as gamesPlayed,  Participation.PlayerID
		from Participation 
		join Games on Games.GameUUID = Participation.GameUUID
		where GameTimestamp >= %s
		and GameTimeStamp < %s 
		and ArenaName = %s
		group by Participation.PlayerID
	),
	Ranks as 
	(
		select GameTimestamp, GameName, Players.PlayerID, GamerTag, Score, 
			ROW_NUMBER() over (partition by GameTimestamp order by score desc) as gamePosition
		from Games 
		join Participation on Games.GameUUID = Participation.GameUUID
		join Players on Participation.PlayerID = Players.PlayerID
		where GameTimestamp >= %s
		and GameTimeStamp < %s
		and ArenaName = %s
	),
	AverageRanks as 
	( select PlayerID, AVG(cast(gamePosition AS FLOAT)) as AverageRank from Ranks
		group by PlayerID),

	totalAchievements as  (
	select  sum ( case when achievedDate is null then 0 when achievedDate is not null then 1 end) as AchievementsCompleted, PlayerID 
	from PlayerAchievement pa join AllAchievements aa on pa.AchID = aa.AchID
	where aa.ArenaName = %s or aa.ArenaName = 'Global Achievements'
	group by PlayerID 
	)



	select Players.PlayerID, GamerTag,players.Level, Missions, round(cast(AverageOpponents as numeric),2) as AverageOpponents, gamesPlayed
	, round(cast(AverageRank as numeric),2) as AverageRank
	, round(cast((AverageOpponents *  1/(AverageRank/AverageOpponents)) as numeric),2) as AvgQualityPerGame
	, round(cast((AverageOpponents * gamesPlayed * 1/(AverageRank/AverageOpponents)) as numeric),2) as TotalQualityScore
	, totalAchievements.AchievementsCompleted
	, totalAchievements.PlayerID as TaPID
	, ph.arenaName
    , pas.locallevel
    , arl.rankName
    from Players 
	join totalGamesPlayed on totalGamesPlayed.PlayerID = Players.PlayerID
	join averageOpponents on averageOpponents.PlayerID = Players.PlayerID
	join AverageRanks on AverageRanks.PlayerID = Players.PlayerID
	join totalAchievements on totalAchievements.PlayerID = Players.PlayerID
    join public."playerHomes" ph 
     on Players.PlayerID = ph.PlayerID 
     and ph.month = %s 
     and ph.arenarow = 1
    join PlayerArenaSummary pas on pas.playerID = ph.PlayerID and pas.ArenaName = ph.ArenaName
	join ArenaRanksLookup arl on arl.ArenaName = pas.ArenaName and arl.ranknumber = pas.localLevel
    
	where Players.playerID = %s 
	"""
	  

	goldenGameQuery = """

with PlayersInGame as (
	SELECT 
	Count (Players.GamerTag) as playersInGame, 
	Games.GameUUID as gameID
	FROM Games
	join Participation on participation.GameUUID = Games.GameUUID
	join Players on Participation.PlayerID = Players.PlayerID
	where games.ArenaName = %s
	group by Games.GameUUID 
),
Ranks as 
(
	select GameTimestamp, GameName, Players.PlayerID, GamerTag, Score, Games.GameUUID, 
		ROW_NUMBER() over (partition by GameTimestamp order by score desc) as gamePosition
	from Games 
	join Participation on Games.GameUUID = Participation.GameUUID
	join Players on Participation.PlayerID = Players.PlayerID
	where games.ArenaName = %s 
),
GoldenGame as (


	select  r.Score, r.GamerTag,r.GameUUID, GameName, r.PlayerID, gamePosition, playersInGame, GameTimestamp
	,round((playersInGame *  (playersInGame/gamePosition)),2) as StarQuality
	from Ranks r join PlayersInGame pig on r.GameUUID = pig.gameID
	where PlayerID = %s
	and GameTimestamp >= %s 
	and GameTimeStamp < %s
	order by StarQuality desc, score desc 
	limit 1
),
Vanquished as (
	select g.PlayerID, g.GameTimestamp, g.gamePosition victoryPos,  g.GamerTag victorName, g.Score victorScore, g.GameName, g.StarQuality victorStarQuality, r.PlayerID vanquishedID, r.GamerTag vanquishedName ,r.gamePosition as vanquishedPos  from 
	Ranks r inner join GoldenGame g on r.gameUUID = g.GameUUID
	where g.PlayerID != r.PlayerID
	and g.gamePosition < r.gamePosition
)
select * from Vanquished"""

	goldenAchievementQuery = """	with firstEarned as (
	select distinct min (achievedDate) over (partition by AchID) as firstAchieved, AchID
	from PlayerAchievement
	where achievedDate is not null

),
data as (
	select count(*) playersEarned,  pa.AchID, achName from PlayerAchievement pa join AllAchievements aa on pa.AchID = aa.AchID
	where achievedDate is not null
	group by AchName, pa.AchID
)
select PlayerID, data.AchName, Description, fe.firstAchieved, playersEarned from PlayerAchievement pa 
join data on data.AchID = pa.AchID
join firstEarned fe on fe.AchID = data.AchID
join AllAchievements aa on pa.AchID = aa.AchID
where PlayerID = %s and pa.achievedDate is not null
and ArenaName = %s
order by playersEarned asc, firstAchieved asc
limit 10
	"""
 
	conn = connectToSource()
	cursor = conn.cursor()
	DBG("BuildPlayerBlob.buildPlayerBlob start[%s], end[%s], target[%s], arena[%s]" % (cachedconfig["StartDate"],cachedconfig["EndDate"],targetID,cachedconfig["SiteNameReal"]),3)

	#startDate, endDate, arenaName, startDate, endDate, arenaName,  startDate, endDate, arenaName, arenaName, PlayerID
	
	endDate = cachedconfig["EndDate"]
	startDate = cachedconfig["StartDate"]
	targetArena = cachedconfig["SiteNameReal"]
	currentMonth = cachedconfig["StartDate"][:7]

	result = cursor.execute(infoQuery,(startDate, endDate, targetArena, startDate, endDate, targetArena,  startDate, endDate, targetArena, targetArena, currentMonth, targetID))

	row = cursor.fetchone()

	if row == None:
		DBG("BuildPlayerBlob info query returned Null. Aborting. [%s]" % (targetID),1)
		return
	#print(row)
	#print ("Players.PlayerID, GamerTag, round(AverageOpponents,2) as AverageOpponents, gamesPlayed,  AverageRank")
	SkillLevelName = ["Recruit","Gunner","Trooper","Captain","Star Lord","Laser Master","Level 7","Level 8","Laser Elite"]

	JSONobject = {}
	JSONobject["PlayerName"] = row[1]
	JSONobject["HomeArenaTrunc"] = row[11]
	JSONobject["SkillLevelName"] = row[13]
	JSONobject["MonthlyGamesPlayed"] = row[5]
	JSONobject["AllGamesPlayed"] = row[3]
	JSONobject["StarQuality"] = "%s" % row[7]
	JSONobject["Achievements"] = row[9]


	result = cursor.execute(goldenGameQuery,(targetArena,targetArena,targetID,startDate,endDate))
	rows = cursor.fetchall()
	if len(rows) > 0:
		row = rows[0]
		#print(row)
		#print ("g.PlayerID, g.GameTimestamp, victoryPos,   victorName,  victorScore, g.GameName, victorStarQuality,  vanquishedID, vanquishedName , vanquishedPos")
		ordinalranks = ["0th","1st","2nd","3rd","4th","5th","6th","7th","8th","9th","10th"]
		JSONobject["GGName"] = row[5]
		JSONobject["GGRank"] = ordinalranks[row[2]]
		JSONobject["GGStars"] = "%i stars" % row[6]
		JSONobject["GGVanq1"] = rows[0][8]
		if len(rows) >= 2:
			JSONobject["GGVanq2"] = rows[1][8]
		if len(rows) >= 3:
			JSONobject["GGVanq3"] = rows[2][8]
		if len(rows) >= 4:
			JSONobject["GGVanq4"] = '%i others' % (len(rows) - 3)

	result = cursor.execute(goldenAchievementQuery,(targetID,targetArena))
	row = cursor.fetchone()
	if row == None:
		DBG("BuildPlayerBlob GoldenAchievementQuery query returned Null. Aborting. [%s]" % (targetID),1)
		return
	#print (row)

	JSONobject["GAName"] = row[1]
	JSONobject["GADesc"] = row[2]

	ordinalOthers = ["No one else has","Only one other person has","Only two others have","%i others have" % row[4]]

	JSONobject["GAOthers"] = ordinalOthers[min(row[4]-1,3)]
	return JSONobject

	
 
	

def executeBuildPlayerBlobs():
	cachedconfig = cfg.getConfig()
	targetIDs = getTop5PlayersRoster(cachedconfig["StartDate"],cachedconfig["EndDate"],cachedconfig["SiteNameReal"])
	DBG("Big 5 players = %s" % (targetIDs,),1)

	#print ("Player profile blobs written!")
	JSONobject = {}
	if len(targetIDs) >= 1: 
		fetchIndividualWithID(targetIDs[0][0])
		JSONobject["GoldenPlayer"] = buildPlayerBlob(cachedconfig["StartDate"],cachedconfig["EndDate"],targetIDs[0][0])
	if len(targetIDs) >= 2:
		fetchIndividualWithID(targetIDs[1][0])
		JSONobject["SilverPlayer"] = buildPlayerBlob(cachedconfig["StartDate"],cachedconfig["EndDate"],targetIDs[1][0])
	if len(targetIDs) >= 3:
		fetchIndividualWithID(targetIDs[2][0])
		JSONobject["BronzePlayer"] = buildPlayerBlob(cachedconfig["StartDate"],cachedconfig["EndDate"],targetIDs[2][0])
	if len(targetIDs) >= 4:
		fetchIndividualWithID(targetIDs[3][0])
		JSONobject["OtherPlayer1"] = buildPlayerBlob(cachedconfig["StartDate"],cachedconfig["EndDate"],targetIDs[3][0])
	if len(targetIDs) >= 5:
		fetchIndividualWithID(targetIDs[4][0])
		JSONobject["OtherPlayer2"] = buildPlayerBlob(cachedconfig["StartDate"],cachedconfig["EndDate"],targetIDs[4][0])
	if len(targetIDs) < 5:
		DBGstring = "Big 5 returned %i: " % (len(targetIDs))
		for target in targetIDs:
			DBGstring = DBGstring + "[%i %s]," % (target[2],target[3])
		DBG(DBGstring,2)

	filepart = "playerBlob"
	if os.name == "nt":
		divider = "\\" 
	elif os.name == "posix":
		divider = "/"
	f = open("JSONBlobs%s%s%s.json" % (divider, cfg.getConfigString("ID Prefix"),filepart), "w+")
	f.write(json.dumps(JSONobject,indent=4))
	f.close()

 