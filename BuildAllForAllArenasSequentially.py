import BuildMonthlyScoresToJSON
import BuildMonthlyStarQualityToJSON
import BuildAchievementScoresToJSON
import BuildPlayerBlob
import BuildHeadToHeadsToJSON
import BuildAnnualArenaMetrics
import BuildAnnualTop3s
import BuildAnnualStars
import ConfigHelper as cfgH
from SQLHelper import jobStart,jobHeartbeat,jobEnd
def buildAllForAllArenasSequentially(jobID = None, startIndex = None):
        cfg = cfgH.getConfig()

        if jobID == None:
                jobID = jobStart("Render all blobs",0
                ,"buildAllForAllArenasSequentially.buildAllForAllArenasSequentially"
                , None, len (cfg["configs"])
                )
        
        if startIndex == None:
                startIndex = 0
        counter = 0
        for config in cfg["configs"]:
                if counter >= startIndex:
                        cfgH.setActive(counter)
                        BuildMonthlyScoresToJSON.executeMonthlyScoresBuild()
                        jobHeartbeat(jobID,counter)
                        BuildMonthlyStarQualityToJSON.executeBuildMonthlyStars()
                        jobHeartbeat(jobID,counter)
                        BuildAchievementScoresToJSON.executeAchievementBuild()
                        BuildPlayerBlob.executeBuildPlayerBlobs(jobID = jobID, counter = counter)
                        #BuildHeadToHeadsToJSON.buildHeadToHeads() 
                        BuildAnnualArenaMetrics.executeBuild()
                        jobHeartbeat(jobID,counter)
                        BuildAnnualTop3s.execute()
                        jobHeartbeat(jobID,counter)
                        BuildAnnualStars.executeBuild_AnnualStars()
                        jobHeartbeat(jobID,counter)
                counter = counter + 1
        jobEnd(jobID)
