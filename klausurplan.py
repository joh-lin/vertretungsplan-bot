import json
import requests
from bs4 import BeautifulSoup

from stundenplan import Stundenplan


class Klausurplan:
    def __init__(self):
        self.plan = {}
        try:
            self.load_from_file()
        except FileNotFoundError:
            self.update()
            self.save_to_file()

    def load_from_file(self):
        print("Klausurplan: loading from file.")
        with open("plaene/klausurplan.json", "r") as f:
            self.plan = json.loads(f.read())

    def save_to_file(self):
        with open("plaene/klausurplan.json", "w+") as f:
            f.write(json.dumps(self.plan))

    def update(self):
        self.plan = {}
        with requests.Session() as session:
            post = session.post("http://termin.selbstlernportal.de/?ug=lev-llg&sa=kl-q1")
            post = session.post("https://selbstlernportal.de/html/termin/termin_klausur.php?anzkw=47&kw=33/2020&endkw"
                                "=26/2021")
        page = post.content
        soup = BeautifulSoup(page, 'html.parser')

        table = soup.find('table', attrs={'class': 'klausur'}).find('tbody')
        for row in table.find_all('tr', attrs={'class': 'klausur'}):
            for day in row.find_all('td'):
                entry = day.find_all('div')[1]
                date = "-".join(entry['id'][2:].split('-')[::-1])
                date = date[:-4] + date[-2:]
                exams = []
                for e in entry.contents:
                    if e.name == 'hr': continue
                    exams.append(e)
                if exams[1].strip():
                    self.plan[date] = exams[1].strip()

    def get_filtered(self, stundenplan):
        klausuren = {}
        schienen = {}
        for _, week in stundenplan.plan.items():
            for day in week:
                for e in day:
                    s = e.split(' ')[0][1:-1]
                    if s not in schienen:
                        schienen[s] = " ".join(e.split(' '))
        for date in self.plan:
            s = self.plan[date][0:2]
            if s in schienen:
                klausuren[date] = schienen[s]
            elif "/" in self.plan[date]:
                klausuren[date] = self.plan[date]
        return klausuren


if __name__ == "__main__":
    plan = Klausurplan()
    plan.update()
    f = plan.get_filtered(Stundenplan(['lingk', 0]))
    print(f)

