import os
import csv
import json
import copy
import base64
import socket
import whois
import time
import shutil
import whois.parser
import ipinfo
import requests
import urllib.parse as up
import pandas as pd
print("\nIGNORE ERROR ##################")
import tensorflow as tf
print("END ERROR    ##################\n")
import numpy as np
import sys
import xml.etree.ElementTree as ET
from time import time
from twilio.rest import Client
from ipinfo.handler_utils import cache_key
from ipwhois import IPWhois
from datetime import datetime
from datetime import date
from pandas.errors import EmptyDataError
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from tensorflow.keras.preprocessing.image import load_img, img_to_array
from tensorflow.keras.models import load_model
from tensorflow.keras.applications.mobilenet import preprocess_input

####################
# HELPER FUNCTIONS #
####################
class failedFetch:
    def __init__(self):
        self.ip = "-"
        self.country = "-"


def getFieldNames():
    """GET FIELD NAMES

    defines column titles of csv file

    Parameters
    ----------
    ( None )


    Returns  
    -------
    names : (list)
            titles of the columns in the csv file

    """
    names = ['domain_id']
    names.append('source_id')
    names.append('domain_name')
    names.append('activity_img')
    names.append('activity_req')
    #names.append('virus_total_score')
    #names.append('virus_total_engines')
    names.append('ip_address')
    names.append('ip_country')
    names.append('registrant_country')
    names.append('registrar')
    names.append('time')
    names.append('date_discovered')

    return names


def updateUrls(source_url_dir, file_to_update, max_num_urls):
    """UPDATE URLS

    gets updated url data from splab_phish_urls, adds to url collector file

    stops adding to the url file if it contains more than max_num_urls

    both the collector and source files are CSV
        format: id, date_discovered, url

    Parameters
    ----------
    source_url_dir: (string)
        path to the directory containing the source urls used
        to update the collector

    file_to_update: (string)
        path to the collector file

    max_num_urls: (int)
        maximum number of urls to add to collector file

    Returns
    -------
    """

    # don't update if collected urls exceeds max number
    collector_exists = False
    collected_urls = []
    try:
        if os.path.exists(file_to_update):
            collector_exists = True
            df = pd.read_csv(file_to_update)
            if len(df) >= max_num_urls:
                print("Url file is full. Skipping update...")
                return

            collected_urls = list(df.url)

    except Exception as e:
        print("UPDATE URL ERROR: collection file read error")
        print(e)
        exit(1)

    # check url source for new urls
    ## build path using date: mmddyyyy.csv
    today = date.today()
    day = str(today.day)
    month = str(today.month)
    year = str(today.year)
    if len(day) == 1:
        day = '0' + day
    if len(month) == 1:
        month = '0' + month
    source_file = month + day + year + ".csv"
    source_file_path = os.path.join(source_url_dir, source_file)

    ## check each row, skip rows with urls containing commas
    if os.path.exists(source_file_path):
        # extract urls
        with open(source_file_path, "r") as f:
            lines = f.readlines()

            # header contains proper num of commas for each row
            num_of_separators = lines[0].count(',')
            header = lines.pop(0)

            # add header to collection file if its new
            try:
                c_file = open(file_to_update, "a+")
            except Exception as e:
                print("UPDATE URL ERROR: Cannot open url collection file")
                print(e)
                exit(1)
            if not collector_exists:
                c_file.write(header)

            # extract urls from each row
            for line in lines:
                if line.count(',') > num_of_separators:
                    continue

                # find url btw 2nd comma and newline
                comma1 = line.find(',') + 1
                comma2 = line.find(',', comma1, -1) + 1
                url = line[comma2:-1]

                # add to url to collection if url is unique
                if url not in collected_urls:
                    c_file.write(line)

    else:
        print("URL UPDATE: %s does not exist, cannot update urls." % (source_file_path))

