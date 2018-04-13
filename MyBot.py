import hlt
from hlt import NORTH, EAST, SOUTH, WEST, STILL, Move, Square, opposite_cardinal
import numpy as np

myID, game_map = hlt.get_init()

cost_dict = {}
MIN_MAP_DISTANCE = min(game_map.width, game_map.height)
MAX_GRASSFIRE_DIST = 255
# let python take care of flooring
MAP_COVERING_DISTANCE = game_map.width / 2 + game_map.height / 2
PRODCOST_LBOUND_DIVISOR = 10
SEARCH_CUTOFF_LENGTH = 3

for square in game_map:
    # use mean to capture basic clustering
    ratio_list = [(n.production + 1) / (n.strength + 1)
                  for n in game_map.neighbors(square, include_self=True) if n.owner == 0]
    cost_dict[(square.x, square.y)] = sum(ratio_list) / len(ratio_list)

hlt.send_init("MyBot")
# END INITIALIZATION


def get_dist_dict(q, d):
    node_queue = q[:]
    dist_dict = d.copy()
    while node_queue:
        x, y,  = node_queue.pop(0)
        if dist_dict[(x, y, )] == 0:
            neighbors = [(n_x, n_y)
                         for (n_x, n_y) in game_map.neighbors_xy(x, y)]

            value_neighbors = [dist_dict[(n_x, n_y)] for (n_x, n_y) in neighbors
                               if dist_dict[(n_x, n_y)] not in (0, MAX_GRASSFIRE_DIST)]

            if len(value_neighbors) > 0:
                new_value = 1 + min(value_neighbors)
                dist_dict[(x, y, )] = new_value
            for (n_x, n_y) in neighbors:
                if dist_dict[(n_x, n_y)] == 0:
                    node_queue.append((n_x, n_y))
    return dist_dict


# initial brushfire / grassfire algo
def get_grassfire_pathmap(game_map, attack_percentile):
    # queue of nodes for the loop
    node_queue = []
    # dictionary of (x, y) : distance
    dist_dict = {}
    for square in game_map:
        # assign 1 for enemy, 255 for unowned, 0 for ours
        if square.owner == 0 and square.strength > 0:
            dist = MAX_GRASSFIRE_DIST
        elif (square.owner == 0 and square.strength == 0) or square.owner == myID:
            dist = 0
        else:
            dist = 1

        dist_dict[(square.x, square.y)] = dist

        if any([n for n in game_map.neighbors(square) if n.owner not in (0, myID)])\
                and dist != MAX_GRASSFIRE_DIST:
            node_queue.append((square.x, square.y))

    final_dist_dict = get_dist_dict(node_queue, dist_dict)

    our_scores = []
    for square in game_map:
        min_dist = final_dist_dict[(square.x, square.y)]

        if square.owner == myID:
            our_scores.append(min_dist)

    return final_dist_dict, np.percentile(our_scores, attack_percentile)


def evaluate_target_str_dict(square, dir_list, target_str_dict, target_move_dict, combine_attack=False,
                             overkill_override=False, return_bool=False, flip_override=False):
    if (square not in target_move_dict) and len(dir_list) > 0:
        # reset target move dict
        if square in target_move_dict:
            prev_target = game_map.get_target(square, target_move_dict[square].direction)
            target_str_dict[prev_target] -= square.strength

        for direction in dir_list:
            target = game_map.get_target(square, direction)
            # check if the target is not moving
            auto_flip_override = target.owner == myID and target.strength < target.production * 5 and \
                ((target in target_move_dict and
                  target_str_dict[target] + square.strength > 255 and
                  target_str_dict[target] == target.strength and
                  target_move_dict[target].direction == STILL)
                 or (target not in target_move_dict and target.strength + square.strength > 255))

            # if combine_attack is True, bypass the square > target requirement
            if combine_attack and square.strength > 0:
                if return_bool:
                    return True
                else:
                    target_str_dict[square] += square.strength
                    target_move_dict[square] = Move(square, direction)
                    return
            elif (target_str_dict[target] + square.strength > 255 + 15 and not auto_flip_override and not flip_override) \
                    or (square.strength < square.production * 5 and not overkill_override)\
                    or (target.strength >= square.strength and target.owner != myID) or square.strength == square.production == 0:
                # continue for now till we get a better direction
                continue
            else:
                if return_bool:
                    return True
                else:
                    # special case for flipping owned target that can't move
                    if auto_flip_override or (flip_override and
                                              target_str_dict[target] + square.strength + target.strength > 255):
                        if target_str_dict[square] + target.strength < 255 and target.strength > 0:
                            target_str_dict[square] += target.strength
                            target_str_dict[target] -= target.strength
                            target_move_dict[target] = Move(target, opposite_cardinal(direction))
                        # can't do flipping! try another one
                        else:
                            continue

                    target_str_dict[target] += square.strength
                    target_move_dict[square] = Move(square, direction)
                    return

        # didn't hit anything, sit STILL!
        if return_bool:
            return False
        else:
            target_str_dict[square] += square.strength
            target_move_dict[square] = Move(square, STILL)
            return
    if return_bool:
        return False
    else:
        return None


