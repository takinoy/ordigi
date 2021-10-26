from tabulate import tabulate


class Summary:
    def __init__(self, path):
        self.actions = (
            'check',
            'import',
            'remove_empty_folders',
            'remove_excluded',
            'sort',
            'update',
        )
        self.path = path
        self.result = {}
        for action in self.actions:
            self.result[action] = 0

        self.errors = 0
        self.errors_items = []

    def append(self, row):
        file_path, action = row

        if action:
            for m in self.actions:
                if action == m:
                    self.result[action] += 1
        else:
            self.errors += 1
            if file_path:
                self.errors_items.append(file_path)

    def print(self):

        print()
        for action in self.result:
            nb = self.result[action]
            if self.result[action] != 0:
                if action == 'check':
                    print(f"SUMMARY: {nb} files checked in {self.path}.")
                elif action == 'import':
                    print(f"SUMMARY: {nb} files imported into {self.path}.")
                elif action == 'sort':
                    print(f"SUMMARY: {nb} files sorted inside {self.path}.")
                elif action == 'remove_excluded':
                    print(f"SUMMARY: {nb} files deleted in {self.path}.")
                elif action == 'remove_empty_folders':
                    print(f"SUMMARY: {nb} empty folders removed in {self.path}.")
                elif action == 'update':
                    print(f"SUMMARY: {nb} files updated in {self.path} database.")

        if sum(self.result.values()) == 0 and not self.errors:
            print(f"SUMMARY: no file imported, sorted or deleted from {self.path}.")

        if self.errors > 0:
            print()
            errors_headers = [f"ERROR: {self.errors} errors reported in files:"]
            errors_result = []
            for path in self.errors_items:
                errors_result.append([path])

            print(tabulate(errors_result, headers=errors_headers))
            print()
