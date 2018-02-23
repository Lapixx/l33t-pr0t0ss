import json
from pathlib import Path

import sc2
from sc2.constants import *

from sc2.position import Point2

class MyBot(sc2.BotAI):
    with open(Path(__file__).parent / "../botinfo.json") as f:
        NAME = json.load(f)["name"]

    async def on_step(self, iteration):
        if iteration == 0:
            await self.chat_send(f"Name: {self.NAME}")

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
        await self.expand()

    async def build_workers(self):
        for cc in self.units(UnitTypeId.NEXUS).ready.noqueue:
            if cc.assigned_harvesters < cc.ideal_harvesters:
                if self.can_afford(UnitTypeId.PROBE):
                    await self.do(cc.train(UnitTypeId.PROBE))

    @sc2.BotAI.expansion_locations.getter
    def expansion_locations(self):
        """List of possible expansion locations."""

        RESOURCE_SPREAD_THRESHOLD = 12.0 # Tried with Abyssal Reef LE, this was fine
        resources = [
            r
            for r in self.state.mineral_field | self.state.vespene_geyser
        ]

        # Group nearby minerals together to form expansion locations
        r_groups = []
        for mf in resources:
            for g in r_groups:
                if any(mf.position.to2.distance_to(p) < RESOURCE_SPREAD_THRESHOLD for p in g):
                    g.add(mf)
                    break
            else: # not found
                r_groups.append({mf})

        # Filter out bases with only one mineral field
        r_groups = [g for g in r_groups if len(g) > 1]

        # Find centers
        avg = lambda l: sum(l) / len(l)
        pos = lambda u: u.position.to2
        centers = {Point2(tuple(map(avg, zip(*map(pos,g))))).rounded: g for g in r_groups}

        return centers

    async def expand(self):
        excess = 0
        for cc in self.units(UnitTypeId.NEXUS).ready:
            excess = excess + cc.assigned_harvesters - cc.ideal_harvesters
        if excess >= 0 and self.units(UnitTypeId.NEXUS).amount < 10 and self.can_afford(UnitTypeId.NEXUS) and not self.already_pending(UnitTypeId.NEXUS):
            location = await self.get_next_expansion()
            if location is not None:
                await self.build(UnitTypeId.NEXUS, near=location)

    async def build_supply(self):
        ccs = self.units(UnitTypeId.NEXUS).ready
        if ccs.exists:
            cc = ccs.first
            if self.supply_left < 4 and not self.already_pending(UnitTypeId.PYLON):
                if self.can_afford(UnitTypeId.PYLON):
                    await self.build(UnitTypeId.PYLON, near=cc.position.towards(self.game_info.map_center, 5))