def get_prod_targets():
    # get all available resources
    avail_cost = [cost_dict[(s.x, s.y)] for s in game_map if s.owner == 0]

    avail_cost_pct_thresh = len(avail_cost) / (game_map.width * game_map.height)

    if avail_cost_pct_thresh < PRODCOST_LBOUND_DIVISOR / 100:
        avail_cost_lbound = 0
    else:
        avail_cost_lbound = np.percentile(avail_cost, avail_cost_pct_thresh / PRODCOST_LBOUND_DIVISOR)

    # target only neighboring sites
    targets = [site for site in game_map if site.owner == 0 and
               len([neighbor for neighbor in game_map.neighbors(site) if neighbor.owner == myID]) != 0
               and site.production > 0 and cost_dict[(site.x, site.y)] > avail_cost_lbound]

    owned_sites = [s for s in game_map if s.owner == myID and cost_dict[(s.x, s.y)] > avail_cost_lbound]
    owned_sites_pct = len(owned_sites) / (game_map.width * game_map.height)
    return targets, avail_cost_pct_thresh, owned_sites_pct


def get_initial_moves(target_str_dict, target_move_dict, targets):
    moves = []

    targets.sort(key=lambda s: cost_dict[(s.x, s.y)])
    untargeted = []

    while len(targets) > 0:
        target = targets.pop()
        required = target.strength + 1
        route = []
        first_route = [(neighbor, opposite_cardinal(direction))
                       for direction, neighbor in enumerate(game_map.neighbors(target))
                       if neighbor.owner == myID and neighbor not in target_move_dict]

        if not first_route:
            untargeted.append(target)
            continue

        first_route.sort(key=lambda x: -x[0].strength)
        passing_route = []

        for site in first_route:
            required -= site[0].strength
            passing_route.append(site)
            if required <= 0:
                break

        route.append(passing_route)
        max_dist = 0
        still_required_list = [required]
        still_idx = 0

        while max_dist < SEARCH_CUTOFF_LENGTH and required > 0 and len(route[-1]) > 0:
            # need to decrease required by the total of current production of the added routes to compensate for waiting
            prev_total_prod = 0
            for idx, route_list in enumerate(route):
                still_required_list[idx] -= prev_total_prod
                total_prod = sum([x[0].production for x in route_list])
                still_required_list[idx] -= total_prod

                if still_required_list[idx] <= 0:
                    still_idx = idx + 1
                    break

                prev_total_prod = total_prod

            new_sites = {}
            for element in route[-1]:
                for direction, neighbor in enumerate(game_map.neighbors(element[0])):
                    # there will be duplicates.. we'll take the first (n, d) pair
                    if neighbor not in new_sites:
                        new_sites[neighbor] = direction

            new_sites_route = [(neighbor, opposite_cardinal(direction))
                                for neighbor, direction in new_sites.items() if neighbor.owner == myID and \
                                (len(route) < 2 or (neighbor not in [element[0] for element in route[-2]]))
                                and neighbor not in target_move_dict]

            # prioritize bigger ones only till the square is dead. this way we can route the extra somewhere else
            new_sites_route.sort(key=lambda x: -x[0].strength)
            passing_route = []
            for new_site in new_sites_route:
                required -= new_site[0].strength
                passing_route.append(new_site)
                if required <= 0:
                    break

            route.append([new_site for new_site in passing_route])
            still_required_list.append(required)
            max_dist += 1

        if still_idx > 0:
            not_moved = [element for stage in route[:still_idx] for element in stage]
            for element in not_moved:
                if element[0].strength > 0:
                    moves.append(evaluate_target_str_dict(element[0], [STILL], target_str_dict, target_move_dict))

        else:
            not_moved = [element for stage in route for element in stage]
            # combine attack is the special case when we kill it and route is of 1 length
            if required < 0 and len(route) == 1 and sum([element[0].strength for element in not_moved]) <= 255:
                combine_attack = True
            else:
                combine_attack = False

            if len(not_moved) > 0:

                for element in not_moved:
                    if element[0].strength > 0:
                        flip_override = False
                        # single-handedly can finish the target up
                        if element not in route[0] and element[0].strength > target.strength:
                            flip_override = True

                        moves.append(evaluate_target_str_dict(element[0], [element[1]], target_str_dict, target_move_dict,
                                     combine_attack=combine_attack, flip_override=flip_override))
            else:
                untargeted.append(target)

    return untargeted, moves


