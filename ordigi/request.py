import inquirer
from blessed import Terminal

term = Terminal()


def load_theme():
    custom_theme = {
        'List': {
            'opening_prompt_color': term.yellow,
        },
        'Question': {
            'brackets_color': term.dodgerblue4,
            'default_color': term.yellow,
        },
        'Checkbox': {
            'selection_icon': '❯',
            'selected_icon': '◉',
            'unselected_icon': '◯',
            'selection_color': term.bold_on_dodgerblue4,
            'selected_color': term.dodgerblue2,
            'unselected_color': term.yellow,
        },
        'List': {
            'selection_color': term.bold_on_dodgerblue4,
            'selection_cursor': '❯',
            'unselected_color': term.yellow,
        },
    }

    return inquirer.themes.load_theme_from_dict(custom_theme)
