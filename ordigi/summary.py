# import pandas as pd
from tabulate import tabulate

class Tables:
    """Create table and display result in Pandas DataFrame"""

    def __init__(self, actions):
        self.actions = actions

        self.table = []

        self.columns = ['action', 'file_path', 'dest_path']
        # self.df = self.dataframe()

    def append(self, action, file_path=None, dest_path=None):
        row = (action, file_path, dest_path)
        self.table.append(row)

    def sum(self, action=None):
        if not action:
            return len(self.table)

        count = 0
        for row in self.table:
            if row[0] == action:
                count += 1

        return count

    # def dataframe(self):
    #     return pd.DataFrame(self.table, columns=self.columns)

    def tabulate(self):
        errors_headers = self.columns
        return tabulate(self.table, headers=errors_headers)

class Summary:
    """Result summary of ordigi program call"""

    def __init__(self, root):
        self.actions = (
            'check',
            'import',
            'remove',
            'sort',
            'update',
        )

        # Set labels
        self.state = ['success', 'errors']
        self.root = root
        self.success_table = Tables(self.actions)
        self.errors_table = Tables(self.actions)
        self.errors = 0

    def append(self, action, success, file_path=None, dest_path=None):
        if action:
            if success:
                self.success_table.append(action, file_path, dest_path)
            else:
                self.errors_table.append(action, file_path, dest_path)

        if not success:
            self.errors +=1

    def print(self):
        """Print summary"""

        print()
        for action in self.actions:
            nb = self.success_table.sum(action)
            if nb != 0:
                if action == 'check':
                    print(f"SUMMARY: {nb} files checked in {self.root}.")
                elif action == 'import':
                    print(f"SUMMARY: {nb} files imported into {self.root}.")
                elif action == 'sort':
                    print(f"SUMMARY: {nb} files sorted inside {self.root}.")
                elif action == 'remove_excluded':
                    print(f"SUMMARY: {nb} files deleted in {self.root}.")
                elif action == 'remove_empty_folders':
                    print(f"SUMMARY: {nb} empty folders removed in {self.root}.")
                elif action == 'update':
                    print(f"SUMMARY: {nb} files updated in {self.root} database.")

        success = self.success_table.sum()
        if not success and not self.errors:
            print(f"SUMMARY: no action done in {self.root}.")

        errors = self.errors_table.sum()
        if errors:
            print()
            print(f"ERROR: {errors} errors reported for files:")
            print(self.success_table.tabulate())

        elif self.errors:
            print(f"ERROR: {errors} errors reported.")