def get_enemy_list(all_borders=True):
    enemy_list = []
    for square in game_map:
        if all_borders:
            if square.owner not in (0, myID) and \
                    any([neighbor.owner != square.owner for neighbor in game_map.neighbors(square)]):
                enemy_list.append(square)
        else:
            if square.owner not in (0, myID) and \
                    any([neighbor.owner == 0 and neighbor.strength == 0 for neighbor in game_map.neighbors(square)]):
                enemy_list.append(square)

    return enemy_list


def find_nearest_direction(owned_square, targets):
    min_distance = MIN_MAP_DISTANCE
    min_x, min_y = min_distance, min_distance
    square_x, square_y = 0, 0
    for square in targets:
        dx, dy, dist = game_map.get_distance_2(square, owned_square)
        if dist < min_distance:
            min_x = dx
            min_y = dy
            square_x = square.x
            square_y = square.y
            min_distance = dist

    if min_x > min_y:
        best_dir = EAST if square_x - owned_square.x == min_x or square_x + game_map.width - owned_square.x == min_x \
            else WEST
    else:
        best_dir = SOUTH if square_y - owned_square.y == min_y or square_y + game_map.height - owned_square.y == min_y \
            else NORTH

    return best_dir, min_distance


def get_enemy_influence_map():
    enemy_set_map = {(square.x, square.y) : set() for square in game_map}
    # 1: update all enemy set
    for square in game_map:
        if square != myID and not (square.owner == 0 and square.strength > 0):
            neutral_tiles = [n for n in game_map.neighbors(square, include_self=True)
                            if (n.owner == 0 and n.strength == 0)]
            if len(neutral_tiles) > 0:
                enemies = [n for n in game_map.neighbors(square, include_self=True)
                             if n.owner not in (myID, 0)]
                if enemies:
                    for tile in [n for n in game_map.neighbors(square, include_self=True)
                                 if not (n.owner == 0 and n.strength > 0)]:
                        enemy_set_map[(tile.x, tile.y)].update(enemies)

    enemy_inf_map = {(square.x, square.y): 0 for square in game_map}
    # 2 : sum up the total possible strength per tile
    for tile, enemies in enemy_set_map.items():
        enemy_inf_map[(tile[0], tile[1])] = sum([x.strength for x in list(enemy_set_map[(tile[0], tile[1])])])

    return enemy_inf_map, enemy_set_map


def get_combat_influence(my_squares, target_str_dict, target_move_dict, enemy_inf_map, enemy_set_map):
    first_line, first_line_squares = [], []

    # 1: get first (front) line squares
    for square in my_squares:
        if square.strength > 0:
            combat_squares = [(d, n) for (d, n) in enumerate(game_map.neighbors(square))
                              if n.owner == 0 and n.strength == 0]

            # logic to check if square is within combat
            if sum([enemy_inf_map[cs.x, cs.y] for (d, cs) in combat_squares]) > 0:
                first_line.append((square, combat_squares))
                first_line_squares.append(square)

    first_line.sort(key=lambda x: (-x[0].strength, -len(x[1])))

    # 2: loop through first line squares
    for square, combat_squares in first_line:
        kill_list = []
        dead_list = []

        for d, cs in combat_squares:
            enemy_str_sum = enemy_inf_map[(cs.x, cs.y)]

            if enemy_str_sum > 0:
                surplus = square.strength - enemy_str_sum
                # it must be the case that at least one of kill and dead is non-empty
                if surplus > 0:
                    kill_list.append((d, surplus, cs))
                else:
                    dead_list.append((d, surplus, cs))

        # 3: prioritize kill
        if kill_list:
            kill_list.sort(key=lambda x: (x[1], -len(enemy_set_map[(x[2].x, x[2].y)])))
            dir_list = [d for (d, n, cs) in kill_list]
            evaluate_target_str_dict(square, dir_list, target_str_dict, target_move_dict,
                                     overkill_override=True)
        # dead
        else:
            # check second lines and see if we can stay and combine
            second_line = [(opposite_cardinal(d), n) for (d, n) in
                           enumerate(game_map.neighbors(square)) if n.owner == myID and
                           n not in first_line_squares and n not in target_move_dict
                           and n.strength >= n.production * 5]
            new_str = square.strength
            second_line_dir_list = []
            for opp_d, n in second_line:
                if new_str + n.strength < 255 + 15:
                    new_str += n.strength
                    second_line_dir_list.append((opp_d, n))

            new_str = min(new_str, 255)
            # if we have enough, square stay and combine
            if new_str > square.strength and new_str - enemy_inf_map[(square.x, square.y)] >= 0:
                evaluate_target_str_dict(square, [STILL], target_str_dict, target_move_dict,
                                         overkill_override=True)
                for opp_d, n in second_line_dir_list:
                    evaluate_target_str_dict(n, [opp_d], target_str_dict, target_move_dict)
            # else, overkill and secondline stay
            else:
                dead_list.sort(key=lambda x: (x[1], -len(enemy_set_map[(x[2].x, x[2].y)])))
                dir_list = [d for (d, n, cs) in dead_list]
                evaluate_target_str_dict(square, dir_list, target_str_dict, target_move_dict,
                                         overkill_override=True)
                for opp_d, n in second_line:
                    evaluate_target_str_dict(n, [STILL], target_str_dict, target_move_dict)

    del first_line
    del first_line_squares
    return


