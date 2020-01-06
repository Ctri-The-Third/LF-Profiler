from psycopg2 import sql
from DBG import DBG
import uuid
import csv 
import json
from SQLconnector import connectToSource, closeConnection
import ConfigHelper as cfg 
import hashlib
import datetime

def getInterestingPlayersRoster(includeChurned,startDate,period,siteName = None, offset = 0):
 
    conn = connectToSource()
    cursor = conn.cursor()
    
    if includeChurned == True:
        query = """
        
        select  * from InterestingPlayers
        order by Missions desc, SeenIn60Days Asc
        OFFSET %s;
        """

        cursor.execute(query, (offset,))
    elif siteName is not None:
        query = sql.SQL("""
    	with MostRecentPerArena as 
	(select max(g.GameTimestamp) as mostRecent, p.playerID, missions, level
	from Games g join Participation p on g.GameUUID = p.GameUUID 
	join players pl on p.PlayerID = pl.playerID 
	group by p.PlayerID,Missions,level)

    select  Missions, Level, PlayerID, MostRecent from MostRecentPerArena
    where mostRecent >  to_date(%s,'YYYY-MM-DD') - INTERVAL '1 day' * %s
    order by Level desc, Missions desc, mostRecent Asc
    offset %s;

    """)
        cursor.execute(query,(startDate,period,offset))

    else:
        query = sql.SQL("""
    	with MostRecentPerArena as 
	(select max(g.GameTimestamp) as mostRecent, p.playerID, missions, level
	from Games g join Participation p on g.GameUUID = p.GameUUID 
	join players pl on p.PlayerID = pl.playerID 
	where ArenaName = %s
	group by p.PlayerID,Missions,level)

    select  Missions, Level, PlayerID, MostRecent from MostRecentPerArena
    where mostRecent >  to_date(%s,'YYYY-MM-DD') - INTERVAL '1 day' * %s
    order by Level desc, Missions desc, mostRecent Asc
    offset %s;

    """)
        
        if siteName == None: #If not set, use default
            siteName = cfg.getConfigString("SiteNameReal")
        cursor.execute(query,(siteName,startDate,period,offset))
    results = cursor.fetchall()
    playerList = []
    for result in results:
        #print (result[0])
        playerList.append(result[2])

    conn.commit()
    closeConnection()
    return playerList
    

def getPlayersWhoMightNeedAchievementUpdates(scope, offset = 0):
    conn = connectToSource()
    cursor = conn.cursor()
    query = """
    select distinct PlayerID from Participation
    where insertedTimestamp > current_date - INTERVAL '7 days'
    offset %s
    """
    cursor.execute(query,(offset,))
    results = cursor.fetchall()
    playerList = []
    for result in results:
        #print (result[0])
        playerList.append(result[0])

    conn.commit()
    
    closeConnection()
    return playerList
    

def addPlayer(playerID,GamerTag,Joined,missions):

    conn = connectToSource()
    cursor = conn.cursor()
    query = sql.SQL("""select missions from players where playerID = %s""")
    playerneedsUpdate = False
    try:
        results = cursor.fetchone()
        if results[0] != missions:
            playerneedsUpdate = True
    except Exception as e:
        playerneedsUpdate = True
        pass
    query =  sql.SQL("""insert into Players 
    (PlayerID,GamerTag,Joined,Missions)
    VALUES
    (%s,%s,%s,%s)
    ON CONFLICT (PlayerID) DO UPDATE
    SET Missions = %s
    """)
    
    data = (playerID,GamerTag,Joined,missions,missions)
    try:
        cursor.execute(query,data)
        DBG("  DBG: SQLHelper.AddPlayer - Added new player %s" % playerID,3)
    
    except:
        DBG("Failed to UPSERT player %s" % playerID,1)
    
    
    conn.commit()
    closeConnection()
    return  playerneedsUpdate

    
def addPlayerArena(playerID,ArenaName,localMissions, localLevel,localAvgScore):

    conn = connectToSource()
    cursor = conn.cursor()

    sql = '''INSERT INTO public.playerarenasummary(
            arenaname, localAvgStdScore, localMissions, localLevel, playerid)
    VALUES (%s, %s, %s, %s, %s)
ON CONFLICT (arenaname,playerid) DO UPDATE
	SET localAvgStdScore = %s,
	localMissions = %s,
	localLevel = %s'''
    cursor.execute(sql,(ArenaName,localAvgScore,localMissions,localLevel,playerID,localAvgScore,localMissions,localLevel))
    conn.commit()
    closeConnection()
    return

