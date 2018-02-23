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
            cc = ccs.first
            if self.supply_left < 4 and not self.already_pending(UnitTypeId.PYLON):
                if self.can_afford(UnitTypeId.PYLON):
                    await self.build(UnitTypeId.PYLON, near=cc.position.towards(self.game_info.map_center, 5))