def get_grassfire_moves(target_str_dict, target_move_dict, grassfire_dict, attack_dist_cutoff, enemy_inf_map,
                            attackers = None):
    moves = []
    # only attack if dist cutoff > 0
    if attack_dist_cutoff > 0:
        if attackers is None:
            attackers = [site for site in game_map
                         if site.owner == myID and grassfire_dict[(site.x, site.y)] < attack_dist_cutoff
                         and site not in target_move_dict and site.strength >= site.production * 5]
            attackers.sort(key=lambda x: (grassfire_dict[(x.x, x.y)], -x.strength))

        for square in attackers:
            dir_list, best_score = list(), MAX_GRASSFIRE_DIST
            for d, n in enumerate(game_map.neighbors(square, include_self=True)):
                # do not move to an enemy influenced box (avoid overkill); do not move to bigger grassfire (backtrack)
                if grassfire_dict[(n.x, n.y)] not in (0, MAX_GRASSFIRE_DIST) and enemy_inf_map[(n.x, n.y)] == 0\
                        and grassfire_dict[(n.x, n.y)] <= grassfire_dict[(square.x, square.y)]:
                    score = grassfire_dict[(n.x, n.y)]
                    if score < best_score:
                        dir_list = list()
                        dir_list.append(d)
                        best_score = score
                    elif score == best_score and score != MAX_GRASSFIRE_DIST:
                        dir_list.append(d)

            evaluate_target_str_dict(square, dir_list, target_str_dict, target_move_dict)

    return moves


while True:
    game_map.get_frame()
    # inits
    target_move_dict = {}
    all_squares = [square for square in game_map]
    my_squares = [square for square in all_squares if square.owner == myID]
    target_str_dict = dict(zip([square for square in all_squares], [0] * len(all_squares)))

    # 1: overkill override!
    enemy_inf_map, enemy_set_map = get_enemy_influence_map()
    get_combat_influence(my_squares, target_str_dict, target_move_dict, enemy_inf_map, enemy_set_map)

    # 2: grassfire towards enemy
    target_list, avail_cost_pct_thresh, owned_sites_pct = get_prod_targets()
    if owned_sites_pct <= 0.1:
        attack_percentile = -30 * (owned_sites_pct / 0.1) + 85
    elif 0.1 < owned_sites_pct < 0.3:
        attack_percentile = 55
    else:
        attack_percentile = 55 + (owned_sites_pct - 0.3) * 10 / 7 * 45

    grassfire_dict, attack_dist_cutoff = get_grassfire_pathmap(game_map, attack_percentile)
    get_grassfire_moves(target_str_dict, target_move_dict, grassfire_dict, attack_dist_cutoff, enemy_inf_map)

    # 3: search for prod!
    untargeted, prod_moves = get_initial_moves(target_str_dict, target_move_dict, target_list)

    # 4: route the rest to the enemy / untargeted prod
    not_moved = list(set(my_squares) - set(target_move_dict.keys()))
    not_moved.sort(key=lambda x: (grassfire_dict[(x.x, x.y)], -x.strength))
    if len(not_moved) > 0:
        if len(untargeted) > 0:
            untargeted_list = sorted(untargeted, key=lambda x: -cost_dict[(x.x, x.y)])
            for square in not_moved:
                target, distance = find_nearest_direction(square, untargeted_list)
                evaluate_target_str_dict(square, [target], target_str_dict, target_move_dict)
        elif attack_dist_cutoff > 0:
            get_grassfire_moves(target_str_dict, target_move_dict, grassfire_dict, 1, enemy_inf_map,
                                attackers=not_moved)
        else:
            untargeted_list = get_enemy_list()
            for square in not_moved:
                target, distance = find_nearest_direction(square, untargeted_list)
                evaluate_target_str_dict(square, [target], target_str_dict, target_move_dict)

    hlt.send_frame(target_move_dict.values())
    del target_move_dict