def readUrls(data, remove_csv_duplicates = True):
    """READ URLS

    reads in all urls from the list passed via command line arg.
    duplicate urls and urls conflicting with those already logged are removed.

    Parameters
    ----------
    data: (metadata class object)
        contains metadata about program state needed to 
        open files properly

    Returns
    -------
    urls: (list)
            list of urls after conflicts/duplicates have been removed

    """
    # determine if the url file is CSV format
    CSV = False
    if '.csv' in data.URL_FILE_PATH:
        CSV = True

    if CSV:

        # extract phishtank csv data
        try:
            df = pd.read_csv(data.URL_FILE_PATH)
        except EmptyDataError:
            print("ReadURLs error. %s is empty." % (filename))
            return None
        container = {}
        awg_data = {}

        # convert records into a dictionary with APWG data
        urls = list(df.loc[:,'url'])

        for url in urls:
            found = 0
            # locate csv record for url
            for i in range(len(df)):
                record = df.loc[i]

                # store metadata in dictionary
                if record["url"] == url:
                    found = 1
                    container["awg_id"] = int(record["id"])
                    container["awg_date_discovered"] = str(record["date_discovered"])
                    awg_data[url] = copy.deepcopy(container)
                    break

            # url record not found
            if found == 0:
                print("ReadURL Error. Problem with read CSV file")
                exit(1)

            # reset for nxt iteration
            container.clear()
    else:
        # Read in url's from file
        with open(data.URL_FILE_PATH) as f: 
            # get urls
            urls = f.readlines()

            # remove \n char
            for i, line in enumerate(urls):
                urls[i] = line[0:-1]

            # remove duplicate urls from url list
            urls = set(urls)
            urls = sorted(urls)

            # retrieve urls currently in csv record
            # filter out duplicates from list
            if remove_csv_duplicates: 
                if data.CSV_FILE_EXISTS and data.CURRENT_DOMAIN_ID > 0:
                    # retrieve current record of urls from csv file
                    df = pd.read_csv(data.CSV_FILE_PATH, na_values=['-', '', 'holder'])
                    url_rec = df.loc[:, 'domain_name'].to_numpy()

                    # remove urls from list which are present in record 
                    for i, url in enumerate(urls):
                        if url in url_rec:
                            urls.remove(urls[i])

        awg_data = None

    return urls, awg_data



def screenshot(current_id, shot_path, urls):
    """SCREENSHOT ANALYSIS

    uses selenium to visit and screenshot urls in input list
    screenshots are saved at dir_path and are named by their domain id

    Parameters
    ----------
    current_id:

    shot_path:

    urls: (list)
        list of urls to visit

    Returns
    -------
    screenshot_paths: (dictionary)
        full path to each screenshot, uses url as key
    """
    try:
        # set up selenium web driver
        BASE_PATH = os.path.dirname(os.path.realpath(__file__))
        DRIVER_PATH = os.path.join(BASE_PATH, 'geckodriver')
        op = Options()
        op.page_load_strategy = 'eager'
        op.set_capability('unhandledPromptBehavior', 'accept')
        op.add_argument('--start-maximized')
        op.add_argument('--disable-web-security')
        op.add_argument('--ignore-certificate-errors')
        op.add_argument("--headless")

        # warn user of potential screenshot overwrite 
        #message = "Begin screenshots? (y/n): "
        #consent = input(message) 
        consent = 'y'

        # take screenshots and record activity of site
        screenshot_paths = {}
        if consent == 'y':
            driver = webdriver.Firefox(options=op, executable_path=DRIVER_PATH)
            #######################
            driver.set_page_load_timeout(10)
            driver.set_script_timeout(10)
            #######################
            domain_id = current_id + 1

            for i, url in enumerate(urls):
                # clean domain name
                clean_url = url.replace('https://', '')
                clean_url = clean_url.replace('http://', '')
                clean_url = clean_url.replace('www.', '')
                url_size = len(clean_url)


                # build screenshot path
                pic = '{id}'.format(id = domain_id + i)
                if url_size >= 4:
                    # name ends with first 4 chars of the url
                    pic += '_' + clean_url[0:4]
                else:
                    pic += clean_url
                pic += '.png'
                pic_path = shot_path + '/' + pic


                # screenshot
                try:
                    driver.get('https://' + clean_url)
                    time.sleep(3)
                    driver.execute_script("window.stop();")

                except Exception as e:
                    driver.save_screenshot(pic_path)
                    screenshot_paths[url] = pic_path
                    continue

                driver.save_screenshot(pic_path)
                screenshot_paths[url] = pic_path

            driver.quit()

        else:
            print("Exiting...")
            exit(1)

    except Exception as e:
        print('Error. screenshot analysis failed')
        print(e)

    return screenshot_paths


