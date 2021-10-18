from tabulate import tabulate


class Summary:

    def __init__(self):
        self.modes = ('record', 'copy', 'move', 'delete')
        self.result = {}
        for mode in self.modes:
            self.result[mode] = 0

        self.errors = 0
        self.errors_items = []

    def append(self, row):
        file_path, mode = row

        if mode:
            for m in self.modes:
                if mode == m:
                    self.result[mode] += 1
        else:
            self.errors += 1
            self.errors_items.append(file_path)

    def print(self):

        print()
        for mode in self.result:
            nb = self.result[mode]
            if self.result[mode] != 0:
                if mode == 'record':
                    print(f"SUMMARY: {nb} files recorded.")
                elif mode == 'copy':
                    print(f"SUMMARY: {nb} files copied.")
                elif mode == 'move':
                    print(f"SUMMARY: {nb} files moved.")
                else:
                    print(f"SUMMARY: {nb} files deleted.")
        if sum(self.result.values()) == 0 and not self.errors:
            print(f"OK !!")

        if self.errors > 0:
            print()
            errors_headers = [f"ERROR: {self.errors} errors reported in files:"]
            errors_result = []
            for path in self.errors_items:
                errors_result.append([path])

            print(tabulate(errors_result, headers=errors_headers))
            print()

