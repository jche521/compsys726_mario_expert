"""
This the primary class for the Mario Expert agent. It contains the logic for the Mario Expert agent to play the game and choose actions.

Your goal is to implement the functions and methods required to enable choose_action to select the best action for the agent to take.

Original Mario Manual: https://www.thegameisafootarcade.com/wp-content/uploads/2017/04/Super-Mario-Land-Game-Manual.pdf
"""

import json
import logging
from enum import Enum

import cv2
from mario_environment import MarioEnvironment
from pyboy.utils import WindowEvent
from dataclasses import dataclass

@dataclass
class Coordinate:
    x: int
    y: int

class EnemyMap(Enum):
    GOOMBA = 0x00
    NOKOBON = 0x04
    BEE = 0x29

class MarioController(MarioEnvironment):
    """
    The MarioController class represents a controller for the Mario game environment.

    You can build upon this class all you want to implement your Mario Expert agent.

    Args:
        act_freq (int): The frequency at which actions are performed. Defaults to 10.
        emulation_speed (int): The speed of the game emulation. Defaults to 0.
        headless (bool): Whether to run the game in headless mode. Defaults to False.
    """

    def __init__(
            self,
            act_freq: int = 15,
            emulation_speed: int = 1,
            headless: bool = False,
    ) -> None:
        super().__init__(
            act_freq=act_freq,
            emulation_speed=emulation_speed,
            headless=headless,
        )

        self.act_freq = act_freq

        # Example of valid actions based purely on the buttons you can press
        valid_actions: dict[str, WindowEvent] = {
            "down": WindowEvent.PRESS_ARROW_DOWN,
            "left": WindowEvent.PRESS_ARROW_LEFT,
            "right": WindowEvent.PRESS_ARROW_RIGHT,
            "up": WindowEvent.PRESS_ARROW_UP,
            "jump": WindowEvent.PRESS_BUTTON_A,
            "slide": WindowEvent.PRESS_BUTTON_B,
            "speed": WindowEvent.RELEASE_SPEED_UP,
        }

        release_button: dict[str, WindowEvent] = {
            "down": WindowEvent.RELEASE_ARROW_DOWN,
            "left": WindowEvent.RELEASE_ARROW_LEFT,
            "right": WindowEvent.RELEASE_ARROW_RIGHT,
            "up": WindowEvent.RELEASE_ARROW_UP,
            "jump": WindowEvent.RELEASE_BUTTON_A,
            "slide": WindowEvent.RELEASE_BUTTON_B,
            "speed": WindowEvent.RELEASE_SPEED_UP,
        }

        self.valid_actions = valid_actions
        self.release_button = release_button

    def get_mario_pos(self):
        mario_x = self._read_m(0xC202)
        mario_y = self._read_m(0xC201)

        return Coordinate(mario_x + 1, mario_y + 1)

    def get_obj_pos(self, req_obj_type):
        MARIO_OBJ_TABLE = 0xD100
        OBJ_SIZE = 0x0b

        for i in range(10):  # object table stores up to 10 object
            obj_addr = MARIO_OBJ_TABLE + (i * OBJ_SIZE)  # get the object address stored in table
            obj_type = self._read_m(obj_addr)  # get object type associated with the object
            if obj_type == req_obj_type:  # if matched, then return the current position of the object
                y = self._read_m(obj_addr + 2)
                x = self._read_m(obj_addr + 3)
                return Coordinate(x, y - 1)
        return Coordinate(0, 0)

    def get_ground_y(self):
        game_area = self.game_area()
        for i in range(len(game_area)):
            for j in range(len(game_area[0])):
                if game_area[i][j] == 1:
                    return i + 2
        return -1

    def get_mario_in_game_area(self):
        game_area = self.game_area()
        for i in range(len(game_area)):
            for j in range(len(game_area[0])):
                if game_area[i][j] == 1:
                    return Coordinate(j + 1, i + 1)
        return -1

    def is_mario_jumping(self):
        on_ground_flag = self._read_m(0xC20A)
        return on_ground_flag == 0x00

    def is_up_clear(self) -> bool:
        game_area = self.game_area()
        ground_y = self.get_ground_y()
        for i in range(1, 5):
            if game_area[ground_y - i][14] == 15 or game_area[ground_y - i][13] == 15:
                return False
        return True

    def can_jump(self) -> bool:
        game_area = self.game_area()

        if self.is_mario_jumping():  # mario is in air, cannot jump
            return False
        # check up if theres enemy
        if not self.is_up_clear():
            return False
        return True

    def get_obstacle_height(self) -> int:
        game_area = self.game_area()
        mario_pos = self.get_mario_in_game_area()
        height = 0
        found_obstacle = False
        for i in range(mario_pos.y, 0, -1):
            for j in range(mario_pos.x, len(game_area[0])):
                if game_area[i][j] == 10 or game_area[i][j] == 14:
                    found_obstacle = True
                    height += 1
                    break

                if not found_obstacle:
                    return height
            found_obstacle = False

    def run_action(self, action: str, tick_count=None) -> None:
        """
        This is a very basic example of how this function could be implemented

        As part of this assignment your job is to modify this function to better suit your needs

        You can change the action type to whatever you want or need just remember the base control of the game is pushing buttons
        """
        if tick_count is None:
            tick_count = self.act_freq

        # Simply toggles the buttons being on or off for a duration of act_freq
        self.pyboy.send_input(self.valid_actions[action])
        if action == "jump":
            self.pyboy.send_input(self.valid_actions["right"])

        for _ in range(tick_count):
            self.pyboy.tick()

        self.pyboy.send_input(self.release_button[action])
        if action == "jump":
            self.pyboy.send_input(self.valid_actions["right"])


