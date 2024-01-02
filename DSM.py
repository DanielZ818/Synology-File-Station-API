import os
import random
import urllib.parse
import time
import requests
from colorama import Fore
from requests import utils


DEFAULT_USER_AGENT = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'
utils.default_user_agent = lambda: DEFAULT_USER_AGENT

class DSM:
    # Fundamentals
    def __init__(self, base_url: str, account: str, password: str):
        sid_file = open('sid.txt', mode='r')
        self.sid = sid_file.read()
        sid_file.close()
        self.account = account
        self.password = password
        self.base_url = base_url

        self.update_sid()

    def __login(self, account, password):
        login_url = self.base_url + "/webapi/auth.cgi"
        params = {'api': 'SYNO.API.Auth',
                  'version': 7,
                  'method': 'login',
                  'account': account,
                  'passwd': password,
                  'session': "FileStation",
                  'format': 'cookie'}
        response = requests.get(login_url, params=params).json()
        print("Got new sid")
        self.sid = response['data']['sid']

        sid_file = open('sid.txt', 'w')
        sid_file.write(self.sid)
        sid_file.close()

    def update_sid(self):
        url = self.base_url + "/webapi/entry.cgi?api=SYNO.FileStation.Info&version=2&method=get&_sid=" + str(self.sid)
        response = dict(requests.get(url).json())
        if 'error' in response.keys():
            self.__login(self.account, self.password)

    def list_file(self, folder_path):
        """
        This function list the files in a folder
        :param folder_path:
        :return: a list with tuple [(file_name, file_path)]
        """
        self.update_sid()
        path = folder_path
        url = self.base_url + "/webapi/entry.cgi"
        params = {'api': 'SYNO.FileStation.List',
                  'version': 2,
                  'method': 'list',
                  'folder_path': path,
                  'additional': ['real_path'],
                  '_sid': self.sid}
        data = requests.get(url, params=params).json()
        files = data['data']['files']
        file_list = []
        for i in files:
            name = i['name']
            path = i['path']
            real_path = i['additional']['real_path']
            file_list.append((name, path))
        return file_list

    def delete(self, path_lst: list[str]) -> str:
        """
        This function deletes files
        :param path_lst: a list of path from shared folder ['/Download/xxx.mp4', '/Download/folder123/']
        :return: taskid -> str
        """
        self.update_sid()
        url = self.base_url + "/webapi/entry.cgi"
        path = '["' + '","'.join(path_lst) + '"]'
        params = {
            'api': 'SYNO.FileStation.Delete',
            'version': 2,
            'method': 'start',
            'path': path,
            '_sid': self.sid
        }
        data = requests.get(url, params=params).json()
        print(Fore.RED + "Delete: " + Fore.YELLOW + path + Fore.RESET)
        return data['data']['taskid']

    def status(self, task_kind: str, taskid: str):
        """
        This function returns the status of a task given task_kind and taskid
        :param task_kind: 'delete', 'copy', 'move', 'compress', or 'extract'
        :param taskid
        :return: bool(finished), float(progress)
        """
        self.update_sid()
        taskid = '"' + taskid + '"'
        api_name = {
            "delete": "Delete",
            "copy": "CopyMove",
            "move": "CopyMove",
            "compress": "Compress",
            "extract": "Extract",
        }

        api = api_name[task_kind]
        version = "2"
        if api == 'Compress' or api == 'CopyMove':
            version = "3"

        url = self.base_url + "/webapi/entry.cgi?api=SYNO.FileStation." + api + "&version=" + version + "&method=status&taskid=" + taskid + "&_sid=" + self.sid

        data = requests.get(url, timeout=10).json()
        data = data['data']
        finished = bool(data['finished'])
        progress = float(data['progress'])
        return finished, progress

    def wait_until_finished(self, task_kind: str, taskid: str):
        """
        This function wait for a task to be completed
        :param task_kind: 'delete', 'copy', 'move', 'compress', or 'extract'
        :param taskid
        :return: None
        """
        finished, progress = self.status(task_kind, taskid)
        while not finished:
            os.system('clear')
            print(Fore.YELLOW + task_kind + ":", Fore.CYAN + str(max(0, round(progress * 100))) + "%")
            finished, progress = self.status(task_kind, taskid)
            print(Fore.RESET + '-----------------------------------------')
            time.sleep(1)
        print(Fore.GREEN + task_kind + " completed")
        print(Fore.RESET + '-----------------------------------------')

    def rename(self, path_lst: list[str], new_name_lst: list[str]):
        """
        This function renames files and folders
        :param path_lst: list of path ['/Shared_Folder/folder/xxx.mp4']
        :param new_name_lst: list of name ['yyy.mp4']
        :return: <file> object
        """
        self.update_sid()
        url = self.base_url + "/webapi/entry.cgi"

        path = '["' + '","'.join(path_lst) + '"]'
        new_name = '["' + '","'.join(new_name_lst) + '"]'

        params = {
            'api': 'SYNO.FileStation.Rename',
            'version': 2,
            'method': 'rename',
            'path': path,
            'name': new_name,
            '_sid': self.sid
        }

        data = requests.get(url, params=params).json()
        for (i, j) in zip(path_lst, new_name_lst):
            print(
                Fore.CYAN + "Rename: " + Fore.GREEN + i + Fore.YELLOW + " -> " + Fore.GREEN + j + Fore.RESET)
        time.sleep(0.1 * len(path_lst))
        print('------------------------------------------------------------------------------')
        return data['data']['files']

    def extract(self, file_path, dest_folder_path, password=None):
        """
        This sends an extract request
        :param password:
        :param dest_folder_path:
        :param file_path:
        :return: taskid -> str
        """
        self.update_sid()
        file_path = file_path.replace('\\', '\\\\')
        extract_url = self.base_url + '/webapi/entry.cgi'
        if password is None:
            password = ''

        params = {'api': 'SYNO.FileStation.Extract',
                  'method': 'start',
                  'version': 2,
                  'file_path': '"' + file_path + '"',
                  'dest_folder_path': '"' + dest_folder_path + '"',
                  'overwrite': 'true',
                  'keep_dir': 'false',
                  'create_subfolder': 'false',
                  'codepage': 'chs',
                  'password': '"' + password + '"',
                  '_sid': self.sid}
        # print(Fore.GREEN + "Extracting: " + Fore.YELLOW + file_path + Fore.RESET)
        return requests.get(extract_url, params=params).json()['data']['taskid']

    def move_file(self, file_path_list: list[str], dest_folder_path: str):
        """
        This funciton move files given each path and destination folder path
        :param file_path_list: ['/Shared_Folder/xxx.mp4']
        :param dest_folder_path: '/Shared_Folder/FolderA'
        :return: taskid -> str
        """

        self.update_sid()
        file_path = '["' + '","'.join(file_path_list) + '"]'
        dest_folder_path = '"' + dest_folder_path + '"'
        move_url = self.base_url + '/webapi/entry.cgi'
        params = {'api': 'SYNO.FileStation.CopyMove',
                  'version': 3,
                  'method': 'start',
                  'path': file_path,
                  'dest_folder_path': dest_folder_path,
                  'overwrite': 'true',
                  'remove_src': 'true',
                  '_sid': self.sid}
        response = requests.get(move_url, params=params)
        return response.json()['data']['taskid']

    def move_all(self, folder_path: str, dest_folder):
        """
        This fucntion move all compressed file in a folder
        :param folder_path: "Shared_Folder/xxx"
        :param dest_folder: "Shared_Folder2/xxx"
        :return: Nonem
        """
        self.update_sid()
        file_list = self.list_file(folder_path)
        move_file = []
        for i in file_list:
            file_name, file_path = i
            extension = '.' + file_name.split('.')[-1]
            compress_ext = ['.zip', '.rar', '.7z', '.tar', '.gz']
            if extension in compress_ext:
                move_file.append(file_path)
        if len(move_file) > 0:
            taskid = self.move_file(move_file, dest_folder)
            self.wait_until_finished('move', taskid)

    def list_task(self):
        url = self.base_url + '/webapi/entry.cgi?api=SYNO.FileStation.BackgroundTask&version=3&method=list' + '&_sid=' + self.sid
        response = requests.get(url).json()
        return response

    def clear_finished_task(self):
        url = self.base_url + '/webapi/entry.cgi?api=SYNO.FileStation.BackgroundTask&version=3&method=clear_finished' + '&_sid=' + self.sid
        response = requests.get(url).json()
        return response['success']

    def logout(self) -> bool:
        logout_url = self.base_url + '/webapi/auth.cgi'
        params = {'api': 'SYNO.API.Auth',
                  'version': 1,
                  'method': 'logout',
                  'session': "FileStation",
                  'sid_': self.sid}
        response = requests.get(logout_url, params=params).json()
        print(Fore.RED + "Logout")
        return response['success']

    def delete_folder_zips(self, folder_path: str):
        delete_path_lst = []
        compress_ext = ['.zip', '.rar', '.7z', '.tar', '.gz']
        for i in ds.list_file(folder_path):
            cur_name, cur_path = i
            if '.' in cur_name and '.' + cur_name.split('.')[1] in compress_ext:
                delete_path_lst.append(cur_path)
            elif '.' not in cur_name:
                delete_path_lst.append(cur_path)
        if not len(delete_path_lst) == 0:
            taskid = self.delete(delete_path_lst)
            self.wait_until_finished('delete', taskid)

    def primary_extract(self, folder_path):
        compress_ext = ['.zip', '.rar', '.7z', '.tar', '.gz']
        for i in ds.list_file(folder_path):
            if '.' in i[0] and '.' + i[0].split('.')[1] in compress_ext:
                self.extract(i[1], folder_path)

    def extract_all(self, folder_path, dest_path):
        compress_ext = ['.zip', '.rar', '.7z', '.tar', '.gz']

        child_ext = {
            'zip': 'gz',
            'gz': 'tar',
            'tar': '!END'
        }

        file_lst = self.list_file(folder_path)
        compressed_lst = []
        for i in file_lst:
            file_name, file_path = i
            if '.' in file_name and '.' + file_name.split(".")[1] in compress_ext:
                compressed_lst.append((file_name, file_path))

        status = {}
        for i in compressed_lst:
            file_name, file_path = i
            file_ext = file_name.split('.')[-1]
            file_name_without_ext = file_name.split('.')[0]
            if file_ext == 'zip':
                child_file = file_name_without_ext + '.tar.gz'
            else:
                child_file = file_name_without_ext + '.' + child_ext[file_ext]

            taskid = self.extract(file_path, dest_path)
            status[file_name] = {
                'parent': None,
                'parent_finished': True,
                'finished': False,
                'send': True,
                'taskid': taskid,
                'progress': 0
            }

            status[child_file] = {
                'parent': file_name,
                'parent_finished': False,
                'finished': False,
                'send': False,
                'taskid': None,
                'progress': None
            }

        while True:
            time.sleep(1)
            new_child = []
            files = status.keys()
            for file_name in files:
                parent, parent_finished, finished, send, taskid, progress = status[file_name].values()
                if not finished and send:
                    finished, progress = self.status('extract', taskid)
                    status[file_name]['progress'] = progress
                    status[file_name]['finished'] = finished

                if finished:
                    # find all child file and send request
                    for child in status.keys():
                        child_parent = status[child]['parent']
                        if child_parent is None:
                            continue
                        child_parent_status = status[status[child]['parent']]
                        if child_parent_status['finished'] and not status[child]['send']:
                            child_taskid = self.extract(dest_path + '/' + child, dest_path)
                            status[child]['parent_finished'] = True
                            status[child]['send'] = True
                            status[child]['taskid'] = child_taskid

                            # Add the next layer into status
                            cur_ext = child.split('.')[-1]
                            if not child_ext[cur_ext] == '!END':
                                child_name_without_ext = child.split('.')[0]
                                nxt_file = child_name_without_ext + '.' + child_ext[cur_ext]

                                new_child.append((nxt_file, {
                                    'parent': child,
                                    'parent_finished': False,
                                    'finished': False,
                                    'send': False,
                                    'taskid': None,
                                    'progress': None
                                }))

            for i in new_child:
                name, sta = i
                status[name] = sta

            os.system('clear')
            all_done = True
            for file_name in status.keys():
                finished = status[file_name]['finished']
                if not finished:
                    all_done = False
                progress = status[file_name]['progress']
                if progress is None:
                    print(Fore.RED + file_name, 'Waiting for parent file to be complete...')
                elif finished:
                    print(Fore.GREEN + file_name, 'Finished')
                else:
                    progress = max(progress, 0)
                    progress = str(round(progress * 100)) + "%"
                    print(Fore.YELLOW + 'Extracting:', file_name, progress)
            print(Fore.RESET + "-----------------------------------------------------")
            if all_done:
                return

    def random(self, folder_path: list[str]):
        file_lst = []
        for folder in folder_path:
            files = self.list_file(folder)
            file_lst.extend(files)

        random.shuffle(file_lst)
        for i in file_lst:
            if i[0].split('.')[-1] == 'mp4':
                title = urllib.parse.quote(i[0].replace('.mp4', '').encode('utf-8'))
                print(Fore.CYAN + i[0], self.open(i[1]) + '&title=' + title)
                print(Fore.YELLOW + '------------------------------------------------------------------------------')

    def open(self, file_path):
        # self.update_sid()
        url = self.base_url + '/webapi/entry.cgi'
        url += '?api=SYNO.FileStation.Download&version=2&method=download&path=' + str(file_path) + "&mode=open&_sid=" + self.sid

        return url


download_path = '/Downloads'
dest_path = "/Folder"
ds = DSM('domain:port', "user", 'password')
print('Logged In')

ds.move_all(download_path, dest_path)
ds.extract_all(dest_path, dest_path)
ds.delete_folder_zips(dest_path)
ds.random([dest_path])
ds.logout()

