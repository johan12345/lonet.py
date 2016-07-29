import argparse
import os
import re
import urllib.parse

import requests
from bs4 import BeautifulSoup
from pushbullet import Pushbullet

pushbullet = None


def download_file(url, dir):
    local_filename = dir + '/' + urllib.parse.unquote_plus(url.split('/')[-1], encoding='iso-8859-1')
    if os.path.exists(local_filename): return;

    print(local_filename)
    r = requests.get(url, stream=True)
    with open(local_filename, 'wb') as f:
        for chunk in r.iter_content(chunk_size=1024):
            if chunk:
                f.write(chunk)

    if pushbullet is not None:
        pushbullet.push_note('Neue Datei', local_filename)
    return local_filename


def download_folder(folder, base_dir):
    dir = base_dir + '/' + folder['name']

    if not os.path.exists(dir):
        os.makedirs(dir)

    if 'url' in folder:
        download_files(folder['url'], dir)

    for key, subfolder in folder['subfolders'].items():
        download_folder(subfolder, dir)


def download_files(url, dir):
    files_page = BeautifulSoup(session.get(url=url).text, 'html.parser')
    for download_link in files_page.select('a[download]'):
        download_file(base_download_url + download_link['href'], dir)
    return files_page


parser = argparse.ArgumentParser(description='Download files from lo-net2.de file storage')
parser.add_argument('-u', '--username', type=str, required=True,
                    help='lo-net2 email address (.lo-net2.de at the end can be omitted)')
parser.add_argument('-p', '--password', type=str, required=True,
                    help='lo-net2 password')
parser.add_argument('-pb', '--pushbullet-token', type=str, help='Pushbullet API token')
args = parser.parse_args()

base_url = 'https://www.lo-net2.de/wws/'
base_download_url = 'https://www.lo-net2.de'

session = requests.Session()

if args.pushbullet_token is not None:
    pushbullet = Pushbullet(args.pushbullet_token)

login_page = session.get('https://www.lo-net2.de/wws/100001.php').text
sid = re.compile('sid=(\d+)').search(login_page).group(1)
main_page = BeautifulSoup(session.post(url=base_url + '100001.php?sid=' + sid,
                                       files={
                                           'default_submit_button': ('', ''),
                                           'login_nojs': ('', ''),
                                           'login_login': ('', args.username),
                                           'login_password': ('', args.password),
                                           'language': ('', '2')
                                       }).text, 'html.parser')
course_links = main_page.select('#status_member_of_19 li > a')

for course_link in course_links:
    course_name = course_link.text
    print(course_name)

    if not os.path.exists(course_name):
        os.makedirs(course_name)

    course_page = BeautifulSoup(session.get(url=base_url + course_link['href']).text, 'html.parser')
    files_url = base_url + course_page('a', text='Dateiablage')[0]['href']
    files_page = download_files(files_url, course_name)

    base_folder = dict(name=course_name, subfolders={})
    for folder_link in files_page.select('#table_folders a'):
        folder_url = base_download_url + folder_link['href']
        query = urllib.parse.urlparse(folder_url).query
        params = urllib.parse.parse_qs(query, keep_blank_values=True)
        path = params['path'][0]
        if path == '': continue

        parts = path.split('/')[1:]

        folder = base_folder
        for i in range(0, len(parts) - 1):
            folder = folder['subfolders'][parts[i]]
        folder['subfolders'][parts[len(parts) - 1]] = dict(
            name=folder_link.text,
            url=folder_url,
            subfolders={}
        )

    download_folder(base_folder, '.')
