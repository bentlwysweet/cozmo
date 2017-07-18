#!/usr/bin/env python3

# Copyright (c) 2017 Anki, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License in the file LICENSE.txt or at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

'''Quick Tap - tap your cube as fast as possible when the colors match, but never tap on red!

After you and Cozmo select your cubes, the third cube acts as the countdown for each round.

TODO: 
more color combinations

'''
import asyncio, random, sys, time

import cozmo

from cozmo.lights import blue_light, Color, green_light, Light, red_light, white_light
from cozmo.util import degrees, distance_mm, radians, speed_mmps

yellow_light = Light(Color(name = 'yellow', rgb = (255, 255, 0)))
purple_light = Light(Color(name = 'purple', rgb = (255, 0, 255)))

COLORS_LIST = [red_light, blue_light, green_light, yellow_light, purple_light, white_light]

CHOOSE_CUBES_STATE = 'choose_cubes'
GAME_STATE = 'game'

BUZZER_DIFFERENT = 'buzzer_different'
BUZZER_RED = 'buzzer_red'
BUZZER_SAME = 'buzzer_same'

RATE_BUZZER_DIFFERENT = 0.17
RATE_BUZZER_RED = 0.33

SCORE_TO_WIN = 5

class QuickTapGame:
    '''The game logic of setting the cube lights and determining the winner after each round.'''
    def __init__(self,robot: cozmo.robot.Robot):
        self.robot = robot
        self.player = QuickTapPlayer()
        self.cozmo_player = CozmoQuickTapPlayer(robot)
        robot.add_event_handler(cozmo.anim.EvtAnimationCompleted, self.on_anim_completed)
        robot.add_event_handler(cozmo.objects.EvtObjectTapped, self.on_cube_tap)

        self.countdown_cube = None

        self.quick_tap_state = CHOOSE_CUBES_STATE

        self.buzzer_display_type = None

        self.round_start_time = None
        self.first_tapper = None
        self.not_first_tapper = None
        self.round_over = False

    async def run(self):
        '''Assigns the cubes, then starts a new round until a player has won.'''
        await self.robot.set_lift_height(0).wait_for_completed()
        await self.assign_cubes()
        self.quick_tap_state = GAME_STATE
        while max(self.player.score, self.cozmo_player.score) < SCORE_TO_WIN:
            await self.game_round()
        await self.report_winner()

    async def game_round(self):
        '''
        '''
        self.round_over = False
        await self.reset_players_and_cubes()
        await self.cube_light_delay()
        self.determine_buzzer_display()
        self.set_buzzer_lights()
        self.round_start_time = time.time()
        await self.cozmo_player.determine_move(self.buzzer_display_type)
        while not self.round_over:
            await asyncio.sleep(0)
        await self.cozmo_anim_reaction()

    async def reset_players_and_cubes(self):
        ''' one line summary

        Args:

        Returns:

        '''
        self.player.reset()
        self.cozmo_player.reset()
        await self.robot.set_lift_height(1.0).wait_for_completed()
        self.turn_off_buzzer_cubes()
        await self.countdown_cube.countdown()
        
    async def cube_light_delay(self):
        ''' one line summary

        Args:

        Returns:

        '''
        delay = random.random() * 4
        await asyncio.sleep(delay)

    def determine_buzzer_display(self):
        ''' one line summary

        Args:

        Returns:

        '''
        probability_red = random.random()
        if probability_red < RATE_BUZZER_RED:
            self.buzzer_display_type = BUZZER_RED
        else:
            probability_different_colors = random.random()
            if probability_different_colors < RATE_BUZZER_DIFFERENT:
                self.buzzer_display_type = BUZZER_DIFFERENT
            else:
                self.buzzer_display_type = BUZZER_SAME

    def on_cube_tap(self, evt, **kwargs):
        ''' one line summary

        Args:

        Returns:

        '''
        if self.quick_tap_state == CHOOSE_CUBES_STATE:
            if kwargs['obj'].object_id != self.cozmo_player.cube.object_id:
                self.player.cube = kwargs['obj']
                self.player.cube.set_lights_off()
        elif self.quick_tap_state == GAME_STATE:
            if kwargs['obj'].object_id == self.player.cube.object_id:
                self.player.register_tap(self.round_start_time)
            elif kwargs['obj'].object_id == self.cozmo_player.cube.object_id:
                self.cozmo_player.register_tap(self.round_start_time)

    async def on_anim_completed(self, evt, **kwargs):
        ''' one line summary

        Args:

        Returns:

        '''
        if self.quick_tap_state == GAME_STATE:
            await self.determine_result_of_round()
            self.report_scores()
            self.turn_off_buzzer_cubes()
            self.round_over = True

    async def determine_result_of_round(self):
        ''' one line summary

        Args:

        Returns:

        '''
        await self.determine_first_tapper()
        if self.first_tapper:
            if self.buzzer_display_type == BUZZER_SAME:
                self.first_tapper.wins_round()
            elif self.buzzer_display_type == BUZZER_DIFFERENT or self.buzzer_display_type == BUZZER_RED:
                self.not_first_tapper.wins_round()

    async def determine_first_tapper(self):
        ''' one line summary

        Args:

        Returns:

        '''
        await asyncio.sleep(1)
        if self.player.has_tapped or self.cozmo_player.has_tapped:
            if self.cozmo_player.elapsed_tap_time < self.player.elapsed_tap_time:
                self.first_tapper = self.cozmo_player
                self.not_first_tapper = self.player
            else:
                self.first_tapper = self.player
                self.not_first_tapper = self.cozmo_player
        else:
            self.first_tapper = None

    async def cozmo_anim_reaction(self):
        ''' one line summary

        Args:

        Returns:

        '''        
        if self.cozmo_player.won_round:
            await self.robot.play_anim_trigger(cozmo.anim.Triggers.OnSpeedtapHandCozmoWin).wait_for_completed()
        else:
            await self.robot.play_anim_trigger(cozmo.anim.Triggers.OnSpeedtapHandPlayerWin).wait_for_completed()

    async def assign_cubes(self):
        '''Cozmo chooses his cube, then the player chooses,
        and the remaining cube becomes the countdown cube.
        '''
        cubes = [self.robot.world.get_light_cube(cozmo.objects.LightCube1Id), self.robot.world.get_light_cube(cozmo.objects.LightCube2Id), self.robot.world.get_light_cube(cozmo.objects.LightCube3Id)]
        await self.cozmo_player.select_cube()
        self.blink_available_cubes()
        await self.robot.world.wait_for(cozmo.objects.EvtObjectTapped)
        self.player.cube.stop_light_chaser()
        self.assign_countdown_cube()

    def blink_available_cubes(self):
        '''Blinks the cubes which Cozmo did not select for himself.'''
        for cube in self.cubes:
            if cube.object_id != self.cozmo_player.cube.object_id:
                cube.start_light_chaser()

    def assign_countdown_cube(self):
        '''Assigns the countdown cube to be whichever cube has not been selected
        by the player or Cozmo.
        '''
        for cube in self.cubes:
            if cube.object_id != self.cozmo_player.cube.object_id and cube.object_id != self.player.cube.object_id:
                self.countdown_cube = cube
                self.countdown_cube.stop_light_chaser()

    def set_buzzer_lights(self):
        '''one line summary

        Args:

        Returns:

        '''
        if self.buzzer_display_type == BUZZER_RED:
            self.turn_on_buzzer_cubes_red()
        elif self.buzzer_display_type == BUZZER_DIFFERENT:
            self.turn_on_buzzer_cubes_different()
        elif self.buzzer_display_type == BUZZER_SAME:
            self.turn_on_buzzer_cubes_same()

    def turn_on_buzzer_cubes_same(self):
        '''one line summary

        Args:

        Returns:

        '''
        same_colors = self.generate_random_buzzer_colors()
        self.player.cube.set_light_corners(*same_colors)
        self.cozmo_player.cube.set_light_corners(*same_colors)

    def generate_random_buzzer_colors(self):
        ''' one line summary

        Args:

        Returns:

        '''
        num_colors = len(COLORS_LIST)
        x = random.randrange(num_colors)
        y = random.randrange(num_colors)
        while y == x:
            y = random.randrange(num_colors)
        return [COLORS_LIST[x], COLORS_LIST[y], COLORS_LIST[x], COLORS_LIST[y]]

    def turn_on_buzzer_cubes_different(self):
        ''' one line summary

        Args:

        Returns:

        '''
        player_cube_colors = self.random_buzzer_colors()
        cozmo_cube_colors = self.random_buzzer_colors()
        while player_cube_colors == cozmo_cube_colors:
            cozmo_cube_colors = self.random_buzzer_colors()
        self.player.cube.set_light_corners(*player_cube_colors)
        self.cozmo_player.cube.set_light_corners(*cozmo_cube_colors)

    def turn_on_buzzer_cubes_red(self):
        ''' one line summary

        Args:

        Returns:

        '''
        self.player.cube.set_lights(cozmo.lights.red_light)
        self.cozmo_player.cube.set_lights(cozmo.lights.red_light)

    def turn_off_buzzer_cubes(self):
        ''' one line summary

        Args:

        Returns:

        '''
        self.player.cube.set_lights_off()
        self.cozmo_player.cube.set_lights_off()

    def report_scores(self):
        ''' one line summary

        Args:

        Returns:

        '''
        print("Player score: {}".format(self.player.score))
        print("Cozmo score: {}".format(self.cozmo_player.score))

    async def report_winner(self):
        ''' one line summary

        Args:

        Returns:

        '''
        print("---------------------------------------------------")
        print("You won {} rounds".format(self.player.score))
        print("Cozmo won {} rounds".format(self.cozmo_player.score))
        if self.cozmo_player.score > self.player.score:
            print("~COZMO WINS QUICK TAP~")
            await self.robot.play_anim_trigger(cozmo.anim.Triggers.OnSpeedtapCozmoWinHighIntensity).wait_for_completed()
        else:
            print("~PLAYER WINS QUICK TAP~")
            await self.robot.play_anim_trigger(cozmo.anim.Triggers.OnSpeedtapPlayerWinHighIntensity).wait_for_completed()
        print("---------------------------------------------------")


