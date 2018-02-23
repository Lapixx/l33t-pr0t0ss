import json
from pathlib import Path

import sc2
from sc2.constants import *

class MyBot(sc2.BotAI):
    with open(Path(__file__).parent / "../botinfo.json") as f:
        NAME = json.load(f)["name"]

    def __init__(self):
        self.warpgate_research_started = False

    async def on_step(self, iteration):
        if iteration == 0:
            await self.chat_send(f"I'd call you a tool, but that would imply you were useful in at least one way.")

        await self.distribute_workers()
        await self.build_supply()
        await self.build_workers()
        await self.build_vespene()
        await self.expand()
        await self.build_strategy()
        await self.build_warpgates()
        await self.spam_stalkers()

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

        if self.has_building(UnitTypeId.FORGE):
            await self.build_structure(self.units(UnitTypeId.NEXUS)[0], UnitTypeId.PHOTONCANNON)

    async def build_structure(self, near, building):
        if self.units(UnitTypeId.PYLON).ready.exists:
            pylon = self.units(UnitTypeId.PYLON).closest_to(near)
            if self.can_afford(building):
                await self.build(building, near=pylon)

    def has_building(self, unit_type):
        return self.already_pending(unit_type) or self.units(unit_type).ready.exists

    async def build_if_missing(self, unit_type, near):
        if not self.has_building(unit_type) and not self.already_pending(unit_type):
            if self.can_afford(unit_type):
                await self.build_structure(near, unit_type)

    async def build_warpgates(self):

        # create gateways (first 1, then cybernetics, then 2, then warpgate research, then 4)
        total_gates = self.units(UnitTypeId.GATEWAY).amount + self.units(UnitTypeId.WARPGATE).amount
        desired_gates = (4 if self.warpgate_research_started else 2) if self.has_building(UnitTypeId.CYBERNETICSCORE) else 1
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

    async def spam_stalkers(self):
        if not self.units(UnitTypeId.PYLON).ready.exists:
            return
        # proxy = self.units(UnitTypeId.PYLON).ready.closest_to(self.enemy_start_locations[0])
        for warpgate in self.units(UnitTypeId.WARPGATE).ready:
            abilities = await self.get_available_abilities(warpgate)
            if AbilityId.WARPGATETRAIN_STALKER in abilities:
                proxy = self.units(UnitTypeId.PYLON).ready.random
                if proxy is None:
                    break
                placement = await self.find_placement(AbilityId.WARPGATETRAIN_STALKER, proxy.position.to2, placement_step=1)
                if placement is None:
                    break
                await self.do(warpgate.warp_in(UnitTypeId.STALKER, placement))

        idle_stalkers = self.units(UnitTypeId.STALKER).idle
        if idle_stalkers.amount >= 1:
            for stalker in idle_stalkers:
                await stalker.attack(self.enemy_start_locations[0])
