"""Entry point.

  - without arguments: opens the graphical game window.
  - with the argument "demo": runs a small console demo of the split-level weighting.
"""

from __future__ import annotations

import sys

from .model.game_state import GameState
from .model.task import focus_multiplier
from .persist.save_manager import SaveManager


def main():
    if len(sys.argv) > 1 and sys.argv[1].lower() == "demo":
        run_split_demo()
        return
    launch_game()


def launch_game():
    # Start pygame + audio. The mixer is set to mono / 16-bit to match the tones
    # we synthesise. Without an audio device it still runs (just silent).
    import pygame

    pygame.init()
    try:
        pygame.mixer.init(frequency=44100, size=-16, channels=1)
    except pygame.error:
        pass  # no audio device -> sound stays silent

    from .ui.game_window import launch

    # Load the save game: gold + open tasks go into the GameState, the Tycoon
    # progress is applied later when the map is built (inside the game window).
    save_manager = SaveManager()
    saved = save_manager.load()

    starting_gold = saved.gold if saved is not None else 0
    game = GameState("Player1", starting_gold)
    if saved is not None:
        saved.apply_quests(game)

    launch(game, save_manager, saved)


# ---------- console demo of the split-level weighting ----------

def run_split_demo():
    print("=== Focus Tycoon - split-level weighting (demo) ===")
    print("Same task, different split levels.\n")

    task_text = "Prepare a biology presentation"
    _run_one_demo(task_text, 1, "FINE  (many tiny steps)")
    _run_one_demo(task_text, 3, "COARSE  (few big chunks)")

    print("Note: this console demo needs a Gemini API key in .env, because the")
    print("offline fallback was removed on purpose.")


def _run_one_demo(task_text, level, label):
    print("------------------------------------------------------------------")
    print(f'Input: "{task_text}"')
    print(f"Split level {level}  ->  {label}")
    print("------------------------------------------------------------------")

    game = GameState("DemoPlayer", 0)
    try:
        quest = game.process_new_task(task_text, "", level)
    except Exception as error:
        print(f"  (AI not available: {error})\n")
        return

    total = 0
    for task in quest.get_stages():
        print(f"  - {task.title:<32} {task.estimated_minutes:>2} min  "
              f"x{focus_multiplier(task.energy_level):.1f}  =  {task.gold_reward:>4} gold")
        total += task.gold_reward
    print(f"\n  => Quest with {quest.get_stage_count()} stages, {total} gold in total.")

    recommendation = game.recommend_next_task()
    if recommendation is not None:
        print(f'  Recommendation first: "{recommendation.title}" '
              f"({recommendation.estimated_minutes} min)\n")


if __name__ == "__main__":
    main()
