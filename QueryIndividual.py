import math
import ConfigHelper
import SQLHelper
import colorama
from colorama import Fore, Back
#: last 5 games' stats
#: Blobs, month to month.
#: Top achievement in terms of rarity
#: most recent achievements
#: Places visited 
conn = SQLHelper.connectToSource()
cursor = conn.cursor()
config = ConfigHelper.getConfig()
colorama.init()

#https://codegolf.stackexchange.com/questions/4707/outputting-ordinal-numbers-1st-2nd-3rd#answer-4712
ordinal = ['0th','%s%s1st%s%s' % (Fore.BLACK,Back.YELLOW,Fore.YELLOW,Back.BLACK), '%s%s2nd%s%s' % (Fore.BLACK,Back.WHITE,Fore.YELLOW,Back.BLACK), '%s%s3rd%s%s' % (Fore.BLACK,Back.RED,Fore.YELLOW,Back.BLACK), '4th', '5th', '6th', '7th', '8th', '9th', '10th',
 '11th', '12th', '13th', '14th', '15th', '16th', '17th', '18th', '19th',
 '20th', '21st', '22nd', '23rd', '24th', '25th', '26th', '27th', '28th',
 '29th', '30th', '31st']



def placesVisited (targetID):
    sql = '''DECLARE @targetID  as varchar (20) 
set @targetID = ?;
select ArenaName, convert(varchar(50),min(gameTimestamp),23) as firstVisited, convert(varchar(50),max(gameTimestamp),23) as mostRecentVisit from Participation p join games g on p.GameUUID = g.GameUUID
where PlayerID = @targetID
group by ArenaName
order by min(gameTimestamp)'''
    global cursor
    global config
    results = cursor.execute(sql,(targetID))
    outStr = "%s**Visited Arenas:**%s\n" % (Fore.WHITE,Fore.WHITE)
    for result in results.fetchall():
        outStr = outStr + "%s(%s%s%s)%s," % (Fore.WHITE,Fore.YELLOW,result[0],Fore.WHITE,Fore.WHITE)
    return outStr
def recentAchievement (targetID):
    sql = '''DECLARE @targetID  as varchar (20) 
DECLARE @ArenaName as varchar(50)
set @targetID = ?
set @ArenaName = ?;

select top (1) *
from PlayerAchievement pa join AllAchievements aa on pa.Image = aa.image
where PlayerID = @targetID
order by achievedDate desc '''

def rarestAchievement (targetID):
    sql = '''DECLARE @targetID  as varchar (20) 
DECLARE @ArenaName as varchar(50)
set @targetID = ?;
set @ArenaName = ?;

with bigData as (
select aa.image, AchName, count (distinct PlayerID) as achievingPlayers
from PlayerAchievement pa join AllAchievements aa on pa.Image = aa.image
where pa.achievedDate is not null and ArenaName = @ArenaName
group by aa.image, AchName
)
select top (1) *
from PlayerAchievement pa join bigData bd on pa.Image = bd.image
where PlayerID = @targetID
order by achievingPlayers asc, achievedDate asc'''


def blobs (targetID):
    sql = '''
DECLARE @targetID  as varchar (20) 
DECLARE @ArenaName as varchar(50)
set @targetID = ?
set @ArenaName = ?;

with Ranks as 
(
	select GameTimestamp,games.GameUUID, GameName, Players.PlayerID, GamerTag, Score, 
		ROW_NUMBER() over (partition by GameTimestamp order by score desc) as gamePosition
	from Games 
	join Participation on Games.GameUUID = Participation.GameUUID
	join Players on Participation.PlayerID = Players.PlayerID
	where Games.ArenaName = @ArenaName
),
totalPlayersPerGame as 
(
	select g.GameUUID, count(*) as playerCount
	from Participation p join Games g on p.GameUUID = g.GameUUID
	group by g.GameUUID
)
, starData0 as  (
select concat(concat(DATEPART(yyyy,GameTimestamp),'-'),CONCAT (CASE WHEN DATEPART(MM,Gametimestamp) < 10 THEN '0' END ,DATEPART(MM,Gametimestamp))) as month, ranks.GameUUID,GameTimestamp,GameName,PlayerID,GamerTag,gamePosition,playerCount, playerCount  * ( playerCount  / gamePosition ) as SQ
from ranks join totalPlayersPerGame tppg 
on ranks.GameUUID = tppg.GameUUID
--where PlayerID = @targetID

)
,starData1 as (
select month, PlayerID,count(*) games,round(avg(cast(gamePosition as float)),2) avgRank, round(avg(cast(playercount as float)),2) avgOpponents, round(avg(cast(SQ as float)),2) avgSQ
from starData0 
group by  month, PlayerID
)
, starData2 as (
select ROW_NUMBER() over (partition by month order by month desc, avgSQ desc) SQrank, * from starData1)

, StdData0 as( select 
	p.PlayerID, 
	GamerTag, 
	avg(Score) as averageScore,
	count(GamerTag) as gamesPlayed,
	convert(varchar(7),GameTimestamp,126) as GameMonth
	
  FROM Participation p
  inner join Players pl on p.PlayerID = pl.PlayerID
  inner join Games g on p.GameUUID = g.GameUUID
  --where convert(varchar(7),GameTimestamp,126) in (@curMonth,@lastMonth)
  and (g.GameName in ('Team','3 Teams','4 Teams', 'Colour Ranked','Individual') or
   g.GameName in ('Continous Ind','Standard 2 Team','Standard 3 Team','Standard 4 Team','Standard Individual','Standard Multi team' )
  )
  and g.ArenaName = @ArenaName
  GROUP BY p.PlayerID, pl.GamerTag, convert(varchar(7),GameTimestamp,126)
)
 , stdData1 as (
 select *, ROW_NUMBER() over (partition by GameMonth order by averageScore desc) as stdRank from StdData0
 )
 
select top (3) month,SQrank,avgSQ,games,stdRank,averageScore,gamesPlayed
from starData2 sq
join StdData1 sd on sq.PlayerID = sd.PlayerID and sq.month = sd.GameMonth
where sq.PlayerID = @targetID 
'''
    global cursor
    global config
    global ordinal
    results = cursor.execute(sql,(targetID,config["SiteNameReal"]))
    outStr = "%s**Month to Month Stats:**%s\n" % (Fore.WHITE,Fore.WHITE)
    for result in results.fetchall():
        #print(result)
        temptStr = "%s: Stars %s (%s)\t Std %s (%s)" % (result[0],ordinal[int(result[1])],result[2],ordinal[int(result[4])],result[5])
        outStr = outStr + "%s(%s%s%s)%s\n" % (Fore.WHITE,Fore.YELLOW,temptStr,Fore.WHITE,Fore.WHITE)
    return outStr

