import json
from pathlib import Path

import random

import sc2
from sc2.constants import *

from sc2.position import Point2

trashtalk = [
    "There are about 37 trillion cells working together in your body right now, and you are disappointing every single one of them.",
    "I'd call you a tool, but that would imply you were useful in at least one way.",
    "You're the type of player to get 3rd place in a 1v1 match",
    "Legend has it that the number 0 was first invented after scientists calculated your chance of doing something useful."
]

class MyBot(sc2.BotAI):
    with open(Path(__file__).parent / "../botinfo.json") as f:
        NAME = json.load(f)["name"]

    async def on_step(self, iteration):
        if iteration == 0:
            await self.chat_send(f"{random.choice(trashtalk)}")

            # available_workers = self.workers
            #
            # for location in self.enemy_start_locations:
            #     if len(available_workers) > 0:
            #         await self.do(available_workers.pop().move(location))
            #
            # for location in self.expansion_locations:
            #     if len(available_workers) > 0:
            #         await self.do(available_workers.pop().move(location))

        await self.distribute_workers()
        await self.build_supply()
        await self.build_workers()
        await self.build_vespene()
        await self.expand()
        await self.build_strategy()
        await self.build_cannons()

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
        if not self.has_building(UnitTypeId.FORGE):
            await self.build_structure(self.units(UnitTypeId.NEXUS)[0], UnitTypeId.FORGE)

    async def build_structure(self, near, building):
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
                    await self.build_structure(pylons.first, UnitTypeId.PHOTONCANNON)

    def has_building(self, unit_type):
        return self.already_pending(unit_type) or self.units(unit_type).ready.exists