def addArenaRank(bigObj):
    conn = connectToSource()
    cursor = conn.cursor()
    for obj in bigObj:
        sql = '''insert into 
    ArenaRanksLookup (ArenaName,rankNumber,rankName)
    VALUES (%s,%s,%s)
    ON CONFLICT (arenaName, rankNumber) DO UPDATE
    SET rankName = %s
        '''
        cursor.execute(sql,(obj['ArenaName'],obj['rankNumber'],obj['rankName'],obj['rankName']))
    conn.commit()
    closeConnection()
    return

def addGame(timestamp, arena, gametype):
    # returns UUID of existing game if already exists, otherwise creates
    # games are never updated.
    
    conn = connectToSource()
    cursor = conn.cursor()
    query = """select GameTimestamp, GameUUID from Games 
    where GameTimestamp = cast(%s as timestamp) AND 
    GameName = %s AND
    ArenaName = %s"""
    cursor.execute(query,(timestamp,gametype,arena))
    result = cursor.fetchone()

    if result == None :
        query = """INSERT INTO Games
        (GameTimestamp, ArenaName, GameName, GameUUID) 
        VALUES
        (cast(%s as timestamp),%s,%s,%s)
        """
        gameUUID = str(uuid.uuid4())
        cursor.execute(query,(timestamp,arena,gametype,gameUUID))
        #print ("SQLconnector.insertGame: Insert game check added a game! : %s" % result)
        conn.commit()
        closeConnection()
        return gameUUID
    else: 
        # print ("SQLconnector: Insert game check found an exiting game! : %s" % result)
         return result[1]

    return ''

def addParticipation(gameUUID, playerID, score):
    conn = connectToSource()
    cursor = conn.cursor()
    query = """select count (*) from Participation
    where GameUUID = %s AND 
    PlayerID = %s"""
    cursor.execute(query,(gameUUID,playerID))
    result = cursor.fetchone()

    if result[0] == 0 :
        query = """INSERT INTO Participation
        (GameUUID, PlayerID, Score, insertedTimestamp) 
        VALUES
        (%s,%s,%s, CURRENT_TIMESTAMP)
        """
        result = cursor.execute(query,(gameUUID,playerID,score))
        #print ("SQLconnector.addParticipation: Added player to game! : %s" % gameUUID)
        conn.commit()
    #else: 
        #print ("SQLconnector.addParticipation: We already know this player played this game! : %s" % gameUUID)

    
    closeConnection()
    return ''

def addAchievement(achName, Description, image, arenaName):
    #do something
    conn =  connectToSource()
    cursor = conn.cursor()

    #print("SQLHelper.addAchievement: Didn't find [{0}], adding it".format(achName))
    AchID = "%s%s" % (achName,arenaName)
    AchID = hashlib.md5(AchID.encode("utf-8")).hexdigest()
    query = """
    INSERT into AllAchievements
        (AchID, AchName, image, Description, ArenaName)
    VALUES (%s,%s,%s,%s,%s)
        ON CONFLICT (AchID) DO UPDATE
        SET image = %s,
        Description = %s
    """
    cursor.execute(query,(str(AchID),achName,image,Description,arenaName,image,Description))
    conn.commit()
    closeConnection()
    return AchID

def addPlayerAchievement(AchID,playerID,newAchievement,achievedDate,progressA,progressB):
#do something
    AchID = str(AchID)
    conn =  connectToSource()
    cursor = conn.cursor()
    if achievedDate == "0000-00-00":
        achievedDate = None
    query = """
    insert into PlayerAchievement
    (AchID,PlayerID,newAchievement,achievedDate,progressA,progressB)
    VALUES (%s, %s, %s, %s, %s, %s)
    ON CONFLICT (AchID, PlayerID) DO 
        UPDATE 
        SET newAchievement = %s, 
        achievedDate = %s,
        progressA = %s,
        progressB = %s

    

    """
    results = cursor.execute(query,(AchID,playerID,newAchievement,achievedDate,progressA,progressB,
    newAchievement,achievedDate,progressA,progressB))


    conn.commit()
    closeConnection()

def addPlayerAchievementScore (playerID, score):
    conn = connectToSource()
    cursor = conn.cursor()
    query = "select playerID from players where playerID = %s "
    data = (playerID,)
    cursor.execute(query,data)

    if cursor.fetchone() == None:
        DBG("SQLHelper.addPlayerAchievementScore didn't find the player, could not update score",2)
    else:
        #print ("SQLHelper.addPlayerAchievementScore found the player, updating their achievement score")
        query = "update players set AchievementScore = ? where playerID = ?"
        cursor.execute(query,(score,playerID))

    conn.commit()
    closeConnection()

