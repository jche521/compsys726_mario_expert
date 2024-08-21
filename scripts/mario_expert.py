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
    NOKOBON = 0x03


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
            act_freq: int = 10,
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
        }

        release_button: dict[str, WindowEvent] = {
            "down": WindowEvent.RELEASE_ARROW_DOWN,
            "left": WindowEvent.RELEASE_ARROW_LEFT,
            "right": WindowEvent.RELEASE_ARROW_RIGHT,
            "up": WindowEvent.RELEASE_ARROW_UP,
            "jump": WindowEvent.RELEASE_BUTTON_A,
            "slide": WindowEvent.RELEASE_BUTTON_B,
        }

        self.valid_actions = valid_actions
        self.release_button = release_button

    def get_mario_pos(self):
        mario_x = self._read_m(0xC202)
        mario_y = self._read_m(0xC201)

        return Coordinate(mario_x+1, mario_y+1)

    def get_obj_pos(self, req_obj_type):
        MARIO_OBJ_TABLE = 0xD100
        OBJ_SIZE = 0x0b
        for i in range(10):  # object table stores up to 10 object
            obj_addr = MARIO_OBJ_TABLE + (i * OBJ_SIZE)  # get the object address stored in table
            obj_type = self._read_m(obj_addr)  # get object type associated with the object
            if obj_type == req_obj_type:  # if matched, then return the current position of the object
                y = self._read_m(obj_addr + 2)
                x = self._read_m(obj_addr + 3)
                return Coordinate(x, y-1)
        return Coordinate(0, 0)



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

    def is_colliding(self, obj_pos: Coordinate) -> bool:
        mario_pos = self.environment.get_mario_pos()
        print(f"Checking collision: Mario({mario_pos.x}, {mario_pos.y}), Enemy({obj_pos.x}, {obj_pos.y})")
        x_collision = abs(mario_pos.x - obj_pos.x) < 10  # Distance threshold
        y_collision = abs(mario_pos.y - obj_pos.y) < 10  # Add y-check if necessary
        return x_collision and y_collision

    def is_enemy_near(self):
        for enemy in EnemyMap:
            pos = self.environment.get_obj_pos(enemy.value)  # get object position if it is stored in the next 10 objects

            if pos.x != 0 and pos.y != 0:
                print(enemy, pos)
                self.enemies.append(pos)

    def choose_action(self):
        frame = self.environment.grab_frame()
        game_area = self.environment.game_area()
        print(game_area)

        # Get Mario's position
        coord = self.environment.get_mario_pos()
        mario_x = self.environment.game_state()["x_position"]
        mario_y = coord.y
        print("Mario position (x, y):", mario_x, mario_y)

        # Store enemies pos if near
        self.is_enemy_near()

        # for all enemies that are near
        for enemy in self.enemies:
            if self.is_colliding(Coordinate(enemy.x, enemy.y)): # check if enemy will collide with mario
                print("Collision detected with enemy.")
                self.actions.append("jump")
                self.past_enemies.append(enemy)

        self.enemies = [enemy for enemy in self.enemies if enemy not in self.past_enemies]

        print("No collision, moving right.")
        self.actions.append("right")

    def step(self):
        """
        Modify this function as required to implement the Mario Expert agent's logic.

        This is just a very basic example
        """

        # Choose an action - button press or other...
        if len(self.actions) == 0:
            self.choose_action()
        else:
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