class QuickTapPlayer():
    ''' one line summary

    Args:

    '''
    def __init__(self):
        self.cube = None
        self.score = 0
        self.has_tapped = False
        self.name = "Player"
        self.elapsed_tap_time = None
        self.won_round = False

    def wins_round(self):
        ''' one line summary

        Args:

        Returns:

        '''
        print("{} wins the round".format(self.name))
        self.score += 1
        self.won_round = True

    def reset(self):
        ''' one line summary

        Args:

        Returns:

        '''
        self.elapsed_tap_time = sys.maxsize
        self.has_tapped = False
        self.won_round = False

    def register_tap(self,round_start_time):
        ''' one line summary

        Args:

        Returns:

        '''
        self.elapsed_tap_time = time.time() - round_start_time
        self.has_tapped = True

class CozmoQuickTapPlayer(QuickTapPlayer):
    ''' one line summary of this class 
        
        Args: robot (cozmo.robot.Robot): passed in from the QuickTapGame class
    '''
    def __init__(self,robot: cozmo.robot.Robot):
        super().__init__()
        self.robot = robot
        self.accuracy_rate = 0.9
        self.name = "Cozmo"

    async def select_cube(self):
        ''' Cozmo looks for a cube, drives to it, and taps it'''
        self.cube = await self.robot.world.wait_for_observed_light_cube()
        self.cube.set_lights(cozmo.lights.white_light)
        await asyncio.sleep(2)
        self.cube.start_light_chaser()
        await self.robot.set_lift_height(1.0).wait_for_completed()
        await self.robot.go_to_object(self.cube,distance_mm(40)).wait_for_completed()
        await self.robot.play_anim_trigger(cozmo.anim.Triggers.OnSpeedtapTap).wait_for_completed()
        self.cube.stop_light_chaser()

    async def determine_move(self,buzzer_display_type):
        ''' one line summary

        Args:

        Returns:

        '''
        await self.hesitate()
        probability_correct = random.random()
        if probability_correct < self.accuracy_rate:
            if buzzer_display_type == BUZZER_SAME:
                await self.tap()
            else:
                await self.not_tap()
        else:
            if buzzer_display_type == BUZZER_RED or buzzer_display_type == BUZZER_DIFFERENT:
                await self.tap()
            else:
                await self.not_tap()

    async def hesitate(self):
        ''' one line summary

        Args:

        Returns:

        '''
        delay = random.random()*.5
        await asyncio.sleep(delay)

    async def tap(self):
        ''' one line summary

        Args:

        Returns:

        '''
        await self.robot.play_anim_trigger(cozmo.anim.Triggers.OnSpeedtapTap).wait_for_completed()

    async def not_tap(self):
        ''' one line summary

        Args:

        Returns:

        '''
        probability_fakeout = random.random()
        if probability_fakeout < 0.5:
            await self.robot.play_anim_trigger(cozmo.anim.Triggers.OnSpeedtapFakeout).wait_for_completed()
        else:
            await self.robot.play_anim_trigger(cozmo.anim.Triggers.OnSpeedtapIdle).wait_for_completed()