def checkDomainActivity(domains, screenshot_paths, model):
    """CHECK DOMAIN ACTIVITY

    uses request module and CNN image classifier to determine
    if a domain is currently active or inactive

    Parameters
    ----------
    domains: (list)
        urls to check 

    screenshot_paths: (dictionary)
        paths to screenshot of each url
        url is the key to its own path

    model: (class object)
        convolutional neural net model being used as an domain 
        activity classifier

    Returns
    -------
    activity_data: (dict)
        activity data as classified by CNN model and python requests
        module for each url

        access data via:   
            activity_data[<url>]['req']     for req module data
            activity_data[<url>]['image']   for classifier data
    """
    activity_data = {}
    ACTIVE = 0
    INACTIVE = 1

    for url in domains:
        activity_data[url] = {}
        # get screenshot
        path = screenshot_paths[url]
        
        # prepare screenshot for analysis
        img = load_img(path, target_size=(224,224))
        img_array = img_to_array(img)
        expanded_img_array = np.expand_dims(img_array, axis=0)
        preprocessed_img = preprocess_input(expanded_img_array)

        # get cnn classifier result
        prediction = model.predict(preprocessed_img)
        if prediction[0][ACTIVE] >= 0.5:
            activity_data[url]["image"] = "active"
        else:
            activity_data[url]["image"] = "inactive"

        # get python request module result
        try:
            req_result = requests.get(url, timeout=10)
            if req_result.ok:
                activity_data[url]["req"] = "active"
            else:
                activity_data[url]["req"] = "inactive"
        except Exception as e:
            activity_data[url]["req"] = "unknown"

    return activity_data


def encodePhishReqURL(uri):
    """ENCODE PHISHTANK REQUEST URL

    encodes the url to analyze using base64 and attaches
    it to the phishtank api url

    returns final url
    """
    url = "http://checkurl.phishtank.com/checkurl/"
    new_check_bytes = uri.encode()
    base64_bytes = base64.b64encode(new_check_bytes)
    base64_new_check = base64_bytes.decode('ascii')
    url += base64_new_check
    return url


def parsePhishTankResponse(xml_string):
    """PARSE PHISTANK RESPONSE

    parses phishtank api xml response for a url

    extract 'in_database' and 'phish_id' attrib's
    """
    phish_id = 0
    in_db = False

    root = ET.fromstring(xml_string)
    results = root.find('results')
    url0 = results.find('url0')
    in_db = url0.find('in_database').text

    if in_db == 'true':
        phish_id = int(url0.find('phish_id').text)
        in_db = True
    else:
        phish_id = -1
        in_db = False

    return phish_id, in_db


def phishTankHtmlActivity(phish_id):
    """PHISH TANK ACTIVITY

    check the phishtank details page for a particular phish_id
    parses the html code to see if its online

    Parameters:
    -----------
    phish_id: (int)
        phish tank id of the url to check

    Returns:
    --------
    ( None )
    """
    url = 'https://phishtank.org/phish_detail.php?phish_id='
    id_str = str(phish_id)
    url += id_str

    r = requests.request("GET", url=url)
    s = r.text

    result = ''
    if "currently ONLINE" in s:
        result = "active"
    elif ("currently offline" in s) or ("currently OFFLINE" in s):
        result = "inactive"
    else:
        result = "invalid"
        print(s)

    return result


def queryPhishAPI(key, database):
    """QUERY PHISHTANK API

    makes a POST request for updated phishtank database

    returns request response
    """
    url = 'http://data.phishtank.com/data/'
    url = url + key + '/'
    url += database

    response = requests.request("POST", url=url)

    return response