class MarioExpert:
    """
    The MarioExpert class represents an expert agent for playing the Mario game.

    Edit this class to implement the logic for the Mario Expert agent to play the game.

    Do NOT edit the input parameters for the __init__ method.

    Args:
        results_path (str): The path to save the results and video of the gameplay.
        headless (bool, optional): Whether to run the game in headless mode. Defaults to False.
    """

    actions = []
    enemies = []
    above_ground = False
    stuck = False
    prevX = -1

    def __init__(self, results_path: str, headless=False):
        self.results_path = results_path
        self.environment = MarioController(headless=headless)
        self.game_area = self.environment.game_area()
        self.video = None

    def is_enemy_near(self):
        for enemy in EnemyMap:
            pos = self.environment.get_obj_pos(
                enemy.value)  # get object position if it is stored in the next 10 objects
            if pos.x != 0 and pos.y != 0:
                print(enemy, pos)
                self.enemies.append(pos)

    def is_enemy_front(self, mario_pos: Coordinate, safety_distance: int):
        for enemy in self.enemies:
            print(mario_pos, enemy)
            if abs(mario_pos.y - enemy.y) <= 5 and safety_distance >= enemy.x - mario_pos.x > 0:
                return True
        return False

    def is_moving_enemy_front(self, game_area, mario_pos: Coordinate):
        for i in range(-2, 4):
            for j in range(2, 9):
                print(f"index out of bound where?: {mario_pos.y - i} {mario_pos.x + j}")
                if game_area[mario_pos.y - i][mario_pos.x + j] == 18:
                    return True
        return False

    def is_enemy_up(self, mario_pos: Coordinate, safety_distance: int):
        for enemy in self.enemies:
            if enemy.y < mario_pos.y and enemy.x - mario_pos.x <= safety_distance:
                return True
        return False

    def is_enemy_below(self, game_area, mario_pos):
        for i in range(3):
            for j in range(5):
                if game_area[mario_pos.y + i][mario_pos.x + j] == 15:
                    return True
        return False

    def is_obstacle_ahead_in_distance(self, game_area, mario_pos, distance) -> bool:
        if mario_pos == -1:
            return False
        for i in range(distance):
            if game_area[mario_pos.y - 1][mario_pos.x + i] == 10 or game_area[mario_pos.y][mario_pos.x + i] == 10 or \
                    game_area[mario_pos.y - 1][mario_pos.x + i] == 14 or game_area[mario_pos.y][mario_pos.x + i] == 14:
                return True
        return False

    def is_gap_ahead(self, game_area, mario_pos) -> bool:
        for i in range(3):
            if game_area[15][mario_pos.x + i] == 0:
                return True
        return False

    def is_jumpable_block_ahead(self, game_area, mario_pos):
        if not self.environment.can_jump():
            return False
        if game_area[mario_pos.y - 3][mario_pos.x + 4] == 13 or game_area[mario_pos.y - 4][mario_pos.x + 3] == 13 or \
                game_area[mario_pos.y - 3][mario_pos.x + 4] == 12 or game_area[mario_pos.y - 4][
            mario_pos.x + 3] == 12 or game_area[mario_pos.y - 3][mario_pos.x + 4] == 10 or game_area[mario_pos.y - 4][
            mario_pos.x + 3] == 10 or game_area[mario_pos.y - 2][mario_pos.x + 3] == 10:
            return True
        return False

    def is_stair(self, game_area, mario_pos):
        if game_area[mario_pos.y - 1][mario_pos.x + 1] == 10:
            return True
        return False

    def is_stuck(self, game_area, mario_pos):
        if not self.environment.can_jump():
            return False
        if game_area[mario_pos.y - 1][mario_pos.x + 1] == 10 and game_area[mario_pos.y + 1][mario_pos.x + 1] == 10 and \
                game_area[mario_pos.y][mario_pos.x + 7] == 10:
            return True
        return False

    def is_block_ending(self, game_area, mario_pos):
        if game_area[mario_pos.y + 1][mario_pos.x + 2] == 0 or game_area[mario_pos.y + 1][mario_pos.x + 1] == 0 or \
                game_area[mario_pos.y + 1][mario_pos.x] == 0:
            return True
        return False

    def is_jump_safe(self, game_area, mario_pos):
        if not self.environment.can_jump():
            return False

        if game_area[mario_pos.y][mario_pos.x + 7] == 15 or game_area[mario_pos.y][mario_pos.x + 8] == 15 or game_area[mario_pos.y][mario_pos.x + 6] == 15:
            return False
        return True

    def choose_action(self):
        game_area = self.environment.game_area()

        # Get Mario's position
        coord = self.environment.get_mario_pos()
        mario_x = self.environment.game_state()["x_position"]
        mario_pos = self.environment.get_mario_in_game_area()

        tick_count = None

        # Store enemies pos if near
        self.is_enemy_near()
        print(game_area)
        print("enemies:  ", self.enemies)

        if mario_x >= 2450:
            self.actions.append("right")
        elif self.is_enemy_front(coord, 40):
            self.actions.append("jump")
            tick_count = 15
        elif self.stuck and self.is_stair(game_area, mario_pos):
            print("attempt to unstuck")
            self.actions.extend(["left", "jump"])
            self.stuck = False
        elif not self.stuck and self.is_stuck(game_area, mario_pos):
            self.actions.extend(["left"])
            print("stuck")
            tick_count = 30
            self.stuck = True
        elif self.is_moving_enemy_front(game_area, mario_pos):
            if self.is_jump_safe(game_area, mario_pos):
                print("bee jump safe")
                self.actions.extend(["jump"])
                tick_count = 15
            else:
                print("bee jump not safe")
                self.actions.append("left")
                tick_count = 30

        elif self.above_ground and self.is_block_ending(game_area, mario_pos):
            print("off block")
            self.actions.append("jump")
            tick_count = 20
        elif self.is_obstacle_ahead_in_distance(game_area, mario_pos, 4):
            if self.is_enemy_up(coord, 40):
                print("enemy up")
                self.actions.append("left")
                tick_count = 30
            elif self.is_obstacle_ahead_in_distance(game_area, mario_pos, 3):
                if self.environment.get_obstacle_height() > 3:
                    print("obstacle too high")
                    self.actions.append("left")
                    tick_count = 30
                else:
                    if self.is_jump_safe(game_area, mario_pos):
                        print("obstacle jump safe")
                        self.actions.extend(["jump", "right"])
                        tick_count = 30
                    else:
                        print("obstacle jump not safe")
                        self.actions.append("left")
                        tick_count = 10
            else:
                self.actions.append("right")
                tick_count = 15
        elif self.is_jumpable_block_ahead(game_area, mario_pos):
            print("on block")
            self.actions.extend(["jump"])
            self.above_ground = True
            tick_count = 15

        elif self.is_gap_ahead(game_area, mario_pos):
            print("gap ahead")
            self.actions.extend(["jump"])
            tick_count = 50
        elif self.is_enemy_below(game_area, mario_pos):
            print("smt below")
            self.actions.extend(["jump"])
            tick_count = 15

        else:
            print("clear ahead")
            self.actions.append("right")
            tick_count = 15

        self.enemies = []
        self.prevX = mario_pos.x
        self.above_ground = False

        return tick_count

    def step(self):
        """
        Modify this function as required to implement the Mario Expert agent's logic.

        This is just a very basic example
        """
        tick_count = None
        # Choose an action - button press or other...
        if len(self.actions) == 0:
            tick_count = self.choose_action()
        else:
            print(self.actions)
            self.environment.run_action(self.actions.pop(0), tick_count)

    def play(self):
        """
        Do NOT edit this method.
        """
        self.environment.reset()

        frame = self.environment.grab_frame()
        height, width, _ = frame.shape

        self.start_video(f"{self.results_path}/mario_expert.mp4", width, height)

        while not self.environment.get_game_over():
            frame = self.environment.grab_frame()
            self.video.write(frame)
            self.step()

        final_stats = self.environment.game_state()
        logging.info(f"Final Stats: {final_stats}")

        with open(f"{self.results_path}/results.json", "w", encoding="utf-8") as file:
            json.dump(final_stats, file)

        self.stop_video()

    def start_video(self, video_name, width, height, fps=30):
        """
        Do NOT edit this method.
        """
        self.video = cv2.VideoWriter(
            video_name, cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height)
        )

    def stop_video(self) -> None:
        """
        Do NOT edit this method.
        """
        self.video.release()
