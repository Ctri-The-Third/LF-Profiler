from DBG import DBG
import math 
import datetime
import string 
import colorama
import queue
import time 
from colorama import Fore, Back
from SQLconnector import connectToSource, closeConnection
from SQLHelper import addPlayer, addPlayerArena, addArenaRank, getPlayers
from FetchHelper import fetchPlayer_root
import workerProgressQueue as wpq
import ConfigHelper as cfg 
import json
from SQLHelper import jobStart,jobHeartbeat,jobEnd
from psycopg2 import sql 

def findNewPlayers(siteName = None,jobID=None):

    
    startTime = datetime.datetime.now()
    lastHeartbeat = startTime
    conn = connectToSource()
    cursor = conn.cursor()

    conn = connectToSource()
    cursor = conn.cursor()
    if siteName is not None:
        targetID = cfg.findSiteIDFromName(siteName)
        siteObj = cfg.getSiteWithoutActivatingByID(targetID)
        sitePrefix = siteObj["ID Prefix"]
        siteName = siteObj["SiteNameReal"]
    else:
        sitePrefix = cfg.getConfigString("ID Prefix")
        siteName = cfg.getConfigString("SiteNameReal")
    params = {}
    params["siteName"] = siteName
    if jobID is None:
        jobID = jobStart("  new players at [%s]" % siteName,0,"FetchPlayerUpdatesAndNewPlayers.findNewPlayers",params)
    else:
        jobHeartbeat(jobID,0)

    
    TickerIcon = ["|","/","-",'\\']
    sitePrefixforSQL = sitePrefix + "%"
    query = sql.SQL("""
with IDs as ( select 
cast (split_part(pl.PlayerID,'-',3) as integer) as ID
from players pl
where playerID like %s
order by 1 desc
offset 5
)
select max (ID) from IDs
    """)
    cursor.execute(query,(sitePrefixforSQL,))
    result = cursor.fetchone()
    if result == None or result[0] == None:
        MaxPlayer = 199 #LaserForce seems to start numbering players at 100
    else: 
        MaxPlayer = result[0]
    region = sitePrefix.split("-")[0]
    siteNumber = sitePrefix.split("-")[1]

    
    ticker = 0
    consecutiveMisses = 0
    currentTarget = MaxPlayer - 100 #we've had situations where the system adds user IDs behind the maximum. This is a stopgap dragnet to catch trailing players.
    AllowedMisses = 100

    
    while consecutiveMisses <= AllowedMisses:
        heartbeatDelta = (datetime.datetime.now() - lastHeartbeat).total_seconds()
        if heartbeatDelta > 30:
            jobHeartbeat(jobID,0)
            lastHeartbeat = datetime.datetime.now()
            conn.commit()
        player =  fetchPlayer_root('',region,siteNumber,currentTarget)
        if 'centre' in player:
            
            codeName = player["centre"][0]["codename"]
            dateJoined = player["centre"][0]["joined"]
            missionsPlayed = player["centre"][0]["missions"]
            skillLevelNum = player["centre"][0]["skillLevelNum"]
            addPlayer("%s%i" % (sitePrefix,currentTarget),codeName,dateJoined,missionsPlayed)
            
            _parseCentresAndAdd(player["centre"],'%s-%s-%s' % (region,siteNumber,currentTarget))
            consecutiveMisses = 0
        else: 
            DBG("DBG: FetchPlayerUpdatesAndNewPlayers.findNewPlayers - Missed a player 7-X-%s" % (currentTarget),3)
            consecutiveMisses = consecutiveMisses + 1
        wpq.updateQ(consecutiveMisses,AllowedMisses,"Seeking new... %s" % TickerIcon[ticker % 4],"ETA ?")    
        currentTarget = currentTarget + 1 
        ticker = ticker + 1
        
    endTime = datetime.datetime.now()
    jobEnd(jobID)
    f = open("Stats.txt","a+")
    
    f.write("searched for {0} players, operation completed after {1}. \t\n".format(currentTarget-MaxPlayer,endTime - startTime ))
    wpq.updateQ(1,1,"Seeking new... %s","Complete")
    f.close()
    conn.commit()
    
    closeConnection()
#summaries! :) 
def updateExistingPlayersLoad(JobID = None):
    conn = connectToSource()
    cursor = conn.cursor()
    offset = 0
    if JobID != None: 
        query = """select ID, started,lastheartbeat,resumeindex, methodname from jobslist 
where finished is null and ID = %s and methodname = 'FetchPlayerUpdatesAndNewPlayers.updateExistingPlayers'
order by started desc"""
        cursor.execute(query, (JobID,))
        results = cursor.fetchone()
        if results[2] is not None:
            startTime = results [2]
        else:
            startTime = results[1]

        if results[3] is not None:
            offset = results[3]
        

    results = getPlayers(offset=offset)
    for playerID in results:
        wpq.summaryQ.put(playerID)
    totalTargetsToUpdate = len(results)
    
    
    closeConnection()
    