def strToDataFrame(file_name, string, data_format):
    """STRING TO DATAFRAME
    converts a string contains db data into a pandas dataframe

    Parameters
    ----------
    file_name: (string)
        the db data is first saved to a file. this is its name.

    string: (string)
        string containing the db data

    data_format: (string)
        format the data is in. **currently just accept csv

    Returns
    -------
    df: (DataFrame)
        pandas dataframe containing db data

        returns False if there was an issue reading the file
    """
    # filepath to hold data
    base_path = os.path.dirname(os.path.realpath(__file__))
    file_path = os.path.join(base_path, file_name)

    # CSV data
    if data_format == "csv":
        # log old versions of database
        if os.path.exists(file_path):
            log_name = "META/PHISHDB/"
            log_name += datetime.now().strftime("%m/%d/%Y_%H:%M:%S_phishdb.csv")
            log_path = os.path.join(base_path, log_name)
            shutil.move(file_path, log_path)

        # create updated db file
        with open(file_path, "w+") as f:
            f.write(string)

        # build dataframe
        df = pd.read_csv(file_path)

    else:
        # unable to read db csv
        df = False

    return df


def searchPhishTank(key, db_name, domains):
    """SEARCH PHISH TANK

    get the activity data for each domain from phishtank api

    Parameters:
    -----------
    domains: (list)
        urls to lookup



    Returns:
    --------
    phish_data: (dictionary)
        phishtank activity value for each url
        data can be accessed via 'phish_data[<url>][?????]
    """
    """
    get updated database

    check if the url is in it

    if so, log its activity value, otherwise '-'
    """
    db_response = queryPhishAPI(key, db_name)

    df = strToDataFrame("pt_database.csv", db_response.text, "csv")

    BASE_PATH = os.path.dirname(os.path.realpath(__file__))

    db_urls = list(db.url)

    # get phishtank activity value for url
    for url in domains:
        if url in db_urls:


    phish_data = {}
    for url in domains:
        # domain came from phishtank
        if data_source == "phish":
            phish_id = url_file_data[url]["awg_id"]
            activity = phishTankActivity(phish_id)
            phish_data[url] = activity
            phish_data[phish_id] = phish_id

        else:
            # check if the domain is in phishtank
            url_encoded = encodePhishReqURL(url)
            r = queryPhishAPI(key, url_encoded)
            phish_id, in_db = parsePhishTankResponse(r.text)

            # scrape phishtanks activity status
            if in_db:
                activity = phishTankActivity(phish_id)
                phish_data[url] = activity
                phish_data[phish_id] = phish_id
            else:
                phish_data[url] = 'n_a'
                phish_data[phish_id] = 'none'

    return phish_data


def searchPhisherman(domains):
    """SEARCH PHISH TANK

    retrieve url, date added, phishtank id for each url using the phisherman scraper

    Parameters:
    -----------
    domains: (list)
        urls to lookup

    Returns:
    --------
    phish_data: (dictionary)
        phishtank data for url including data added to phishtank and phishtank id
        data can be accessed via 'phish_data[<url>]['date' or 'phish_id']
    """
    # generate path to file
    base_path = os.path.dirname(os.path.realpath(__file__)) 
    filename = 'PHISHERMAN/log.csv'
    full_path = os.path.join(base_path, filename)

    # extract phishtank csv data
    try:
        df = pd.read_csv(full_path)
    except EmptyDataError:
        print("Search phishtank error. %s is empty." % (filename))
        return None

    # encapsulate url with its phishtank data
    phish_data = {}
    container = {}

    for url in domains:
        found = 0
        # search each phishtank log record
        for i in range(len(df)):
            record = df.loc[i]

            # phishtank data found
            if record["url"] == url:
                found = 1
                container["phish_id"] = int(record["phish_id"])
                container["date"] = record["date"]
                phish_data[url] = copy.deepcopy(container)
                break

        # phishtank data not found
        if found == 0:
            container["phish_id"] = '-'
            container["date"] = '-'
            phish_data[url] = copy.deepcopy(container)

        # reset for nxt iteration
        container.clear()
    
    return phish_data