class BlinkyCube(cozmo.objects.LightCube):
    ''' Same as a normal cube, plus method to display moving rotating rainbow lights.

        Args: same arguments as cozmo.objects.LightCube
    '''
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self._chaser = None

    def start_light_chaser(self):
        ''' rotates four colors around the cube light corners in a continuous loop'''
        if self._chaser:
            raise ValueError("Light chaser already running")
        async def _chaser():
            rainbow_colors = [cozmo.lights.blue_light,cozmo.lights.red_light,cozmo.lights.green_light,cozmo.lights.white_light]
            while True:
                for i in range(4):
                    self.set_light_corners(*rainbow_colors)
                    await asyncio.sleep(0.1, loop = self._loop)
                    light = rainbow_colors.pop(0)
                    rainbow_colors.append(light)
        self._chaser = asyncio.ensure_future(_chaser(), loop = self._loop)

    def stop_light_chaser(self):
        ''' one line summary

        Args:

        Returns:

        '''
        if self._chaser:
            self._chaser.cancel()
            self._chaser = None
        self.set_lights_off()

    async def countdown(self):
        ''' Sets all lights, then 3, then 2, then 1, then 0.'''
        self.set_light_corners(cozmo.lights.green_light, cozmo.lights.green_light, cozmo.lights.green_light, cozmo.lights.green_light)
        await asyncio.sleep(.5)
        self.set_light_corners(cozmo.lights.green_light, cozmo.lights.green_light, cozmo.lights.green_light, cozmo.lights.off_light)
        await asyncio.sleep(.5)
        self.set_light_corners(cozmo.lights.green_light, cozmo.lights.green_light, cozmo.lights.off_light, cozmo.lights.off_light)
        await asyncio.sleep(.5)
        self.set_light_corners(cozmo.lights.green_light, cozmo.lights.off_light, cozmo.lights.off_light, cozmo.lights.off_light)
        await asyncio.sleep(.5)
        self.set_light_corners(cozmo.lights.off_light, cozmo.lights.off_light, cozmo.lights.off_light, cozmo.lights.off_light)
        await asyncio.sleep(.5)

# Make sure World knows how to instantiate the BlinkyCube subclass
cozmo.world.World.light_cube_factory = BlinkyCube

async def cozmo_program(robot: cozmo.robot.Robot):
    game = QuickTapGame(robot)
    await game.run()

cozmo.run_program(cozmo_program)