def updateExistingPlayersExecute():
    
    updateExistingPlayersLoad()
    TotalEntries = wpq.summaryQ.qsize()
    jobID = jobStart("Fetch summaries, all known players",0,"FetchPlayerUpdatesAndNewPlayers.updateExistingPlayers",None,TotalEntries,delay=-2)
    return jobID


def updateExistingPlayersLoop(JobID = None):
    startTime = datetime.datetime.now()
    conn = connectToSource()
    cursor = conn.cursor()
    offset = 0
    TotalEntries = wpq.summaryQ.qsize()

    if JobID == None:
        JobID = jobStart("Fetch summaries, all known players",0,"FetchPlayerUpdatesAndNewPlayers.updateExistingPlayers",None,TotalEntries)
        startTime = datetime.datetime.now()

    
    global WorkerStatus

    lastHeartbeat = startTime
    counter = offset
    jobHeartbeat(JobID,counter)
    while wpq.summaryQ.empty() == False:
        targetID = wpq.summaryQ.get()
        targetID = targetID[0]
        heartbeatDelta = (datetime.datetime.now() - lastHeartbeat).total_seconds()
        if heartbeatDelta > 30:
            jobHeartbeat(JobID,counter)
            lastHeartbeat = datetime.datetime.now()
        counter = TotalEntries - wpq.summaryQ.qsize() 
        WorkerStatus = {}
        WorkerStatus["CurEntry"] = counter
        WorkerStatus["TotalEntries"] = TotalEntries
        WorkerStatus["CurrentAction"] = "summary of %s" % (targetID) 
        delta = "[    Calculating     ]"
        if counter >= 20:
            delta = ((datetime.datetime.now() - startTime).total_seconds() / counter) 
            delta = (TotalEntries - counter) * delta #seconds remaining
            seconds = round(delta,0)
            minutes = 0
            hours = 0

            if (seconds > 60 ):
                minutes = math.floor(seconds / 60)
                seconds = seconds % 60 
            if (minutes > 60):
                hours = math.floor(minutes / 60 )
                minutes = minutes % 60
            
            delta = "%ih, %im, %is" % (hours,minutes,seconds)
            
        wpq.updateQ(counter,TotalEntries,"summary of %s" % (targetID) ,delta)
            
        

        ID = targetID.split('-')
        player = fetchPlayer_root('',ID[0],ID[1],ID[2])

        datetime_list = []
        missions = 0
        level = 0
        for i in player["centre"]:
            datetime_list.append (str(i["joined"]))
            missions += int(i["missions"])
            level = max(level,int(i["skillLevelNum"]))
        joined = min(datetime_list)
        codeName = str(player["centre"][0]["codename"])


        #DBG("Summary update for player %s-%s-%s, [%i/%i]" % (ID[0],ID[1],ID[2],counter,TotalEntries),3)
        addPlayer(targetID,codeName,joined,missions) 
        _parseCentresAndAdd(player["centre"],targetID)
    jobEnd(JobID)
    endTime = datetime.datetime.now()
    f = open("Stats.txt","a+")
    f.write("Queried {0} players' aggregates, operation completed after {1}. \t\n".format(TotalEntries,endTime - startTime ))
    f.close()

def manualTargetSummary(rootID):
    ID = rootID.split('-')
    if len(ID) < 3:
        DBG("ERROR, malform user ID, could not split. Aborting",2)
        return
    player = fetchPlayer_root('',ID[0],ID[1],ID[2])
    if player == {}:
        DBG("ManualTargetSummary failed! Aborting",1)
        return
    DBG("Manual update of player sumary complete",1)
    addPlayer(rootID,player["centre"][0]["codename"],player["centre"][0]["joined"],player["centre"][0]["missions"])
    _parseCentresAndAdd(player["centre"],rootID)
    return player

def manualTargetSummaryAndIncludeRank(rootID):
    player = manualTargetSummary(rootID)
    bigObj = []
    for centre in player['centre']:
        #obj['ArenaName'],obj['rankNumber'],obj['rankName']
        obj = {}
        obj['rankNumber'] = centre['skillLevelNum']
        obj['rankName'] = centre['skillLevelName']
        obj['ArenaName'] = centre['name']
        bigObj.append(obj)
    addArenaRank(bigObj)


 
def _parseCentresAndAdd(centres, playerID):
    for centre in centres:
        summaryValue = 0
        try:
            for summary in centre['summary']:
                if summary[0] == 'Standard':
                    summaryValue = summary[3]
                    break
        except Exception as e:
            DBG("ERROR: FetchPlayerUpdatesAndNewPlayers._parseCentresAndAdd failed to find average score for player %s" % (playerID,))
        addPlayerArena(playerID,centre['name'],centre['missions'],centre["skillLevelNum"],summaryValue)
        