def getWhoIs(domains): 
    """GET WHO IS
    
    retrieve relevant whois data from python_whois api

    PYTHON WHOIS FIELDS
            _regex = {
                    'domain_name':
                    'registrar': 
                    'whois_server':
                    'referral_url':
                    'updated_date':
                    'creation_date':
                    'expiration_date':
                    'name_servers':  
                    'status':       
                    'emails':      
                    'dnssec':    
                    'name':     
                    'org':     
                    'address': 
                    'city':   
                    'state': 
                    'zipcode':
                    'country': }

    Parameters
    ----------
    domains: (list)
            list of domains to gather data on

    Returns
    -------
    whois_data: (dict)
            a dictionary of the whois data for each domain
            the dictionary is indexed by domain url
    """
    whois_data = {}

    # build dictionary of whois data for each domain
    for url in domains:

        try:
            w = whois.whois(url)
            keys = list(w.keys())

            # convert datetime objects to strings
            #   updated date
            time_pattern = "%m/%d/%Y, %H:%M:%S"
            upd_date = 'updated_date'
            c_date = 'creation_date'
            exper_date = 'expiration_date'
            if upd_date in keys:
                if isinstance(w[upd_date], list):
                    for i in range(len(w[upd_date])): 
                        if not isinstance(w[upd_date][i], str):
                            up_date = w[upd_date][i].strftime(time_pattern)
                            w[upd_date][i] = up_date
                elif w[upd_date] is not None:
                    if not isinstance(w[upd_date], str):
                        up_date = w[upd_date].strftime(time_pattern)
                        w[upd_date] = up_date

            #   creation date
            if c_date in keys:
                if isinstance(w[c_date], list):
                    for i in range(len(w[c_date])): 
                        if not isinstance(w[c_date][i], str):
                            create_date = w[c_date][i].strftime(time_pattern)
                            w[c_date][i] = create_date
                elif w[c_date] is not None:
                    if not isinstance(w[c_date], str):
                        create_date = w[c_date].strftime(time_pattern)
                        w[c_date] = create_date

            #   expiration date
            if exper_date in keys:
                if isinstance(w[exper_date], list):
                    for i in range(len(w[exper_date])): 
                        if not isinstance(w[exper_date][i], str):
                            exp_date = w[exper_date][i].strftime(time_pattern)
                            w[exper_date][i] = exp_date
                elif w[exper_date] is not None:
                    if not isinstance(w[exper_date], str):
                        exp_date = w[exper_date].strftime(time_pattern)
                        w[exper_date] = exp_date

        except whois.parser.PywhoisError:
            w = {}

        whois_data[url] = w

    return whois_data


def getVirusTotal(token, domains): 
    """GET VIRUS TOTAL 
    
    retrieves relevant data from virustotal api including:
    1) virus total phishing score for each domain
    2) virus total engines which labeled domain as a threat

    Parameters
    ----------
    token: (string)
        virus total access token 

    domains: (list)
            list of domains to gather data on

    Returns
    -------
    virus_data: (dict)
            a dictionary of the virustotal data for each domain
            the dictionary is indexed by domain url
    """
    virus_data = {}

    # request virustotal scan each domain in list
    for domain in domains:
        # encode domain
        payload = "url=" + domain
        domain_id = base64.urlsafe_b64encode(domain.encode()).decode().strip("=")

        # get scan report 
        url = "https://www.virustotal.com/api/v3/urls"
        url = url + '/' + domain_id
        headers = {

            "Accept": "application/json",

            "x-apikey": token

        }
        response = requests.request("GET", url, headers=headers)
        report = response.json()

        # create dict entry for report
        virus_data[domain] = report

    return virus_data


def getIpInfo(handler, domains): 
    """GET IP INFO

    get info related to domain ip using ipinfo api

    IPINFO FREE PLAN FIELDS
    {
      "ip": "66.87.125.72",
      "hostname": "ip-66-87-125-72.spfdma.spcsdns.net",
      "city": "Springfield",
      "region": "Massachusetts",
      "country": "US",
      "loc": "42.1015,-72.5898",
      "org": "AS10507 Sprint Personal Communications Systems",
      "postal": "01101",
      "timezone": "America/New_York"
    }


    Parameters
    ----------
    handler: (ipinfo handler class object)
        handler object used to retrieve ip details

    domains: (list)
            list of domains to gather data on

    Returns
    -------
    ip_data: (dict)
            a dictionary of the ip data for each domain
            the dictionary is indexed by domain url
            
    """
    ip_data = {}

    # get ip data for each domain
    for url in domains:
        try:
            # retrieve data
            parsed_url = up.urlparse(url)
            ip = socket.gethostbyname(parsed_url.netloc)
            details = handler.getDetails(ip, timeout=10)
            ip_data[url] = details
        except Exception as e:
            ip_data[url] = failedFetch()

    return ip_data