def recentGames(targetID):
    sql = '''
DECLARE @targetID  as varchar (20) 
DECLARE @ArenaName as varchar(50)
set @targetID = ?;
set @ArenaName = ?;

with Ranks as 
(
	select GameTimestamp,games.GameUUID, GameName, Players.PlayerID, GamerTag, Score, 
		ROW_NUMBER() over (partition by GameTimestamp order by score desc) as gamePosition
	from Games 
	join Participation on Games.GameUUID = Participation.GameUUID
	join Players on Participation.PlayerID = Players.PlayerID
	where Games.ArenaName = @ArenaName
),
totalPlayersPerGame as 
(
	select g.GameUUID, count(*) as playerCount
	from Participation p join Games g on p.GameUUID = g.GameUUID
	group by g.GameUUID
)

select top(3) ranks.GameUUID,convert(varchar(17),GameTimestamp,113),GameName,PlayerID,GamerTag,gamePosition,playerCount, playerCount  * ( playerCount  / gamePosition ) as SQ
from ranks join totalPlayersPerGame tppg 
on ranks.GameUUID = tppg.GameUUID
where PlayerID = @targetID
order by GameTimestamp desc


    '''
    global ordinal
    global cursor
    global config
    results = cursor.execute(sql,(targetID,config["SiteNameReal"]))
    outStr = "%s**Recent Games:**%s\n" % (Fore.WHITE,Fore.WHITE)
    for result in results.fetchall():
        #print(result)
        temptStr = "%s: %s \t rank %s, of %s" % (result[1],result[2],ordinal[int(result[5])],result[6])
        outStr = outStr + "%s(%s%s%s)%s\n" % (Fore.WHITE,Fore.YELLOW,temptStr,Fore.WHITE,Fore.WHITE)
    return outStr[0:-1]

def PlaysWhen(targetID):
    sql = '''
    declare @targetID as varchar(50)
declare @arenaName as varchar(50)
set @targetID = ?;
set @arenaName = ?;



with dateData as (
select distinct case 
	when DATEPART( dw, GameTimestamp) = 1 then 'Sunday'
	when DATEPART( dw, GameTimestamp) = 2 then 'Monday'
	when DATEPART( dw, GameTimestamp) = 3 then 'Tuesday'
	when DATEPART( dw, GameTimestamp) = 4 then 'Wednesday'
	when DATEPART( dw, GameTimestamp) = 5 then 'Thursday'
	when DATEPART( dw, GameTimestamp) = 6 then 'Friday'
	when DATEPART( dw, GameTimestamp) = 7 then 'Saturday'
end as dayName, 
	DATEPART (dw,GameTimestamp) as day
from Games
),
data as (
	select count (*) as games, DATEPART( dw, GameTimestamp) as day, datePart(HH,GameTimestamp) as hour
	from players pl join Participation p on pl.PlayerID = p.PlayerID 
	join games g on p.GameUUID = g.GameUUID
	where p.playerID = @targetID
	and g.ArenaName = @arenaName
	group by DATEPART( dw, GameTimestamp), datePart(HH,GameTimestamp)
)

select top (2) games,dayName,hour from data d join   dateData dd on d.day =dd.day
order by games desc'''
    global ordinal
    global cursor
    global config
    results = cursor.execute(sql,(targetID,config["SiteNameReal"]))
    outStr = "%s**Common Game Times:**%s\n" % (Fore.WHITE,Fore.WHITE)
    for result in results.fetchall():
        #print(result)
        temptStr = "on %s at %s:00ish" % (result[1],result[2])
        outStr = outStr + "%s(%s%s%s)%s," % (Fore.WHITE,Fore.YELLOW,temptStr,Fore.WHITE,Fore.WHITE)
    return outStr
targetID = '9-6-106'
print("",recentGames(targetID))
print("",blobs(targetID),Fore.WHITE)
print("",PlaysWhen(targetID))
print("rarest achieve",rarestAchievement(targetID))
print("recent achieve",recentAchievement(targetID))
print(placesVisited(targetID))