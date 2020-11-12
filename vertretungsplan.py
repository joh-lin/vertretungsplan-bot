import base64
import datetime
import gzip
import json
import uuid

import bs4
import requests
from stundenplan import Stundenplan

DATA_URL = "https://app.dsbcontrol.de/JsonHandler.ashx/GetData"
username = "153482"
password = "llg-schueler"


def get_timetable():
    # Iso format is for example 2019-10-29T19:20:31.875466
    current_time = datetime.datetime.now().isoformat()
    # Cut off last 3 digits and add 'Z' to get correct format
    current_time = current_time[:-3] + "Z"

    # Parameters required for the server to accept our data request
    params = {
        "UserId": username,
        "UserPw": password,
        "AppVersion": "2.5.9",
        "Language": "de",
        "OsVersion": "28 8.0",
        "AppId": str(uuid.uuid4()),
        "Device": "SM-G930F",
        "BundleId": "de.heinekingmedia.dsbmobile",
        "Date": current_time,
        "LastUpdate": current_time
    }
    # Convert params into the right format
    params_bytestring = json.dumps(params, separators=(',', ':')).encode("UTF-8")
    params_compressed = base64.b64encode(gzip.compress(params_bytestring)).decode("UTF-8")

    # Send the request
    json_data = {"req": {"Data": params_compressed, "DataType": 1}}
    timetable_data = requests.post(DATA_URL, json=json_data)

    # Decompress response
    data_compressed = json.loads(timetable_data.content)["d"]
    data = json.loads(gzip.decompress(base64.b64decode(data_compressed)))

    # Find the timetable page, and extract the timetable URL from it
    final = []
    for page in data["ResultMenuItems"][0]["Childs"]:
        for child in page["Root"]["Childs"]:
            if isinstance(child["Childs"], list):
                for sub_child in child["Childs"]:
                    final.append(sub_child["Detail"])
            else:
                final.append(child["Childs"]["Detail"])
    if not final:
        raise Exception("Timetable data could not be found")
    output = []
    infos = {}
    for entry in final:
        if entry.endswith(".htm") and not entry.endswith(".html") and not entry.endswith("news.htm"):
            substitution, infos = fetch_timetable(entry)
            output.append(substitution)
    if len(output) == 1:
        return output[0], infos
    else:
        return output, infos


def fetch_timetable(timetableurl):
    results = []
    infodata = {}
    sauce = requests.get(timetableurl).text
    soupi = bs4.BeautifulSoup(sauce, "html.parser")
    ind = -1

    # substitution data
    for soup in soupi.find_all('table', {'class': 'mon_list'}):
        ind += 1
        updates = [o.p.findAll('span')[-1].next_sibling.split("Stand: ")[1] for o in
                   soupi.findAll('table', {'class': 'mon_head'})][ind]
        titles = [o.text for o in soupi.findAll('div', {'class': 'mon_title'})][ind]
        date = titles.split(" ")[0]
        day = titles.split(" ")[1].split(", ")[0].replace(",", "")
        entries = soup.find_all("tr")
        entries.pop(0)
        for entry in entries:
            infos = entry.find_all("td")
            if len(infos) < 2:
                continue
            for class_ in infos[1].text.split(", "):
                new_entry = {"class": infos[0].text if infos[0].text != "\xa0" else "---",
                             "lesson": class_ if infos[1].text != "\xa0" else "---",
                             "teacher": infos[2].text if infos[2].text != "\xa0" else "---",
                             "subject": infos[4].text if infos[4].text != "\xa0" else "---",
                             "comment": infos[5].text if infos[5].text != "\xa0" else "---",
                             "type": infos[6].text if infos[6].text != "\xa0" and infos[
                                 6].text != "+" else "---",
                             "room": infos[7].text if infos[7].text != "\xa0" and infos[7].text != "+" else "---",
                             "date": date.rjust(10, "0").replace('.', '-')[:-2],
                             "day": day}
                results.append(new_entry)

    # infos
    ind = -1
    for soup in soupi.find_all('table', {'class': 'info'}):
        ind += 1
        titles = [o.text for o in soupi.findAll('div', {'class': 'mon_title'})][ind]
        date = titles.split(" ")[0]
        date = date.rjust(10, "0").replace('.', '-')[:-2]
        infodata[date] = []
        for tr in soup.find_all('tr')[1:]:
            e = []
            for td in tr.find_all('td'):
                e.append(td.text.replace("\xa0", ""))
            infodata[date].append(e)

    return results, infodata


class Vertretungsplan:
    def __init__(self):
        self.plan = {}
        self.infos = {}
        try:
            self.load_from_file()
        except FileNotFoundError:
            self.update()
            self.save_to_file()

    def load_from_file(self):
        with open("plaene/vertretungsplan.json", "r") as f:
            self.plan = json.loads(f.read())
        with open("plaene/vertretungsplaninfos.json", "r") as f:
            self.infos = json.loads(f.read())

    def save_to_file(self):
        with open("plaene/vertretungsplan.json", "w+") as f:
            f.write(json.dumps(self.plan))
        with open("plaene/vertretungsplaninfos.json", "w+") as f:
            f.write(json.dumps(self.infos))

    def update(self):
        timetable, infos = get_timetable()
        self.infos = infos
        self.plan = {}
        for entry in timetable:
            date = entry["date"]
            if date not in self.plan:
                self.plan[date] = []
            self.plan[date].append(entry)

        #return self.plan

    def get_filtered(self, stundenplan: Stundenplan):
        """
        Retuns plan filtered using a timetable object.
        :param stundenplan:
        :return: Dictionary
        """
        ef = {}
        for date in self.plan:
            for entry in self.plan[date]:
                if entry["class"] == "EF" and entry["subject"] in stundenplan.get_subjects():
                    if entry['date'] not in ef:
                        ef[entry['date']] = []
                    ef[entry['date']].append(entry)
        return ef

    def print(self):
        plan = self.get_filtered(Stundenplan(["lingk", 0]))
        for date in plan:
            print(date)
            for e in plan[date]:
                print(e)


if __name__ == "__main__":
    vplan = Vertretungsplan()
    vplan.update()
    vplan.save_to_file()
    for date in vplan.infos:
        print(date)
        for e in vplan.infos[date]:
            print("    " + str(e))