def logMeta(data, 
            activity_data,
            whois_data,
            ip_data,
            awg_data,
            domains): 
    """LOG METADATA

    stores all metadata created for each url in a file

    data is stored as a dictionary which can be indexed using the url
    and the type of data

    i.e. to get phishtank data out of the file
        log[url]["phishtank_data"]

    Parameters
    ----------
    data: (metadata class object)
        contains metadata about program state and files

    phishtank_data: (dict)
        contains url phishtank id and date added

    activity_data: (dict)
        contains cnn classifier activity prediction and request
        module result for each url

    whois_data: (dict)
        whois data for each domain
        indexed by url from input url file

    virus_data: (dict)
        virus total api data for each domain
        indexed by url from input url file

    ip_data: (dict)
        ip data from ipinfo api for each domain
        indexed by url from input url file


    Returns
    -------
    ( None )
    """
    log = {}
    domain_id = data.CURRENT_DOMAIN_ID + 1

    for i, url in enumerate(domains):
        # clean domain name
        clean_url = url.replace('https://', '')
        clean_url = clean_url.replace('http://', '')
        clean_url = clean_url.replace('www.', '')
        url_size = len(clean_url)

        # pic name starts with id of domain in csv file
        file_name = '{id}'.format(id = domain_id + i)
        if url_size >= 4:
            # name ends with first 4 chars of the url
            file_name += '_' + clean_url[0:4]
        else:
            file_name += clean_url
        file_name += '.json'
        file_path = data.META_PATH + '/' + file_name

        with open(file_path, 'w') as logfile:
            log["url"] = url
            #log["phishtank_data"] = phishtank_data[url]
            log["activity_data"] = activity_data[url]
            log["whois_data"] = whois_data[url]
            #log["virus_data"] = virus_data[url]

            if awg_data is not None:
                log["awg_data"] = awg_data[url]

            # convert ip Details object to dict
            if ip_data[url].ip is not '-':
                ip_key = cache_key(ip_data[url].ip)
                ip_dict = data.HANDLER.cache[ip_key]
                log["ip_data"] = ip_dict

            try:
                log_js = json.dumps(log, indent=1, sort_keys=True)
                logfile.write(log_js)
            except Exception as e:
                print("LOG META ERROR: could not log: ", url)
                print(e)

            # reset
            log.clear()


