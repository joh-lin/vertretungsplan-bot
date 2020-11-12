import requests
from bs4 import BeautifulSoup
import datetime as dtime
import json


class Stundenplan:
    def __init__(self, name):
        self.name = name
        if not type(name) is list:
            raise Exception("Non Tuple object passed as name")
        self.plan = {}
        try:
            self.load_from_file()
        except FileNotFoundError:
            self.update()
            self.save_to_file()

    def load_from_file(self):
        print("Stundenplan: loading from file.")
        with open("plaene/" + self.name[0] + str(self.name[1]) + ".json", "r") as f:
            self.plan = json.loads(f.read())

    def save_to_file(self):
        with open("plaene/" + self.name[0] + str(self.name[1]) + ".json", "w+") as f:
            f.write(json.dumps(self.plan))

    @staticmethod
    def download_page(name):
        print(f"Downloading timetable for {name}")
        login_payload = {
            "group": "LEV-LLG",
            "grouplogin": "LLG",
            "grouppw": "llg",
            "group_check": "Anmelden"
        }
        search_payload = {
            "search": name[0],
            "wochewahl": "A"
        }
        # download page
        html = ""
        with requests.Session() as session:
            post = session.post("https://selbstlernportal.de/html/planinfo/planinfo_login.inc.php", data=login_payload)
            post = session.post("https://selbstlernportal.de/html/planinfo/planinfo_start.php?ug=lev-llg",
                                data=search_payload)
            if name[1] != 0:
                post = session.get(f"https://selbstlernportal.de/html/planinfo/planinfo_start.php?ug=lev-llg&wochewahl=A&dbidx={name[1]}",)
        return post.content

    @staticmethod
    def check_name(name):
        if type(name) is str:
            name = [name, 0]
        page = Stundenplan.download_page(name)
        soup = BeautifulSoup(page, "html.parser")

        if "Keine Objekte gefunden" in str(page) or "Zu viele" in str(page):  # invalid name
            print("keine objekte gefunden")
            return [], []
        table_header = soup.find("table", attrs={'class': 'plan'}).find('th')
        if table_header.text == "A-Woche-Stundenplan von ":  # name not found
            try:
                form = soup.find('form', attrs={'name': 'quicksearch'})
                options = form.find_all('option')
                return [o.text for o in options[1:]], [o['value'] for o in options[1:]]
            except:
                return [], []
        else:
            return [name[0]], [0]

    def update(self):
        plan = {}
        html = self.download_page(self.name)

        # extract table
        data_a = []
        data_b = []
        soup = BeautifulSoup(html, 'html.parser')
        table = soup.find('table', attrs={'class': 'plan'})
        tbody_a = table.find_all('tbody')[0]
        tbody_b = table.find_all('tbody')[1]

        # tbody A
        rows = tbody_a.find_all('tr')
        for row in rows:
            cols = row.find_all('td')
            cols = [ele.text.strip() for ele in cols]
            data_a.append(cols)
            for i in range(len(cols)):
                if cols[i] == "":
                    cols[i] = "---"

        # body B
        rows = tbody_b.find_all('tr')
        for row in rows:
            cols = row.find_all('td')
            cols = [ele.text.strip() for ele in cols]
            for i in range(len(cols)):
                if cols[i] == "" or cols[i] == " ":
                    cols[i] = "---"

            data_b.append(cols)
        plan["A"] = data_a[:-3]
        plan["B"] = data_b[:-3]
        self.plan = plan
        return plan

    def get_day(self, date: dtime.date):
        weekday = date.weekday()
        if date.isocalendar()[1] % 2 == 0:  # even = A
            week = "A"
        else:  # odd = B
            week = "B"
        table = self.plan[week]
        subjects = []
        for row in table:
            subjects.append(row[weekday])
        return subjects

    def get_subjects(self):
        subjects = []
        for week in ("A", "B"):
            for row in self.plan[week]:
                for entry in row:
                    if entry != "---":
                        s = entry.split(" ")[1]
                        if s not in subjects:
                            subjects.append(s)
        return subjects


if __name__ == "__main__":
    names, values = Stundenplan.check_name(["gruber", 1295])
    print(names)
    print(values)
