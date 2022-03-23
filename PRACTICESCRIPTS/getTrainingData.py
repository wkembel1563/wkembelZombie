import sys
from selenium import webdriver
from selenium.webdriver.chrome.service import Service

def collectScreenShots(urls):
    """TAKE SCREENSHOTS

    uses selenium to visit and screenshot urls in input list

    two types of screenshots are taken. screenshots of valid urls and
    screenshots of invalid urls. invalid urls are generated by appending 
    a random string onto the end of each valid url

    invalid screenshots are saved to SCREENSHOTS/INACTIVE_DOMAIN
    valid screenshots are saved to SCREENSHOTS/ACTIVE_DOMAIN

    the name of each screenshot is the same as the domain name. invalid domain
    screenshot names have "_inv" appended to the end

    Parameters
    ----------
    urls: (list)
        list of urls to visit

    Returns
    -------
    ( None )
    """
    # set up selenium web driver
    ser = Service('/home/kaifeng/chromedriver')
    op = webdriver.ChromeOptions()
    op.add_argument('--start-maximized')
    # driver = webdriver.Chrome(service=ser, options=op)

    message = "Screenshots will write to dir using domain name as photo name. Continue? (y/n): "
    consent = input(message) 

    # take screenshots and save to SHOT_PATH
    if consent == 'y':
        for url in urls:
            # build valid path
            temp = url
            temp = temp.replace('.', '_')
            valid_pic = '{id}.png'.format(id = temp)
            valid_pic_path = ACTIVE_SHOT_PATH + valid_pic

            # build invalid path
            invalid_pic = '{id}.png'.format(id = temp + "_inv")
            invalid_pic_path = INACTIVE_SHOT_PATH + invalid_pic

            # screenshot valid url
            driver.get('https://' + url)
            driver.save_screenshot(valid_pic_path)

            # screenshot invalid url
            driver.get('https://' + url + "/thisisarandomurlstringthatdoesntexist")
            driver.save_screenshot(invalid_pic_path)
    else:
        print("Exiting...")
        exit(1)


def getURLS(filename):
    """GET URLS

    gets the urls stored in the given file

    assumes the urls have already been cleaned

    Parameters:
    -----------
    filename: (string)
        file contains one url per line

    Returns:
    --------
    urls: (list)
        list of all the url strings in the file
    """
    with open(filename) as f: 
        # get urls
        urls = f.readlines()

        # remove \n char
        for i, line in enumerate(urls):
            urls[i] = line[0:-1]

    return list(urls)


ACTIVE_SHOT_PATH = "SCREENSHOTS/ACTIVE_DOMAIN/"
INACTIVE_SHOT_PATH = "SCREENSHOTS/INACTIVE_DOMAIN/"
URLFILE = 1

# validate input
if len(sys.argv) != 2:
    print("Error. Require two CL args: <.py file> <url file>")
    exit(1)

# retrieve url file
# <python3> <.py file> <url file>
filename = sys.argv[URLFILE]

# extract url data
urls = getURLS(filename)

# get screenshot data and store in directories
collectScreenShots(urls)