def writeCsv(data, 
            activity_data,
            whois_data,
            ip_data,
            awg_data,
            domains): 
    """WRITE CSV

    creates data record in csv file for each domain

    Parameters
    ----------
    data: (metadata class object)
        contains metadata about program state and files

    phishtank_data: (dict)
        contians url phishtank id and date added

    activity_data: (dict)
        contains cnn classifier activity prediction and request
        module result for each url

    whois_data: (dict)
        whois data for each domain
        indexed by url from input url file

    virus_data: (dict)
        virus total api data for each domain
        indexed by url from input url file

    ip_data: (dict)
        ip data from ipinfo api for each domain
        indexed by url from input url file


    Returns
    -------
    ( None )
    """
    # set csv write mode based on state of file
    if data.CURRENT_DOMAIN_ID == data.EMPTY: 
        data.write_mode = 'w' 

    # append records to csv file
    elif data.CSV_FILE_EXISTS:
        data.write_mode = 'a'

    # csv file does not exist
    else: 
        print("Write CSV Error. CSV file does not exist")
        exit(1)

    # write to csv 
    with open(data.CSV_FILE_PATH, data.write_mode, newline='') as csvfile: 

        # prepare write object
        writer = csv.DictWriter(csvfile, fieldnames=data.FIELD_TITLES)
        if data.write_mode == 'w':
            writer.writeheader()

        # save domain data 
        domain_id = data.CURRENT_DOMAIN_ID + 1
        engines_malicious = {}
        malicious_list = []
        blacklist = ['malicious', 'phishing', 'suspicious', 'malware']
        for url in domains:
            # # prepare list of engines that concluded malicious
            # try:
            #     url_results = virus_data[url]['data']['attributes']['last_analysis_results']
            #     for engine in url_results.keys():
            #         if url_results[engine]['result'] in blacklist:
            #             malicious_list.append(url_results[engine]['engine_name'])
            #     engines_malicious[url] = malicious_list

            #     try:
            #         m_score = virus_data[url]['data']['attributes']['last_analysis_stats']['malicious']
            #     except Exception as e:
            #         m_score = 0

            #     try:
            #         s_score = virus_data[url]['data']['attributes']['last_analysis_stats']['suspicious']
            #     except Exception as e:
            #         s_score = 0

            #     v_score = m_score + s_score
            # except Exception as e:
            #     print("No virus total record")
            #     v_score = 0
            #     engines_malicious[url] = "No data"

            # # reset list
            # malicious_list = []

            # save to csv
            #   stopgaps
            if whois_data[url] == {}:
                country = ''
                registrar = ''
            else:
                country = whois_data[url].country
                registrar = whois_data[url].registrar
            if awg_data is None:
                awg_id = '-'
                awg_date = '-'
            else:
                awg_id = awg_data[url]["awg_id"]
                awg_date = awg_data[url]["awg_date_discovered"]

            if ip_data[url].ip is not '-':
                ip_country = ip_data[url].details.get('country', None)
            else:
                ip_country = '-'

            writer.writerow({
                data.FIELD_TITLES[data.DOMAINID]:domain_id,
                data.FIELD_TITLES[data.SOURCE_ID]:awg_id,
                data.FIELD_TITLES[data.DOMAINNAME]:url,
                data.FIELD_TITLES[data.ACTIVITY_IMG]:activity_data[url]["image"],
                data.FIELD_TITLES[data.ACTIVITY_REQ]:activity_data[url]["req"],
                data.FIELD_TITLES[data.IP]:ip_data[url].ip,
                data.FIELD_TITLES[data.IPCOUNTRY]:ip_country,
                data.FIELD_TITLES[data.REGCOUNTRY]:country,
                data.FIELD_TITLES[data.REGISTRAR]:registrar,
                data.FIELD_TITLES[data.TIME]:data.now,
                data.FIELD_TITLES[data.SOURCE_DATE]:awg_date})
            domain_id += 1

            # removed
            # data.FIELD_TITLES[data.PHISHID]:phishtank_data[url]["phish_id"],
            # data.FIELD_TITLES[data.OPENCODE]:'-',
            # data.FIELD_TITLES[data.VSCORE]:v_score,
            # data.FIELD_TITLES[data.VENGINES]:engines_malicious[url],

        # update current domain id
        data.CURRENT_DOMAIN_ID = domain_id - 1


