import inquirer
from blessed import Terminal

term = Terminal()

# TODO allow exit from inquierer prompt

# TODO fix 'opening_prompt_color': term.yellow,
def load_theme():
    """
    Customize inquirer
    source:https://github.com/magmax/python-inquirer/blob/master/inquirer/themes.py
    """
    custom_theme = {
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



# def edit_prompt(self, key: str, value: str) -> str:
#         print(f"Date conflict for file: {self.file_path}")
#         choices_list = [
#             inquirer.List(
#                 'edit',
#                 message=f"Edit '{key}' metadata",
#                 choices = [
#                     (f"{key}: '{value}'", value),
#                     ("custom", None),
#                 ],
#                 default=value,
#             ),
#         ]
#         answers = inquirer.prompt(choices_list, theme=self.theme)

#         if not answers['edit']:
#             prompt = [
#                 inquirer.Text('edit', message="value"),
#             ]
#             answers = inquirer.prompt(prompt, theme=self.theme)
#             return self.get_date_format(answers['edit'])
#         else:
#             return answers['date_list']


#     choices = [
#         (f"date original:'{date_original}'", date_original),
#         (f"date filename:'{date_filename}'", date_filename),
#         ("custom", None),
#     ]
#     default = f'{date_original}'
#     return self._get_date_media_interactive(choices, default)