def getTop5PlayersRoster(startDate,endDate,ArenaName):
    
    conn = connectToSource()
    cursor = conn.cursor()
    query = """with PlayersInGame as (
	SELECT 
	Count (Players.GamerTag) as playersInGame, 
	Games.GameUUID as gameID
	FROM Games 
	join Participation on participation.GameUUID = Games.GameUUID
	join Players on Participation.PlayerID = Players.PlayerID
	where GameTimestamp >= %s
	and GameTimeStamp < %s
	and games.ArenaName = %s
	group by Games.GameUUID ),
averageOpponents as 
(
	select avg(cast(playersInGame as float)) as AverageOpponents,  players.PlayerID from Participation 
	join PlayersInGame on Participation.GameUUID = PlayersInGame.gameID
	join Games on Games.GameUUID = PlayersInGame.gameID
	join Players on Participation.PlayerID = players.PlayerID
	where games.ArenaName = %s
	group by  players.PlayerID		
),
totalGamesPlayed as 
(
	select count(*) as gamesPlayed,  Participation.PlayerID
	from Participation 
	join Games on Games.GameUUID = Participation.GameUUID
	where GameTimestamp >= %s
	and GameTimeStamp < %s
	and games.ArenaName = %s
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
	and games.ArenaName = %s
),
AverageRanks as 
( select PlayerID, AVG(cast(gamePosition as float)) as AverageRank from Ranks
	group by PlayerID), 
AverageScores as (
SELECT 
	Players.PlayerID, 	
	avg(Score) as averageScore	
	FROM Participation
	inner join Players on Participation.PlayerID = Players.PlayerID
	inner join Games on Participation.GameUUID = Games.GameUUID
	join totalGamesPlayed on totalGamesPlayed.PlayerID = Players.PlayerID
	join averageOpponents on averageOpponents.PlayerID = Players.PlayerID
	join AverageRanks on AverageRanks.PlayerID = Players.PlayerID
	where GameTimestamp >= %s
	and GameTimeStamp < %s
	and games.ArenaName = %s
	and (
	Games.GameName in ('Team','3 Teams','4 Teams', 'Colour Ranked','Individual')
    or Games.GameName in ('Standard - Solo', 'Standard - Team','Standard [3 Team] (10)','Standard [3 Team] (15)','Standard 2 Team',
    'Standard 3 Team','Standard 4 Team','Standard Individual','Standard Multi team','- Standard [2 Team] (15))')
	)
	group by Players.PlayerID
 ),
StarQuality as
(
	SELECT  Players.PlayerID, GamerTag
	, round(cast(AverageOpponents as numeric),2) as AverageOpponents, gamesPlayed
	, round(cast(AverageRank as numeric),2) as AverageRank
	, round(cast(AverageOpponents *  1/(AverageRank/AverageOpponents) as numeric),2) as AvgQualityPerGame
	, round(cast(AverageOpponents * gamesPlayed * 1/(AverageRank/AverageOpponents) as numeric),2) as TotalQualityScore, averageScore, AchievementScore
	from Players
	join totalGamesPlayed on totalGamesPlayed.PlayerID = Players.PlayerID
	join averageOpponents on averageOpponents.PlayerID = Players.PlayerID
	join AverageRanks on AverageRanks.PlayerID = Players.PlayerID
	left join AverageScores on AverageScores.PlayerID = Players.PlayerID
),
GoldenTop3 as 
(
	select PlayerID, ROW_NUMBER() over (order by avgQualityPerGame desc) as playerRank from StarQuality
	where StarQuality.gamesPlayed >= 3
	order by AvgQualityPerGame desc
	limit 3 
),
BestScorer as (
	SELECT PlayerID --, GamerTag, round(AverageOpponents,2) as AverageOpponents, gamesPlayed, round(AverageRank,2) as AverageRank, 
	--round((AverageOpponents *  1/(AverageRank/AverageOpponents)),2) as AvgQualityPerGame,
	--round((AverageOpponents * gamesPlayed * 1/(AverageRank/AverageOpponents)),2) as TotalQualityScore, averageScore, AchievementScore
	from AverageScores 
	where PlayerID not in (select PlayerID from GoldenTop3) 
	order by averageScore desc
	limit 1
),
Achievers as (
    select playerID, count(*) achievements
    from PlayerAchievement pa join AllAchievements aa on aa.AchID = pa.AchID
    where achievedDate is not null and aa.ArenaName = %s
    group by playerID 
),
BestAchiever as(

	SELECT Players.PlayerID
	--GamerTag, round(AverageOpponents,2) as AverageOpponents, gamesPlayed, round(AverageRank,2) as AverageRank, 
	--round((AverageOpponents *  1/(AverageRank/AverageOpponents)),2) as AvgQualityPerGame,
	--round((AverageOpponents * gamesPlayed * 1/(AverageRank/AverageOpponents)),2) as TotalQualityScore, averageScore, AchievementScore
	from Players
	join totalGamesPlayed on totalGamesPlayed.PlayerID = Players.PlayerID
	where players.PlayerID not in (select PlayerID from GoldenTop3) and Players.PlayerID not in (select PlayerID from BestScorer)
	order by Players.AchievementScore desc
	limit 1
)

select p.PlayerID , GamerTag, playerRank, 'Top3' as source from GoldenTop3 p
join Players pl on pl.PlayerID = p.PlayerID
union 
select  p.PlayerID , GamerTag, 4 as playerRank, 'BestScorer' as source from BestScorer p
join Players pl on pl.PlayerID = p.PlayerID
union 
select  p.PlayerID , GamerTag, 5 as playerRank, 'BestAchiever' as source from BestAchiever p
join Players pl on pl.PlayerID = p.PlayerID
order by playerRank asc
"""
    data = (startDate,endDate,ArenaName
        ,ArenaName
        ,startDate,endDate,ArenaName
        ,startDate,endDate,ArenaName
        ,startDate,endDate,ArenaName,ArenaName)
    cursor.execute(query,data)
    rows = cursor.fetchall()
    if rows == None:
        DBG(" SQLHelper.getTop5Players didn't find any players. Is there data in all tables?/",2)
    else:
        DBG ("SQLHelper.getTop5Players found all 5 players",3)

    conn.commit()
    closeConnection()
    return rows

