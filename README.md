# halite-2016-bot
[Halite 2016](https://2016.halite.io/) was an AI programming challenge where user-submitted bots fight for control of a 2D grid. The competition was open from November 2016 to February 2017.

`MyBot.py` is the last version that I submitted. I finished with rank [31/1592 (top 2%)](https://2016.halite.io/user.php?userID=4571). Game replays of my bot can also be viewed [here](https://2016.halite.io/user.php?userID=4571).

Note that since I joined the competition quite late in January 2017 and only had a couple of weeks to code while working full-time, I focused more on fast implementation and A/B testing instead of writing pretty modularized codes / functions.

Overall I really enjoyed the competition and am satisfied with my result.
The big eureka moment was implementing the influence map for combat and grassfire (a.k.a. wavefront / brushfire) algorithm for path planning.
Those two alone bumped my rank to around 70 IIRC.
Other notable improvements were making sure my squares don't kill each other and not moving all the time (sometimes staying still is better).
My bot's weakest component is the production search, which doesn't look ahead more than 1 neighboring square.
I tried several path finding algorithms but nothing worked well to my liking and/or they timed out.
Therefore, I intentionally made my bot a bit more offense-oriented instead of production-gathering,
which worked better on small maps with many players.

# Core algorithm

At each iteration of the game, my bot does the following in order:

1. __*Instruct frontline squares to overkill enemies*__
- Calculate the enemy influence map, which is the sum of enemy strengths affecting a given tile after 1 move. The implementation is inspired by [this post](http://aigamedev.com/open/tutorial/influence-map-mechanics/).
- Using the influence map, prioritize my frontline squares to move to a tile where the overkill mechanism can kill the most enemies. If a kill is not possible, check the second lines and see if combining squares is more beneficial.
2. __*Use the grassfire algorithm for path planning*__
- Run the grassfire algorithm on the map, which yields the distance needed to the closest enemy tile. The implementation is inspired by [this post](http://aigamedev.com/open/tutorial/influence-map-mechanics/).
- Using different cutoffs (through trial and error) of (my owned sites / total sites) ratio, instruct a percentage of my tiles to attack the enemy.
3. __*Search for production*__
- Retrieve a list of neighboring target unowned squares sorted by cost or (prod / str).
- For every target, route my squares that are within 3 moves. Also decide whether it is better for some squares to stay still instead when the occupied production is high enough.
4. __*Route the unmoved squares to either an enemy or untargeted prod*__
- Make sure that every move does not result in combining squares with > 255 + 10 strength.

# Running the bot locally

You can run a match between MyBot.py and RandomBot.py locally by invoking the following:

```
./halite -d "34 34" -s 123 "python3 MyBot.py" "python3 RandomBot.py"
```

where
- `d` is the map size, and
- `s` is the map seed (optional); useful for debugging.

If run correctly, it should print the following at the end:

```
Map seed was 123
Opening a file at 809900-123.hlt
Player #1, MyBot, came in rank #1 and was last alive on frame #76!
Player #2, RandomPythonBot, came in rank #2 and was last alive on frame #75!
```

The `*.hlt` file will be created in the current folder.
To visualize the match, you can upload it to the [halite visualizer](https://2016.halite.io/local_visualizer.php).

# Sample game replay

Here is a replay of a game where my bot (in red) won (can also be viewed [here](https://2016.halite.io/game.php?replay=ar1487266971-1401338381.hlt)):

![alt text](https://github.com/frabi/halite-2016-bot/blob/master/replay.gif "")








