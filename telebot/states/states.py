from aiogram.fsm.state import State, StatesGroup


class CreateNight(StatesGroup):
    date = State()              # оставим для обратной совместимости, но не используем
    location = State()
    searching_game = State()
    picking_game = State()
    time_start = State()
    time_end = State()
    slots = State()


class EditNight(StatesGroup):
    new_date = State()
    new_location = State()


class AddSessionToNight(StatesGroup):
    searching_game = State()
    picking_game = State()
    time_start = State()
    time_end = State()
    slots = State()