def dumpParticipantsAndGamesToCSV():
    conn = connectToSource()
    cursor = conn.cursor()
    query = """select * From Participation"""
    cursor.execute(query)
    count = 0 
    file = open("CSV dump - participation","w+")
    for row in cursor.fetchall():
        count = count + 1
        file.write("%s,%s,%i\n" % (row[0],row[1],row[2]))
    file.close()
    
    DBG("Dumped %i rows to CSV dump - participation.csv" % (count))
    query = """select * From Games"""
    cursor.execute(query)
    count = 0 
    file = open("CSV dump - Games","w+")
    for row in cursor.fetchall():
        count = count + 1
        file.write("%s,%s,%s\n" % (row[0],row[1],row[2]))
    file.close()
    closeConnection()
    print("Dumped %i rows to CSV dump - Games.csv" % (count))


def importPlayersFromCSV(path):
    conn=connectToSource()
    cursor = conn.cursor()
    file = open (path,"r")
    readCSV = csv.reader(file, delimiter=',')
    sql = '''insert into Players (PlayerID,GamerTag,Joined,Missions,Level)
	    values(?,?,?,?,?)'''
    for row in readCSV:
        DBG(row)
        cursor.execute(sql,(row[0],row[1],row[2],row[3],row[4]))
    conn.commit()
    closeConnection()



def jobStart(description,resumeIndex,methodName, methodParams, completeIndex = None, delay = 0):

    ID = str(uuid.uuid4())
    SQL  = """INSERT into jobsList ("desc","id","started","methodname","methodparams","completeindex") values 
    (%s,%s,now() + interval '%s minutes',%s,%s,%s)"""
    conn=connectToSource()
    cursor = conn.cursor()

    cursor.execute(SQL,(description,ID,delay,methodName,json.dumps(methodParams),completeIndex))

    conn.commit()
    closeConnection()

    return ID

def jobEnd(ID):
    SQL = """UPDATE jobsList 
    SET finished = now(),
    resumeindex = NULL
    where id = %s """
    
    conn=connectToSource()
    cursor = conn.cursor()

    cursor.execute(SQL,(ID,))

    conn.commit()
    closeConnection()


def jobHeartbeat(ID,progressIndex):
    SQL = """UPDATE jobsList 
    SET lastHeartbeat = now(),
    resumeIndex = %s
    where ID = %s """
    
    conn=connectToSource()
    cursor = conn.cursor()

    cursor.execute(SQL,(progressIndex,ID))

    conn.commit()
    closeConnection()

_activeJobsCacheTime = None
_activeJobsCacheResults = None
def getActiveJobs():
    global _activeJobsCacheTime
    global _activeJobsCacheResults
    
    if _activeJobsCacheTime is None or (datetime.datetime.now()- _activeJobsCacheTime).seconds >= 5:
        if _activeJobsCacheTime is not None:
            delta = (datetime.datetime.now() - _activeJobsCacheTime)
        SQL = """ with data as (select row_number() over (partition by healthstatus order by finished desc ) as row, * from public."jobsView")
    select * from data where finished is null or (finished is not null and row <= 3 and row > 0)
    order by finished desc, started asc"""
        conn =connectToSource()
        cursor = conn.cursor()
        
        cursor.execute(SQL)
        results = cursor.fetchall()
        closeConnection()
        _activeJobsCacheResults = results
        _activeJobsCacheTime = datetime.datetime.now()
    return _activeJobsCacheResults