###########################
# OBJECTS GLOBAL VARIABLES#
###########################
class metadata:

    def __init__(self):
        # ACCESS TOKENS
        self.IPINFO_ACCESS_TOKEN = '2487a60e548477'                          
        self.VIRUS_TOTAL_ACCESS_TOKEN = 'd80137e9f5e82896483095b49a7f0e73b5fd0dbc7bd98f1d418ff3ae9c83951e'
        self.twilio_sid = 'AC643cb218d386523498c4e54cab0fdcf4' 
        self.twilio_auth_token = '4794ef24fc522c0f5569afbd672896f0'
        self.phishtank_api_key = '8a2c896086a34c5a7c5a076948679e25af31e93b9b34b6265f1763acb04453aa'
        self.phishtank_db = 'online-valid.csv'

        # FILES PATHS
        self.BASE_PATH = os.path.dirname(os.path.realpath(__file__))
        self.CSV_FILE_CHOICE = ''                       # csv file to write to
        self.URL_FILE_CHOICE = ''                       # url file to read from
        self.SHOT_RELATIVE_PATH = ''                    # relative path to screenshot folder
        self.META_RELATIVE_PATH = ''                    # relative path to metadata dir

        self.CSV_FILE_PATH = ''	                     # absolute path to csv file
        self.URL_FILE_PATH = ''                          # absolute path to urlfile
        self.SHOT_PATH = ''                              # absolute path to screenshot dir
        self.META_PATH = ''                              # absolute path to metadata dir

        # VALUES UPDATED IN init()
        self.HANDLER = 0                                 # ipinfo handler to get ip data
        self.CSV_FILE_EXISTS = True                      # determines if the data is written to old file or new
        self.FIELD_TITLES = []                           # titles of columns in csv file
        self.CURRENT_DOMAIN_ID = -1                      # last domain id used in csv file
        self.EMPTY = 0                                   # used to determine if csv file is empty

        # CONSTS
        self.NUM_OF_ARGS = 2                             # num of command line arguments
        self.DATASOURCE = 1                              # arg position for data source (cert or phish)
        self.write_mode = 'w'                            # csv file write mode upon opening
        self.now = datetime.now().strftime("%m/%d/%Y, %H:%M:%S")

        ###################
        # CSV COL INDECES #
        ###################
        self.DOMAINID = 0
        #self.PHISHID = 1
        self.SOURCE_ID = 1
        self.DOMAINNAME = 2
        self.ACTIVITY_IMG = 3
        self.ACTIVITY_REQ = 4
        #self.VSCORE = 5
        #self.VENGINES = 6
        self.IP = 5
        self.IPCOUNTRY = 6
        self.REGCOUNTRY = 7
        self.REGISTRAR = 8
        self.TIME = 9
        self.SOURCE_DATE = 10

    def print_state(self):
        # File paths
        print("CSV file path:")
        print(self.CSV_FILE_PATH)
        print("\nURL file path:")
        print(self.URL_FILE_PATH)
        print("\nMETADATA file path:")
        print(self.META_PATH)
        print("\nSCREENSHOT file path:")
        print(self.SHOT_PATH)

        # Domain id
        print("\nCurrent domain id: %d" % (self.CURRENT_DOMAIN_ID))

    def init(self, args): 
        """ INIT

        performs validation on CL input and initializes 
        dynamic global data

        Parameters
        ----------
        args: (list)
                list of command line arguments ['<pythonfile>' '<urlfile>']

        Returns
        -------
        ( None )

        """

        # validate CL input length build file paths
        ## two args means a url file was passed, contains relative path
        arg_len = len(args)
        if arg_len == self.NUM_OF_ARGS:
            if args[self.DATASOURCE] == 'cert':
                self.CSV_FILE_CHOICE = 'CSV/cert_data.csv'
                self.URL_FILE_CHOICE = 'URLFILES/cert_urls.csv'
                self.SHOT_RELATIVE_PATH = 'SCREENSHOTS/CERT'
                self.META_RELATIVE_PATH = 'META/CERT'

            elif args[self.DATASOURCE] == 'phish':
                self.CSV_FILE_CHOICE = 'CSV/phish_data.csv'
                self.URL_FILE_CHOICE = 'URLFILES/phish_urls.csv'
                self.SHOT_RELATIVE_PATH = 'SCREENSHOTS/PHISH'
                self.META_RELATIVE_PATH = 'META/PHISH'

            else:
                print("DATA INIT ERROR: invalid data source specified.\
                'cert' or 'phish' is accepted")
                exit(1)

        ## invalid num of args
        elif arg_len != self.NUM_OF_ARGS:
            print("Arg Error. Invalid CL input format: <data source>")
            exit(1)

        ## build file paths
        self.CSV_FILE_PATH = os.path.join(self.BASE_PATH, self.CSV_FILE_CHOICE)
        self.SHOT_PATH = os.path.join(self.BASE_PATH, self.SHOT_RELATIVE_PATH)
        self.META_PATH = os.path.join(self.BASE_PATH, self.META_RELATIVE_PATH)
        self.URL_FILE_PATH = os.path.join(self.BASE_PATH, self.URL_FILE_CHOICE)

        # initialize global variables
        self.HANDLER = ipinfo.getHandler(self.IPINFO_ACCESS_TOKEN)
        self.FIELD_TITLES = getFieldNames()
        
        # establish domain id of next domain to be logged
        if os.path.exists(self.CSV_FILE_PATH):

            # empty files start with domain id 0
            if os.stat(self.CSV_FILE_PATH).st_size == self.EMPTY or os.stat(self.CSV_FILE_PATH).st_size == 1:
                self.CURRENT_DOMAIN_ID = 0

            # existing files start with last domain id stored
            else: 
                df = pd.read_csv(self.CSV_FILE_PATH, na_values=['-', '', 'holder'])

                # determine current largest domain_id in csv record
                csv_record = df.to_numpy()
                num_records = csv_record.shape[0]
                self.CURRENT_DOMAIN_ID = int(df.loc[num_records - 1, self.FIELD_TITLES[0]])

        # csv file has not been created yet
        else:
            self.CSV_FILE_EXISTS = False
