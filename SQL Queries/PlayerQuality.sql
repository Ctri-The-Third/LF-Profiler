with PlayersInGame as (
	SELECT 
	Count ([LaserScraper].[dbo].[Players].[GamerTag]) as playersInGame, 
	Games.GameUUID as gameID
	FROM [LaserScraper].[dbo].[Games] as Games
	join Participation on participation.GameUUID = Games.GameUUID
	join Players on Participation.PlayerID = Players.PlayerID
	--where Games.GameTimestamp > '2019-05-23'
	group by Games.GameUUID ),
averageOpponents as 
(
	select round(avg(cast(playersInGame as float)),2) as AverageOpponents,  players.PlayerID from Participation 
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
	--where Games.GameTimestamp > '2019-05-23'
	group by Participation.PlayerID
)

select Players.PlayerID, GamerTag, AverageOpponents, gamesPlayed, (AverageOpponents * gamesPlayed) as QualityGameScore from Players
join totalGamesPlayed on totalGamesPlayed.PlayerID = Players.PlayerID
join averageOpponents on averageOpponents.PlayerID = Players.PlayerID
order by QualityGameScore desc
--quality is measured by: 
--* Number of games multiplied by 
--* the average number of members they play with
--* divided by their average rank within those players