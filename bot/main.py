import json
from pathlib import Path

import random
import math
import sc2
from sc2.constants import *

from sc2.position import Point2

trashtalk = [
    "Did you know sharks only kill 5 people each year? Looks like you got some competition",
    "I'd call you a tool, but that would imply you were useful in at least one way.",
    "You're the type of player to get 3rd place in a 1v1 match",
    "I'd love to see things from your perspective, but I don't think I could shove my head that far up my ass.",
    "Legend has it that the number 0 was first invented after scientists calculated your chance of doing something useful."
]

class MyBot(sc2.BotAI):
    with open(Path(__file__).parent / "../botinfo.json") as f:
        NAME = json.load(f)["name"]

    def __init__(self):
        self.warpgate_research_started = False
        self.attempted_proxy_locations = []

    async def on_step(self, iteration):
        try:
            if iteration == 0:
                await self.chat_send(f"{random.choice(trashtalk)}")

                next_expansion = await self.get_next_expansion()
                self.first_ramp_location = self.townhalls.first.position.towards(next_expansion, 15)
        except (Exception):
            pass

        try:
            await self.distribute_workers()
            await self.build_supply()
            await self.build_workers()
            await self.build_vespene()
            await self.expand()
        except (Exception):
            pass

        try:
            await self.handle_chrono_boost()
        except (Exception):
            pass

        try:
            await self.build_warpgates()
            await self.spam_zealots()
            await self.spam_stalkers()
            await self.build_proxies()
        except (Exception):
            pass

        try:
            await self.build_strategy()
            await self.build_cannons()
        except (Exception):
            pass

    async def build_workers(self):
        allowed_excess = 4
        for cc in self.units(UnitTypeId.NEXUS).ready.noqueue:
            excess = cc.assigned_harvesters - cc.ideal_harvesters
            if excess < allowed_excess:
                if self.can_afford(UnitTypeId.PROBE):
                    await self.do(cc.train(UnitTypeId.PROBE))

    async def expand(self):
        excess = 0
        for cc in self.units(UnitTypeId.NEXUS).ready:
            excess = excess + cc.assigned_harvesters - cc.ideal_harvesters
        if excess >= 4 and self.units(UnitTypeId.NEXUS).amount < 10 and self.can_afford(UnitTypeId.NEXUS) and not self.already_pending(UnitTypeId.NEXUS):
            location = await self.get_next_expansion()
            if location is not None:
                await self.build(UnitTypeId.NEXUS, near=location)
                await self.build(UnitTypeId.PYLON, near=location)

    async def build_supply(self):
        ccs = self.units(UnitTypeId.NEXUS).ready
        if ccs.exists:
            cc = ccs.random
            if self.supply_left < 4 and not self.already_pending(UnitTypeId.PYLON):
                if self.can_afford(UnitTypeId.PYLON):
                    await self.build(UnitTypeId.PYLON, near=cc.position.towards(self.game_info.map_center, 5))

    async def build_vespene(self):

        # create workers for existing assimilators
        for assim in self.geysers:
            if assim.assigned_harvesters < assim.ideal_harvesters:
                if self.can_afford(UnitTypeId.PROBE):
                    ccs = self.townhalls.ready.noqueue.prefer_close_to(assim.position)
                    if len(ccs) >= 1:
                        await self.do(ccs[0].train(UnitTypeId.PROBE))

        # check if there are unsaturated assimilators first (or a new one is already pending)
        vesp_workers_needed = 0
        for assim in self.geysers:
            vesp_workers_needed = vesp_workers_needed + assim.ideal_harvesters - assim.assigned_harvesters
        if vesp_workers_needed > 0 or self.already_pending(UnitTypeId.ASSIMILATOR):
            return

        for nexus in self.townhalls.ready:
            # only create assims when there is enough mineral gathering going on
            if nexus.assigned_harvesters < 12 and not nexus.assigned_harvesters >= nexus.ideal_harvesters:
                break
            vgs = self.state.vespene_geyser.closer_than(20.0, nexus)
            for vg in vgs:
                if self.units(UnitTypeId.ASSIMILATOR).closer_than(1.0, vg).exists:
                    break

                if not self.can_afford(UnitTypeId.ASSIMILATOR):
                    break

                worker = self.select_build_worker(vg.position)
                if worker is None:
                    break

                await self.do(worker.build(UnitTypeId.ASSIMILATOR, vg))

    async def build_strategy(self):
        if len(self.townhalls) > 1:
            if not self.has_building(UnitTypeId.FORGE):
                await self.build_structure(UnitTypeId.FORGE, self.units(UnitTypeId.NEXUS)[0])

    async def build_structure(self, building, near):
        if self.units(UnitTypeId.PYLON).ready.exists:
            pylon = self.units(UnitTypeId.PYLON).closest_to(near)
            if self.can_afford(building):
                await self.build(building, near=pylon)

    async def build_cannons(self):
        if self.has_building(UnitTypeId.FORGE):
            nexuses = self.townhalls
            for nexus in nexuses:
                pylons = self.units(UnitTypeId.PYLON).closer_than(20, nexus)
                if len(pylons) is not 0 and len(self.units(UnitTypeId.PHOTONCANNON).closer_than(20, pylons.first)) <= 2:
                    await self.build_structure(UnitTypeId.PHOTONCANNON, pylons.first)

    def has_building(self, unit_type):
        return self.already_pending(unit_type) or self.units(unit_type).ready.exists

    async def build_if_missing(self, unit_type, near):
        if not self.has_building(unit_type) and not self.already_pending(unit_type):
            if self.can_afford(unit_type):
                await self.build_structure(unit_type, near)

    async def try_chrono_boost(self, target):
        if target.has_buff(BuffId.CHRONOBOOSTENERGYCOST):
            return
        for nexus in self.townhalls:
            abilities = await self.get_available_abilities(nexus)
            if AbilityId.EFFECT_CHRONOBOOSTENERGYCOST in abilities:
                await self.do(nexus(AbilityId.EFFECT_CHRONOBOOSTENERGYCOST, target))
                return

    async def handle_chrono_boost(self):
        # speed up warpgate research first
        ccores = self.units(UnitTypeId.CYBERNETICSCORE).ready
        if ccores.exists:
            ccore = ccores.first
            if not ccore.is_idle:
                await self.try_chrono_boost(ccore)

        # boost all building nexuses
        for nexus in self.townhalls:
            if not nexus.is_idle:
                await self.try_chrono_boost(nexus)

    async def build_warpgates(self):

        # create gateways (first 1, then cybernetics, then warpgate research, then 4)
        total_gates = self.units(UnitTypeId.GATEWAY).amount + self.units(UnitTypeId.WARPGATE).amount
        desired_gates = 4 if self.warpgate_research_started else 1
        if self.can_afford(UnitTypeId.GATEWAY) and total_gates < desired_gates:
            await self.build(UnitTypeId.GATEWAY, near=self.townhalls.first)

        # research warpgate
        await self.build_if_missing(UnitTypeId.CYBERNETICSCORE, self.townhalls.first)
        if self.units(UnitTypeId.CYBERNETICSCORE).ready.exists and self.can_afford(AbilityId.RESEARCH_WARPGATE) and not self.warpgate_research_started:
            ccore = self.units(UnitTypeId.CYBERNETICSCORE).ready.first
            await self.do(ccore(AbilityId.RESEARCH_WARPGATE))
            self.warpgate_research_started = True

        # morph to gateways to warpgates
        for gateway in self.units(UnitTypeId.GATEWAY).ready:
            abilities = await self.get_available_abilities(gateway)
            if AbilityId.MORPH_WARPGATE in abilities and self.can_afford(AbilityId.MORPH_WARPGATE):
                await self.do(gateway(AbilityId.MORPH_WARPGATE))

    async def build_proxies(self):
        total_gates = self.units(UnitTypeId.GATEWAY).amount + self.units(UnitTypeId.WARPGATE).amount
        if total_gates < 2:
            return

        expansions = self.expansion_locations
        for exp in expansions:
            if not exp in self.attempted_proxy_locations:
                if self.can_afford(UnitTypeId.PYLON):
                    await self.build(UnitTypeId.PYLON, near=exp)
                    self.attempted_proxy_locations.append(exp)

    async def spam_zealots(self):
        for gateway in self.units(UnitTypeId.GATEWAY).idle:
            if self.can_afford(UnitTypeId.ZEALOT) and self.units(UnitTypeId.ZEALOT).amount < 10:
                await self.do(gateway.train(UnitTypeId.ZEALOT))

        for zealot in self.units(UnitTypeId.ZEALOT).idle:
            if self.units(UnitTypeId.GATEWAY).closer_than(5.0, zealot).exists:
                await self.do(zealot.move(self.first_ramp_location))


    def get_enemy_target(self):
        enemy_units = self.known_enemy_units
        if enemy_units.exists:
            return enemy_units.first
        return self.enemy_start_locations[0]

    def get_enemy_base(self):
        enemy_structures = self.known_enemy_structures
        if enemy_structures.exists:
            return enemy_structures.first
        return self.enemy_start_locations[0]

    async def spam_stalkers(self):
        if not self.units(UnitTypeId.PYLON).ready.exists:
            return

        # find pylon closest to enemy
        proxy = self.units(UnitTypeId.PYLON).ready.closest_to(self.get_enemy_base())
        if proxy is None:
            return

        # warp in stalkers
        for warpgate in self.units(UnitTypeId.WARPGATE).ready:
            abilities = await self.get_available_abilities(warpgate)
            if AbilityId.WARPGATETRAIN_STALKER in abilities:
                placement = await self.find_placement(AbilityId.WARPGATETRAIN_STALKER, proxy.position.to2, placement_step=1)
                if placement is None:
                    break
                await self.do(warpgate.warp_in(UnitTypeId.STALKER, placement))

        idle_stalkers = self.units(UnitTypeId.STALKER).idle
        for stalker in idle_stalkers:
            # move stalkers away from pylons
            if self.units(UnitTypeId.PYLON).closer_than(5.0, stalker).exists:
                await self.do(stalker.move(stalker.position.towards(self.game_info.map_center, 10)))

        # attack when 10 stalkers are available
        if idle_stalkers.amount >= 10:
            for stalker in idle_stalkers:
                await self.do(stalker.attack(self.get_enemy_target()))

    async def get_closest_enemy_expansion(self):
        """Find next expansion location."""

        closest = None
        distance = math.inf
        for el in self.expansion_locations:
            def is_near_to_expansion(t):
                return t.position.distance_to(el) < self.EXPANSION_GAP_THRESHOLD

            if any(map(is_near_to_expansion, self.enemy_start_locations[0])):
                # already taken
                continue

            th = self.townhalls.first
            d = await self._client.query_pathing(self.enemy_start_locations[0], el)
            if d is None:
                continue

            if d < distance:
                distance = d
                closest = el
        return closest