from aiogram.fsm.state import State, StatesGroup


class CreateNight(StatesGroup):
    date = State()
    location = State()
    is_free = State()          # NEW
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


class PollTime(StatesGroup):
    picking_from = State()
    picking_to = State()


class AddGame(StatesGroup):
    title = State()
    players = State()
    duration = State()
    subscriber_only = State()