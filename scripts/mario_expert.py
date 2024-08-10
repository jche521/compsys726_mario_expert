"""
This the primary class for the Mario Expert agent. It contains the logic for the Mario Expert agent to play the game and choose actions.

Your goal is to implement the functions and methods required to enable choose_action to select the best action for the agent to take.

Original Mario Manual: https://www.thegameisafootarcade.com/wp-content/uploads/2017/04/Super-Mario-Land-Game-Manual.pdf
"""

import json
import logging
import random
from argparse import Action

import cv2
from mario_environment import MarioEnvironment
from pyboy.utils import WindowEvent


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
        valid_actions: list[WindowEvent] = [
            WindowEvent.PRESS_ARROW_DOWN,
            WindowEvent.PRESS_ARROW_LEFT,
            WindowEvent.PRESS_ARROW_RIGHT,
            WindowEvent.PRESS_ARROW_UP,
            WindowEvent.PRESS_BUTTON_A,
            WindowEvent.PRESS_BUTTON_B,
        ]

        release_button: list[WindowEvent] = [
            WindowEvent.RELEASE_ARROW_DOWN,
            WindowEvent.RELEASE_ARROW_LEFT,
            WindowEvent.RELEASE_ARROW_RIGHT,
            WindowEvent.RELEASE_ARROW_UP,
            WindowEvent.RELEASE_BUTTON_A,
            WindowEvent.RELEASE_BUTTON_B,
        ]

        self.valid_actions = valid_actions
        self.release_button = release_button

    def run_action(self, action: int) -> None:
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
    def __init__(self, results_path: str, headless=False):
        self.results_path = results_path

        self.environment = MarioController(headless=headless)

        self.video = None

    def get_mario_pos(self, game_area):
        for i in range(len(game_area)):
            for j in range(len(game_area[i])):
                if game_area[i][j] == 1:
                    return j+1, i+1

    def check_infront_clear(self, x, y, game_area) -> bool:
        if game_area[y][x+1] != 0 or game_area[y-1][x+1] != 0 or game_area[y][x+2] != 0 or game_area[y-1][x+2] != 0:
            return False
        return True

    def check_infront_hole(self, x, y, game_area) -> bool:
        if game_area[15][x+1] == 0 or game_area[15][x+2] == 0:
            return True
        return False
    def check_powerup(self, x,y,game_area) -> bool:
        for i in range(y-5, y):
            if game_area[i][x+1] == 13 or game_area[i][x] == 13:
                return True
        return False

    def check_up_clear(self, x, y, game_area) -> bool:
        for i in range(1, 5):
            if game_area[y - i][x + 3] == 15 or game_area[y - i][x + 2] == 15:
                return False
        return True

    def choose_action(self):
        state = self.environment.game_state()
        frame = self.environment.grab_frame()
        game_area = self.environment.game_area()
        x, y = self.get_mario_pos(game_area)
        print(game_area, x, y)

        # if self.check_infront_clear(x, y, game_area):
        #     if self.check_powerup(x, y, game_area):
        #         print("power up - jump, right")
        #         self.actions.append(4)  # Jump
        #         self.actions.append(2)  # Right
        #     else:
        #         print("in front clear - right")
        #         self.actions.append(2)  # Right
        # else:
        #     if self.check_up_clear(x, y, game_area):
        #         print("front not clear up clear - jump")
        #         self.actions.append(4)  # Jump
        #     else:
        #         print("front not clear up not clear - left, right, jump")
        #         self.actions.extend([1,1,1, 2, 2, 4])  # Left, Right, Jump

        if self.check_infront_clear(x, y, game_area) == False:
            print("Infront is not clear")
            self.actions.append(4)
        elif self.check_infront_hole(x,y,game_area):
            print("Infront is a hole")
            if y > 6:
                self.actions.append(4)
            else:
                self.actions.append(2)
        elif self.check_up_clear(x, y, game_area) == False:
            print("Up is not clear")
            self.actions.extend([1, 1, 1, 2, 4, 2])
        elif self.check_powerup(x, y, game_area):
            print("grabbing powerup")
            self.actions.extend([4,2])
        else:
            print("not defined")

            self.actions.append(2)  # Right
    def step(self):
        """
        Modify this function as required to implement the Mario Expert agent's logic.

        This is just a very basic example
        """

        # Choose an action - button press or other...
        if len(self.actions) == 0:
            self.choose_action()

        # Run the action on the environment
        print("before",self.actions)
        self.environment.run_action(self.actions.pop(0))
        print("after",self.actions)




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
