"""
This the primary class for the Mario Expert agent. It contains the logic for the Mario Expert agent to play the game and choose actions.

Your goal is to implement the functions and methods required to enable choose_action to select the best action for the agent to take.

Original Mario Manual: https://www.thegameisafootarcade.com/wp-content/uploads/2017/04/Super-Mario-Land-Game-Manual.pdf
"""

import json
import logging
import random
from argparse import Action
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
                    return i+2
        return -1

    def get_mario_in_game_area(self):
        game_area = self.game_area()
        for i in range(len(game_area)):
            for j in range(len(game_area[0])):
                if game_area[i][j] == 1:
                    return Coordinate(j+1, i+1)
        return -1

    def is_mario_jumping(self):
        on_ground_flag = self._read_m(0xC20A)
        return on_ground_flag == 0x00

    def is_colliding(self, obj_pos: Coordinate) -> bool:
        mario_pos = self.get_mario_pos()
        print(f"Checking collision: Mario({mario_pos.x}, {mario_pos.y}), Enemy({obj_pos.x}, {obj_pos.y})")
        x_collision = abs(mario_pos.x - obj_pos.x) < 35  # Distance threshold
        y_collision = abs(mario_pos.y - obj_pos.y) < 20  # Add y-check if necessary
        return x_collision and y_collision

    def is_front_clear(self) -> bool:
        game_area = self.game_area()
        ground_y = self.get_ground_y()
        print("y:", ground_y)
        if game_area[ground_y-1][11] != 0 or game_area[ground_y-2][11] != 0:
            return False
        return True

    def is_down_clear(self) -> bool:
        game_area = self.game_area()
        if game_area[15][10] == 0:
            return True
        return False

    def is_up_clear(self) -> bool:
        game_area = self.game_area()
        ground_y = self.get_ground_y()
        print("y:", ground_y)
        for i in range(1, 5):
            if game_area[ground_y - i][14] == 15 or game_area[ground_y - i][13] == 15:
                return False
        return True

    def can_jump(self) -> bool:
        game_area = self.game_area()

        if self.is_mario_jumping(): # mario is in air, cannot jump
            return False
        # check up if theres enemy
        if not self.is_up_clear():
            return False
        return True

    # new stuff here
    def is_obstacle_ahead_in_distance(self, distance) -> bool:
        game_area = self.game_area()
        mario_pos = self.get_mario_in_game_area()
        if mario_pos == -1:
            return False
        for i in range(distance):
            if game_area[mario_pos.y-1][mario_pos.x+i] == 10 or game_area[mario_pos.y][mario_pos.x+i] == 10 or game_area[mario_pos.y-1][mario_pos.x+i] == 14 or game_area[mario_pos.y][mario_pos.x+i] == 14:
                return True
        return False
    def is_obstacle_ahead(self) -> bool:
        game_area = self.game_area()
        mario_pos = self.get_mario_in_game_area()
        if mario_pos == -1:
            return False
        if game_area[mario_pos.y-1][mario_pos.x+3] == 10 or game_area[mario_pos.y][mario_pos.x+3] == 10 or game_area[mario_pos.y-1][mario_pos.x+2] == 14 or game_area[mario_pos.y][mario_pos.x+2] == 14:
            return True
        return False

    def is_gap_ahead(self) -> bool:
        game_area = self.game_area()
        mario_pos = self.get_mario_in_game_area()
        for i in range(3):
            if game_area[15][mario_pos.x+i] == 0:
                return True
        return False

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
                    print("height:", height)
                    return height
            found_obstacle = False

    def run_action(self, action: str) -> None:
        """
        This is a very basic example of how this function could be implemented

        As part of this assignment your job is to modify this function to better suit your needs

        You can change the action type to whatever you want or need just remember the base control of the game is pushing buttons
        """

        # Simply toggles the buttons being on or off for a duration of act_freq
        self.pyboy.send_input(self.valid_actions[action])

        for _ in range(self.act_freq):
            self.pyboy.tick()

        self.pyboy.send_input(self.release_button[action])


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
    past_enemies = []

    def __init__(self, results_path: str, headless=False):
        self.results_path = results_path

        self.environment = MarioController(headless=headless)

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
            if abs(mario_pos.y - enemy.y) <= 5 and abs(mario_pos.x - enemy.x) <= safety_distance:
                print(f"enemy at front {mario_pos}")
                return True
        return False

    def is_moving_enemy_front(self, mario_pos: Coordinate):
        game_area = self.environment.game_area()
        mario_pos = self.environment.get_mario_in_game_area()

        for i in range(3):
            for j in range(3):
                if game_area[mario_pos.y-i][mario_pos.x + j] == 18:
                    return True
        return False

    def is_enemy_up(self, mario_pos: Coordinate, safety_distance: int):
        for enemy in self.enemies:
            if enemy.y < mario_pos.y and enemy.x - mario_pos.x <= safety_distance:
                print(f"enemy at top {mario_pos}")
                return True
        return False

    def choose_action(self):
        frame = self.environment.grab_frame()
        game_area = self.environment.game_area()
        print(game_area)

        # Get Mario's position
        coord = self.environment.get_mario_pos()
        mario_x = self.environment.game_state()["x_position"]
        mario_y = coord.y
        print("Mario position (x, y):", coord.x, mario_y)

        # Store enemies pos if near
        self.is_enemy_near()
        print(self.enemies)
        if self.is_enemy_front(coord, 40):
            self.actions.append("jump")
        elif self.environment.is_obstacle_ahead_in_distance(4): # if there is obstacle ahead
            if self.is_enemy_up(coord, 40): # check if theres enemy at the top
                print("enemy up")
                self.actions.extend(["left", "left"])
            elif self.environment.is_obstacle_ahead_in_distance(2): # when reach the obstacle
                if self.environment.get_obstacle_height() > 3:
                    print("obstacle too high")
                    self.actions.extend(["left", "left", "right", "jump"])
                else:
                    print("obstacle jumpable")
                    self.actions.extend(["jump", "right"])
            else:
                self.actions.append("right")
        elif self.is_moving_enemy_front(coord):
            print("beeeeeeeeeee")
            self.actions.append("jump")
        elif self.environment.is_gap_ahead():
            print("gap_ahead")
            self.actions.append("jump")

        else:
            print("fuck")
            self.actions.append("right")

        self.enemies = []
        # for all enemies that are near
        # for enemy in self.enemies:
        #     if self.environment.is_colliding(Coordinate(enemy.x, enemy.y)):  # check if enemy will collide with mario
        #         print(f"Collision detected with enemy {enemy.y}, {mario_y}")
        #         if enemy.y > mario_y:
        #             if not self.environment.can_jump():
        #                 self.actions.extend(["left", "right", "jump", "right"])
        #             else:
        #                 self.actions.append("jump")
        #         else:
        #             self.actions.append("jump")
        #         self.past_enemies.append(enemy)
        #
        # # remove enemy that is already passed
        # self.enemies = [enemy for enemy in self.enemies if enemy not in self.past_enemies]
        #
        # if not self.environment.is_front_clear():
        #     print("Obstacle ahead, jump")
        #     self.actions.append("jump")
        #     self.actions.append("right")
        # elif self.environment.is_down_clear() and self.environment.get_ground_y() > 10:
        #     self.actions.append("jump")
        #     self.actions.append("right")
        # else:
        #     print("No collision, moving right.")
        #     self.actions.append("right")





    def step(self):
        """
        Modify this function as required to implement the Mario Expert agent's logic.

        This is just a very basic example
        """

        # Choose an action - button press or other...
        if len(self.actions) == 0:
            self.choose_action()
        else:
            print(self.actions)
            self.environment.run_action(self.actions.pop(0))

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
