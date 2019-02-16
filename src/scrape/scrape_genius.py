import sys, time, json, csv
import requests, argparse
from tqdm import tqdm
from db import database as db # imports a linked directory lol python suxx ass

# CONFIG_PATH = "/Users/peugeotbaguette/Developer/cogsys/github/anlp_ws18/src/config.json"
CONFIG_PATH = "/Users/glaser/Developer/cogsys/github/anlp_ws18/src/config_loiz.json"
with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
    config = json.load(f)
## Setup Genius session
ACCESS_TOKEN = config["genius_access_token"]

SESSION = requests.Session()
SESSION.headers = {'application': 'ANLP Project',
       'User-Agent': 'http://github.com/glaserL/anlp_ws18'}
SLEEP_MIN = 0.2  # Enforce minimum wait time between API calls (seconds)
SESSION.headers['authorization'] = 'Bearer ' + ACCESS_TOKEN
MAX_BATCH_SIZE = 1000

def find_artist_id(artist_name, max_request = 1):
    search_url = 'https://api.genius.com/search/'
    params = {'q' : artist_name, 'per_page' : 20}
    for i in range(max_request): # multiple Request still aint working
        params['page'] = i
        response = SESSION.request("GET", search_url ,params = params)
        results = response.json()['response']['hits']
        for result in results:
            primary_artist = result['result']['primary_artist']
            if primary_artist['name'] == artist_name:
                return primary_artist['id']
        time.sleep(0.2)
    return ""


def get_songs_for_artist(id, genre = 'N/A', max_request = 1):
    search_url = 'https://api.genius.com/artists/%s/songs'
    params = {'q' : id, 'per_page' : 50}
    result = []
    for i in range(1, max_request+1): # 0 indices causes invalid page error
        params['page'] = i
        response = SESSION.request("GET", search_url % id, params = params)
        if response.ok: # skip broken requests
            songs = response.json()['response']['songs']
            for song in songs:
                if song['lyrics_state'] == 'complete': # filter out garbage
                    result.append({
                        'title' : song['title'],
                        'artist' : song['primary_artist']['name'],
                        'url' : song['url'],
                        'genre' : genre
                    })
        time.sleep(0.1)
    return result

def collect_raw_songdata(artist_ids, n):
    database = db.Database()
    connection = database.get_connection()
    statements = []
    # prettify output
    try:
        from tqdm import tqdm
        iterator = tqdm(artist_ids)
    except ModuleNotFoundError:
        iterator = artist_ids
    sql_statement = ("INSERT INTO songs VALUES(NULL, :title, :artist, NULL, :genre, :url, NULL, " 
    "NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL);")
    for genre, artist_id in iterator:
        songs_of_artist = get_songs_for_artist(artist_id, genre = genre, max_request = n//50)
        statements.extend(songs_of_artist)
        if len(statements) > 500:
            connection.executemany(sql_statement, statements)
            connection.commit()
            statements.clear()
    connection.executemany(sql_statement, statements) # clearup
    connection.commit()
    connection.close()


def main(arguments):
        if arguments.ids:
            database = db.Database()
            conn = database.get_connection()
            select_statement = "SELECT id, artist FROM scrape WHERE genius_id IS NULL;"
            update_statement = "UPDATE scrape SET genius_id = ? WHERE id = ?;"
            statements = []
            cur = conn.cursor()
            cur.execute(select_statement)
            for entry in tqdm(list(cur)):
                sql_id, artist_name = entry
                genius_id = find_artist_id(artist_name)
                genius_id = genius_id if genius_id != "" else "N/A" # make missings visible 
                statements.append((genius_id, sql_id))
                if len(statements)>50: # we keep it low to keep reexecutions useful
                    conn.executemany(update_statement, statements)
                    conn.commit()
                    statements.clear()
            # cleanup rest
            conn.executemany(update_statement, statements)
            conn.commit()
            statements.clear()
            conn.close()
            del conn
            del database
        if arguments.write:
            artist_ids = []
            for genre in arguments.genre:        
                database = db.Database()
                conn = database.get_connection()
                select_statement = "SELECT genre, genius_id FROM scrape WHERE genius_id != 'N/A' AND genre = %s;" % genre
                cur = conn.cursor()
                cur.execute(select_statement)
                artist_ids = [(genre, artist_id) for genre, artist_id in cur]
                conn.close()
                del conn
                del database
                collect_raw_songdata(artist_ids, args.number_of_songs)
        if not arguments.write and not arguments.ids:
            print("Specify what to do!:")
            print(arguments)            
        

if(__name__ == "__main__"):
    parser = argparse.ArgumentParser(description='Params')
    parser.add_argument('--ids', action ='store_true',
                        help = 'Will collect ids for artist')
    parser.add_argument("--write", action = 'store_true',
                        help = 'given artist ids, will write song ids to db')
    parser.add_argument("-n","--number_of_songs", type = int, default = 50,
                        help = "How many songs to get per artist")
    parser.add_argument('-g','--genre', nargs="*")
    args = parser.parse_args()
    main(args)

