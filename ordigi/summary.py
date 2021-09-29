from tabulate import tabulate


class Summary(object):

    def __init__(self):
        self.records = []
        self.success = 0
        self.error = 0
        self.error_items = []

    def append(self, row):
        id, status = row

        if status:
            self.success += 1
        else:
            self.error += 1
            self.error_items.append(id)

    def print(self):
        if self.error > 0:
            error_headers = ["File"]
            error_result = []
            for id in self.error_items:
                error_result.append([id])

            print('Errors details:')
            print(tabulate(error_result, headers=error_headers))
            print("\n")

        headers = ["Metric", "Count"]
        result = [
                    ["Success", self.success],
                    ["Error", self.error],
                 ]

        print()
        print('Summary:')
        print(tabulate(result, tablefmt="plain"))
